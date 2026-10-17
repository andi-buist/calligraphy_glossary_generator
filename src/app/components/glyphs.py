import tkinter as tk

from tkinter import ttk

from src.app.components.session import AppSession
from src.symbols.characters import Glyph

class GlyphEditor(tk.Frame):
    """
    A grid editor for arranging Glyphs into a Character
    """
    def __init__(self, parent, session: AppSession):
        self.session = session

        self.drag_mode: str | None = None
        self.drag_start: tuple[float, float] | None = None
        self.drag_extent: tuple[tuple[float, float], tuple[float, float]] | None = None

        self.extent_moved = False

        self.glyph_hash_var = tk.StringVar()
        self.glyph_picker: ttk.Combobox | None = None
        self.glyph_picker_items: list[tuple[str, Glyph]] = []

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
        self.canvas.bind("<ButtonPress-1>", self.drag_extent_start)
        self.canvas.bind("<B1-Motion>", self.drag_extent_motion)
        self.canvas.bind("<ButtonRelease-1>", self.drag_extent_end)

        options = tk.Frame(self, pady=4)
        options.columnconfigure(0, weight=1)
        options.grid(column=0, row=1, sticky="EW")
        self.character_glyph_label = tk.Label(options)
        self.character_glyph_label.grid(
            column=0, row=0, columnspan=5, sticky="EW", padx=4, pady=4
        )

        self.glyph_picker = ttk.Combobox(
            options,
            textvariable=self.glyph_hash_var,
            values=(),
            state="readonly",
        )
        self.glyph_picker.grid(column=0, row=1, sticky="EW", padx=4)
        tk.Button(options, text="Add existing glyph", command=self.place_glyph).grid(
            column=1, row=1, padx=4
        )
        tk.Button(options, text="New glyph", command=self.create_glyph).grid(
            column=2, row=1, padx=4
        )
        self.remove_glyph_button = tk.Button(
            options,
            text="Remove from character",
            command=self.remove_glyph,
        )
        self.remove_glyph_button.grid(column=3, row=1, padx=4)

    def refresh(self):
        selected_glyph_hash = self._selected_glyph_hash()
        self.draw_canvas()

        glyph_hash_by_identity = {
            id(glyph): glyph_hash
            for glyph_hash, glyph in self.session.glyph_glossary_data.items()
        }
        active_glyph = self.session.active_glyph
        active_glyph_hash = glyph_hash_by_identity[id(active_glyph)]
        glyph_label = (
            f"'{active_glyph.detail}'"
            if active_glyph.detail is not None
            else active_glyph_hash
        )
        self.character_glyph_label.configure(
            text=f"Character: {self.session.active_character_hash} | Glyph: {glyph_label}"
        )

        self.glyph_picker_items = sorted(
            self.session.glyph_glossary_data.items(),
            key=lambda item: (
                item[1].detail is None,
                (item[1].detail or "").casefold(),
                item[0],
            ),
        )
        display_values = [
            f"'{glyph.detail}'" if glyph.detail is not None else glyph_hash
            for glyph_hash, glyph in self.glyph_picker_items
        ]
        self.glyph_picker.configure(values=display_values)
        if self.glyph_picker_items:
            selected_idx = next(
                (
                    idx
                    for idx, (glyph_hash, _) in enumerate(self.glyph_picker_items)
                    if glyph_hash == selected_glyph_hash
                ),
                0,
            )
            self.glyph_picker.current(selected_idx)
        else:
            self.glyph_hash_var.set("")
        self.remove_glyph_button.configure(
            state=(
                "normal"
                if len(self.session.active_character.glyphs) > 1
                else "disabled"
            )
        )

    def _selected_glyph_hash(self) -> str | None:
        if self.glyph_picker is not None:
            selected_idx = self.glyph_picker.current()
            if 0 <= selected_idx < len(self.glyph_picker_items):
                return self.glyph_picker_items[selected_idx][0]
        return None

    def place_glyph(self):
        glyph_hash = self._selected_glyph_hash()
        if glyph_hash:
            self.session.add_glyph_to_character(glyph_hash)

    def create_glyph(self):
        self.session.create_glyph_for_character()

    def remove_glyph(self):
        if len(self.session.active_character.glyphs) > 1:
            self.session.remove_active_glyph_from_character()

    def _canvas_point(self, event: tk.Event) -> tuple[float, float]:
        return (
            min(max(event.x / self.session.CANVAS_SIZE, 0.0), 1.0),
            min(max(event.y / self.session.CANVAS_SIZE, 0.0), 1.0),
        )

    def _snap_to_grid(self, value: float) -> float:
        cell_count = self.session.CANVAS_SIZE // self.session.CELL_SIZE
        return round(value * cell_count) / cell_count

    def drag_extent_start(self, event: tk.Event):
        x, y = self._canvas_point(event)
        character = self.session.active_character
        nearest_distance = 12 / self.session.CANVAS_SIZE

        self.drag_mode = None

        if self.session.active_glyph_idx is not None:
            (x0, y0), (x1, y1) = character.glyph_extents[self.session.active_glyph_idx]
            for corner_name, (cx, cy) in (
                ("top-left", (x0, y0)),
                ("top-right", (x1, y0)),
                ("bottom-left", (x0, y1)),
                ("bottom-right", (x1, y1)),
            ):
                distance = ((cx - x) ** 2 + (cy - y) ** 2) ** 0.5
                if distance <= nearest_distance:
                    self.drag_mode = corner_name
                    nearest_distance = distance

            self.session.active_stroke_idx = 0
            self.drag_start = (x, y)
            self.drag_extent = character.glyph_extents[self.session.active_glyph_idx]
            self.drag_mode = self.drag_mode or "move"
            self.extent_moved = False

    def drag_extent_motion(self, event: tk.Event):
        if self.session.active_glyph_idx is None or self.drag_start is None or self.drag_extent is None:
            return
        x, y = self._canvas_point(event)
        dx, dy = x - self.drag_start[0], y - self.drag_start[1]
        (x0, y0), (x1, y1) = self.drag_extent

        if self.drag_mode == "move":
            grid_size = self.session.CELL_SIZE / self.session.CANVAS_SIZE
            width = max(grid_size, round((x1 - x0) / grid_size) * grid_size)
            height = max(grid_size, round((y1 - y0) / grid_size) * grid_size)
            x0 = min(max(self._snap_to_grid(x0 + dx), 0.0), 1.0 - width)
            y0 = min(max(self._snap_to_grid(y0 + dy), 0.0), 1.0 - height)
            extent = ((x0, y0), (x0 + width, y0 + height))
        else:
            minimum_size = self.session.CELL_SIZE / self.session.CANVAS_SIZE
            if "left" in self.drag_mode:
                x0 = min(
                    max(self._snap_to_grid(x0 + dx), 0.0),
                    x1 - minimum_size,
                )
            elif "right" in self.drag_mode:
                x1 = max(
                    min(self._snap_to_grid(x1 + dx), 1.0),
                    x0 + minimum_size,
                )
            if "top" in self.drag_mode:
                y0 = min(
                    max(self._snap_to_grid(y0 + dy), 0.0),
                    y1 - minimum_size,
                )
            elif "bottom" in self.drag_mode:
                y1 = max(
                    min(self._snap_to_grid(y1 + dy), 1.0),
                    y0 + minimum_size,
                )
            extent = ((x0, y0), (x1, y1))
        self.session.active_character.glyph_extents[self.session.active_glyph_idx] = extent
        self.extent_moved = self.extent_moved or extent != self.drag_extent
        self.draw_canvas()

    def drag_extent_end(self, _event: tk.Event):
        if self.session.active_glyph_idx is not None:
            self.session.refresh(
                "glyphs" if self.extent_moved else "glyph-selection"
            )
        self.drag_start = None
        self.drag_extent = None

    def draw_canvas(self):
        """
        Draw the character's glyph extents and their stroke paths.
        """
        def draw_gridlines():
            for pos in range(0, self.session.CANVAS_SIZE, self.session.CELL_SIZE):
                self.canvas.create_line(pos, 0, pos, self.session.CANVAS_SIZE, fill="#999999")
                self.canvas.create_line(0, pos, self.session.CANVAS_SIZE, pos, fill="#999999")
        CORNER_GRIP_RADIUS = 6

        self.canvas.delete("all")
        draw_gridlines()

        character = self.session.active_character
        for idx, (glyph, extent) in enumerate(zip(character.glyphs, character.glyph_extents)):
            (x0, y0), (x1, y1) = extent
            left, top = x0 * self.session.CANVAS_SIZE, y0 * self.session.CANVAS_SIZE
            right, bottom = x1 * self.session.CANVAS_SIZE, y1 * self.session.CANVAS_SIZE

            active = idx == self.session.active_glyph_idx

            self.canvas.create_rectangle(
                left, top, right, bottom,
                outline="#d44" if active else "#666",
                width=3 if active else 1
            )

            width, height = right - left, bottom - top
            for stroke in glyph.strokes:
                points = [
                    (
                        left + ((x * (self.session.GRID_BREAKS - 1) + 0.5) / self.session.GRID_BREAKS) * width,
                        top + ((y * (self.session.GRID_BREAKS - 1) + 0.5) / self.session.GRID_BREAKS) * height,
                    )
                    for x, y in stroke.spline_path_points
                ]
                if len(points) >= 2:
                    self.canvas.create_line(*[coordinate for point in points for coordinate in point],
                    fill="#d44" if active else "#666",
                    width=3 if active else 1)
                elif points:
                    x, y = points[0]
                    self.canvas.create_oval(x - 2, y - 2, x + 2, y + 2,
                                            fill="#d44" if active else "#666",
                                            outline="#d44" if active else "#666")
            if active:
                for corner_x, corner_y in (
                    (left, top),
                    (right, top),
                    (left, bottom),
                    (right, bottom),
                ):
                    self.canvas.create_oval(
                        corner_x - CORNER_GRIP_RADIUS,
                        corner_y - CORNER_GRIP_RADIUS,
                        corner_x + CORNER_GRIP_RADIUS,
                        corner_y + CORNER_GRIP_RADIUS,
                        fill="#d44",
                        outline="white",
                    )