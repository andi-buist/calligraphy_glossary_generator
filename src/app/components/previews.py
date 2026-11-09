import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageDraw, ImageTk

from src.symbols.characters import Character, glyph_similarity
from src.symbols.radicals import get_largest_rectangular_area
from src.app.components.session import AppSession

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


        character=self.session.active_character
        self.character_object_cache=(character, generate_preview_image(character))

    def get_similarity_scores(self):
        this_char = self.session.active_character
        other_chars = {hash: el for hash,el in self.session.character_glossary_data.items() if hash != self.session.active_character_hash}

        result={hash: glyph_similarity(this_char, other_char) for hash,other_char in other_chars.items()}
        top_score_hash=sorted(result, key=result.get, reverse=True)[0]

        if result.get(top_score_hash) > 0.80:
            self.similarity_score_label.config(text=f"Similar character found:\n{top_score_hash}: {100 * result.get(top_score_hash):.1f}%")


class GlyphPreview(tk.Frame):
    def __init__(self, parent, session: AppSession):
        self.session = session
        self.glyph_image: ImageTk.PhotoImage | None = None

        super().__init__(parent)
        self.columnconfigure(0, weight=1)
        ttk.Label(
            self,
            text="Rendered Glyph",
            anchor="center",
        ).grid(column=0, row=0, sticky="EW")
        self.image_label=tk.Label(
            self,
            image="",
            highlightthickness=1,
            highlightbackground="black",
        )
        self.image_label.grid(column=0, row=1)
        self.refresh()

    def refresh(self):
        glyph = self.session.active_glyph
        if glyph is None:
            self.glyph_image = None
            self.image_label.configure(image="")
            return

        self.glyph_image = ImageTk.PhotoImage(
            glyph.draw(),
            master=self,
        )
        self.image_label.configure(image=self.glyph_image)