import os
import tkinter as tk
from tkinter import messagebox, ttk
from PIL import Image, ImageTk
import typing
import json
import jsbeautifier
import numpy as np
import secrets
from bidict import bidict

from src.symbols.utils import bezier
from src.symbols.characters.base import CHARACTER_TYPES, Character
from src.symbols.brushstrokes import CurveProfile, BrushStroke, BrushStrokeGroup, StrokeCollection

TREEVIEW_ICONS_FP="src/gui/icons"
GLOSSARY_JSON_FP="src/dictionary/data/glossary.json"

class OptionDialog(tk.Toplevel):
    """
        This dialog accepts a list of options.
        If an option is selected, the results property is to that option value
        If the box is closed, the results property is set to zero
    """
    def __init__(self,parent,title,question,options):
        super().__init__(self,parent)
        self.title(title)
        self.question = question
        self.transient(parent)
        self.protocol("WM_DELETE_WINDOW",self.cancel)
        self.options = options
        self.createWidgets()
        self.grab_set()

        # await user response
        self.wait_window()
    def createWidgets(self):
        frmQuestion = tk.Frame(self)
        tk.Label(frmQuestion,text=self.question).grid()
        frmQuestion.grid(row=1)
        frmButtons = tk.Frame(self)
        frmButtons.grid(row=2)
        column = 0
        for option in self.options:
            btn = tk.Button(frmButtons,text=option,command=lambda x=option:self.setOption(x))
            btn.grid(column=column,row=0)
            column += 1 
    def setOption(self,optionSelected):
        self.destroy()
        return optionSelected
    def cancel(self):
        self.destroy()
        return None

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
        if self.on_refresh is not None:
            self.on_refresh()
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

class DrawingTool(tk.Frame):
    GRID_BREAKS=15
    CELL_SIZE=36
    canvas_size=GRID_BREAKS * CELL_SIZE
    def __init__(self, parent):
        super().__init__(parent, padx=24, pady=24)

        self.parent = parent

        self.columnconfigure(0, weight=2, uniform="panes")
        self.columnconfigure(1, weight=3, uniform="panes")
        self.rowconfigure(0, weight=1)

        # Globally relevant =====
        self.character_treeview_icons: dict[str, ImageTk.PhotoImage] = {}
        self.show_stroke_options: tk.BooleanVar = tk.BooleanVar(self, False)

        self.character_glossary_data: dict=self.clean_definition_json_import()
        self.character_tree_ids: bidict[str, str]=bidict({}) # bidict so we can lookup {hash <-> tree_id}
        self.character_type_tree_ids: bidict[str, str]=bidict({}) # bidict so we can lookup {character_type <-> tree_id}

        # Relevant to current character =====
        # GUI-only -----
        self.active_stroke_idx: int=0

        # Glossary-definition items -----
        self.active_character_hash: str=""
        self.active_stroke_control_points: list[list[tuple[int,int]]]=[]
        self.active_stroke_weight_vars: list[tk.IntVar]=[tk.IntVar(self, 4)]
        self.active_stroke_profile_control_points: list[list[tuple[float,float]]]=[]
        self.active_stroke_profile_bounds_vars: list[tuple[tk.StringVar,tk.StringVar]]=[]
        self.active_character_type_var=tk.StringVar(self, "")
        self.active_character_defs_vars: list[tk.StringVar]=[]
        self.active_character_cache: tuple[Character, ImageTk.PhotoImage]=None # must cache the photoimage too, as otherwise it gets GC'd
        self.rendered_glyph_label: tk.Label | None = None

        # End of init, run app build tools =====
        # add icons to icon dict
        for fp in os.listdir(TREEVIEW_ICONS_FP):
            if fp.endswith(".png"):
                temp_image = Image.open(TREEVIEW_ICONS_FP + "/" + fp)
                self.character_treeview_icons[fp.removesuffix(".png")] = ImageTk.PhotoImage(temp_image)

        self.build_left_pane()
        self.build_canvas_pane()
        # Set starting position as first character in definitions -----
        first_hash=list(self.character_glossary_data.keys())[0]
        self.active_character_hash=first_hash
        self.character_definition_to_editor(
            self.json_to_character(self.character_glossary_data[first_hash])
        )

    def on_app_close(self):
        answer=messagebox.askyesno("Exit",
                                   "Are you sure you want to exit?")
        if answer:
            self.save_glossary_to_json()
            self.parent.destroy()
            
    def refresh(self, *_):
        """
        Rebuild all subcomponents and perform any top-level calcs.
        """
        self.rebuild_active_character_image_cache()
        self.build_left_pane()
        self.build_canvas_pane()

    def rebuild_active_character_image_cache(self):
        """
        Sets `self.active_character_cache` to the `Character` object and `ImageTk.PhotoImage`, built from `self.active_stroke_control_points`.
        """
        def _internal_build_char() -> Character:
            strokes=[]
            for idx, control_points in enumerate(self.active_stroke_control_points):
                if len(control_points) > 1:
                    scaled_control_points=[(x / (self.GRID_BREAKS - 1), y / (self.GRID_BREAKS - 1)) for x,y in control_points]
                    strokes.append(BrushStroke(control_points=scaled_control_points,
                                               weight=self.active_stroke_weight_vars[idx].get(),
                                               profile=CurveProfile(control_points=self.active_stroke_profile_control_points[idx],
                                                                    bounds=tuple(float(var.get()) for var in self.active_stroke_profile_bounds_vars[idx]))))

            return Character(character_type=self.active_character_type_var.get(),
                             definition=[x.get() for x in self.active_character_defs_vars],
                             strokes=strokes)

        if len(self.active_stroke_control_points) > 0:
            sub_lengths_check=[len(el) > 1 for el in self.active_stroke_control_points]
            if any(sub_lengths_check):
                char_tmp=_internal_build_char()
                self.active_character_cache=(char_tmp, ImageTk.PhotoImage(char_tmp.glyph))
            else:
                self.active_character_cache=None

    def refresh_character_preview(self):
        self.rebuild_active_character_image_cache()
        if self.rendered_glyph_label is not None and self.rendered_glyph_label.winfo_exists():
            image = self.active_character_cache[1] if self.active_character_cache else None
            self.rendered_glyph_label.configure(image=image)

    def clean_definition_json_import(self):
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

    def character_definition_to_editor(self, character: Character) -> None:
        """
        Converts a `Character` into the editor setup so it can be edited.
        """
        decomposed_strokes: list[list[tuple[int,int]]]=[]
        decomposed_stroke_weights: list[int]=[]
        decomposed_curve_profile_control_points: list[list[tuple[float,float]]]=[]
        decomposed_curve_profile_bounds: list[tuple[float,float]]=[]
        for stroke in character.strokes:
            grid_scaled_coord_path=[(int(x * (self.GRID_BREAKS - 1)), int(y * (self.GRID_BREAKS - 1))) for x,y in stroke.control_points]
            decomposed_strokes.append(grid_scaled_coord_path)
            decomposed_stroke_weights.append(stroke.weight)
            decomposed_curve_profile_control_points.append(stroke.profile.control_points.copy())
            decomposed_curve_profile_bounds.append(stroke.profile.bounds)

        self.active_stroke_idx=0
        self.active_stroke_control_points=decomposed_strokes
        self.active_stroke_weight_vars=[tk.IntVar(self, value) for value in decomposed_stroke_weights]
        self.active_stroke_profile_control_points=decomposed_curve_profile_control_points
        self.active_stroke_profile_bounds_vars=[(tk.StringVar(self, l), tk.StringVar(self, r)) for l,r in decomposed_curve_profile_bounds]

        self.active_character_type_var=tk.StringVar(self, character.character_type)
        self.active_character_type_var.trace_add("write", self.update_treeview)

        self.active_character_defs_vars: list[tk.StringVar]=[tk.StringVar(self, value) for value in character.definition]
        for definition_var in self.active_character_defs_vars:
            definition_var.trace_add("write", self.update_treeview)

        self.rebuild_active_character_image_cache()
        self.refresh()

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
        if not self.active_character_hash:
            return

        if self.active_character_hash not in self.character_glossary_data:
            return

        # get active entry in glossary
        item = self.character_glossary_data[self.active_character_hash]

        # for each locally tracked variable, assign to the working glossary
        item["character_type"] = self.active_character_type_var.get()
        item["definition"] = [var.get() for var in self.active_character_defs_vars]

        active_strokes = []
        active_stroke_weights = []
        active_stroke_profile_control_points = []
        active_stroke_profile_bounds = []
        for idx, path in enumerate(self.active_stroke_control_points):
            if not path:
                continue

            active_strokes.append(
                [(x / (self.GRID_BREAKS - 1), y / (self.GRID_BREAKS - 1)) for x, y in path]
            )
            active_stroke_weights.append(self.active_stroke_weight_vars[idx].get())
            active_stroke_profile_control_points.append(
                self.active_stroke_profile_control_points[idx]
            )
            active_stroke_profile_bounds.append(
                (float(self.active_stroke_profile_bounds_vars[idx][0].get()),
                 float(self.active_stroke_profile_bounds_vars[idx][1].get()))
            )

        item["stroke_control_points"] = active_strokes
        item["stroke_weights"] = active_stroke_weights
        item["stroke_profile_control_points"] = active_stroke_profile_control_points
        item["stroke_profile_bounds"] = active_stroke_profile_bounds

    def update_treeview(self, *_args):
        """
        Updates the treeview to reflect changes made to active character
        """
        self.commit_active_character_to_memory()
        if not self.active_character_hash or not hasattr(self, "dictionary_treeview"):
            return

        item = self.character_glossary_data[self.active_character_hash]
        tree_id = self.character_tree_ids.get(self.active_character_hash)
        group_id = self.character_type_tree_ids.get(item["character_type"])
        if tree_id and group_id:
            if self.dictionary_treeview.parent(tree_id) != group_id:
                self.dictionary_treeview.move(tree_id, group_id, tk.END)
            extra_defs_text = ""
            if len(item["definition"]) > 1:
                extra_defs_text = f" (+{len(item['definition']) - 1} more...)"
            self.dictionary_treeview.item(
                tree_id,
                values=(f"{item['definition'][0]}{extra_defs_text}",),
            )

    def save_file_beautiful(self, data: dict):
        def round_floats(o):
            if isinstance(o, float):
                return round(o, 3)
            if isinstance(o, dict):
                return {k: round_floats(v) for k, v in o.items()}
            if isinstance(o, (list, tuple)):
                return [round_floats(x) for x in o]
            return o
        with open(GLOSSARY_JSON_FP, "w") as file:
            options = jsbeautifier.default_options()
            options.indent_size = 2

            file.write(jsbeautifier.beautify(json.dumps(round_floats(data)), options))

    def save_glossary_to_json(self):
        self.commit_active_character_to_memory()
        self.save_file_beautiful(self.character_glossary_data)
        self.refresh()

    def select_character(self, hash: str, save_current: bool = True):
        """
        Selects a character by its hash (if it exists)
        """
        if hash in self.character_glossary_data:
            if save_current: # persist current changes, then move
                self.commit_active_character_to_memory() 
            self.active_character_hash=hash
            self.character_definition_to_editor(
                self.json_to_character(self.character_glossary_data[hash])
            )
        else:
            print(f"{hash} is not a valid character hash, ignoring event.")

    def add_new_stroke_items(self):
        self.active_stroke_control_points.append([])
        self.active_stroke_weight_vars.append(tk.IntVar(self, 1))
        self.active_stroke_profile_control_points.append(CurveProfile.REALISTIC.copy().control_points)
        self.active_stroke_profile_bounds_vars.append((tk.StringVar(self, CurveProfile.REALISTIC.bounds[0]), tk.StringVar(self, CurveProfile.REALISTIC.bounds[1])))

    def build_left_pane(self):
        """
        Construct the left-hand pane containing the treeview and character attributes.
        """
        def build_character_select_pane() -> tk.Frame:
            """
            Allows the user to select the character currently being edited from the glossary, add a new one, or delete one.
            """
            def add_entry(character_template: dict = None):
                tv: ttk.Treeview=self.dictionary_treeview
                hash: str=secrets.token_hex(4)

                if character_template is None:
                    # if the user has a type selected, new entry should be placed here
                    # otherwise, go with the active-character's type
                    focus_character_type = self.character_type_tree_ids.inverse.get(tv.focus(), None)
                    if focus_character_type is None:
                            focus_character_type = self.active_character_type_var.get()

                    character_template: dict={
                        "character_type": focus_character_type,
                        "definition": ["example definition"],
                        "stroke_control_points": [[[0.5, 0.0], [0.5, 1.0]]],
                        "stroke_weights": [1],
                        "stroke_profile_control_points":[CurveProfile.REALISTIC.copy().control_points],
                        "stroke_profile_bounds": [CurveProfile.REALISTIC.copy().bounds]
                        }

                self.character_glossary_data[hash]=character_template
                self.save_glossary_to_json()

                self.select_character(hash)
                self.refresh()

            def remove_entry(hash: str):
                self.commit_active_character_to_memory()

                hashes=list(self.character_glossary_data)
                if len(hashes) <= 1:
                    messagebox.showwarning(
                        "Cannot remove character",
                        "At least one character must remain in the glossary.",
                        parent=self.winfo_toplevel(),
                    )
                    return

                next_active_hash=self.active_character_hash
                if hash == self.active_character_hash:
                    removed_idx=hashes.index(hash)
                    next_active_hash=hashes[removed_idx - 1] if removed_idx > 0 else hashes[1]

                del self.character_glossary_data[hash]
                self.save_glossary_to_json()

                if hash == self.active_character_hash:
                    self.active_character_hash=next_active_hash
                    self.character_definition_to_editor(
                        self.json_to_character(self.character_glossary_data[next_active_hash])
                    )
                else:
                    self.refresh()

            def leftclick_entry(event: tk.Event):
                """
                Operation to perform on `self.dictionary_treeview` item doubleclick - assign to current view.
                """
                tv: ttk.Treeview=self.dictionary_treeview
                item=tv.identify("item", event.x, event.y)
                hash=tv.item(item, "text")
                self.select_character(hash)

            def middleclick_entry(event: tk.Event):
                tv: ttk.Treeview=self.dictionary_treeview
                item=tv.identify("item", event.x, event.y)
                hash=self.character_tree_ids.inverse.get(item, None)

                if hash:
                    character_to_clone = self.character_glossary_data[hash]
                    add_entry(character_to_clone.copy())


            def rightclick_entry(event: tk.Event):
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
                        remove_entry(hash)

            def construct_dictionary_treeview():
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

                tv.tag_configure('headings', image=self.character_treeview_icons["folder"])
                tv.tag_configure('selected', background="#b2cdec", image=self.character_treeview_icons["editing"])

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
                for hash, item in self.character_glossary_data.items():
                    char=self.json_to_character(item)

                    row_tags = ('selected',) if hash == self.active_character_hash else ('unselected',)
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

                if self.active_character_hash in self.character_tree_ids.keys():
                    tv.see(item=self.character_tree_ids[self.active_character_hash])

            character_select_pane=tk.Frame(self.left_pane)
            character_select_pane.columnconfigure(0, weight=1)
            character_select_pane.rowconfigure(0, weight=1)
            character_select_pane.rowconfigure(1, weight=8)

            tk.Button(character_select_pane, command=add_entry, text="+ Add new entry").grid(column=0, row=0, sticky="EW")

            self.dictionary_treeview=ttk.Treeview(character_select_pane, columns=("defs"))
            self.dictionary_treeview.grid(column=0, row=1, sticky="NSEW")
            self.dictionary_treeview.bind("<ButtonPress-1>", leftclick_entry)
            self.dictionary_treeview.bind("<ButtonPress-2>", middleclick_entry)
            self.dictionary_treeview.bind("<ButtonPress-3>", rightclick_entry)
            construct_dictionary_treeview()

            return character_select_pane


        def build_character_type_pane() -> tk.Frame:
            """
            `self.left_pane` element for modifying the `Character.character_type`.
            """
            # Character - Type:
            character_type_pane=tk.Frame(self.left_pane)
            character_type_pane.columnconfigure(0, weight=1)
            character_type_pane.columnconfigure(1, weight=3)
            tk.Label(character_type_pane, text=f"Type:").grid(column=0, row=0, sticky="NSEW")
            character_type_input=tk.OptionMenu(character_type_pane, self.active_character_type_var, *list(typing.get_args(CHARACTER_TYPES)))
            character_type_input.grid(column=1, row=0, sticky="NSEW")

            return character_type_pane

        def build_character_defs_pane() -> tk.Frame:
            """
            `self.left_pane` element for modifying the `Character.definition`.
            """
            def add_or_remove_character_defs(value: int):
                if value > 0:
                    definition_var=tk.StringVar(self, value="")
                    definition_var.trace_add("write", self.update_treeview)
                    self.active_character_defs_vars.append(definition_var)
                elif len(self.active_character_defs_vars) > 1:
                    _ = self.active_character_defs_vars.pop()
                self.update_treeview()
                self.refresh()
            
            # Character - Definition(s):
            character_defs_pane=tk.Frame(self.left_pane)
            character_defs_pane.columnconfigure(0, weight=1)
    
            character_defs_increment_pane=tk.Frame(character_defs_pane)
            character_defs_increment_pane.columnconfigure(0, weight=1)
            character_defs_increment_pane.columnconfigure(1, weight=1)
            character_defs_increment_pane.grid(column=0, row=0, sticky="NEW")
            character_defs_decrease=tk.Button(character_defs_increment_pane, command=lambda: add_or_remove_character_defs(-1), text="-")
            character_defs_increase=tk.Button(character_defs_increment_pane, command=lambda: add_or_remove_character_defs(1), text="+")
            character_defs_decrease.grid(column=0, row=0, sticky="NSEW")
            character_defs_increase.grid(column=1, row=0, sticky="NSEW")
    
            for idx in range(len(self.active_character_defs_vars)):
                entry_row=tk.Frame(character_defs_pane)
                entry_row.grid(column=0, row=idx+1)
    
                tk.Label(entry_row, text=f"Def {idx}:").pack(side=tk.LEFT)
    
                entry_field=ttk.Entry(entry_row, textvariable=self.active_character_defs_vars[idx])
                entry_field.pack(side=tk.LEFT)

            return character_defs_pane

        def build_render_character_pane() -> tk.Frame:
            """
            `self.left_pane` element for displaying the resulting `Character.glyph` `Image.Image`.
            Goes through a precalculated `self.active_character_cache` which is a `tuple[Character, ImageTk.PhotoImage]`,
            as garbage collection removes images precalculated inline this way.
            """          
            render_character_pane=tk.Frame(self.left_pane)
            render_character_pane.columnconfigure(0, weight=1)

            if self.active_character_cache:
                tk.Label(render_character_pane, text="Rendered Glyph").grid(column=0, row=0, sticky="NEW")
                image_label=tk.Label(render_character_pane,
                                       image=self.active_character_cache[1],
                                       highlightthickness=1, highlightbackground="black")
                image_label.grid(column=0, row=1)
                self.rendered_glyph_label = image_label

            return render_character_pane

        # Left Pane --------------------
        if hasattr(self, "left_pane"):
                    self.left_pane.destroy()
        self.left_pane=tk.Frame(self,
                               padx=4,
                               pady=4,
                               highlightthickness=1, highlightbackground="black")
        self.left_pane.columnconfigure(0, weight=1)
        self.left_pane.rowconfigure(4, weight=1)
        self.left_pane.grid(column=0, row=0, sticky="NSEW", padx=12)
        self.rendered_glyph_label = None

        build_character_select_pane().grid(column=0, row=0, sticky="NEW")
        build_character_type_pane().grid(column=0, row=1, sticky="NEW")
        build_character_defs_pane().grid(column=0, row=2, sticky="NEW")
        build_render_character_pane().grid(column=0, row=3, sticky="NEW")
        tk.Button(self.left_pane, text="Save", command=self.save_glossary_to_json).grid(
            column=0, row=5, sticky="EW"
        )

    def build_canvas_pane(self):
        """
        Construct the canvas pane containing the `BrushStroke` drawing tool.
        """
        def build_stroke_options_pane() -> tk.Frame:
            """
            `self.canvas_pane` element for scrubbing through active `BrushStrokes`, modifying weight, etc.
            """
            def change_stroke_idx(value: int):
                """
                Helper for incrementing/decrementing the `self.active_stroke_idx` value
                """
                def remove_stroke_definition_empties() -> bool:
                    """
                    Helper for removing empty`BrushStroke` slots, should they appear, in `self.active_stroke_control_points`, `self.active_stroke_weight_vars`.
                    """
                    empty_results=[]
                    current_stroke_removed=False

                    # stroke control points is the decider here, as it makes the call on whether
                    # the stroke "exists" or not, the others are sort of metadata for it
                    while any(len(el) <= 1 for el in self.active_stroke_control_points):
                        target_empty_idx=[idx for idx, el in enumerate(self.active_stroke_control_points) if len(el) <= 1][0]

                        _=self.active_stroke_control_points.pop(target_empty_idx)
                        _=self.active_stroke_weight_vars.pop(target_empty_idx)
                        _=self.active_stroke_profile_control_points.pop(target_empty_idx)
                        _=self.active_stroke_profile_bounds_vars.pop(target_empty_idx)

                        empty_results.append(target_empty_idx)
                        if target_empty_idx <= self.active_stroke_idx:
                            if target_empty_idx == self.active_stroke_idx:
                                current_stroke_removed=True
                            self.active_stroke_idx=self.active_stroke_idx - 1
                    self.active_stroke_idx=max(0, self.active_stroke_idx)
                    if len(empty_results) > 0:
                        print(f"Some empty strokes were found at {empty_results}, removed.")
                    # print(f"diagnostics: removed {empty_results},\n current index {self.active_stroke_idx},\n paths {self.active_stroke_control_points}")
                    return current_stroke_removed

                current_stroke_removed=remove_stroke_definition_empties()

                if len(self.active_stroke_control_points) < 1:
                    self.active_stroke_idx=0
                    if value > 0:
                        self.add_new_stroke_items()
                    self.refresh()
                    return

                cur_idx=self.active_stroke_idx
                new_idx=cur_idx + value

                if current_stroke_removed and value < 0:
                    new_idx=cur_idx

                if new_idx >= 0:
                    if len(self.active_stroke_control_points) <= new_idx:
                        self.add_new_stroke_items()
                    self.active_stroke_idx=new_idx
                else:
                    print(f"Tried to reduce idx to {new_idx}, ignoring.")

                self.refresh()

            stroke_options_pane=tk.Frame(self.canvas_pane, pady=4)
            stroke_options_pane.columnconfigure(0, weight=1)
            stroke_options_pane.columnconfigure(1, weight=3)
            stroke_options_pane.columnconfigure(2, weight=3)
            stroke_options_pane.columnconfigure(3, weight=1)

            prev_stroke_button=tk.Button(stroke_options_pane, command=lambda: change_stroke_idx(-1), text="\u2b9c")
            next_stroke_button=tk.Button(stroke_options_pane, command=lambda: change_stroke_idx(1), text="\u2b9e")

            prev_stroke_button.grid(column=0, row=0, sticky="EW")
            next_stroke_button.grid(column=3, row=0, sticky="EW")

            tk.Label(stroke_options_pane, text=
                     f"Character {self.active_character_hash} | "
                     f"Brushstroke {self.active_stroke_idx} | "
                     f"Weight={self.active_stroke_weight_vars[self.active_stroke_idx].get()}"
                     ).grid(column=1, row=0, columnspan=2)
            
            if self.show_stroke_options.get():
                weight_slider=ttk.Scale(stroke_options_pane, variable=self.active_stroke_weight_vars[self.active_stroke_idx], from_=1,to=16)
                weight_slider.bind("<ButtonRelease-1>", self.refresh)
                weight_slider.grid(column=1, row=1, columnspan=2)

                try:
                    crv_prf = CurveProfile(control_points=self.active_stroke_profile_control_points[self.active_stroke_idx],
                                        bounds=tuple(float(var.get()) for var in self.active_stroke_profile_bounds_vars[self.active_stroke_idx]))
                except IndexError:
                    crv_prf = CurveProfile(
                        control_points=CurveProfile.REALISTIC.copy().control_points,
                        bounds=CurveProfile.REALISTIC.copy().bounds,
                    )
                self.curve_profile_widget=CurveProfileWidget(stroke_options_pane,
                                                            size=(128,128),
                                                            curve_profile=crv_prf,
                                                            on_refresh=self.refresh_character_preview,
                                                            )
                self.curve_profile_widget.grid(column=1, row=2, columnspan=2)

                if len(self.active_stroke_profile_bounds_vars) > 0:
                    self.bounds_left_spinbox=ttk.Spinbox(stroke_options_pane,
                                                        textvariable=self.active_stroke_profile_bounds_vars[self.active_stroke_idx][0],
                                                        command=self.refresh_character_preview,
                                                        to=16.0, increment=0.1)
                    self.bounds_right_spinbox=ttk.Spinbox(stroke_options_pane,
                                                        textvariable=self.active_stroke_profile_bounds_vars[self.active_stroke_idx][1],
                                                        command=self.refresh_character_preview,
                                                        to=16.0, increment=0.1)
                    self.bounds_left_spinbox.grid(column=1, row=3, sticky="E")
                    self.bounds_right_spinbox.grid(column=2, row=3, sticky="W")

            return stroke_options_pane

        
        # Canvas Pane -------------------
        if hasattr(self, "canvas_pane"):
            self.canvas_pane.destroy()
        self.canvas_pane=tk.Frame(self,
                                   padx=4,
                                   pady=4,
                                   highlightthickness=1, highlightbackground="black")
        self.canvas_pane.columnconfigure(0, weight=1)
        self.canvas_pane.grid(row=0, column=1, sticky="NSEW", padx=12)
        self.canvas=tk.Canvas(self.canvas_pane,
                              width=self.canvas_size,
                              height=self.canvas_size,
                              highlightthickness=1, highlightbackground="black")
        self.canvas.grid(column=0, row=0, sticky="NS")

        self.canvas.bind("<ButtonPress-1>", self.leftclick_x_y)
        self.canvas.bind("<ButtonPress-3>", self.rightclick_x_y)
        self.draw_canvas()

        build_stroke_options_pane().grid(column=0, row=1, sticky="EW")

        tk.Checkbutton(self.canvas_pane,
                variable=self.show_stroke_options,
                text="Show stroke options",
                command=self.refresh).grid(column=0, row=2, sticky="SW")

    def leftclick_x_y(self, event: tk.Event):
        """
        Action to perform on `self.canvas` left-click: add integer coordinates to `self.active_stroke_control_points[self.active_stroke_idx].`
        """
        if not self.active_stroke_idx < len(self.active_stroke_control_points):
            self.active_stroke_control_points.append([])

        x,y=(min(self.canvas_size, event.x) // self.CELL_SIZE, min(self.canvas_size, event.y) // self.CELL_SIZE)
        self.active_stroke_control_points[self.active_stroke_idx].append((x,y))
        self.refresh()

    def rightclick_x_y(self, event: tk.Event):
        """
        Action to perform on `self.canvas` right-click: remove most recent matching integer coordinates from `self.active_stroke_control_points[self.active_stroke_idx].`
        """
        x,y=(min(self.canvas_size, event.x) // self.CELL_SIZE, min(self.canvas_size, event.y) // self.CELL_SIZE)
        # get most recent (last) item in list which contains x,y as coords, and drop
        matching_idxs=[]
        for idx, (lx,ly) in enumerate(self.active_stroke_control_points[self.active_stroke_idx]):
            if lx == x and ly == y:
                matching_idxs.append(idx)

        if len(matching_idxs) > 0:
            _=self.active_stroke_control_points[self.active_stroke_idx].pop(matching_idxs[-1])

        self.refresh()

    def draw_canvas(self):
        """
        Draw to `self.canvas` - add gridlines, red indicators and thick lines for current stroke, faded indicators and thin lines for others.
        """
        def draw_gridlines():
            for pos in range(0, self.canvas_size, self.CELL_SIZE):
                self.canvas.create_line(pos, 0, pos, self.canvas_size)
                self.canvas.create_line(0, pos, self.canvas_size, pos)
        
        self.canvas.delete('all')
        draw_gridlines()

        if self.active_stroke_idx < len(self.active_stroke_control_points):
            for stroke_idx, stroke in enumerate(self.active_stroke_control_points):
                for coord_idx, (x, y) in enumerate(stroke):

                    # the active stroke
                    if self.active_stroke_idx == stroke_idx:
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

# Main app -------------
root=tk.Tk()
root.title("Character Drawing Tool DEBUG")
drawing_tool = DrawingTool(root)
drawing_tool.pack(fill="both", expand=True)
root.protocol("WM_DELETE_WINDOW", drawing_tool.on_app_close)

root.mainloop()