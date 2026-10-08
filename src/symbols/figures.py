import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
import numpy as np
import textwrap

from src.symbols import radicals
from src.symbols.characters.base import *

def _row_col(n: int):
    """
    Gets the closest square-ish row-col count, prioritising width
    """
    return (int(np.ceil(n / np.ceil(np.sqrt(n)))), int(np.ceil(np.sqrt(n))))

# can't be statically-typed due to circular imports :/ - list[Character]
def character_sheet(characters: list[Character]):
    def _add_character(character: Character, ax: plt.Axes, titles: bool = True, show_masks: bool = False):
            glyph_width, glyph_height = character.glyph.size

            ax.imshow(character.glyph, extent=(0, glyph_width, glyph_height, 0), alpha = 1)
            # show the masks
            if show_masks:
                (rect_area), _ = radicals.get_largest_rectangular_area(character.glyph)
                if rect_area is not None:
                    rect_w, rect_h = (rect_area[1][0] - rect_area[0][0], rect_area[1][1] - rect_area[0][1])
                    ax.add_patch(Rectangle(rect_area[0], rect_w, rect_h, color = (1,0,0,0.3)))

            if titles:
                working_type, working_def = character.definition[0]
                title = f"{working_type}:\n'{working_def}'"
                ax.set_title(textwrap.fill(title, width=title_line_width), {'fontsize': title_fontsize})
            ax.tick_params(which="minor", length=0)
            ax.grid(which="minor", color="black", linestyle=":", linewidth=1, alpha = 0.3)
            ax.set_xlim(0, glyph_width)
            ax.set_ylim(glyph_height, 0)
    
    _rc = _row_col(len(characters))
    title_fontsize = max(6, min(10, 12 / np.sqrt(max(_rc))))
    title_line_width = max(12, int(32 / np.sqrt(max(_rc))))
    fig, axs = plt.subplots(_rc[0], _rc[1], tight_layout = True, squeeze=False)

    fig.set_figheight(6)
    fig.set_figwidth(6)

    if len(characters) > 1:
        idx = 0
        for i in range(_rc[0]):
            for j in range(_rc[1]):
                _cur_ax: plt.Axes = axs[i,j]
                _cur_ax.set_xticks([])
                _cur_ax.set_yticks([])
                for spine in _cur_ax.spines.values():
                    spine.set_visible(False)

                #if still have characters to add, add them
                if idx < len(characters):
                    _add_character(characters[idx], _cur_ax, False if len(characters) > 64 else True)
                idx += 1
    else:
        _add_character(characters[0], axs[0, 0])

    fig