import tkinter as tk
from tkinter import ttk
import typing
from PIL import Image, ImageDraw, ImageTk
from threading import Thread

from src.symbols.characters import Character, CHARACTER_TYPES, glyph_similarity
from src.symbols.radicals import get_largest_rectangular_area
from src.app.components.session import AppSession

class CharacterDefinitions(tk.Frame):
    def __init__(self, parent, session: AppSession):
        super().__init__(parent)
        self.session: AppSession=session
        self.columnconfigure(0, weight=1)

        self.remove_character_button = tk.Button(
            self,
            text="Remove Character",
            command=self.remove_active_character,
        )
        self.remove_character_button.pack(fill="x", side="bottom")

        self.entries_frame = tk.Frame(self)
        self.entries_frame.columnconfigure(0, weight=1)
        self.entries_frame.columnconfigure(1, weight=3)
        self.entries_frame.columnconfigure(2, weight=3)

        character_defs_increase=tk.Button(self, command=self.add_character_def, text="+")
        character_defs_increase.pack(fill="x")
        self.entries_frame.pack(fill="both", expand=True)

        self.refresh()

    def remove_active_character(self):
        self.session.remove_character(self.session.active_character_hash)

    def refresh(self):
        for child in self.entries_frame.winfo_children():
            child.destroy()

        for idx in range(len(self.session.active_character_defs_vars)):
            tk.Label(self.entries_frame, text=f"Def {idx}:").grid(column=0, row=idx)
            entry_type_field=tk.OptionMenu(
                self.entries_frame,
                self.session.active_character_defs_vars[idx][0],
                *typing.get_args(CHARACTER_TYPES)
                )
            entry_type_field.grid(column=1, row=idx, sticky="EW")
            entry_def_field=ttk.Entry(self.entries_frame, textvariable=self.session.active_character_defs_vars[idx][1])
            entry_def_field.bind("<Return>", self.session.update_treeview)
            entry_def_field.bind("<FocusOut>", self.session.update_treeview)
            entry_def_field.grid(column=2, row=idx, sticky="EW")

            if idx > 0:
                remove_def_button=tk.Button(self.entries_frame, text="-", command=lambda idx=idx: self.remove_character_def(idx))
                remove_def_button.grid(column=3, row=idx)

    def add_character_def(self):
        type_var=tk.StringVar(self.session.master, value=self.session.active_character_defs_vars[-1][0].get())
        definition_var=tk.StringVar(self.session.master, value="")
        self.session.active_character_defs_vars.append((type_var, definition_var))

        self.session.commit_active_character_to_memory()
        self.session.refresh("metadata")
        self.refresh()

    def remove_character_def(self, idx: int):
        _=self.session.active_character_defs_vars.pop(idx)

        self.session.commit_active_character_to_memory()
        self.session.refresh("metadata")
        self.refresh()

class CharacterPreview(tk.Frame):
    def __init__(self, parent, session: AppSession):
        self.session = session
        
        self.character_object_cache: tuple[Character, ImageTk.PhotoImage] = None # must cache the photoimage too, as otherwise it gets GC'd

        super().__init__(parent)
        self.columnconfigure(0, weight=1)

        tk.Label(self, text="Rendered Character").grid(column=0, row=0, sticky="NEW")
        self.image_label=tk.Label(
            self,
            image="",
            highlightthickness=1,
            highlightbackground="black",
        )
        self.image_label.grid(column=0, row=1)

        # self.similarity_score_label=tk.Label(self, text="")
        # self.similarity_score_label.grid(column=0, row=2)

        self.refresh()

    def refresh(self):
        self.refresh_active_character_image_cache()

        if self.character_object_cache is not None:
            self.image_label.config(image=self.character_object_cache[1])

            # t=Thread(target=self.get_similarity_scores, daemon=True)
            # t.start()

    def refresh_active_character_image_cache(self):
        """
        Cache the active Character and its rendered preview image.
        """
        def generate_preview_image(character: Character) -> ImageTk.PhotoImage:
            glyph = character.draw()
            (rect_area), _ = get_largest_rectangular_area(glyph)

            draw=ImageDraw.Draw(glyph, "RGBA")
            draw.rectangle(rect_area, fill="#ff000033", outline="#ff0000")

            return ImageTk.PhotoImage(glyph)


        character=self.session.character_glossary_data[self.session.active_character_hash]
        self.character_object_cache=(character, generate_preview_image(character))

    def get_similarity_scores(self):
        this_char = self.session.character_glossary_data[self.session.active_character_hash]
        other_chars = {hash: el for hash,el in self.session.character_glossary_data.items() if hash != self.session.active_character_hash}

        result={hash: glyph_similarity(this_char, other_char) for hash,other_char in other_chars.items()}
        top_score_hash=sorted(result, key=result.get, reverse=True)[0]

        if result.get(top_score_hash) > 0.80:
            self.similarity_score_label.config(text=f"Similar character found:\n{top_score_hash}: {100 * result.get(top_score_hash):.1f}%")