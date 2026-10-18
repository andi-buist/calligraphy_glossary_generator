from __future__ import annotations

from PIL import Image
from typing import Literal
import copy
import numpy as np

from src.symbols.strokes import BrushStroke, GLYPH_SIZE

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

def add_glyph_constants(cls):
    cls.DEFAULT = cls(strokes = [BrushStroke([(0.5,0.0),(0.5,1.0)])])
    return cls

@add_glyph_constants
class Glyph:
    def __init__(self,
                 strokes: list[BrushStroke],
                 detail: str | None = None):
        self.strokes = [strokes] if isinstance(strokes, BrushStroke) else strokes
        self.detail = detail

    def draw(self, 
             extent: tuple[tuple[float,float], tuple[float,float]] = ((0.0,0.0),(1.0,1.0)), 
             size: tuple[int, int] = (GLYPH_SIZE, GLYPH_SIZE)) -> Image.Image:
        """Draw a glyph image from the character strokes."""
        width, height = size
        subwidth = extent[1][0] - extent[0][0]
        subheight = extent[1][1] - extent[0][1]

        glyph_canvas = Image.new(mode="RGBA", size=(int(width * subwidth), int(height * subheight)), color=(255, 255, 255, 0))

        for stroke in self.strokes:
            glyph_canvas = stroke.draw(glyph_canvas)

        return glyph_canvas

class Character:
    def __init__(self,
                 definition: list[tuple[CHARACTER_TYPES, str]],
                 glyphs: list[Glyph]=[],
                 glyph_extents: list[tuple[tuple[float,float], tuple[float,float]]]=[],
                 subcharacters: list[Character]=[],
                 subcharacter_extents: list[tuple[tuple[float,float], tuple[float,float]]]=[]):
        self.definition = definition
        self.glyphs = glyphs
        self.glyph_extents = glyph_extents
        self.subcharacters = subcharacters
        self.subcharacter_extents = subcharacter_extents

    def clone(self):
        clone = type(self).__new__(type(self))
        clone.definition = copy.deepcopy(self.definition)
        clone.glyphs = self.glyphs.copy()
        clone.glyph_extents = copy.deepcopy(self.glyph_extents)
        return clone

    def draw(self, 
             extent: tuple[tuple[float,float], tuple[float,float]] = ((0.0,0.0),(1.0,1.0)), 
             size: tuple[int, int] = (GLYPH_SIZE, GLYPH_SIZE)) -> Image.Image:
        """Draw a glyph image from the character strokes."""
        width, height = size

        subwidth = extent[1][0] - extent[0][0]
        subheight = extent[1][1] - extent[0][1]

        character_canvas = Image.new(mode="RGBA", size=(int(width * subwidth), int(height * subheight)), color=(255, 255, 255, 255))

        if len(self.glyphs) > 0:
            if self.glyph_extents is None:
                _glyph_extents = [((0.0,0.0),(1.0,1.0))] * len(self.glyphs)
            else:
                _glyph_extents = self.glyph_extents

            for glyph, glyph_extent in zip(self.glyphs, _glyph_extents):
                glyph_canvas = glyph.draw(extent = glyph_extent, size=(int(width * subwidth), int(height * subheight)))
                character_canvas.alpha_composite(
                    glyph_canvas,
                    dest=(
                        int(width * glyph_extent[0][0]),
                        int(height * glyph_extent[0][1]),
                    ),
                )

        if len(self.subcharacters) > 0:
            if self.subcharacter_extents is None:
                _subcharacter_extents = [((0.0,0.0),(1.0,1.0))] * len(self.subcharacters)
            else:
                _subcharacter_extents = self.subcharacter_extents

            for subcharacter, subcharacter_extent in zip(self.subcharacters, _subcharacter_extents):
                subcharacter_canvas = subcharacter.draw(extent = subcharacter_extent)
                character_canvas.alpha_composite(
                    subcharacter_canvas,
                    dest=(
                        int(width * subcharacter_extent[0][0]),
                        int(height * subcharacter_extent[0][1]),
                    ),
                )

        if len(self.subcharacters) > 0:
            if self.subcharacter_extents is None:
                _subcharacter_extents = [((0.0,0.0),(1.0,1.0))] * len(self.subcharacters)
            else:
                _subcharacter_extents = self.subcharacter_extents

            for glyph, glyph_extent in zip(self.glyphs, _glyph_extents):
                glyph_canvas = glyph.draw(extent = glyph_extent)
                character_canvas.alpha_composite(
                    glyph_canvas,
                    dest=(
                        int(width * glyph_extent[0][0]),
                        int(height * glyph_extent[0][1]),
                    ),
                )

        return character_canvas

def glyph_orientation(character: Character) -> Literal["horizontal", "vertical"]:
    hv_score = 0
    for stroke_bbox in [np.asarray(stroke.bbox) for stroke in character.strokes]:
        bbox_range = (stroke_bbox[:, 0].max() - stroke_bbox[:, 0].min(),
                        stroke_bbox[:, 1].max() - stroke_bbox[:, 1].min())
        if bbox_range[0] > bbox_range[1]:
            hv_score -= bbox_range[0].max()
        else:
            hv_score += bbox_range[1].max()
    return "horizontal" if hv_score < 0 else "vertical"

def glyph_similarity(a: Character, b: Character) -> float:
    i0, i1 = (np.asarray(1.0 - (np.asarray(el.draw().convert("L"), dtype=float)/ 255.0), int) for el in (a,b))
    return np.sum(np.bitwise_and(i0 == 1, i1 == 1)) / max(np.sum(i0 == 1),np.sum(i1 == 1))

def glyph_similarity_matrix(characters: list[Character]):
    scores=np.ndarray((len(characters),) * 2, dtype=float)
    for idx0, char0 in enumerate(characters):
        for idx1, char1 in enumerate(characters):
            scores[idx0][idx1] = glyph_similarity(char0, char1)
    return np.triu(scores, 1) # upper tri, remove diagonal (self-self)