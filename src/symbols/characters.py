from PIL import Image
from typing import Literal
import copy
import numpy as np

from src.symbols.strokes import BrushStroke, BrushStrokeGroup, StrokeCollection, flatten_nested_brushstrokes, GLYPH_SIZE

CHARACTER_TYPES = Literal["noun", 
                          "verb", 
                          "adjective", 
                          "adverb", 
                          "pronoun", 
                          "preposition", 
                          "determiner", 
                          "interrogative", 
                          "conjunction", 
                          "number", 
                          "letter", 
                          "symbol"]

class Character:
    def __init__(self,
                 definition: list[tuple[CHARACTER_TYPES, str]],
                 strokes: StrokeCollection):
        self.strokes = [strokes] if isinstance(strokes, BrushStroke) else strokes
        self.glyph = self.generate_glyph()
        self.definition = definition

    def clone(self):
        clone = type(self).__new__(type(self))
        clone.definition = copy.deepcopy(self.definition)
        clone.strokes = copy.deepcopy(self.strokes)
        clone.glyph = clone.generate_glyph()
        return clone

    def generate_glyph(self) -> Image.Image:
        """Draw a glyph image from the character strokes."""
        active_canvas = Image.new(mode="RGBA", size=(GLYPH_SIZE, GLYPH_SIZE), color=(255, 255, 255, 255))

        for stroke in flatten_nested_brushstrokes(self.strokes):
            active_canvas = stroke.draw(active_canvas)

        return active_canvas

class CompoundCharacter(Character):
    def __init__(self, character_type: CHARACTER_TYPES, definition: any, parent: Character, child: Character):
        self.character_type = character_type
        self.definition = definition

        self.parent: Character = parent.clone()
        self.child: Character = child.clone()

    def generate_glyph(self):
        pass
        # 1. get parent empty region
        
        # 2. scale child coords to that empty region
        # 3. combine BrushStroke lists of parent and child, assign to self.strokes
        # 4. run generate_glyph()
        pass

def glyph_orientation(character: Character) -> Literal["horizontal", "vertical"]:
    hv_score = 0
    for stroke_bbox in [np.asarray(stroke.bbox) for stroke in flatten_nested_brushstrokes(character.strokes)]:
        bbox_range = (stroke_bbox[:, 0].max() - stroke_bbox[:, 0].min(),
                        stroke_bbox[:, 1].max() - stroke_bbox[:, 1].min())
        if bbox_range[0] > bbox_range[1]:
            hv_score -= bbox_range[0].max()
        else:
            hv_score += bbox_range[1].max()
    return "horizontal" if hv_score < 0 else "vertical"

def glyph_similarity(a: Character, b: Character) -> float:
    i0, i1 = (np.asarray(1.0 - (np.asarray(el.glyph.convert("L"), dtype=float)/ 255.0), int) for el in (a,b))
    return np.sum(np.bitwise_and(i0 == 1, i1 == 1)) / max(np.sum(i0 == 1),np.sum(i1 == 1))

def glyph_similarity_matrix(characters: list[Character]):
    scores=np.ndarray((len(characters),) * 2, dtype=float)
    for idx0, char0 in enumerate(characters):
        for idx1, char1 in enumerate(characters):
            scores[idx0][idx1] = glyph_similarity(char0, char1)
    return np.triu(scores, 1) # upper tri, remove diagonal (self-self)