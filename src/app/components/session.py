import tkinter as tk
from tkinter import messagebox
import typing
import uuid

from src.symbols.characters import Glyph, Character
from src.symbols.strokes import BrushStroke
from src.dictionary.data import (
    export_characters_and_glyphs_to_json,
    import_glyphs_from_json,
    import_characters_from_json,
)

class AppSession:
    GRID_BREAKS = 15
    CELL_SIZE = 36
    CANVAS_SIZE = GRID_BREAKS * CELL_SIZE

    def __init__(self, master: tk.Misc):
        self.master: tk.Misc=master
        self.on_change: list[typing.Callable[[str], None]]=[]

        # Globally relevant =================
        self.glyph_glossary_data: dict[str, Glyph] = import_glyphs_from_json()
        self.character_glossary_data: dict[str, Character]=import_characters_from_json(self.glyph_glossary_data)

        if not self.character_glossary_data:
            raise ValueError("The glossary must contain at least one character.")

        # Relevant to current Character =====
        self.active_character_hash: str=""
        self.active_character_defs_vars: list[tuple[tk.StringVar,tk.StringVar]]=[]
        self.current_page: str = "Character"
        # Relevant to current Glyph =========
        self.active_glyph_idx: int=0

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

    def export_glossary_json(self):
        """
        Writes the JSON from the session glossary.
        """
        self.commit_active_character_to_memory()
        for character in self.character_glossary_data.values():
            self.register_character_glyphs(character)
        export_characters_and_glyphs_to_json(
            self.character_glossary_data,
            self.glyph_glossary_data,
        )

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

    @property
    def active_character(self) -> Character:
        return self.character_glossary_data[self.active_character_hash]

    @property
    def active_glyph(self) -> Glyph:
        return self.active_character.glyphs[self.active_glyph_idx]

    @property
    def active_glyph_strokes(self) -> list[BrushStroke]:
        return self.active_glyph.strokes

    def register_character_glyphs(self, character: Character) -> None:
        registered_ids = {id(glyph) for glyph in self.glyph_glossary_data.values()}
        for glyph in character.glyphs:
            if id(glyph) not in registered_ids:
                self.glyph_glossary_data[self._new_glyph_hash()] = glyph
                registered_ids.add(id(glyph))

    def _new_glyph_hash(self) -> str:
        glyph_hash = uuid.uuid4().hex
        while glyph_hash in self.glyph_glossary_data:
            glyph_hash = uuid.uuid4().hex
        return glyph_hash

    def add_glyph_to_character(self, glyph_hash: str) -> None:
        character = self.active_character
        new_idx = len(character.glyphs)

        glyph = self.glyph_glossary_data[glyph_hash]
        character.glyphs.append(glyph)

        character.glyph_extents.append(((0.0,0.0),(1.0,1.0)))
        self.active_glyph_idx = new_idx
        self.active_stroke_idx = 0
        self.refresh("glyphs")

    def create_glyph_for_character(self) -> str:
        glyph_hash = self._new_glyph_hash()
        self.glyph_glossary_data[glyph_hash] = Glyph([BrushStroke([(0.5,0.0),(0.5,1.0)])])
        self.add_glyph_to_character(glyph_hash)
        return glyph_hash

    def remove_active_glyph_from_character(self) -> None:
        character = self.active_character
        if len(character.glyphs) <= 1:
            raise ValueError("A character must contain at least one glyph.")
        character.glyphs.pop(self.active_glyph_idx)
        character.glyph_extents.pop(self.active_glyph_idx)
        self.active_glyph_idx = min(self.active_glyph_idx, len(character.glyphs) - 1)
        self.active_stroke_idx = 0
        self.refresh("glyphs")

    def add_stroke_point(self, point: tuple[float, float]) -> None:
        strokes = self.active_glyph_strokes
        if self.active_stroke_idx == len(strokes):
            strokes.append(BrushStroke([point]))
        else:
            stroke = strokes[self.active_stroke_idx]
            strokes[self.active_stroke_idx] = BrushStroke(
                stroke.control_points + [point],
                profile=stroke.profile,
            )
        self.refresh("stroke")

    def remove_stroke_point(self, point: tuple[float, float]) -> None:
        strokes = self.active_glyph_strokes
        if self.active_stroke_idx >= len(strokes):
            return

        stroke = strokes[self.active_stroke_idx]
        grid_max = self.GRID_BREAKS - 1
        target = (round(point[0] * grid_max), round(point[1] * grid_max))
        matching_idx = next(
            (
                idx for idx in range(len(stroke.control_points) - 1, -1, -1)
                if tuple(round(value * grid_max) for value in stroke.control_points[idx]) == target
            ),
            None,
        )
        if matching_idx is None:
            return

        points = stroke.control_points.copy()
        points.pop(matching_idx)
        if points:
            strokes[self.active_stroke_idx] = BrushStroke(
                points,
                profile=stroke.profile,
            )
        else:
            strokes.pop(self.active_stroke_idx)
            self.active_stroke_idx = min(self.active_stroke_idx, len(strokes))
        self.refresh("stroke")

    def remove_active_stroke(self) -> None:
        strokes = self.active_glyph_strokes
        if len(strokes) <= 1:
            raise ValueError("A glyph must contain at least one stroke.")
        if self.active_stroke_idx < len(strokes):
            strokes.pop(self.active_stroke_idx)
            self.active_stroke_idx = min(self.active_stroke_idx, len(strokes) - 1)
            self.refresh("stroke")

    def select_glyph(self, idx: int, stroke_idx: int | None = None) -> None:
        if not 0 <= idx < len(self.active_character.glyphs):
            raise IndexError(f"{idx} is not a valid glyph index.")
        strokes = self.active_character.glyphs[idx].strokes
        selected_stroke_idx = 0 if stroke_idx is None else stroke_idx
        if not 0 <= selected_stroke_idx <= len(strokes):
            raise IndexError(f"{selected_stroke_idx} is not a valid stroke index.")
        self.active_glyph_idx = idx
        self.active_stroke_idx = selected_stroke_idx
        self.refresh("stroke" if stroke_idx is not None else "glyph-selection")

    def select_stroke(self, idx: int) -> None:
        if not 0 <= idx <= len(self.active_glyph_strokes):
            raise IndexError(f"{idx} is not a valid stroke index.")
        self.active_stroke_idx = idx
        self.refresh("stroke")

    def stroke_changed(self):
        self.refresh("stroke")

    def profile_changed(self):
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
        self.register_character_glyphs(character)
        self.active_glyph_idx=0
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