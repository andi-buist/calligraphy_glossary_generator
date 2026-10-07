from PIL import Image
from typing import Literal
import copy
import numpy as np

from src.symbols import brushstrokes

GLYPH_SIZE = brushstrokes.GLYPH_SIZE
CHARACTER_TYPES = Literal["noun", "verb", "adjective", "adverb", "pronoun", "preposition", "conjunction", "number", "letter", "symbol"]

class Character:
    def __init__(self,
                 character_type: CHARACTER_TYPES,
                 definition: any,
                 strokes: brushstrokes.StrokeCollection):
        self.strokes = [strokes] if isinstance(strokes, brushstrokes.BrushStroke) else strokes
        self.glyph = self.generate_glyph()
        self.glyph_orientation: Literal["horizontal", "vertical"] = self._get_glyph_orientation()
        self.character_type = character_type
        self.definition = definition

    def clone(self):
        clone = type(self).__new__(type(self))
        clone.character_type = self.character_type
        clone.definition = self.definition
        clone.strokes = copy.deepcopy(self.strokes)
        clone.glyph = clone.generate_glyph()
        clone.glyph_orientation = clone._get_glyph_orientation()
        return clone

    def generate_glyph(self) -> Image.Image:
        """Draw a glyph image from the character strokes."""
        active_canvas = Image.new(mode="RGBA", size=(GLYPH_SIZE, GLYPH_SIZE), color=(255, 255, 255, 255))

        for stroke in brushstrokes.flatten_nested_brushstrokes(self.strokes):
            active_canvas = stroke.draw(active_canvas)

        return active_canvas

    def _get_glyph_orientation(self):
        hv_score = 0
        for stroke_bbox in [np.asarray(stroke.bbox) for stroke in brushstrokes.flatten_nested_brushstrokes(self.strokes)]:
            bbox_range = (stroke_bbox[:, 0].max() - stroke_bbox[:, 0].min(),
                          stroke_bbox[:, 1].max() - stroke_bbox[:, 1].min())
            if bbox_range[0] > bbox_range[1]:
                hv_score -= bbox_range[0].max()
            else:
                hv_score += bbox_range[1].max()
        return "horizontal" if hv_score < 0 else "vertical"