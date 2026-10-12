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

class Glyph:
    def __init__(self,
                 strokes: StrokeCollection,
                 extent: tuple[tuple[float,float], tuple[float,float]] = ((0.0,0.0),(1.0,1.0))):
        self.strokes = [strokes] if isinstance(strokes, BrushStroke) else strokes
        self.extent = extent

    def draw(self) -> Image.Image:
        """Draw a glyph image from the character strokes."""
        subwidth = self.extent[1][0] - self.extent[0][0]
        subheight = self.extent[1][1] - self.extent[0][1]
        width, height = (GLYPH_SIZE, GLYPH_SIZE)

        stroke_canvas = Image.new(mode="RGBA", size=(int(width * subwidth), int(height * subheight)), color=(255, 255, 255, 255))
        glyph_canvas = Image.new(mode="RGBA", size=(width, height), color=(255, 255, 255, 255))

        for stroke in flatten_nested_brushstrokes(self.strokes):
            stroke_canvas = stroke.draw(stroke_canvas)

        glyph_canvas.paste(stroke_canvas, (int(width * self.extent[0][0]), int(height * self.extent[0][1])))
        return glyph_canvas

class Character:
    def __init__(self,
                 definition: list[tuple[CHARACTER_TYPES, str]],
                 glyphs: list[Glyph]):
        self.definition = definition
        self.glyphs = glyphs

    def clone(self):
        clone = type(self).__new__(type(self))
        clone.definition = copy.deepcopy(self.definition)
        clone.glyphs = copy.deepcopy(self.glyphs)
        return clone

    def draw(self) -> Image.Image:
        """Draw a glyph image from the character strokes."""
        character_canvas = Image.new(mode="RGBA", size=(GLYPH_SIZE, GLYPH_SIZE), color=(255, 255, 255, 255))

        for glyph in self.glyphs:
            glyph_canvas = glyph.draw()
            character_canvas.paste(glyph_canvas)

        return character_canvas

# TODO: cleanup
class CompoundCharacter(Character):
    def __init__(self,
                 characters: tuple[Character, Character],
                 placement: Literal["LEFT-RIGHT", "RIGHT-LEFT", "TOP-BOTTOM", "BOTTOM-TOP"]):
        self.characters:tuple[Character,Character]=characters
        self.placement:str=placement
        self.glyph = self.generate_glyph()

    def generate_glyph(self) -> Image.Image:
        """Draw a glyph image by combining the source characters."""
        def draw_character(character: Character, canvas: Image, fill_extent:bool=True):
            strokes=flatten_nested_brushstrokes(character.strokes)

            if strokes is not None and fill_extent:
                scaled_strokes: list[BrushStroke]=[]
                min_x = min(stroke.bbox[0][0] for stroke in strokes)
                min_y = min(stroke.bbox[0][1] for stroke in strokes)
                max_x = max(stroke.bbox[1][0] for stroke in strokes)
                max_y = max(stroke.bbox[1][1] for stroke in strokes)
                width = max_x - min_x
                height = max_y - min_y

                def scale_point(point: tuple[float, float]) -> tuple[float, float]:
                    x = (point[0] - min_x) / width if width else 0.5
                    y = (point[1] - min_y) / height if height else 0.5
                    return x, y

                for stroke in strokes:
                    scaled_stroke = copy.copy(stroke)
                    scaled_stroke.control_points = [
                        scale_point(point) for point in stroke.control_points
                    ]
                    scaled_stroke.spline_path_points = [
                        scale_point(point) for point in stroke.spline_path_points
                    ]
                    scale_min = scale_point(stroke.bbox[0])
                    scale_max = scale_point(stroke.bbox[1])
                    scaled_stroke.bbox = (
                        scale_min,
                        scale_max,
                    )
                    scaled_strokes.append(scaled_stroke)
            else:
                scaled_strokes=strokes

            for stroke in scaled_strokes:
                canvas = stroke.draw(canvas)

            return canvas

        match self.placement:
            case "LEFT-RIGHT" | "RIGHT-LEFT":
                canvas0 = Image.new(mode="RGBA", size=(GLYPH_SIZE //2, GLYPH_SIZE), color=(255, 255, 255, 255))
                canvas1 = Image.new(mode="RGBA", size=(GLYPH_SIZE //2, GLYPH_SIZE), color=(255, 255, 255, 255))
            case "TOP-BOTTOM" | "BOTTOM-TOP":
                canvas0 = Image.new(mode="RGBA", size=(GLYPH_SIZE, GLYPH_SIZE // 2), color=(255, 255, 255, 255))
                canvas1 = Image.new(mode="RGBA", size=(GLYPH_SIZE, GLYPH_SIZE // 2), color=(255, 255, 255, 255))

        canvas0 = draw_character(self.characters[0], canvas0)
        canvas1 = draw_character(self.characters[1], canvas1)

        output_img = Image.new(mode="RGBA", size=(GLYPH_SIZE, GLYPH_SIZE), color=(255, 255, 255, 255))

        match self.placement:
            case "LEFT-RIGHT" | "RIGHT-LEFT":
                output_img.paste(canvas0, (0,0))
                output_img.paste(canvas1, (GLYPH_SIZE // 2,0))
            case "TOP-BOTTOM" | "BOTTOM-TOP":
                output_img.paste(canvas0, (0,0))
                output_img.paste(canvas1, (0,GLYPH_SIZE // 2))

        return output_img

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
    i0, i1 = (np.asarray(1.0 - (np.asarray(el.draw().convert("L"), dtype=float)/ 255.0), int) for el in (a,b))
    return np.sum(np.bitwise_and(i0 == 1, i1 == 1)) / max(np.sum(i0 == 1),np.sum(i1 == 1))

def glyph_similarity_matrix(characters: list[Character]):
    scores=np.ndarray((len(characters),) * 2, dtype=float)
    for idx0, char0 in enumerate(characters):
        for idx1, char1 in enumerate(characters):
            scores[idx0][idx1] = glyph_similarity(char0, char1)
    return np.triu(scores, 1) # upper tri, remove diagonal (self-self)