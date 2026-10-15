import tkinter as tk
from tkinter import messagebox
import typing

from src.symbols.characters import Glyph, Character
from src.symbols.strokes import CurveProfile, BrushStroke
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
        self.import_glossary_json()

        if not self.character_glossary_data:
            raise ValueError("The glossary must contain at least one character.")

        # Relevant to current Character =====
        self.active_character_hash: str=""
        self.active_character_defs_vars: list[tuple[tk.StringVar,tk.StringVar]]=[]
        self.active_character_glyphs: list[Glyph] # must be a list, as could have same Glyph twice
        self.active_character_glyph_extents: list[tuple[tuple[float,float],tuple[float,float]]]=[] # the extent of each Glyph in the Character

        # Relevant to current Glyph =========
        self.active_glyph_idx: int=0
        self.active_glyph_strokes: list[BrushStroke]

        # Relevant to current BrushStroke ===
        self.active_stroke_idx: int=0

        # Setup -----------------------------
        first_character_hash=next(iter(self.character_glossary_data))
        self.active_character_hash=first_character_hash
        self.character_object_to_editor(self.character_glossary_data[first_character_hash])

    def refresh(self, change: str = "all"):
        if len(self.on_change) > 0:
            for refresh_callable in self.on_change:
                refresh_callable(change)

    def import_glossary_json(self):
        """
        Sets the session glossary from the JSON.
        """
        self.character_glossary_data = import_characters_from_json()

    def export_glossary_json(self):
        """
        Writes the JSON from the session glossary.
        """
        self.commit_active_character_to_memory()
        export_characters_to_json(self.character_glossary_data)

    def select_stroke(self, idx: int):
        """
        Selects a stroke by its idx (if it exists)
        """
        if idx < len(self.glyph_stroke_control_points):
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
            
            self.active_character_hash=hash
            self.character_object_to_editor(
                self.character_glossary_data[hash]
            )
            self.refresh("selection")
        else:
            raise KeyError(f"{hash} is not a valid character hash.")

    def remove_character(self, hash: str):
        """
        Removes a Character from the internal glossary, selects the next available, then saves the glossary JSON.
        """
        if hash not in self.character_glossary_data.keys():
            return

        answer = messagebox.askyesno("Remove entry",
                                        f"Remove the glossary entry for character {hash}?",
                                        icon="question",
                                        parent=self.master.winfo_toplevel()
                                        )
        
        if answer:
            self.commit_active_character_to_memory()
            hashes=list(self.character_glossary_data.keys())

            if len(hashes) <= 1:
                messagebox.showwarning(
                    "Cannot remove character",
                    "At least one character must remain in the glossary.",
                    parent=self.master.winfo_toplevel(),
                )
                return
            
            next_active_hash=self.active_character_hash
            removing_active = hash == self.active_character_hash
            if removing_active:
                removed_idx=hashes.index(hash)
                next_active_hash=hashes[removed_idx - 1] if removed_idx > 0 else hashes[removed_idx + 1]
    
            del self.character_glossary_data[hash]
    
            if removing_active:
                self.select_character(next_active_hash, save_current=False)
            else:
                self.refresh("list")
            self.export_glossary_json()

    def add_new_stroke_items(self):
        self.active_glyph_strokes.append(BrushStroke())

    def stroke_changed(self):
        self.commit_active_character_to_memory()
        self.refresh("stroke")

    def profile_changed(self):
        self.commit_active_character_to_memory()
        self.refresh("preview")

    def update_treeview(self, *_):
        self.commit_active_character_to_memory()
        self.refresh("metadata")

    def scale_from_grid(self, path: list[tuple[int,int]]) -> list[tuple[float,float]]:
        """
        Converts stroke from grid-index integer tuples to 0-1 coordinate-grid float tuples.
        """
        grid_max = self.GRID_BREAKS - 1
        return [(x / grid_max, y / grid_max) for x, y in path]

    def scale_to_grid(self, path: list[tuple[float,float]]) -> list[tuple[int,int]]:
        """
        Converts stroke 0-1 coordinate-grid float tuples to grid-index integer tuples.
        """
        grid_max = self.GRID_BREAKS - 1
        return [(int(x * grid_max), int(y * grid_max)) for x,y in path]

    def character_object_to_editor(self, character: Character) -> None:
        """
        Converts a `Character` into the editor setup so it can be edited.
        """
        self.active_character_glyphs = character.glyphs
        self.active_character_glyph_extents = character.glyph_extents

        self.active_glyph_idx=0
        self.active_glyph_strokes=character.glyphs[0].strokes

        self.active_stroke_idx=0

        self.active_character_defs_vars: list[tuple[tk.StringVar,tk.StringVar]]=[
            (tk.StringVar(self.master, t), tk.StringVar(self.master, d)) for t,d in character.definition
        ]

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
        item.definition = [(t.get(), d.get()) for t,d in self.active_character_defs_vars]