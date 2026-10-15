import tkinter as tk

from src.app.components.session import AppSession

class StrokeEditor(tk.Frame):
    """
    A grid editor for editing a Glyph's brush strokes.
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
        self.canvas.bind("<ButtonPress-1>", self.leftclick_x_y)
        self.canvas.bind("<ButtonPress-3>", self.rightclick_x_y)
        self.draw_canvas()

        active_idx = self.session.active_stroke_idx
        stroke_count = len(self.session.active_glyph_strokes)

        options = tk.Frame(self, pady=4)
        options.columnconfigure(0, weight=1)
        options.columnconfigure(1, weight=1)
        options.grid(column=0, row=1, sticky="EW")

        glyph_hash_by_identity = {
            id(glyph): glyph_hash
            for glyph_hash, glyph in self.session.glyph_glossary_data.items()
        }
        active_glyph = self.session.active_glyph
        glyph_name = (
            f"'{active_glyph.detail}'"
            if active_glyph.detail is not None
            else glyph_hash_by_identity[id(active_glyph)]
        )
        tk.Label(
            options,
            text=f"Glyph: {glyph_name} | "
                 f"Stroke {min(active_idx + 1, stroke_count + 1)} of {stroke_count}",
        ).grid(column=0, row=0, columnspan=2, sticky="W", padx=2, pady=(0, 4))

        tk.Button(
            options,
            text="Add stroke",
            command=lambda: self.session.select_stroke(len(self.session.active_glyph_strokes)),
        ).grid(column=0, row=1, sticky="EW", padx=4)
        tk.Button(
            options,
            text="Remove stroke",
            command=self.session.remove_active_stroke,
            state=(
                "normal"
                if stroke_count > 1 and active_idx < stroke_count
                else "disabled"
            ),
        ).grid(column=1, row=1, sticky="EW", padx=4)

    def leftclick_x_y(self, event: tk.Event):
        """
        Add a point to the selected stroke, or start a new stroke if selected.
        """
        grid_max = self.session.GRID_BREAKS - 1
        x, y = (
            min(grid_max, max(0, event.x // self.CELL_SIZE)),
            min(grid_max, max(0, event.y // self.CELL_SIZE)),
        )
        self.session.add_stroke_point((x / grid_max, y / grid_max))

    def rightclick_x_y(self, event: tk.Event):
        """
        Remove the most recent point in the clicked grid cell.
        """
        active_idx = self.session.active_stroke_idx
        if active_idx >= len(self.session.active_glyph_strokes):
            return

        grid_max = self.session.GRID_BREAKS - 1
        x, y = (
            min(grid_max, max(0, event.x // self.CELL_SIZE)),
            min(grid_max, max(0, event.y // self.CELL_SIZE)),
        )
        self.session.remove_stroke_point((x / grid_max, y / grid_max))

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

        active_idx = self.session.active_stroke_idx
        strokes = self.session.active_glyph_strokes
        for stroke_idx, stroke in enumerate(strokes):
            active = stroke_idx == active_idx
            points = [
                ((x * (self.session.GRID_BREAKS - 1) + 0.5) * self.CELL_SIZE,
                 (y * (self.session.GRID_BREAKS - 1) + 0.5) * self.CELL_SIZE)
                for x, y in stroke.control_points
            ]
            if len(points) >= 2:
                self.canvas.create_line(
                    *[coordinate for point in points for coordinate in point],
                    fill="#444" if active else "#666",
                    width=3 if active else 1,
                )
            for point_idx, (x, y) in enumerate(points):
                self.canvas.create_rectangle(
                    x - self.CELL_SIZE / 2,
                    y - self.CELL_SIZE / 2,
                    x + self.CELL_SIZE / 2,
                    y + self.CELL_SIZE / 2,
                    fill="#f00" if active else "#888",
                    stipple="gray50" if active else "gray25",
                )
                if active:
                    self.canvas.create_text(
                        x - self.CELL_SIZE // 3,
                        y - self.CELL_SIZE // 3,
                        text=str(point_idx),
                    )