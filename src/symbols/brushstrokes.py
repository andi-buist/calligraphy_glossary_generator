from __future__ import annotations

from PIL import Image, ImageDraw
from typing import Literal
import math
import numpy as np

from src.symbols.utils import splines 

GLYPH_SIZE = 128
STROKE_THICKNESS = 4.0
GLYPH_MARGIN = 0.1

def add_thickness_profile_constants(cls):
    cls.LINEAR = cls(control_points=[(0.0,0.0),(1.0,1.0)], bounds=(0.0,1.0))
    cls.REALISTIC = cls(control_points=[(0.0,0.0),(0.35,0.05),(0.6,1.0),(0.95,0.7),(1.0,0.5)], bounds=(1.0,4.0))
    return cls

@add_thickness_profile_constants
class CurveProfile():
    """
    A Bezier curve used to map x -> y to alter the thickness along the length of a `BrushStroke`
    """
    def __init__(self, control_points: list[tuple[float,float]], bounds: tuple[float,float]):
        self.control_points: list[tuple[float,float]] = control_points
        self.profile: list[tuple[float,float]] = self.get_profile()
        self.bounds = bounds

    def copy(self):
        return CurveProfile(control_points=self.control_points.copy(),
                            bounds=self.bounds)

    def get_profile(self) -> list[tuple[float,float]]:
        tmp_profile = splines.get_bezier_path_points(self.control_points)
        _, y = list(map(list, zip(*tmp_profile)))
        ymin, ymax = (min(y), max(y))
        tmp_profile = [(x, ((y - ymin)/(ymax - ymin))) for x,y in tmp_profile]

        return tmp_profile

    def map(self, x: float):
        """
        x -> y from the profile curve
        """
        pmx, pmy = list(map(list, zip(*self.profile)))
        key_distances = [abs(xx - x) for xx in pmx]
        return self.bounds[0] + (pmy[key_distances.index(min(key_distances))] * (self.bounds[1] - self.bounds[0]))

def add_brushstroke_constants(cls):
    # horizontal and vertical lines at specified x/y
    HOR = [(0.0, 0.0), (1.0, 0.0)]
    VER = [(0.0, 0.0), (0.0, 1.0)]

    offsets = [0.2, 0.4, 0.6, 0.8]
    for offset in offsets:
        hor_path = [(x, y + offset) for (x,y) in HOR]
        ver_path = [(x + offset, y) for (x,y) in VER]

        hor_constant_name = f"HOR_0{int(offset * 10)}"
        ver_constant_name = f"VER_0{int(offset * 10)}"

        setattr(cls, hor_constant_name, cls(control_points = hor_path))
        setattr(cls, ver_constant_name, cls(control_points = ver_path))

    # basic named horizontal and vertical lines
    cls.TOP = cls(control_points = HOR)
    cls.HOR_CENTRE = cls(control_points=[(0.0, 0.5), (1.0, 0.5)])
    cls.BOTTOM = cls(control_points=[(0.0, 1.0), (1.0, 1.0)])

    cls.LEFT = cls(control_points = VER)
    cls.VER_CENTRE = cls(control_points=[(0.5, 0.0), (0.5, 1.0)])
    cls.RIGHT = cls(control_points=[(1.0, 0.0), (1.0, 1.0)])

    # common basic shaped strokes
    cls.LEG_LEFT = cls(control_points=[(0.1, 0.0), (0.1, 0.7), (0.0, 1.0)], weight = 2)
    cls.LEG_CENTRE = cls(control_points=[(0.5,0.0),(0.5,0.7),(0.6,1.0)])
    cls.RISER_TOP_CENTRE = cls(control_points=[(0.7,0.0),(0.3,0.1)])
    cls.RISER_CENTRE_CENTRE = cls(control_points=[(0.7,0.5),(0.3,0.6)])
    cls.LOOP_RIGHT = cls(control_points=[(0.7,0.0),(0.7,1.0),(0.2,1.0),(0.2,0.5),(1.0,0.3)])
    cls.LEG_SHORT_CENTRE = cls(control_points=[(0.5,0.6),(0.5,1.0)])
    cls.CURVE_LEFT = cls(control_points=[(0.4,0.0),(1.0,0.0),(1.0,0.5),(1.0,0.8),(0.2,0.9)], weight = 1)
    cls.DESCENDER_TOP_CENTRELEFT = cls(control_points=[(0.55,0.2),(0.45,0.3)])
    cls.DESCENDER_CENTRE_CENTRELEFT = cls(control_points=[(0.55,0.4),(0.45,0.5)])
    cls.DESCENDER_BOTTOM_CENTRERIGHT = cls(control_points=[(0.7,0.7),(0.75,0.9)])
    cls.DESCENDER_TOP_CENTRE = cls(control_points=[(0.75,0.175),(0.9,0.225)])
    cls.HOOK_LEFT = cls(control_points=[(0.7,0.0),(0.7,0.8),(0.2,1.0)], weight = 2)
    cls.CURLYCUE_LEFT = cls(control_points=[(1.0,0.0),(0.2,0.2),(0.2,0.2),(1.0,0.2),(1.0,0.6),(1.0,1.0),(0.5,1.0),(0.0,1.0),(0.2,0.4)], weight = 2)
    cls.ZIGZAG = cls(control_points=[(0.0,0.3),(0.5,0.3),(1.0,0.25),(1.0,0.25),(0.5,0.5),(0.0,0.7),(0.0,0.7),(0.5,0.7),(1.0,0.8)])
    cls.SEVEN = cls(control_points=[(0.3,0.2),(0.3,0.0),(0.3,0.0),(0.7,0.0),(0.7,0.0),(0.7,0.7),(0.8,1.0)])
    cls.ARC_RIGHT = cls(control_points=[(0.5,0.0),(0.0,0.2),(0.0,0.3),(0.0,0.5),(0.5,0.5),(1.0,0.5)], weight = 2)
    cls.V_DOWN = cls(control_points=[(0.0,0.0),(0.5,1.0),(1.0,0.0)], weight = 8)
    cls.V_UP = cls(control_points=[(0.0,1.0),(0.5,0.0),(1.0,1.0)], weight = 8)

    return cls

@add_brushstroke_constants 
class BrushStroke():
    """
    Defines a single brushstroke from a set of Bezier control points, weighting,
    and a profile curve (`CurveProfile`) to use to alter the thickness along 
    the stroke length
    """
    def __init__(self,
                 control_points: list[tuple[float, float]],
                 weight: float = 1.0,
                 profile: CurveProfile | None = None):
        if any(not 0.0 <= value <= 1.0 for point in control_points for value in point):
            raise ValueError('Brush stroke coordinates must be between 0.0 and 1.0')

        self.control_points = control_points
        self.weight = weight
        self.profile = profile if profile is not None else CurveProfile(
            control_points=CurveProfile.REALISTIC.control_points.copy(),
            bounds=CurveProfile.REALISTIC.bounds,
        )
        self.spline_path_points = splines.get_bezier_path_points(control_points, max(1, int(weight)))
        self.bbox = self._get_bbox()

    def _get_bbox(self) -> tuple[tuple[float, float], tuple[float, float]]:
        coord_nparray = np.asarray(self.spline_path_points)
        return ((coord_nparray[:, 0].min(),coord_nparray[:, 1].min()),(coord_nparray[:, 0].max(),coord_nparray[:, 1].max()))

    def scale(self, dir: Literal["l","r","u","d"], scale: float) -> list[tuple[float,float]]:
        bpp = self.spline_path_points
        for idx, coord in enumerate(bpp):
            match dir:
                case "l":
                    bpp[idx] = (coord[0] * scale, coord[1])
                case "r":
                    bpp[idx] = (1.0 - ((1.0 - coord[0]) * scale), coord[1])
                case "u":
                    bpp[idx] = (coord[0], coord[1] * scale)
                case "d":
                    bpp[idx] = (coord[0], 1.0 - ((1.0 - coord[1]) * scale))
            self.bbox = self._get_bbox()
        return bpp

    def draw(self, canvas: Image):
        active_canvas = canvas

        canvas_area = tuple(x * (1 - GLYPH_MARGIN * 2) for x in active_canvas.size)
        canvas_margin = tuple(x * GLYPH_MARGIN for x in active_canvas.size)

        scaled_path_points = []
        for x in self.spline_path_points:
            _pos = tuple(canvas_margin[n] + x[n] * canvas_area[n] for n in [0, 1])
            scaled_path_points.append(_pos)

        draw = ImageDraw.Draw(active_canvas)

        for idx, centre in enumerate(scaled_path_points):
            cur_thickness = self.profile.map(idx / len(scaled_path_points))

            draw.ellipse((centre[0] - cur_thickness,
                        centre[1] - cur_thickness,
                        centre[0] + cur_thickness,
                        centre[1] + cur_thickness),
                        fill=(0,0,0,255))
        return active_canvas

class BrushStrokeGroup(list):
    """
    A helper class to extend the base `list` to specifically contain a parent-child
    `BrushStroke` relationship
    """
    def __init__(
            self,
            parent: BrushStroke,
            children: list[BrushStroke | BrushStrokeGroup] | BrushStrokeGroup,
            *,
            scale_method: Literal["inherit", "combine"] = "inherit"
    ):
        if not isinstance(parent, BrushStroke):
            raise TypeError("BrushStrokeGroup parent must be a BrushStroke")
        if isinstance(children, BrushStrokeGroup):
            children = [children]
        elif not isinstance(children, list):
            raise TypeError("BrushStrokeGroup children must be a list or BrushStrokeGroup")
        if any(not isinstance(child, (BrushStroke, BrushStrokeGroup)) for child in children):
            raise TypeError("BrushStrokeGroup children must be BrushStroke or BrushStrokeGroup objects")
        if scale_method not in ("inherit", "combine"):
            raise ValueError("scale_method must be 'inherit' or 'combine'")

        super().__init__([parent, *children])
        self.scale_method = scale_method


StrokeCollection = BrushStroke | BrushStrokeGroup | list[BrushStroke | BrushStrokeGroup]

def map_unit_coords_to_margined_canvas(coords: tuple[float, float]) -> tuple[float, float]:
    drawable_scale = 1.0 - 2.0 * GLYPH_MARGIN
    return tuple(GLYPH_MARGIN + coord * drawable_scale for coord in coords)

def flatten_nested_brushstrokes(strokes: StrokeCollection):
    def flatten_stroke_tree(stroke: BrushStroke | BrushStrokeGroup):
        if isinstance(stroke, BrushStroke):
            yield stroke
        else:
            for child in stroke:
                if not isinstance(child, (BrushStroke, BrushStrokeGroup)):
                    raise TypeError("BrushStrokeGroup children must be BrushStroke or BrushStrokeGroup objects")
                yield from flatten_stroke_tree(child)
    
    if isinstance(strokes, BrushStroke):
        yield strokes
    elif isinstance(strokes, BrushStrokeGroup):
        for stroke in strokes:
            if not isinstance(stroke, (BrushStroke, BrushStrokeGroup)):
                raise TypeError("BrushStrokeGroup children must be BrushStroke or BrushStrokeGroup objects")
            yield from flatten_stroke_tree(stroke)
    elif isinstance(strokes, list):
        for stroke in strokes:
            if not isinstance(stroke, (BrushStroke, BrushStrokeGroup)):
                raise TypeError("Stroke lists may contain only BrushStroke or BrushStrokeGroup objects")
            yield from flatten_stroke_tree(stroke)
    else:
        raise TypeError("Strokes must be a BrushStroke, BrushStrokeGroup, or a list of those objects")