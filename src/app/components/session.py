import os
import tkinter as tk
from tkinter import messagebox, filedialog
import typing
from typing import Literal
import secrets

from src.symbols.characters import Glyph, Character
from src.symbols.strokes import BrushStroke
from src.dictionary.data import (
    export_characters_and_glyphs_to_json,
    import_characters_and_glyphs_from_json
)

class AppSession:
    GRID_BREAKS = 15
    CELL_SIZE = 36
    CANVAS_SIZE = GRID_BREAKS * CELL_SIZE

    def __init__(self, master: tk.Misc):
        self.master: tk.Misc=master
        self.on_change: list[typing.Callable[[str], None]]=[]

        self.root_filepath=filedialog.askdirectory()
        if not self.root_filepath:
            raise FileNotFoundError("Directory not selected, exiting.")
        else:
            if os.path.exists(self.root_filepath + "/characters.json"):
                self.characters_json_filepath = self.root_filepath + "/characters.json"
            else: raise FileNotFoundError(f"Couldn't find characters.json in {self.root_filepath}")
            if os.path.exists(self.root_filepath + "/glyphs.json"):
                self.glyphs_json_filepath = self.root_filepath + "/glyphs.json"
            else: raise FileNotFoundError(f"Couldn't find glyphs.json in {self.root_filepath}")

        # Globally relevant =================
        self.current_page = tk.StringVar(value="Character")

        characters_imported, glyphs_imported = import_characters_and_glyphs_from_json(self.characters_json_filepath, self.glyphs_json_filepath)
        self.character_glossary_data: dict[str, Character] = characters_imported
        self.glyph_glossary_data: dict[str, Glyph] = glyphs_imported

        if not self.character_glossary_data:
            raise ValueError("The glossary must contain at least one character.")

        # Relevant to current element =====
        self.active_character_hash: str | None = None
        self.active_glyph_hash: str | None = None
        self.active_definitions_vars: list[tuple[tk.StringVar,tk.StringVar]]=[]

        # Relevant to Character/Glyph components
        self.active_hierarchy_idx: tuple[Literal["glyph","subcharacter"], int] | None = ("glyph",0)
        self.active_glyph_stroke_idx: int=0

        # Setup -----------------------------
        self.set_init_state()

    def set_init_state(self):
        first_character_hash=next(iter(self.character_glossary_data))
        self.active_character_hash=first_character_hash
        self.character_object_to_editor(self.character_glossary_data[first_character_hash])
        self.active_glyph_hash = next(iter(self.glyph_glossary_data), None)

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
            self.characters_json_filepath,
            self.glyphs_json_filepath
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
        character = self.character_glossary_data.get(hash)
        if character is None:
            return

        users = [
            (character_hash, candidate)
            for character_hash, candidate in self.character_glossary_data.items()
            if character_hash != hash
            and any(subcharacter is character for subcharacter in candidate.subcharacters)
        ]
        if users:
            user_details = "\n".join(
                f"{character_hash}: "
                f"{candidate.definition[0][1] if candidate.definition else '(no definition)'}"
                for character_hash, candidate in users
            )
            messagebox.showwarning(
                "Cannot remove character",
                f"Character {hash} is used as a component by:\n{user_details}",
                parent=self.master.winfo_toplevel(),
            )
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

    def remove_glyph(self, hash: str) -> None:
        glyph = self.glyph_glossary_data.get(hash)
        if glyph is None:
            return

        users = [
            (character_hash, character)
            for character_hash, character in self.character_glossary_data.items()
            if any(component is glyph for component in character.glyphs)
        ]
        if users:
            user_details = "\n".join(
                f"{character_hash}: "
                f"{character.definition[0][1] if character.definition else '(no definition)'}"
                for character_hash, character in users
            )
            messagebox.showwarning(
                "Cannot remove glyph",
                f"Glyph {hash} is used as a component by:\n{user_details}",
                parent=self.master.winfo_toplevel(),
            )
            return

        answer = messagebox.askyesno(
            "Remove entry",
            f"Remove the glossary entry for glyph {hash}?",
            icon="question",
            parent=self.master.winfo_toplevel(),
        )
        if not answer:
            return

        del self.glyph_glossary_data[hash]
        if self.active_glyph_hash == hash:
            self.active_glyph_hash = next(iter(self.glyph_glossary_data), None)
            self.active_glyph_stroke_idx = 0
            self.refresh("glyph-selection")
        else:
            self.refresh("list")
        self.export_glossary_json()

    @property
    def active_character(self) -> Character:
        if self.active_character_hash is None:
            raise RuntimeError("No character is selected.")
        return self.character_glossary_data[self.active_character_hash]

    @property
    def active_glyph(self) -> Glyph | None:
        if self.active_glyph_hash is None:
            return None
        return self.glyph_glossary_data[self.active_glyph_hash]

    @property
    def active_component(self) -> Glyph | Character:
        if self.active_hierarchy_idx is None:
            raise RuntimeError("The active character has no selected component.")
        ac_type, ac_idx = self.active_hierarchy_idx
        if ac_type == "glyph":
            return self.active_character.glyphs[ac_idx]
        else:
            return self.active_character.subcharacters[ac_idx]

    @property
    def active_glyph_strokes(self) -> list[BrushStroke]:
        glyph = self.active_glyph
        if glyph is None:
            raise RuntimeError("No glyph is selected.")
        return glyph.strokes

    def register_character_glyphs(self, character: Character) -> None:
        registered_ids = {id(glyph) for glyph in self.glyph_glossary_data.values()}
        for glyph in character.glyphs:
            if id(glyph) not in registered_ids:
                self.glyph_glossary_data[self._new_glyph_hash()] = glyph
                registered_ids.add(id(glyph))

    def _new_glyph_hash(self) -> str:
        glyph_hash = secrets.token_hex(8)

        # quick check to ensure we don't overwrite an existing entry
        while glyph_hash in self.glyph_glossary_data:
            glyph_hash = secrets.token_hex(8)

        return glyph_hash

    # Glyph addition, creation -----
    def add_glyph_to_character(self, glyph_hash: str) -> None:
        character = self.active_character
        new_idx = len(character.glyphs)

        glyph = self.glyph_glossary_data[glyph_hash]
        character.glyphs.append(glyph)

        character.glyph_extents.append(((0.0,0.0),(1.0,1.0)))
        self.active_hierarchy_idx = ("glyph", new_idx)
        self.active_glyph_hash = glyph_hash
        self.active_glyph_stroke_idx = 0
        self.refresh("glyphs")

    def create_glyph_for_character(self) -> str:
        glyph_hash = self._new_glyph_hash()
        self.glyph_glossary_data[glyph_hash] = Glyph([BrushStroke([(0.5,0.0),(0.5,1.0)])])
        self.add_glyph_to_character(glyph_hash)
        return glyph_hash

    # Subcharacter addition -----
    def add_subcharacter_to_character(self, character_hash: str) -> None:
        character = self.active_character
        new_idx = len(character.subcharacters)

        subcharacter = self.character_glossary_data[character_hash]
        character.subcharacters.append(subcharacter)

        character.subcharacter_extents.append(((0.0,0.0),(1.0,1.0)))
        self.active_hierarchy_idx = ("subcharacter", new_idx)
        self.refresh("glyphs")

    # Active component removal ---
    def remove_active_component_from_character(self) -> None:
        if self.active_hierarchy_idx is None:
            return
        character = self.active_character
        ac_type, ac_idx = self.active_hierarchy_idx

        if ac_type == "glyph":
            character.glyphs.pop(ac_idx)
            character.glyph_extents.pop(ac_idx)
            if len(character.glyphs) > 0:
                self.active_hierarchy_idx = ("glyph", min(ac_idx, len(character.glyphs) - 1))
            elif len(character.subcharacters):
                self.active_hierarchy_idx = ("subcharacter", min(ac_idx, len(character.subcharacters) - 1))
            else:
                print("Character has no Glyphs or Subcharacters!")
                self.active_hierarchy_idx = None
        else:
            character.subcharacters.pop(ac_idx)
            character.subcharacter_extents.pop(ac_idx)
            if len(character.subcharacters):
                self.active_hierarchy_idx = ("subcharacter", min(ac_idx, len(character.subcharacters) - 1))
            elif len(character.glyphs) > 0:
                self.active_hierarchy_idx = ("glyph", min(ac_idx, len(character.glyphs) - 1))
            else:
                print("Character has no Glyphs or Subcharacters!")
                self.active_hierarchy_idx = None

        self.refresh("glyphs")

    def add_stroke_point(self, point: tuple[float, float]) -> None:
        strokes = self.active_glyph_strokes
        if self.active_glyph_stroke_idx == len(strokes):
            strokes.append(BrushStroke([point]))
        else:
            stroke = strokes[self.active_glyph_stroke_idx]
            strokes[self.active_glyph_stroke_idx] = BrushStroke(
                stroke.control_points + [point],
                profile=stroke.profile,
            )
        self.refresh("stroke")

    def remove_stroke_point(self, point: tuple[float, float]) -> None:
        strokes = self.active_glyph_strokes
        if self.active_glyph_stroke_idx >= len(strokes):
            return

        stroke = strokes[self.active_glyph_stroke_idx]
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
            strokes[self.active_glyph_stroke_idx] = BrushStroke(
                points,
                profile=stroke.profile,
            )
        else:
            strokes.pop(self.active_glyph_stroke_idx)
            self.active_glyph_stroke_idx = min(self.active_glyph_stroke_idx, len(strokes))
        self.refresh("stroke")

    def remove_active_stroke(self) -> None:
        strokes = self.active_glyph_strokes
        if len(strokes) <= 1:
            raise ValueError("A glyph must contain at least one stroke.")
        if self.active_glyph_stroke_idx < len(strokes):
            strokes.pop(self.active_glyph_stroke_idx)
            self.active_glyph_stroke_idx = min(self.active_glyph_stroke_idx, len(strokes) - 1)
            self.refresh("stroke")

    def select_glyph(self, idx: int, stroke_idx: int | None = None) -> None:
        if not 0 <= idx < len(self.active_character.glyphs):
            raise IndexError(f"{idx} is not a valid glyph index.")
        glyph = self.active_character.glyphs[idx]
        strokes = glyph.strokes
        selected_stroke_idx = 0 if stroke_idx is None else stroke_idx
        if not 0 <= selected_stroke_idx <= len(strokes):
            raise IndexError(f"{selected_stroke_idx} is not a valid stroke index.")
        self.active_hierarchy_idx = ("glyph", idx)
        self.active_glyph_hash = next(
            (
                glyph_hash
                for glyph_hash, candidate in self.glyph_glossary_data.items()
                if candidate is glyph
            ),
            None,
        )
        self.active_glyph_stroke_idx = selected_stroke_idx
        self.refresh("stroke" if stroke_idx is not None else "glyph-selection")

    def select_glyph_by_hash(self, glyph_hash: str) -> None:
        if glyph_hash not in self.glyph_glossary_data:
            raise KeyError(f"{glyph_hash} is not a valid glyph hash.")
        self.active_glyph_hash = glyph_hash
        self.active_glyph_stroke_idx = 0
        self.refresh("glyph-selection")

    def select_subcharacter(self, idx: int) -> None:
        if not 0 <= idx < len(self.active_character.subcharacters):
            raise IndexError(f"{idx} is not a valid subcharacter index.")
        self.active_hierarchy_idx = ("subcharacter", idx)
        self.refresh("glyph-selection")

    def select_stroke(self, idx: int) -> None:
        if not 0 <= idx <= len(self.active_glyph_strokes):
            raise IndexError(f"{idx} is not a valid stroke index.")
        self.active_glyph_stroke_idx = idx
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
        if len(character.glyphs) > 0:
            self.active_hierarchy_idx = ("glyph", 0)
        elif len(character.subcharacters) > 0:
            self.active_hierarchy_idx = ("subcharacter", 0)
        else:
            print("Character has no Glyph or Subcharacter data!")
            self.active_hierarchy_idx = None
        self.active_definitions_vars: list[tuple[tk.StringVar,tk.StringVar]]=[
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
        item.definition = [(t.get(), d.get()) for t,d in self.active_definitions_vars]