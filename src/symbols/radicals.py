from PIL import Image
import numpy as np
from src.symbols import brushstrokes
from src.symbols.characters.base import Character

GLYPH_SIZE = brushstrokes.GLYPH_SIZE

def get_largest_rectangular_area(glyph: Image.Image) -> tuple[tuple[tuple[int,int],tuple[int,int]], float]:
    grayscale = np.asarray(glyph.convert("L"), dtype=float)
    ink = np.asarray(1.0 - (grayscale / 255.0), int)

    rows, cols = ink.shape

    # a single row shape
    heights = np.zeros(cols, dtype=int)
    max_area = 0
    best_corners = None

    # for each row
    for r in range(rows):
        # where there is no ink, tick up the value for that pixel column
        heights = np.where(ink[r] == 0, heights + 1, 0)
        # make a new stack of row indexes
        row_index_stack = []
        # add a boundary
        extended_heights = np.append(heights, 0)

        # for each row's pixel
        for i, h in enumerate(extended_heights):
            while row_index_stack and extended_heights[row_index_stack[-1]] >= h:
                # get and remove the final index
                height_idx = row_index_stack.pop()
                # get the height at index
                height = extended_heights[height_idx]

                c1 = 0 if not row_index_stack else row_index_stack[-1] + 1
                c2 = i 
                width = c2 - c1
                
                area = height * width
                if area > max_area:
                    max_area = area
                    r1 = r - height + 1
                    r2 = r + 1
                    
                    best_corners = ((c1, r1), (c2, r2)) 
            
            row_index_stack.append(i)

    return best_corners, max_area

def rect_in_rect(inner_rect: tuple[tuple[float,float],tuple[float,float]], outer_rect: tuple[tuple[float,float],tuple[float,float]]) -> bool:
    if inner_rect and outer_rect:
        #print(f"inner rect {inner_rect}, outer rect {outer_rect}")
        return all((outer_rect[0][0] <= inner_rect[0][0],
                    outer_rect[0][1] <= inner_rect[0][1],
                    outer_rect[1][0] >= inner_rect[1][0],
                    outer_rect[1][1] >= inner_rect[1][1]))
    else:
        return False

def rect_edge_patches(glyph: Image.Image):
    corners, _ = get_largest_rectangular_area(glyph)
    (x1, y1), (x2, y2) = corners
    x1, y1 = x1 / GLYPH_SIZE, y1 / GLYPH_SIZE
    x2, y2 = x2 / GLYPH_SIZE, y2 / GLYPH_SIZE

    l_patch = ((0.0,0.0),(x1,1.0)) if x1 > 0.0 else None
    r_patch = ((x2,0.0),(1.0,1.0)) if x2 < 1.0 else None
    u_patch = ((0.0,0.0),(1.0,y1)) if y1 > 0.0 else None
    d_patch = ((0.0,y2),(1.0,1.0)) if y2 < 1.0 else None

    return l_patch, r_patch, u_patch, d_patch

def rect_edge_patch_scaling(character: Character) -> Character:
    scaled_character = character.clone()
    l_patch, r_patch, u_patch, d_patch = rect_edge_patches(scaled_character.glyph)

    def scale_tree(node, inherited_scales=(), include_own_scales=True):
        if isinstance(node, brushstrokes.BrushStrokeGroup):
            parent_scales = scale_tree(node[0], inherited_scales, include_own_scales)
            child_includes_own_scales = node.scale_method == "combine"
            for child in node[1:]:
                scale_tree(child, parent_scales, child_includes_own_scales)
            return parent_scales
        if not isinstance(node, brushstrokes.BrushStroke):
            raise TypeError("Stroke trees may contain only BrushStroke or BrushStrokeGroup objects")

        canvas_bbox = tuple(brushstrokes.map_unit_coords_to_margined_canvas(corner) for corner in node.bbox)
        own_scales = []
        if include_own_scales:
            if rect_in_rect(canvas_bbox, l_patch):
                own_scales.append("l")
            elif rect_in_rect(canvas_bbox, r_patch):
                own_scales.append("r")
            if rect_in_rect(canvas_bbox, u_patch):
                own_scales.append("u")
            elif rect_in_rect(canvas_bbox, d_patch):
                own_scales.append("d")

        scale_set = set(inherited_scales) | set(own_scales)
        scales = tuple(direction for direction in ("l", "r", "u", "d") if direction in scale_set)
        for direction in scales:
            node.scale(direction, 0.5)
        return scales

    if isinstance(scaled_character.strokes, brushstrokes.BrushStrokeGroup):
        scale_tree(scaled_character.strokes)
    else:
        for component in scaled_character.strokes:
            scale_tree(component)

    scaled_character.glyph = scaled_character.generate_glyph()
    scaled_character.glyph_orientation = scaled_character._get_glyph_orientation()
    return scaled_character
