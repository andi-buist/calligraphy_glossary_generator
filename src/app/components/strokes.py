import tkinter as tk
from tkinter import ttk

from src.app.components.session import CharacterEditorSession
from src.app.components.curves import CurveProfileWidget
from src.symbols.strokes import CurveProfile

class StrokeEditor(tk.Frame):
    def __init__(self, parent, session: CharacterEditorSession):
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
        self.canvas.bind("<ButtonPress-1>", self.leftclick_x_y)
        self.canvas.bind("<ButtonPress-3>", self.rightclick_x_y)
        self.draw_canvas()

        active_idx = self.session.current_stroke_idx
        has_active_stroke = active_idx < len(self.session.character_stroke_control_points)

        options = tk.Frame(self, pady=4)
        options.columnconfigure(0, weight=1)
        options.columnconfigure(1, weight=3)
        options.columnconfigure(2, weight=3)
        options.columnconfigure(3, weight=1)
        options.grid(column=0, row=1, sticky="EW")

        tk.Button(options, command=lambda: self.change_stroke_idx(-1), text="\u2b9c").grid(
            column=0, row=0, sticky="EW"
        )
        tk.Button(options, command=lambda: self.change_stroke_idx(1), text="\u2b9e").grid(
            column=3, row=0, sticky="EW"
        )
        tk.Label(
            options,
            text=f"Character {self.session.character_hash} | "
                 f"Brushstroke {active_idx}",
        ).grid(column=1, row=0, columnspan=2)

        if self.session.show_stroke_options_var.get() and has_active_stroke:
            curve_profile=CurveProfile(
                control_points=self.session.character_stroke_profile_control_points[active_idx],
                bounds=tuple(
                    float(var.get())
                    for var in self.session.character_stroke_profile_bounds_vars[active_idx]
                ),
            )
            curve_profile_widget=CurveProfileWidget(
                options,
                size=(128, 128),
                curve_profile=curve_profile,
                on_refresh=self.session.profile_changed,
            )
            curve_profile_widget.grid(column=1, row=2, columnspan=2)

            left_bound, right_bound = self.session.character_stroke_profile_bounds_vars[active_idx]
            ttk.Spinbox(
                options,
                textvariable=left_bound,
                command=self.session.profile_changed,
                to=16.0,
                increment=0.1,
            ).grid(column=1, row=3, sticky="E")
            ttk.Spinbox(
                options,
                textvariable=right_bound,
                command=self.session.profile_changed,
                to=16.0,
                increment=0.1,
            ).grid(column=2, row=3, sticky="W")

        tk.Checkbutton(
            self,
            variable=self.session.show_stroke_options_var,
            text="Show stroke options",
            command=lambda: self.session.refresh("stroke"),
        ).grid(column=0, row=2, sticky="SW")

    def remove_empty_strokes(self):
        removed_idxs = []
        for idx in reversed(range(0, len(self.session.character_stroke_control_points))):
            if len(self.session.character_stroke_control_points[idx]) <= 1:
                if idx == self.session.current_stroke_idx:
                    continue
                # Remove the empty/invalid stroke data across all parallel lists
                self.session.character_stroke_control_points.pop(idx)
                self.session.active_stroke_source_control_points.pop(idx)
                self.session.character_stroke_profile_control_points.pop(idx)
                self.session.character_stroke_profile_bounds_vars.pop(idx)

                removed_idxs.append(idx)
                
                # Shift the active index left if a preceding stroke was removed
                if idx < self.session.current_stroke_idx:
                    self.session.current_stroke_idx -= 1

        if len(removed_idxs) > 0:
            print(f"Found empty strokes, removed {removed_idxs}")

    def change_stroke_idx(self, value: int):
        self.session.current_stroke_idx = max(0, self.session.current_stroke_idx)
        new_idx = self.session.current_stroke_idx + value
        if new_idx < 0:
            return
        if new_idx >= len(self.session.character_stroke_control_points):
            if len(self.session.character_stroke_control_points[-1]) > 1:    
                self.session.add_new_stroke_items()
            else:
                print(f"Current stroke is incomplete, staying put")
                new_idx = self.session.current_stroke_idx
        self.session.current_stroke_idx = new_idx

        self.remove_empty_strokes()

        self.session.stroke_changed()

    def leftclick_x_y(self, event: tk.Event):
        """
        Action to perform on `self.canvas` left-click: add integer coordinates to `self.character_stroke_control_points[self.current_stroke_idx].`
        """
        if self.session.current_stroke_idx >= len(self.session.character_stroke_control_points):
            self.session.add_new_stroke_items()

        grid_max = self.session.GRID_BREAKS - 1
        x, y = (
            min(grid_max, max(0, event.x // self.CELL_SIZE)),
            min(grid_max, max(0, event.y // self.CELL_SIZE)),
        )
        self.session.character_stroke_control_points[self.session.current_stroke_idx].append((x, y))
        self.session.stroke_changed()

    def rightclick_x_y(self, event: tk.Event):
        """
        Action to perform on `self.canvas` right-click: remove most recent matching integer coordinates from `self.character_stroke_control_points[self.current_stroke_idx].`
        """
        active_idx = self.session.current_stroke_idx
        if active_idx >= len(self.session.character_stroke_control_points):
            return

        x, y = (
            min(self.session.GRID_BREAKS - 1, max(0, event.x // self.CELL_SIZE)),
            min(self.session.GRID_BREAKS - 1, max(0, event.y // self.CELL_SIZE)),
        )
        stroke = self.session.character_stroke_control_points[active_idx]
        matching_idx = next(
            (idx for idx in range(len(stroke) - 1, -1, -1) if stroke[idx] == (x, y)),
            None,
        )
        if matching_idx is not None:
            stroke.pop(matching_idx)
            self.session.stroke_changed()

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