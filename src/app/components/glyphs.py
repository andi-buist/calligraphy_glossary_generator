import tkinter as tk
import numpy as np

from src.app.components.session import AppSession

class GlyphEditor(tk.Frame):
    """
    A grid editor for arranging Glyphs into a Character
    """
    def __init__(self, parent, session: AppSession):
        self.session = session

        self.CANVAS_SIZE = session.CANVAS_SIZE
        self.CELL_SIZE = session.CELL_SIZE

        super().__init__(parent, padx=4, pady=4, highlightthickness=1, highlightbackground="black")

        self.refresh()

    def refresh(self):
        for child in self.winfo_children():
            child.destroy()

        self.columnconfigure(0, weight=1)
        self.canvas=tk.Canvas(
            self,
            width=self.CANVAS_SIZE,
            height=self.CANVAS_SIZE,
            highlightthickness=1,
            highlightbackground="black",
        )
        self.canvas.grid(column=0, row=0, sticky="NS")
        self.canvas.bind("<ButtonPress-1>", self.drag_extent_corner_start)
        self.canvas.bind("<ButtonRelease-1>", self.drag_extent_corner_end)
        self.draw_canvas()

        options = tk.Frame(self, pady=4)
        options.columnconfigure(0, weight=1)
        options.columnconfigure(1, weight=3)
        options.columnconfigure(2, weight=3)
        options.columnconfigure(3, weight=1)
        options.grid(column=0, row=1, sticky="EW")

        tk.Button(options, command=lambda: self.change_glyph_hash(list(self.session.active_character_glyphs.keys()).index(self.session.active_glyph_hash) - 1), text="\u2b9c").grid(
            column=0, row=0, sticky="EW"
        )
        tk.Button(options, command=lambda: self.change_glyph_hash(list(self.session.active_character_glyphs.keys()).index(self.session.active_glyph_hash) + 1), text="\u2b9e").grid(
            column=3, row=0, sticky="EW"
        )
        tk.Label(
            options,
            text=f"Character {self.session.active_character_hash} | "
                 f"Glyph {self.session.active_glyph_hash}",
        ).grid(column=1, row=0, columnspan=2)

    def change_glyph_hash(self, new_idx: int):
        self.session.active_glyph_hash = list(self.session.active_character_glyphs.keys())[new_idx]

        self.session.stroke_changed()

    def drag_extent_corner_start(self, event: tk.Event):
        """
        Action to perform on `self.canvas` left-click: add or drag existing Bezier coord
        """
        raw_loc=(event.x, self.canvas_size[1] - event.y)
        x, y=self.scale_from_padded_canvas(raw_loc)
        self.select_extent_corner((x,y))

    def drag_extent_corner_end(self, event: tk.Event):
        if self.selected_curve_control_point_idx is not None:
            raw_loc=(event.x, self.canvas_size[1] - event.y)
            x, y=(min(max(i, 0.0),1.0) for i in self.scale_from_padded_canvas(raw_loc))

            if self.selected_curve_control_point_idx == 0:
                self.curve_profile.control_points[self.selected_curve_control_point_idx] = (0.0,y)
            elif self.selected_curve_control_point_idx == len(self.curve_profile.control_points) - 1:
                self.curve_profile.control_points[self.selected_curve_control_point_idx] = (1.0,y)
            else:
                self.curve_profile.control_points[self.selected_curve_control_point_idx] = (x,y)

            self.refresh()

    def scale_to_padded_canvas(self, coord: tuple[float,float]) -> tuple[int,int]:
        rawx, rawy = coord
        padded_canvas_size = (self.canvas_size[0] - 2 * self.PADDING_PX,
                                self.canvas_size[1] - 2 * self.PADDING_PX)
        scaled_coord = ((rawx * padded_canvas_size[0]) + self.PADDING_PX,
                        - 1.0 * (rawy * padded_canvas_size[1]) + self.PADDING_PX + padded_canvas_size[1])

        return scaled_coord

    def scale_from_padded_canvas(self, coord: tuple[int,int]) -> tuple[float,float]:
            rawx, rawy = (min(max(i, 0), self.canvas_size[idx]) for idx, i in enumerate(coord))
            padded_canvas_size = (self.canvas_size[0] - 2 * self.PADDING_PX,
                                    self.canvas_size[1] - 2 * self.PADDING_PX)
            scaled_coord = ((rawx - self.PADDING_PX) / padded_canvas_size[0],
                            (rawy - self.PADDING_PX) / padded_canvas_size[1])

            return scaled_coord

    def select_extent_corner(self, coord: tuple[float,float]):
        min_selection_distance_halo = 0.1

        x, y = coord
        distances=[max(0, float(np.sqrt((cx - x) ** 2 + (cy - y) ** 2)) - min_selection_distance_halo) for cx,cy in self.session.active_character_glyph_extents]
        if 0 in distances:
            self.selected_curve_control_point_idx = distances.index(0)
        else:
            self.selected_curve_control_point_idx = None

    def draw_canvas(self):
        """
        Draw to `self.canvas` - add gridlines, red indicators and thick lines for current stroke, faded indicators and thin lines for others.
        """
        def draw_gridlines():
            for pos in range(0, self.CANVAS_SIZE, self.CELL_SIZE):
                self.canvas.create_line(pos, 0, pos, self.CANVAS_SIZE)
                self.canvas.create_line(0, pos, self.CANVAS_SIZE, pos)
        
        self.canvas.delete('all')
        draw_gridlines()

        if self.session.current_stroke_idx < len(self.session.character_stroke_control_points):
            for s_idx, stroke in enumerate(self.session.character_stroke_control_points):
                for coord_idx, (x, y) in enumerate(stroke):
                    # the active stroke
                    if self.session.current_stroke_idx == s_idx:
                        self.canvas.create_rectangle(x * self.CELL_SIZE, y * self.CELL_SIZE, (x + 1) * self.CELL_SIZE, (y + 1) * self.CELL_SIZE, fill="#f00", stipple="gray50")
                        self.canvas.create_text(x * self.CELL_SIZE + self.CELL_SIZE // 5, y * self.CELL_SIZE + self.CELL_SIZE // 5, text=f"{coord_idx}")

                        # draw lines between current and previous point
                        if coord_idx > 0:
                            px, py=stroke[coord_idx - 1]
                            self.canvas.create_line(px * self.CELL_SIZE + self.CELL_SIZE/2,
                                                    py * self.CELL_SIZE + self.CELL_SIZE/2,
                                                    x * self.CELL_SIZE + self.CELL_SIZE/2,
                                                    y * self.CELL_SIZE + self.CELL_SIZE/2,
                                                    width=3, fill="#444")
                    # the inactive stroke(s)
                    else:
                        self.canvas.create_rectangle(x * self.CELL_SIZE, y * self.CELL_SIZE, (x + 1) * self.CELL_SIZE, (y + 1) * self.CELL_SIZE, fill="#888", stipple="gray25")

                        # draw lines between current and previous point
                        if coord_idx > 0:
                            px, py=stroke[coord_idx - 1]
                            self.canvas.create_line(px * self.CELL_SIZE + self.CELL_SIZE/2,
                                                    py * self.CELL_SIZE + self.CELL_SIZE/2,
                                                    x * self.CELL_SIZE + self.CELL_SIZE/2,
                                                    y * self.CELL_SIZE + self.CELL_SIZE/2,
                                                    width=1, fill="#666")