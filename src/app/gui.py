import os
import copy
import tkinter as tk
from tkinter import messagebox, ttk
from PIL import Image, ImageTk
import typing
import json
import jsbeautifier
import numpy as np
import secrets
from bidict import bidict

from src.symbols.characters.base import CHARACTER_TYPES, Character
from src.symbols.brushstrokes import CurveProfile, BrushStroke, StrokeCollection

TREEVIEW_ICONS_FP="src/app/icons"
GLOSSARY_JSON_FP="src/dictionary/data/glossary.json"

class CharacterEditorSession:
    GRID_BREAKS = 15
    CELL_SIZE = 36
    CANVAS_SIZE = GRID_BREAKS * CELL_SIZE

    def __init__(self, master: tk.Misc):
        self.master: tk.Misc=master
        self.on_change: typing.Callable[[str], None] | None = None

        # Globally relevant =================
        self.character_glossary_data: dict=self.import_glossary_json()

        self.treeview_icons = {}
        for fp in os.listdir(TREEVIEW_ICONS_FP):
            if fp.endswith(".png"):
                with Image.open(os.path.join(TREEVIEW_ICONS_FP, fp)) as temp_image:
                    self.treeview_icons[fp.removesuffix(".png")] = ImageTk.PhotoImage(temp_image.copy(), master=master)

        # Relevant to current character =====
        self.current_stroke_idx: int=0

        self.character_hash: str=""
        self.character_stroke_control_points: list[list[tuple[int,int]]]=[]
        self.character_stroke_weight_vars: list[tk.IntVar]=[]
        self.character_stroke_profile_control_points: list[list[tuple[float,float]]]=[]
        self.character_stroke_profile_bounds_vars: list[tuple[tk.StringVar,tk.StringVar]]=[]

        self.character_stroke_parentage: dict[int,list[int]]={}

        self.character_type_var=tk.StringVar(master, "")
        self.character_defs_vars: list[tk.StringVar]=[]
        self.character_object_cache: tuple[Character, ImageTk.PhotoImage] | None = None # must cache the photoimage too, as otherwise it gets GC'd

        self.show_stroke_options_var=tk.BooleanVar(master, False)

        if not self.character_glossary_data:
            raise ValueError("The glossary must contain at least one character.")

        first_hash=next(iter(self.character_glossary_data))
        self.character_hash=first_hash
        self.character_definition_to_editor(self.json_to_character(self.character_glossary_data[first_hash]))
        self.rebuild_active_character_image_cache()

    def refresh(self, change: str = "all"):
        if self.on_change is not None:
            #print(f"Refresh @{change}")
            self.on_change(change)

    def import_glossary_json(self):
        def is_valid_character_definition(item: dict) -> bool:
            """
            Safety check to ensure glossary json is not malformed against expected `Character` construction attributes.
            """
            _character_type=item.get("character_type")
            _definitions=item.get("definition")
            _strokes=item.get("stroke_control_points")
            _stroke_weights=item.get("stroke_weights")

            return all([_character_type in list(typing.get_args(CHARACTER_TYPES)),
                        len(_definitions) > 0,
                        len(_strokes) > 0,
                        len(_stroke_weights) > 0,
                        len(_strokes) == len(_stroke_weights)])

        output_dict: dict={}
        with open(GLOSSARY_JSON_FP, "r") as file:
            source_dict: dict[str, dict]=json.load(file)

        for k,v in source_dict.items():
            if is_valid_character_definition(v):
                output_dict[k]=v.copy()

                for idx, coord_list in enumerate(v.get("stroke_control_points")):
                    stroke_coords: list[tuple[float,float]]=[]
                    for coord in coord_list:
                        stroke_coords.append((coord[0], coord[1]))
                    output_dict[k]["stroke_control_points"][idx]=stroke_coords
            else:
                raise ValueError(f"Character {k} is incorrectly defined, check glossary json.")

        return output_dict

    def save_glossary_to_json(self):
        def save_file_beautiful(data: dict):
            with open(GLOSSARY_JSON_FP, "w") as file:
                options = jsbeautifier.default_options()
                options.indent_size = 2

                file.write(jsbeautifier.beautify(json.dumps(data), options))

        self.commit_active_character_to_memory()
        save_file_beautiful(self.character_glossary_data)

    def select_character(self, hash: str, save_current: bool = True):
        """
        Selects a character by its hash (if it exists)
        """
        if hash in self.character_glossary_data:
            if save_current: # persist current changes, then move
                self.commit_active_character_to_memory()
            self.character_hash=hash
            self.character_definition_to_editor(
                self.json_to_character(self.character_glossary_data[hash])
            )
            self.rebuild_active_character_image_cache()
            self.refresh("selection")
        else:
            raise KeyError(f"{hash} is not a valid character hash.")

    def add_new_stroke_items(self):
        self.character_stroke_control_points.append([])
        self.active_stroke_source_control_points.append(None)
        self.character_stroke_weight_vars.append(tk.IntVar(self.master, 1))
        self.character_stroke_profile_control_points.append(CurveProfile.REALISTIC.copy().control_points)
        self.character_stroke_profile_bounds_vars.append((
            tk.StringVar(self.master, CurveProfile.REALISTIC.bounds[0]),
            tk.StringVar(self.master, CurveProfile.REALISTIC.bounds[1]),
        ))

    def stroke_changed(self):
        self.rebuild_active_character_image_cache()
        self.commit_active_character_to_memory()
        self.refresh("stroke")

    def profile_changed(self):
        self.rebuild_active_character_image_cache()
        self.commit_active_character_to_memory()
        self.refresh("preview")

    def update_treeview(self, *_):
        self.commit_active_character_to_memory()
        self.refresh("metadata")

    def rebuild_active_character_image_cache(self):
        """
        Sets `self.character_object_cache` to the `Character` object and `ImageTk.PhotoImage`, built from `self.character_stroke_control_points`.
        """
        def _internal_build_char() -> Character:
            strokes=[]
            for idx, control_points in enumerate(self.character_stroke_control_points):
                if len(control_points) > 1:
                    scaled_control_points=self._get_normalized_stroke_control_points(idx)
                    strokes.append(BrushStroke(control_points=scaled_control_points,
                                                weight=self.character_stroke_weight_vars[idx].get(),
                                                profile=CurveProfile(control_points=self.character_stroke_profile_control_points[idx],
                                                                    bounds=tuple(float(var.get()) for var in self.character_stroke_profile_bounds_vars[idx]))))

            return Character(character_type=self.character_type_var.get(),
                                definition=[x.get() for x in self.character_defs_vars],
                                strokes=strokes)

        if len(self.character_stroke_control_points) > 0:
            sub_lengths_check=[len(el) > 1 for el in self.character_stroke_control_points]
            if any(sub_lengths_check):
                char_tmp=_internal_build_char()
                self.character_object_cache=(char_tmp, ImageTk.PhotoImage(char_tmp.glyph))
            else:
                self.character_object_cache=None
        else:
            self.character_object_cache=None

    def _get_normalized_stroke_control_points(self, idx: int) -> list[tuple[float,float]]:
        grid_path = self.character_stroke_control_points[idx]
        source_path = self.active_stroke_source_control_points[idx]
        grid_max = self.GRID_BREAKS - 1

        if source_path is not None and len(source_path) == len(grid_path):
            if all(
                (int(x * grid_max), int(y * grid_max)) == point
                for point, (x, y) in zip(grid_path, source_path)
            ):
                return source_path

        return [(x / grid_max, y / grid_max) for x, y in grid_path]

    def character_definition_to_editor(self, character: Character) -> None:
        """
        Converts a `Character` into the editor setup so it can be edited.
        """
        decomposed_strokes: list[list[tuple[int,int]]]=[]
        decomposed_source_control_points: list[list[tuple[float,float]]]=[]
        decomposed_stroke_weights: list[int]=[]
        decomposed_curve_profile_control_points: list[list[tuple[float,float]]]=[]
        decomposed_curve_profile_bounds: list[tuple[float,float]]=[]
        for stroke in character.strokes:
            grid_scaled_coord_path=[(int(x * (self.GRID_BREAKS - 1)), int(y * (self.GRID_BREAKS - 1))) for x,y in stroke.control_points]
            decomposed_strokes.append(grid_scaled_coord_path)
            decomposed_source_control_points.append(list(stroke.control_points))
            decomposed_stroke_weights.append(stroke.weight)
            decomposed_curve_profile_control_points.append(stroke.profile.control_points.copy())
            decomposed_curve_profile_bounds.append(stroke.profile.bounds)

        self.current_stroke_idx=0
        self.character_stroke_control_points=decomposed_strokes
        self.active_stroke_source_control_points=decomposed_source_control_points
        self.character_stroke_weight_vars=[tk.IntVar(self.master, value) for value in decomposed_stroke_weights]
        self.character_stroke_profile_control_points=decomposed_curve_profile_control_points
        self.character_stroke_profile_bounds_vars=[
            (tk.StringVar(self.master, l), tk.StringVar(self.master, r))
            for l,r in decomposed_curve_profile_bounds
        ]

        self.character_type_var=tk.StringVar(self.master, character.character_type)
        self.character_type_var.trace_add("write", self.update_treeview)

        self.character_defs_vars: list[tk.StringVar]=[
            tk.StringVar(self.master, value) for value in character.definition
        ]
        for definition_var in self.character_defs_vars:
            definition_var.trace_add("write", self.update_treeview)

    def json_to_character(self, item: dict) -> Character:
        """
        Converts a glossary json item into a `Character`.
        """
        source_strokes: list[list[list]]=item.get("stroke_control_points")
        source_stroke_weights: list[int]=item.get("stroke_weights")
        source_profile_control_points=item.get("stroke_profile_control_points")
        source_profile_bounds=item.get("stroke_profile_bounds")
        if (source_profile_control_points is None) != (source_profile_bounds is None):
            raise ValueError("Stroke profile control points and bounds must be provided together.")
        if source_profile_control_points is not None and (
            len(source_profile_control_points) != len(source_strokes)
            or len(source_profile_bounds) != len(source_strokes)
        ):
            raise ValueError("Stroke profile data must match the number of strokes.")

        strokes: StrokeCollection=[]
        for idx, stroke_coords in enumerate(source_strokes):
            profile = None
            if source_profile_control_points is not None:
                profile = CurveProfile(
                    control_points=[tuple(point) for point in source_profile_control_points[idx]],
                    bounds=tuple(source_profile_bounds[idx]),
                )
            strokes.append(BrushStroke(stroke_coords, source_stroke_weights[idx], profile))

        return Character(item.get("character_type"),
                            item.get("definition"),
                            strokes)

    def commit_active_character_to_memory(self):
        """
        Copies editor state to the active character's entry in `self.character_glossary_data`.
        """
        if not self.character_hash:
            return

        if self.character_hash not in self.character_glossary_data:
            return

        # get active entry in glossary
        item = self.character_glossary_data[self.character_hash]

        # for each locally tracked variable, assign to the working glossary
        item["character_type"] = self.character_type_var.get()
        item["definition"] = [var.get() for var in self.character_defs_vars]

        active_strokes = []
        active_stroke_weights = []
        character_stroke_profile_control_points = []
        active_stroke_profile_bounds = []
        for idx, path in enumerate(self.character_stroke_control_points):
            if not path:
                continue

            active_strokes.append(self._get_normalized_stroke_control_points(idx))
            active_stroke_weights.append(self.character_stroke_weight_vars[idx].get())
            character_stroke_profile_control_points.append(
                self.character_stroke_profile_control_points[idx]
            )
            active_stroke_profile_bounds.append(
                (float(self.character_stroke_profile_bounds_vars[idx][0].get()),
                    float(self.character_stroke_profile_bounds_vars[idx][1].get()))
            )

        item["stroke_control_points"] = active_strokes
        item["stroke_weights"] = active_stroke_weights
        item["stroke_profile_control_points"] = character_stroke_profile_control_points
        item["stroke_profile_bounds"] = active_stroke_profile_bounds

class StrokeHierarchy(tk.Frame):
    def __init__(self, parent, session: CharacterEditorSession):
        self.session: CharacterEditorSession=session

        self.stroke_tree_ids: bidict[int, str]=bidict({}) # bidict so we can lookup {hash <-> tree_id}

        super().__init__(parent)
        self.columnconfigure(0, weight=1)

        self.dictionary_treeview=ttk.Treeview(self)
        self.dictionary_treeview.grid(column=0, row=1, sticky="NSEW")
        self.dictionary_treeview.bind("<ButtonPress-1>", self.drag_control_point_start)
        self.dictionary_treeview.bind("<ButtonRelease-1>", self.drag_control_point_end)

        self.refresh()

    def refresh(self):
        """
        Constructs hierarchy of strokes in accordance with `self.session.character_stroke_parentage`.
        """
        # 1. Clear the treeview --------------------------------
        tv: ttk.Treeview=self.dictionary_treeview
        tv.delete(*tv.get_children())
        self.stroke_tree_ids=bidict({})

        tv.heading("#0", text="Character")
        tv.heading("defs", text="Definition(s)")

        tv.tag_configure('headings', image=self.session.treeview_icons["numpage"])
        tv.tag_configure('selected', background="#b2cdec", image=self.session.treeview_icons["paint"])

        root_id=tv.insert("",
                          tk.END,
                          text=f"root",
                          open=True,
                          tags=('headings',)
                          )

        # 3. add the character items
        for idx, item in enumerate(self.session.character_stroke_control_points):
            row_tags = ('selected',) if idx == self.session.current_stroke_idx else ('unselected',)

            tree_id=tv.insert(root_id,
                              tk.END,
                              text=f"{idx}",
                              tags=row_tags
                              )
            self.stroke_tree_ids[idx]=tree_id

        if self.session.current_stroke_idx in self.stroke_tree_ids:
            tv.see(item=self.stroke_tree_ids[self.session.current_stroke_idx])

class CharacterHierarchy(tk.Frame):
    def __init__(self, parent, session: CharacterEditorSession):
        self.session: CharacterEditorSession=session
        
        self.character_tree_ids: bidict[str, str]=bidict({}) # bidict so we can lookup {hash <-> tree_id}
        self.character_type_tree_ids: bidict[str, str]=bidict({}) # bidict so we can lookup {character_type <-> tree_id}

        super().__init__(parent)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        self.rowconfigure(1, weight=8)

        tk.Button(self, text="+ Add new entry", command=self.add_entry).grid(column=0, row=0, sticky="EW")

        self.dictionary_treeview=ttk.Treeview(self, columns=("defs"))
        self.dictionary_treeview.grid(column=0, row=1, sticky="NSEW")
        self.dictionary_treeview.bind("<ButtonPress-1>", self.leftclick_entry)
        self.dictionary_treeview.bind("<ButtonPress-2>", self.middleclick_entry)
        self.dictionary_treeview.bind("<ButtonPress-3>", self.rightclick_entry)

        self.refresh()

    def refresh(self):
        """
        Constructs `Character.character_type` headers and places all glossary json items under respectively against hash.
        """
        # 1. Clear the treeview --------------------------------
        tv: ttk.Treeview=self.dictionary_treeview
        tv.delete(*tv.get_children())
        self.character_type_tree_ids=bidict({})
        self.character_tree_ids=bidict({})

        tv.heading("#0", text="Character")
        tv.heading("defs", text="Definition(s)")

        tv.tag_configure('headings', image=self.session.treeview_icons["folder"])
        tv.tag_configure('selected', background="#b2cdec", image=self.session.treeview_icons["editing"])

        # 2. build the character_type groups first
        for heading in list(typing.get_args(CHARACTER_TYPES)):
            tree_id=tv.insert("",
                                tk.END,
                                text=f"{heading.title()}",
                                open=True,
                                tags=('headings',)
                                )
            self.character_type_tree_ids[heading]=tree_id

        # 3. add the character items
        for hash, item in self.session.character_glossary_data.items():
            char=self.session.json_to_character(item)

            row_tags = ('selected',) if hash == self.session.character_hash else ('unselected',)
            extra_defs_text = ""
            if len(char.definition) > 1:
                extra_defs_text = f" (+{len(char.definition)-1} more...)"

            tree_id=tv.insert(self.character_type_tree_ids[char.character_type],
                                tk.END,
                                text=f"{hash}",
                                values=(f"{char.definition[0]}{extra_defs_text}",),
                                tags=row_tags
                                )
            self.character_tree_ids[hash]=tree_id

        if self.session.character_hash in self.character_tree_ids:
            tv.see(item=self.character_tree_ids[self.session.character_hash])

    def update_active_entry(self):
        self.session.commit_active_character_to_memory()
        active_hash = self.session.character_hash
        tree_id = self.character_tree_ids.get(active_hash)
        if tree_id is None:
            return

        item = self.session.character_glossary_data[active_hash]
        group_id = self.character_type_tree_ids.get(item["character_type"])
        if group_id is not None and self.dictionary_treeview.parent(tree_id) != group_id:
            self.dictionary_treeview.move(tree_id, group_id, tk.END)

        definitions = item["definition"]
        extra_defs_text = f" (+{len(definitions) - 1} more...)" if len(definitions) > 1 else ""
        self.dictionary_treeview.item(
            tree_id,
            values=(f"{definitions[0]}{extra_defs_text}",),
        )

    def leftclick_entry(self, event: tk.Event):
        """
        Operation to perform on `self.dictionary_treeview` item doubleclick - assign to current view.
        """
        tv: ttk.Treeview=self.dictionary_treeview
        item=tv.identify("item", event.x, event.y)
        hash=self.character_tree_ids.inverse.get(item)
        if hash is not None:
            self.session.select_character(hash)

    def middleclick_entry(self, event: tk.Event):
        tv: ttk.Treeview=self.dictionary_treeview
        item=tv.identify("item", event.x, event.y)
        hash=self.character_tree_ids.inverse.get(item, None)

        if hash:
            character_to_clone = copy.deepcopy(self.session.character_glossary_data[hash])
            self.add_entry(character_to_clone)


    def rightclick_entry(self, event: tk.Event):
        tv: ttk.Treeview=self.dictionary_treeview
        item=tv.identify("item", event.x, event.y)
        hash=self.character_tree_ids.inverse.get(item, None)

        if hash:
            answer = messagebox.askyesno("Remove entry",
                                            f"Remove the glossary entry for {hash}?",
                                            icon="question",
                                            parent=self.winfo_toplevel()
                                            )
            if answer:
                self.remove_entry(hash)

    def add_entry(self, character_template: dict | None = None):
        tv: ttk.Treeview=self.dictionary_treeview
        hash: str=secrets.token_hex(4)

        if character_template is None:
            # if the user has a type selected, new entry should be placed here
            # otherwise, go with the active-character's type
            focus_character_type = self.character_type_tree_ids.inverse.get(tv.focus(), None)
            if focus_character_type is None:
                    focus_character_type = self.session.character_type_var.get()

            character_template: dict={
                "character_type": focus_character_type,
                "definition": ["example definition"],
                "stroke_control_points": [[[0.5, 0.0], [0.5, 1.0]]],
                "stroke_weights": [1],
                "stroke_profile_control_points":[CurveProfile.REALISTIC.copy().control_points],
                "stroke_profile_bounds": [CurveProfile.REALISTIC.copy().bounds]
                }

        self.session.character_glossary_data[hash]=copy.deepcopy(character_template)
        self.session.select_character(hash, save_current=True)
        self.session.save_glossary_to_json()

    def remove_entry(self, hash: str):
        self.session.commit_active_character_to_memory()

        hashes=list(self.session.character_glossary_data)
        if len(hashes) <= 1:
            messagebox.showwarning(
                "Cannot remove character",
                "At least one character must remain in the glossary.",
                parent=self.winfo_toplevel(),
            )
            return

        next_active_hash=self.session.character_hash
        removing_active = hash == self.session.character_hash
        if removing_active:
            removed_idx=hashes.index(hash)
            next_active_hash=hashes[removed_idx - 1] if removed_idx > 0 else hashes[1]

        del self.session.character_glossary_data[hash]
        if removing_active:
            self.session.select_character(next_active_hash, save_current=False)
        else:
            self.session.refresh("list")
        self.session.save_glossary_to_json()

class CharacterType(tk.Frame):
    def __init__(self, parent, session: CharacterEditorSession):
        super().__init__(parent)
        self.session: CharacterEditorSession=session

        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=3)

        tk.Label(self, text="Type:").grid(column=0, row=0, sticky="NSEW")

        character_type_input=tk.OptionMenu(
            self,
            self.session.character_type_var,
            *typing.get_args(CHARACTER_TYPES),
        )
        character_type_input.grid(column=1, row=0, sticky="NSEW")

class CharacterDefinitions(tk.Frame):
    def __init__(self, parent, session: CharacterEditorSession):
        super().__init__(parent)
        self.session: CharacterEditorSession=session
        self.columnconfigure(0, weight=1)

        inc_dec_button_row=tk.Frame(self)
        inc_dec_button_row.columnconfigure(0, weight=1)
        inc_dec_button_row.columnconfigure(1, weight=1)
        inc_dec_button_row.grid(column=0, row=0, sticky="NEW")

        character_defs_decrease=tk.Button(inc_dec_button_row, command=lambda: self.add_or_remove_character_defs(-1), text="-")
        character_defs_increase=tk.Button(inc_dec_button_row, command=lambda: self.add_or_remove_character_defs(1), text="+")
        character_defs_decrease.grid(column=0, row=0, sticky="NSEW")
        character_defs_increase.grid(column=1, row=0, sticky="NSEW")

        self.entries_frame = tk.Frame(self)
        self.entries_frame.columnconfigure(0, weight=1)
        self.entries_frame.columnconfigure(1, weight=3)
        self.entries_frame.grid(column=0, row=1, sticky="NSEW")
        self.refresh()

    def refresh(self):
        for child in self.entries_frame.winfo_children():
            child.destroy()

        for idx in range(len(self.session.character_defs_vars)):
            tk.Label(self.entries_frame, text=f"Def {idx}:").grid(column=0, row=idx)
            entry_field=ttk.Entry(self.entries_frame, textvariable=self.session.character_defs_vars[idx])
            entry_field.grid(column=1, row=idx, sticky="EW")

    def add_or_remove_character_defs(self, value: int):
        if value > 0:
            definition_var=tk.StringVar(self.session.master, value="")
            definition_var.trace_add("write", self.session.update_treeview)
            self.session.character_defs_vars.append(definition_var)
        elif len(self.session.character_defs_vars) > 1:
            _ = self.session.character_defs_vars.pop()
        else:
            print(f"Character must have at least 1 definition")
            return
        self.session.commit_active_character_to_memory()
        self.session.refresh("metadata")
        self.refresh()

class CurveProfileWidget(tk.Frame):
    PADDING_PX = 16
    def __init__(
        self,
        parent,
        size: tuple[int,int],
        curve_profile: CurveProfile,
        on_refresh: typing.Callable[[], None] | None = None,
    ):
        super().__init__(parent)
        self.rowconfigure(0, weight=1)

        self.canvas_size=size
        self.curve_profile: CurveProfile=curve_profile

        self.on_refresh = on_refresh

        self.selected_curve_control_point_idx: int=None

        self.canvas=tk.Canvas(self,
                              width=size[0],
                              height=size[1],
                              highlightthickness=1, highlightbackground="black")
        self.canvas.grid(column=0, row=0)
        self.canvas.bind("<ButtonPress-1>", self.drag_control_point_start)
        self.canvas.bind("<ButtonRelease-1>", self.drag_control_point_end)
        self.canvas.bind("<Double-1>", self.add_control_point)
        self.canvas.bind("<ButtonPress-3>", self.remove_control_point)

        self.refresh()

    def refresh(self):
        self.draw_canvas()

    def scale_to_padded_canvas(self, coord: tuple[float,float]) -> tuple[int,int]:
        rawx, rawy = coord
        padded_canvas_size = (self.canvas_size[0] - 2 * self.PADDING_PX,
                                self.canvas_size[1] - 2 * self.PADDING_PX)
        scaled_coord = ((rawx * padded_canvas_size[0]) + self.PADDING_PX,
                        - 1.0 * (rawy * padded_canvas_size[1]) + self.PADDING_PX + padded_canvas_size[1])

        return scaled_coord

    def scale_from_padded_canvas(self, coord: tuple[int,int]) -> tuple[float,float]:
            rawx, rawy = (min(max(i, 0), self.canvas_size[idx]) for idx, i in enumerate(coord))
            padded_canvas_size = (self.canvas_size[0] - 2 * self.PADDING_PX,
                                    self.canvas_size[1] - 2 * self.PADDING_PX)
            scaled_coord = ((rawx - self.PADDING_PX) / padded_canvas_size[0],
                            (rawy - self.PADDING_PX) / padded_canvas_size[1])

            return scaled_coord

    def draw_canvas(self):
        """
        Draw to `self.canvas` - add the curve and points
        """
        self.canvas.delete('all')

        # draw curve control points
        for coord_idx, (x,y) in enumerate(self.curve_profile.control_points):
            x1, y1 = self.scale_to_padded_canvas((x,y))
            if coord_idx > 0:
                px, py=self.curve_profile.control_points[coord_idx - 1]
                x0, y0 = self.scale_to_padded_canvas((px,py))
                self.canvas.create_line(x0, y0, x1, y1,
                                        width=1, fill="#bbb")

            ex0,ey0,ex1,ey1 = (x1-2.0,y1-2.0,x1+2.0,y1+2.0)
            self.canvas.create_oval(ex0, ey0, ex1, ey1,
                                    fill="#000")

        # draw curve line
        for coord_idx, (x, y) in enumerate(self.curve_profile.profile):
            if coord_idx > 0:
                px, py=self.curve_profile.profile[coord_idx - 1]
                x0, y0, x1, y1 = (*self.scale_to_padded_canvas((px,py)), *self.scale_to_padded_canvas((x,y)))
                self.canvas.create_line(x0, y0, x1, y1,
                                        width=1, fill="#444")

    def select_curve_control_point(self, coord: tuple[float,float]):
        min_selection_distance_halo = 0.1

        x, y = coord
        distances=[max(0, float(np.sqrt((cx - x) ** 2 + (cy - y) ** 2)) - min_selection_distance_halo) for cx,cy in self.curve_profile.control_points]
        if 0 in distances:
            self.selected_curve_control_point_idx = distances.index(0)
        else:
            self.selected_curve_control_point_idx = None

    def drag_control_point_start(self, event: tk.Event):
        """
        Action to perform on `self.canvas` left-click: add or drag existing Bezier coord
        """
        raw_loc=(event.x, self.canvas_size[1] - event.y)
        x, y=self.scale_from_padded_canvas(raw_loc)
        self.select_curve_control_point((x,y))

    def drag_control_point_end(self, event: tk.Event):
        if self.selected_curve_control_point_idx is not None:
            raw_loc=(event.x, self.canvas_size[1] - event.y)
            x, y=(min(max(i, 0.0),1.0) for i in self.scale_from_padded_canvas(raw_loc))

            if self.selected_curve_control_point_idx == 0:
                self.curve_profile.control_points[self.selected_curve_control_point_idx] = (0.0,y)
            elif self.selected_curve_control_point_idx == len(self.curve_profile.control_points) - 1:
                self.curve_profile.control_points[self.selected_curve_control_point_idx] = (1.0,y)
            else:
                self.curve_profile.control_points[self.selected_curve_control_point_idx] = (x,y)

            self.curve_profile.profile=self.curve_profile.get_profile()
            self.refresh()
            if self.on_refresh is not None:
                self.on_refresh()

    def add_control_point(self, event: tk.Event):
        """
        Action to perform on `self.canvas` right-click: remove Bezier coord
        """
        raw_loc=(event.x, self.canvas_size[1] - event.y)
        x, y=self.scale_from_padded_canvas(raw_loc)

        self.curve_profile.control_points.insert(-1, (x,y))
        self.selected_curve_control_point_idx = None

        self.curve_profile.profile=self.curve_profile.get_profile()
        self.refresh()
        if self.on_refresh is not None:
            self.on_refresh()

    def remove_control_point(self, event: tk.Event):
        """
        Action to perform on `self.canvas` right-click: remove Bezier coord
        """
        raw_loc=(event.x, self.canvas_size[1] - event.y)
        x, y=self.scale_from_padded_canvas(raw_loc)
        self.select_curve_control_point((x,y))

        if self.selected_curve_control_point_idx is not None:
            if self.selected_curve_control_point_idx not in (0, len(self.curve_profile.control_points) - 1):
                _ = self.curve_profile.control_points.pop(self.selected_curve_control_point_idx)
                self.selected_curve_control_point_idx = None

                self.curve_profile.profile=self.curve_profile.get_profile()
                self.refresh()
                if self.on_refresh is not None:
                    self.on_refresh()

class StrokeEditor(tk.Frame):
    def __init__(self, parent, session: CharacterEditorSession):
        self.session = session

        self.CANVAS_SIZE = session.CANVAS_SIZE
        self.CELL_SIZE = session.CELL_SIZE

        super().__init__(parent, padx=4, pady=4, highlightthickness=1, highlightbackground="black")

        self.refresh()

    def refresh(self):
        for child in self.winfo_children():
            child.destroy()

        self.columnconfigure(0, weight=1)
        self.canvas=tk.Canvas(
            self,
            width=self.CANVAS_SIZE,
            height=self.CANVAS_SIZE,
            highlightthickness=1,
            highlightbackground="black",
        )
        self.canvas.grid(column=0, row=0, sticky="NS")
        self.canvas.bind("<ButtonPress-1>", self.leftclick_x_y)
        self.canvas.bind("<ButtonPress-3>", self.rightclick_x_y)
        self.draw_canvas()

        active_idx = self.session.current_stroke_idx
        has_active_stroke = active_idx < len(self.session.character_stroke_control_points)
        active_weight = (
            self.session.character_stroke_weight_vars[active_idx].get()
            if has_active_stroke else 1
        )
        options = tk.Frame(self, pady=4)
        options.columnconfigure(0, weight=1)
        options.columnconfigure(1, weight=3)
        options.columnconfigure(2, weight=3)
        options.columnconfigure(3, weight=1)
        options.grid(column=0, row=1, sticky="EW")

        tk.Button(options, command=lambda: self.change_stroke_idx(-1), text="\u2b9c").grid(
            column=0, row=0, sticky="EW"
        )
        tk.Button(options, command=lambda: self.change_stroke_idx(1), text="\u2b9e").grid(
            column=3, row=0, sticky="EW"
        )
        tk.Label(
            options,
            text=f"Character {self.session.character_hash} | "
                 f"Brushstroke {active_idx} | Weight={active_weight}",
        ).grid(column=1, row=0, columnspan=2)

        if self.session.show_stroke_options_var.get() and has_active_stroke:
            weight_slider=ttk.Scale(
                options,
                variable=self.session.character_stroke_weight_vars[active_idx],
                from_=1,
                to=16,
            )
            weight_slider.bind("<ButtonRelease-1>", lambda *_: self.session.stroke_changed())
            weight_slider.grid(column=1, row=1, columnspan=2)

            curve_profile=CurveProfile(
                control_points=self.session.character_stroke_profile_control_points[active_idx],
                bounds=tuple(
                    float(var.get())
                    for var in self.session.character_stroke_profile_bounds_vars[active_idx]
                ),
            )
            curve_profile_widget=CurveProfileWidget(
                options,
                size=(128, 128),
                curve_profile=curve_profile,
                on_refresh=self.session.profile_changed,
            )
            curve_profile_widget.grid(column=1, row=2, columnspan=2)

            left_bound, right_bound = self.session.character_stroke_profile_bounds_vars[active_idx]
            ttk.Spinbox(
                options,
                textvariable=left_bound,
                command=self.session.profile_changed,
                to=16.0,
                increment=0.1,
            ).grid(column=1, row=3, sticky="E")
            ttk.Spinbox(
                options,
                textvariable=right_bound,
                command=self.session.profile_changed,
                to=16.0,
                increment=0.1,
            ).grid(column=2, row=3, sticky="W")

        tk.Checkbutton(
            self,
            variable=self.session.show_stroke_options_var,
            text="Show stroke options",
            command=lambda: self.session.refresh("stroke"),
        ).grid(column=0, row=2, sticky="SW")

    def remove_empty_strokes(self):
        removed_idxs = []
        for idx in reversed(range(0, len(self.session.character_stroke_control_points))):
            if len(self.session.character_stroke_control_points[idx]) <= 1:
                if idx == self.session.current_stroke_idx:
                    continue
                # Remove the empty/invalid stroke data across all parallel lists
                self.session.character_stroke_control_points.pop(idx)
                self.session.active_stroke_source_control_points.pop(idx)
                self.session.character_stroke_weight_vars.pop(idx)
                self.session.character_stroke_profile_control_points.pop(idx)
                self.session.character_stroke_profile_bounds_vars.pop(idx)

                removed_idxs.append(idx)
                
                # Shift the active index left if a preceding stroke was removed
                if idx < self.session.current_stroke_idx:
                    self.session.current_stroke_idx -= 1

        if len(removed_idxs) > 0:
            print(f"Found empty strokes, removed {removed_idxs}")

    def change_stroke_idx(self, value: int):
        self.session.current_stroke_idx = max(0, self.session.current_stroke_idx)
        new_idx = self.session.current_stroke_idx + value
        if new_idx < 0:
            return
        if new_idx >= len(self.session.character_stroke_control_points):
            if len(self.session.character_stroke_control_points[-1]) > 1:    
                self.session.add_new_stroke_items()
            else:
                print(f"Current stroke is incomplete, staying put")
                new_idx = self.session.current_stroke_idx
        self.session.current_stroke_idx = new_idx
        self.session.stroke_changed()
        self.remove_empty_strokes()

    def leftclick_x_y(self, event: tk.Event):
        """
        Action to perform on `self.canvas` left-click: add integer coordinates to `self.character_stroke_control_points[self.current_stroke_idx].`
        """
        if self.session.current_stroke_idx >= len(self.session.character_stroke_control_points):
            self.session.add_new_stroke_items()

        grid_max = self.session.GRID_BREAKS - 1
        x, y = (
            min(grid_max, max(0, event.x // self.CELL_SIZE)),
            min(grid_max, max(0, event.y // self.CELL_SIZE)),
        )
        self.session.character_stroke_control_points[self.session.current_stroke_idx].append((x, y))
        self.session.stroke_changed()

    def rightclick_x_y(self, event: tk.Event):
        """
        Action to perform on `self.canvas` right-click: remove most recent matching integer coordinates from `self.character_stroke_control_points[self.current_stroke_idx].`
        """
        active_idx = self.session.current_stroke_idx
        if active_idx >= len(self.session.character_stroke_control_points):
            return

        x, y = (
            min(self.session.GRID_BREAKS - 1, max(0, event.x // self.CELL_SIZE)),
            min(self.session.GRID_BREAKS - 1, max(0, event.y // self.CELL_SIZE)),
        )
        stroke = self.session.character_stroke_control_points[active_idx]
        matching_idx = next(
            (idx for idx in range(len(stroke) - 1, -1, -1) if stroke[idx] == (x, y)),
            None,
        )
        if matching_idx is not None:
            stroke.pop(matching_idx)
            self.session.stroke_changed()

    def draw_canvas(self):
        """
        Draw to `self.canvas` - add gridlines, red indicators and thick lines for current stroke, faded indicators and thin lines for others.
        """
        def draw_gridlines():
            for pos in range(0, self.CANVAS_SIZE, self.CELL_SIZE):
                self.canvas.create_line(pos, 0, pos, self.CANVAS_SIZE)
                self.canvas.create_line(0, pos, self.CANVAS_SIZE, pos)
        
        self.canvas.delete('all')
        draw_gridlines()

        if self.session.current_stroke_idx < len(self.session.character_stroke_control_points):
            for s_idx, stroke in enumerate(self.session.character_stroke_control_points):
                for coord_idx, (x, y) in enumerate(stroke):
                    # the active stroke
                    if self.session.current_stroke_idx == s_idx:
                        self.canvas.create_rectangle(x * self.CELL_SIZE, y * self.CELL_SIZE, (x + 1) * self.CELL_SIZE, (y + 1) * self.CELL_SIZE, fill="#f00", stipple="gray50")
                        self.canvas.create_text(x * self.CELL_SIZE + self.CELL_SIZE // 5, y * self.CELL_SIZE + self.CELL_SIZE // 5, text=f"{coord_idx}")

                        # draw lines between current and previous point
                        if coord_idx > 0:
                            px, py=stroke[coord_idx - 1]
                            self.canvas.create_line(px * self.CELL_SIZE + self.CELL_SIZE/2,
                                                    py * self.CELL_SIZE + self.CELL_SIZE/2,
                                                    x * self.CELL_SIZE + self.CELL_SIZE/2,
                                                    y * self.CELL_SIZE + self.CELL_SIZE/2,
                                                    width=3, fill="#444")
                    # the inactive stroke(s)
                    else:
                        self.canvas.create_rectangle(x * self.CELL_SIZE, y * self.CELL_SIZE, (x + 1) * self.CELL_SIZE, (y + 1) * self.CELL_SIZE, fill="#888", stipple="gray25")

                        # draw lines between current and previous point
                        if coord_idx > 0:
                            px, py=stroke[coord_idx - 1]
                            self.canvas.create_line(px * self.CELL_SIZE + self.CELL_SIZE/2,
                                                    py * self.CELL_SIZE + self.CELL_SIZE/2,
                                                    x * self.CELL_SIZE + self.CELL_SIZE/2,
                                                    y * self.CELL_SIZE + self.CELL_SIZE/2,
                                                    width=1, fill="#666")

class CharacterPreview(tk.Frame):
    def __init__(self, parent, session: CharacterEditorSession):
        self.session = session

        super().__init__(parent)
        self.columnconfigure(0, weight=1)

        self.refresh()

    def refresh(self):
        for child in self.winfo_children():
            child.destroy()

        if self.session.character_object_cache is None:
            return

        tk.Label(self, text="Rendered Glyph").grid(column=0, row=0, sticky="NEW")
        image_label=tk.Label(
            self,
            image=self.session.character_object_cache[1],
            highlightthickness=1,
            highlightbackground="black",
        )
        image_label.grid(column=0, row=1)

class DrawingTool(tk.Frame):
    GRID_BREAKS = CharacterEditorSession.GRID_BREAKS
    CELL_SIZE = CharacterEditorSession.CELL_SIZE
    canvas_size = CharacterEditorSession.CANVAS_SIZE

    def __init__(self, parent):
        self.session = CharacterEditorSession(parent)

        super().__init__(parent, padx=24, pady=24)
        self._build_layout()
        self.session.on_change = self.refresh

        self.refresh("all")

    def _build_layout(self):
        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=3)
        self.rowconfigure(0, weight=1)

        self.left_pane=tk.Frame(
            self,
            padx=4,
            pady=4,
            highlightthickness=1,
            highlightbackground="black",
        )
        self.left_pane.columnconfigure(0, weight=1)
        self.left_pane.rowconfigure(0, weight=4)
        self.left_pane.rowconfigure(1, weight=1)
        self.left_pane.rowconfigure(2, weight=4)
        self.left_pane.rowconfigure(3, weight=3)
        self.left_pane.rowconfigure(4, weight=1)
        self.left_pane.grid(column=0, row=0, sticky="NSEW", padx=12)

        self.character_hierarchy = CharacterHierarchy(self.left_pane, self.session)
        self.character_hierarchy.grid(column=0, row=0, sticky="NSEW")
        self.character_type = CharacterType(self.left_pane, self.session)
        self.character_type.grid(column=0, row=1, sticky="EW")
        self.character_definitions = CharacterDefinitions(self.left_pane, self.session)
        self.character_definitions.grid(column=0, row=2, sticky="NEW")
        self.character_preview = CharacterPreview(self.left_pane, self.session)
        self.character_preview.grid(column=0, row=3, sticky="NEW")
        tk.Button(
            self.left_pane,
            text="Save",
            command=self.session.save_glossary_to_json,
        ).grid(column=0, row=4, sticky="EW")

        self.stroke_editor = StrokeEditor(self, self.session)
        self.stroke_editor.grid(column=1, row=0, sticky="NSEW", padx=12)

    def _rebuild_character_fields(self):
        self.character_type.destroy()
        self.character_definitions.destroy()
        self.character_type = CharacterType(self.left_pane, self.session)
        self.character_type.grid(column=0, row=1, sticky="EW")
        self.character_definitions = CharacterDefinitions(self.left_pane, self.session)
        self.character_definitions.grid(column=0, row=2, sticky="EW")

    def refresh(self, change: str = "all"):
        if change == "list":
            self.character_hierarchy.refresh()
        elif change == "metadata":
            self.character_hierarchy.update_active_entry()
        elif change == "preview":
            self.character_preview.refresh()
        elif change in ("selection", "stroke", "all"):
            if change in ("selection", "all"):
                self._rebuild_character_fields()
                self.character_hierarchy.refresh()
            self.stroke_editor.refresh()
            self.character_preview.refresh()

    def on_app_close(self):
        answer=messagebox.askyesno(
            "Exit",
            "Are you sure you want to exit?",
            parent=self.winfo_toplevel(),
        )
        if answer:
            self.session.save_glossary_to_json()
            self.winfo_toplevel().destroy()