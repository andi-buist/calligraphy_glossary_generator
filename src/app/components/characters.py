import tkinter as tk
from tkinter import ttk
import typing
from PIL import Image, ImageDraw, ImageTk
from threading import Thread

from src.symbols.characters import Character, CHARACTER_TYPES, glyph_similarity
from src.symbols.strokes import CurveProfile, BrushStroke, StrokeCollection
from src.symbols.radicals import get_largest_rectangular_area
from src.app.components.session import CharacterEditorSession

class CharacterDefinitions(tk.Frame):
    def __init__(self, parent, session: CharacterEditorSession):
        super().__init__(parent)
        self.session: CharacterEditorSession=session
        self.columnconfigure(0, weight=1)

        remove_character_button=tk.Button(self, text="Remove Character", command=lambda hash=self.session.character_hash: self.session.remove_character(hash))
        remove_character_button.pack(fill="x", side="bottom")

        self.entries_frame = tk.Frame(self)
        self.entries_frame.columnconfigure(0, weight=1)
        self.entries_frame.columnconfigure(1, weight=3)
        self.entries_frame.columnconfigure(2, weight=3)

        character_defs_increase=tk.Button(self, command=self.add_character_def, text="+")
        character_defs_increase.pack(fill="x")
        self.entries_frame.pack(fill="both", expand=True)

        self.refresh()

    def refresh(self):
        for child in self.entries_frame.winfo_children():
            child.destroy()

        for idx in range(len(self.session.character_defs_vars)):
            tk.Label(self.entries_frame, text=f"Def {idx}:").grid(column=0, row=idx)
            entry_type_field=tk.OptionMenu(
                self.entries_frame,
                self.session.character_defs_vars[idx][0],
                *typing.get_args(CHARACTER_TYPES)
                )
            entry_type_field.grid(column=1, row=idx, sticky="EW")
            entry_def_field=ttk.Entry(self.entries_frame, textvariable=self.session.character_defs_vars[idx][1])
            entry_def_field.bind("<Return>", self.session.update_treeview)
            entry_def_field.grid(column=2, row=idx, sticky="EW")

            if idx > 0:
                remove_def_button=tk.Button(self.entries_frame, text="-", command=lambda idx=idx: self.remove_character_def(idx))
                remove_def_button.grid(column=3, row=idx)

    def add_character_def(self):
        type_var=tk.StringVar(self.session.master, value=self.session.character_defs_vars[-1][0].get())
        definition_var=tk.StringVar(self.session.master, value="")
        self.session.character_defs_vars.append((type_var, definition_var))

        self.session.commit_active_character_to_memory()
        self.session.refresh("metadata")
        self.refresh()

    def remove_character_def(self, idx: int):
        _=self.session.character_defs_vars.pop(idx)

        self.session.commit_active_character_to_memory()
        self.session.refresh("metadata")
        self.refresh()

class CharacterPreview(tk.Frame):
    def __init__(self, parent, session: CharacterEditorSession):
        self.session = session
        
        self.character_object_cache: tuple[Character, ImageTk.PhotoImage] = None # must cache the photoimage too, as otherwise it gets GC'd

        super().__init__(parent)
        self.columnconfigure(0, weight=1)

        self.refresh()

    def refresh(self):
        for child in self.winfo_children():
            child.destroy()

        self.refresh_active_character_image_cache()

        tk.Label(self, text="Rendered Glyph").grid(column=0, row=0, sticky="NEW")
        image_label=tk.Label(
            self,
            image=self.character_object_cache[1],
            highlightthickness=1,
            highlightbackground="black",
        )
        image_label.grid(column=0, row=1)

        self.similarity_score_label=tk.Label(self, text="")
        self.similarity_score_label.grid(column=0, row=2)
        t=Thread(target=self.get_similarity_scores, daemon=True)
        t.start()

    def refresh_active_character_image_cache(self):
        """
        Sets `self.character_object_cache` to the `Character` object and `ImageTk.PhotoImage`, built from `self.character_stroke_control_points`.
        """
        def internal_build_char() -> Character:
            strokes=[]
            for idx, control_points in enumerate(self.session.character_stroke_control_points):
                if len(control_points) > 1:
                    scaled_control_points=self.session._get_normalized_stroke_control_points(idx)
                    strokes.append(BrushStroke(control_points=scaled_control_points,
                                                profile=CurveProfile(control_points=self.session.character_stroke_profile_control_points[idx],
                                                                    bounds=tuple(float(var.get()) for var in self.session.character_stroke_profile_bounds_vars[idx]))))

            return Character(definition=[(x.get(),y.get()) for x,y in self.session.character_defs_vars],
                             strokes=strokes)

        def generate_preview_image(character: Character) -> ImageTk.PhotoImage:
            glyph = character.glyph
            (rect_area), _ = get_largest_rectangular_area(character.glyph)

            draw=ImageDraw.Draw(glyph, "RGBA")
            draw.rectangle(rect_area, fill="#ff000033", outline="#ff0000")

            return ImageTk.PhotoImage(glyph)


        if len(self.session.character_stroke_control_points) > 0:
            sub_lengths_check=[len(el) > 1 for el in self.session.character_stroke_control_points]
            if any(sub_lengths_check):
                character=internal_build_char()
                self.character_object_cache=(character, generate_preview_image(character))
            else:
                self.character_object_cache=None
        else:
            self.character_object_cache=None

    def get_similarity_scores(self):
        this_char = self.session.json_to_character(self.session.character_glossary_data[self.session.character_hash])
        other_chars = {hash: self.session.json_to_character(el) for hash,el in self.session.character_glossary_data.items() if hash != self.session.character_hash}

        result={hash: glyph_similarity(this_char, other_char) for hash,other_char in other_chars.items()}
        top_score_hash=sorted(result, key=result.get, reverse=True)[0]

        if result.get(top_score_hash) > 0.80:
            self.similarity_score_label.config(text=f"Similar character found:\n{top_score_hash}: {100 * result.get(top_score_hash):.1f}%")