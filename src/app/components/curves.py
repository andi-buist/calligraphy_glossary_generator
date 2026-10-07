import tkinter as tk
import typing
import numpy as np

from src.symbols.strokes import CurveProfile

class CurveProfileWidget(tk.Frame):
    PADDING_PX = 16
    def __init__(
        self,
        parent,
        size: tuple[int,int],
        curve_profile: CurveProfile,
        on_refresh: typing.Callable[[], None] | None = None,
    ):
        super().__init__(parent)
        self.rowconfigure(0, weight=1)

        self.canvas_size=size
        self.curve_profile: CurveProfile=curve_profile

        self.on_refresh = on_refresh

        self.selected_curve_control_point_idx: int=None

        self.canvas=tk.Canvas(self,
                              width=size[0],
                              height=size[1],
                              highlightthickness=1, highlightbackground="black")
        self.canvas.grid(column=0, row=0)
        self.canvas.bind("<ButtonPress-1>", self.drag_control_point_start)
        self.canvas.bind("<ButtonRelease-1>", self.drag_control_point_end)
        self.canvas.bind("<Double-1>", self.add_control_point)
        self.canvas.bind("<ButtonPress-2>", self.reset_curve)
        self.canvas.bind("<ButtonPress-3>", self.remove_control_point)

        self.refresh()

    def refresh(self):
        self.curve_profile.profile=self.curve_profile.get_profile()
        self.draw_canvas()
        if self.on_refresh is not None:
            self.on_refresh()

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

    def draw_canvas(self):
        """
        Draw to `self.canvas` - add the curve and points
        """
        self.canvas.delete('all')

        # draw curve control points
        for coord_idx, (x,y) in enumerate(self.curve_profile.control_points):
            x1, y1 = self.scale_to_padded_canvas((x,y))
            if coord_idx > 0:
                px, py=self.curve_profile.control_points[coord_idx - 1]
                x0, y0 = self.scale_to_padded_canvas((px,py))
                self.canvas.create_line(x0, y0, x1, y1,
                                        width=1, fill="#bbb")

            ex0,ey0,ex1,ey1 = (x1-2.0,y1-2.0,x1+2.0,y1+2.0)
            self.canvas.create_oval(ex0, ey0, ex1, ey1,
                                    fill="#000")

        # draw curve line
        for coord_idx, (x, y) in enumerate(self.curve_profile.profile):
            if coord_idx > 0:
                px, py=self.curve_profile.profile[coord_idx - 1]
                x0, y0, x1, y1 = (*self.scale_to_padded_canvas((px,py)), *self.scale_to_padded_canvas((x,y)))
                self.canvas.create_line(x0, y0, x1, y1,
                                        width=1, fill="#444")

    def select_curve_control_point(self, coord: tuple[float,float]):
        min_selection_distance_halo = 0.1

        x, y = coord
        distances=[max(0, float(np.sqrt((cx - x) ** 2 + (cy - y) ** 2)) - min_selection_distance_halo) for cx,cy in self.curve_profile.control_points]
        if 0 in distances:
            self.selected_curve_control_point_idx = distances.index(0)
        else:
            self.selected_curve_control_point_idx = None

    def drag_control_point_start(self, event: tk.Event):
        """
        Action to perform on `self.canvas` left-click: add or drag existing Bezier coord
        """
        raw_loc=(event.x, self.canvas_size[1] - event.y)
        x, y=self.scale_from_padded_canvas(raw_loc)
        self.select_curve_control_point((x,y))

    def drag_control_point_end(self, event: tk.Event):
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

    def add_control_point(self, event: tk.Event):
        """
        Action to perform on `self.canvas` right-click: remove Bezier coord
        """
        raw_loc=(event.x, self.canvas_size[1] - event.y)
        x, y=self.scale_from_padded_canvas(raw_loc)

        self.curve_profile.control_points.insert(-1, (x,y))
        self.selected_curve_control_point_idx = None

        self.refresh()

    def remove_control_point(self, event: tk.Event):
        """
        Action to perform on `self.canvas` right-click: remove Bezier coord
        """
        raw_loc=(event.x, self.canvas_size[1] - event.y)
        x, y=self.scale_from_padded_canvas(raw_loc)
        self.select_curve_control_point((x,y))

        if self.selected_curve_control_point_idx is not None:
            if self.selected_curve_control_point_idx not in (0, len(self.curve_profile.control_points) - 1):
                _ = self.curve_profile.control_points.pop(self.selected_curve_control_point_idx)
                self.selected_curve_control_point_idx = None

                self.refresh()

    def reset_curve(self, event: tk.Event):
        self.curve_profile.control_points[:]=CurveProfile.REALISTIC.copy().control_points
        self.refresh()