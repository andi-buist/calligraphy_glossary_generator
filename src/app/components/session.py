import tkinter as tk
from tkinter import messagebox
import typing

from src.symbols.characters import Character
from src.symbols.strokes import CurveProfile, BrushStroke, StrokeCollection
from src.dictionary.data import import_characters_from_json, export_characters_to_json

class AppSession:
    GRID_BREAKS = 15
    CELL_SIZE = 36
    CANVAS_SIZE = GRID_BREAKS * CELL_SIZE

    def __init__(self, master: tk.Misc):
        self.master: tk.Misc=master
        self.on_change: list[typing.Callable[[str], None]]=[]

        # Globally relevant =================
        self.character_glossary_data: dict[str, Character]={}
        self.import_characters()

        # Relevant to current character =====
        self.current_stroke_idx: int=0

        self.character_hash: str=""
        self.character_stroke_control_points: list[list[tuple[int,int]]]=[]
        self.character_stroke_profile_control_points: list[list[tuple[float,float]]]=[]
        self.character_stroke_profile_bounds_vars: list[tuple[tk.StringVar,tk.StringVar]]=[]

        self.character_defs_vars: list[tuple[tk.StringVar,tk.StringVar]]=[]

        if not self.character_glossary_data:
            raise ValueError("The glossary must contain at least one character.")

        first_hash=next(iter(self.character_glossary_data))
        self.character_hash=first_hash
        self.character_definition_to_editor(self.character_glossary_data[first_hash])

    def refresh(self, change: str = "all"):
        if len(self.on_change) > 0:
            for refresh_callable in self.on_change:
                refresh_callable(change)

    def import_characters(self):
        self.character_glossary_data = import_characters_from_json()

    def export_glossary_json(self):
        self.commit_active_character_to_memory()
        export_characters_to_json(self.character_glossary_data)

    def select_stroke(self, idx: int):
        """
        Selects a stroke by its idx (if it exists)
        """
        if idx < len(self.character_stroke_control_points):
            self.current_stroke_idx=idx
            self.refresh("stroke")
        else:
            raise KeyError(f"{idx} is not a valid stroke index.")
    
    def select_character(self, hash: str, save_current: bool = True):
        """
        Selects a character by its hash (if it exists)
        """
        if hash in self.character_glossary_data:
            if save_current: # persist current changes, then move
                self.commit_active_character_to_memory()
            self.character_hash=hash
            self.character_definition_to_editor(
                self.character_glossary_data[hash]
            )
            self.refresh("selection")
        else:
            raise KeyError(f"{hash} is not a valid character hash.")

    def remove_character(self, hash: str):
        if hash not in self.character_glossary_data.keys():
            return

        answer = messagebox.askyesno("Remove entry",
                                        f"Remove the glossary entry for character {hash}?",
                                        icon="question",
                                        parent=self.master.winfo_toplevel()
                                        )
        
        if answer:
            self.commit_active_character_to_memory()
            hashes=list(self.character_glossary_data)

            if len(hashes) <= 1:
                messagebox.showwarning(
                    "Cannot remove character",
                    "At least one character must remain in the glossary.",
                    parent=self.master.winfo_toplevel(),
                )
                return
            
            next_active_hash=self.character_hash
            removing_active = hash == self.character_hash
            if removing_active:
                removed_idx=hashes.index(hash)
                next_active_hash=hashes[removed_idx - 1] if removed_idx > 0 else hashes[removed_idx + 1]
    
            del self.character_glossary_data[hash]
            del self.character_glossary_stroke_parentage_data[hash]
    
            if removing_active:
                self.select_character(next_active_hash, save_current=False)
            else:
                self.refresh("list")
            self.export_glossary_json()

    def add_new_stroke_items(self):
        self.character_stroke_control_points.append([])
        self.active_stroke_source_control_points.append(None)
        self.character_stroke_profile_control_points.append(CurveProfile.REALISTIC.copy().control_points)
        self.character_stroke_profile_bounds_vars.append((
            tk.StringVar(self.master, CurveProfile.REALISTIC.bounds[0]),
            tk.StringVar(self.master, CurveProfile.REALISTIC.bounds[1]),
        ))

    def stroke_changed(self):
        self.commit_active_character_to_memory()
        self.refresh("stroke")

    def profile_changed(self):
        self.commit_active_character_to_memory()
        self.refresh("preview")

    def update_treeview(self, *_):
        self.commit_active_character_to_memory()
        self.refresh("metadata")

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
        decomposed_curve_profile_control_points: list[list[tuple[float,float]]]=[]
        decomposed_curve_profile_bounds: list[tuple[float,float]]=[]
        for stroke in character.strokes:
            grid_scaled_coord_path=[(int(x * (self.GRID_BREAKS - 1)), int(y * (self.GRID_BREAKS - 1))) for x,y in stroke.control_points]
            decomposed_strokes.append(grid_scaled_coord_path)
            decomposed_source_control_points.append(list(stroke.control_points))
            decomposed_curve_profile_control_points.append(stroke.profile.control_points.copy())
            decomposed_curve_profile_bounds.append(stroke.profile.bounds)

        self.current_stroke_idx=0
        self.character_stroke_control_points=decomposed_strokes
        self.active_stroke_source_control_points=decomposed_source_control_points
        self.character_stroke_profile_control_points=decomposed_curve_profile_control_points
        self.character_stroke_profile_bounds_vars=[
            (tk.StringVar(self.master, l), tk.StringVar(self.master, r))
            for l,r in decomposed_curve_profile_bounds
        ]

        self.character_defs_vars: list[tuple[tk.StringVar,tk.StringVar]]=[
            (tk.StringVar(self.master, t), tk.StringVar(self.master, d)) for t,d in character.definition
        ]

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
        item.definition = [(t.get(), d.get()) for t,d in self.character_defs_vars]

        active_strokes = []
        character_stroke_profile_control_points = []
        active_stroke_profile_bounds = []
        for idx, path in enumerate(self.character_stroke_control_points):
            if not path:
                continue

            active_strokes.append(self._get_normalized_stroke_control_points(idx))
            character_stroke_profile_control_points.append(
                self.character_stroke_profile_control_points[idx]
            )
            active_stroke_profile_bounds.append(
                (float(self.character_stroke_profile_bounds_vars[idx][0].get()),
                    float(self.character_stroke_profile_bounds_vars[idx][1].get()))
            )

        item["stroke_control_points"] = active_strokes
        item["stroke_profile_control_points"] = character_stroke_profile_control_points
        item["stroke_profile_bounds"] = active_stroke_profile_bounds