import tkinter as tk

from src.app.components.session import AppSession

class GlyphEditor(tk.Frame):
    """
    A grid editor for editing a Glyph's brush strokes.
    """
    def __init__(self, parent, session: AppSession):
        self.session = session

        super().__init__(parent, padx=4, pady=4, highlightthickness=1, highlightbackground="black")

        self._build_widgets()
        self.refresh()

    def _build_widgets(self):
        self.columnconfigure(0, weight=1)
        self.canvas=tk.Canvas(
            self,
            width=self.session.CANVAS_SIZE,
            height=self.session.CANVAS_SIZE,
            highlightthickness=1,
            highlightbackground="black",
        )
        self.canvas.grid(column=0, row=0, sticky="NS")
        self.canvas.bind("<ButtonPress-1>", self.leftclick_x_y)
        self.canvas.bind("<ButtonPress-3>", self.rightclick_x_y)

        options = tk.Frame(self, pady=4)
        options.grid(column=0, row=1, sticky="EW")

        self.context_label = tk.Label(options)
        self.context_label.grid(row=0, column=0, sticky="W", padx=2, pady=(0, 4))

    def refresh(self):
        self.draw_canvas()

        active_glyph = self.session.active_glyph
        if active_glyph is None:
            self.context_label.configure(text="No glyph selected")
            return

        stroke_idx = self.session.active_glyph_stroke_idx
        stroke_count = len(active_glyph.strokes)
        glyph_name = active_glyph.index_path or self.session.active_glyph_hash
        self.context_label.configure(
            text=f"Glyph: '{glyph_name}' | "
            f"Stroke {min(stroke_idx + 1, stroke_count + 1)} of {stroke_count}"
        )

    def leftclick_x_y(self, event: tk.Event):
        """
        Add a point to the selected stroke, or start a new stroke if selected.
        """
        if self.session.active_glyph is None:
            return

        grid_max = self.session.GRID_BREAKS - 1
        x, y = (
            min(grid_max, max(0, event.x // self.session.CELL_SIZE)),
            min(grid_max, max(0, event.y // self.session.CELL_SIZE)),
        )
        self.session.add_stroke_point((x / grid_max, y / grid_max))

    def rightclick_x_y(self, event: tk.Event):
        """
        Remove the most recent point in the clicked grid cell.
        """
        if self.session.active_glyph is None:
            return

        active_idx = self.session.active_glyph_stroke_idx
        if active_idx >= len(self.session.active_glyph_strokes):
            return

        grid_max = self.session.GRID_BREAKS - 1
        x, y = (
            min(grid_max, max(0, event.x // self.session.CELL_SIZE)),
            min(grid_max, max(0, event.y // self.session.CELL_SIZE)),
        )
        self.session.remove_stroke_point((x / grid_max, y / grid_max))

    def draw_canvas(self):
        """
        Draw to `self.canvas` - add gridlines, red indicators and thick lines for current stroke, faded indicators and thin lines for others.
        """
        def draw_gridlines():
            for pos in range(0, self.session.CANVAS_SIZE, self.session.CELL_SIZE):
                self.canvas.create_line(pos, 0, pos, self.session.CANVAS_SIZE, fill="#999999")
                self.canvas.create_line(0, pos, self.session.CANVAS_SIZE, pos, fill="#999999")
        
        self.canvas.delete('all')
        draw_gridlines()

        active_glyph = self.session.active_glyph
        if active_glyph is None:
            self.canvas.create_text(
                self.session.CANVAS_SIZE // 2,
                self.session.CANVAS_SIZE //2,
                text="Select a glyph to edit its strokes.",
            )
            return

        active_idx = self.session.active_glyph_stroke_idx
        for stroke_idx, stroke in enumerate(active_glyph.strokes):
            active = stroke_idx == active_idx
            points = [
                ((x * (self.session.GRID_BREAKS - 1) + 0.5) * self.session.CELL_SIZE,
                (y * (self.session.GRID_BREAKS - 1) + 0.5) * self.session.CELL_SIZE)
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
                    x - self.session.CELL_SIZE / 2,
                    y - self.session.CELL_SIZE / 2,
                    x + self.session.CELL_SIZE / 2,
                    y + self.session.CELL_SIZE / 2,
                    fill="#f00" if active else "#888",
                    stipple="gray50" if active else "gray25",
                )
                if active:
                    self.canvas.create_text(
                        x - self.session.CELL_SIZE // 3,
                        y - self.session.CELL_SIZE // 3,
                        text=str(point_idx),
                    )