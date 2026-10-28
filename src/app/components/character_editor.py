import tkinter as tk
from tkinter import ttk
from typing import Literal

from src.app.components.session import AppSession
from src.symbols.characters import Glyph, Character


class CharacterEditor(tk.Frame):
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

        self.subcharacter_hash_var = tk.StringVar()
        self.subcharacter_picker: ttk.Combobox | None = None
        self.subcharacter_picker_items: list[tuple[str, Character]] = []

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
        self.character_label = tk.Label(options)
        self.character_label.grid(
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
            column=1, row=1, sticky="EW", padx=4
        )
        tk.Button(options, text="New glyph", command=self.create_glyph).grid(
            column=2, row=1, sticky="EW", padx=4
        )

        self.subcharacter_picker = ttk.Combobox(
            options,
            textvariable=self.subcharacter_hash_var,
            values=(),
            state="readonly",
        )
        self.subcharacter_picker.grid(column=0, row=2, sticky="EW", padx=4)
        tk.Button(options, text="Add existing subcharacter", command=self.place_subcharacter).grid(
            column=1, row=2, sticky="EW", padx=4
        )

    def refresh(self):
        selected_glyph_hash = self._selected_glyph_hash()
        selected_subcharacter_hash = self._selected_subcharacter_hash()
        self.draw_canvas()

        ac_type, ac_idx = self.session.active_component_idx

        glyph_hash_by_identity = {
            id(glyph): glyph_hash
            for glyph_hash, glyph in self.session.glyph_glossary_data.items()
        }

        subcharacter_hash_by_identity = {
            id(character): character_hash
            for character_hash, character in self.session.character_glossary_data.items()
        }

        active_component = self.session.active_component

        if ac_type == "glyph":
            active_glyph_hash = glyph_hash_by_identity[id(active_component)]

            glyph_label = (
                f"'{active_component.detail}'"
                if active_component.detail is not None
                else active_glyph_hash
            )

            self.character_label.configure(
                text=f"Character: {self.session.active_character_hash} | Glyph: {glyph_label}"
            )
        else:
            active_subcharacter_hash = subcharacter_hash_by_identity[id(active_component)]

            subcharacter_label = (
                f"'{active_component.definition[0][1]}'"
                if active_component.definition is not None
                else active_subcharacter_hash
            )
            
            self.character_label.configure(
                text=f"Character: {self.session.active_character_hash} | Subcharacter: {subcharacter_label}"
            )

        # Glyph picker setup ---------------
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

        # Subcharacter picker setup ---------------
        self.subcharacter_picker_items = sorted(
            self.session.character_glossary_data.items(),
            key=lambda item: (
                item[1].definition is None,
                (item[1].definition[0][1] or "").casefold(),
                item[0],
            ),
        )
        display_values = [
            f"'{character.definition[0][1]}'" if character.definition is not None else character_hash
            for character_hash, character in self.subcharacter_picker_items
        ]
        self.subcharacter_picker.configure(values=display_values)
        if self.subcharacter_picker_items:
            selected_idx = next(
                (
                    idx
                    for idx, (subcharacter_hash, _) in enumerate(self.subcharacter_picker_items)
                    if subcharacter_hash == selected_subcharacter_hash
                ),
                0,
            )
            self.subcharacter_picker.current(selected_idx)
        else:
            self.subcharacter_hash_var.set("")

    # Glyph adder/remover functions -------------
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
    
    # Subcharacter adder/remover functions -------------
    def _selected_subcharacter_hash(self) -> str | None:
        if self.subcharacter_picker is not None:
            selected_idx = self.subcharacter_picker.current()
            if 0 <= selected_idx < len(self.subcharacter_picker_items):
                return self.subcharacter_picker_items[selected_idx][0]
        return None

    def place_subcharacter(self):
        subcharacter_hash = self._selected_subcharacter_hash()
        if subcharacter_hash:
            self.session.add_subcharacter_to_character(subcharacter_hash)

    # Canvas functions ------------
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

        if self.session.active_component_idx is not None:
            ac_type, ac_idx = self.session.active_component_idx
            if ac_type == "glyph":
                (x0, y0), (x1, y1) = character.glyph_extents[ac_idx]
            else:
                (x0, y0), (x1, y1) = character.subcharacter_extents[ac_idx]

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

            if ac_type == "glyph":
                self.drag_extent = character.glyph_extents[ac_idx]
            else:
                self.drag_extent = character.subcharacter_extents[ac_idx]

            self.drag_mode = self.drag_mode or "move"
            self.extent_moved = False

    def drag_extent_motion(self, event: tk.Event):
        if self.session.active_component_idx is None or self.drag_start is None or self.drag_extent is None:
            return
        
        x, y = self._canvas_point(event)
        dx, dy = x - self.drag_start[0], y - self.drag_start[1]
        (x0, y0), (x1, y1) = self.drag_extent

        ac_type, ac_idx = self.session.active_component_idx

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

        if ac_type == "glyph":
            self.session.active_character.glyph_extents[ac_idx] = extent
        else:
            self.session.active_character.subcharacter_extents[ac_idx] = extent

        self.extent_moved = self.extent_moved or extent != self.drag_extent
        self.draw_canvas()

    def drag_extent_end(self, _event: tk.Event):
        if self.session.active_component_idx is not None:
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

        ac_type, ac_idx = self.session.active_component_idx

        component_dict: dict[Literal["glyph", "subcharacter"], zip[tuple[Glyph | Character, tuple[tuple[float, float], tuple[float, float]]]]] = {
            "glyph": zip(character.glyphs, character.glyph_extents),
            "subcharacter": zip(character.subcharacters, character.subcharacter_extents)
            }

        for component_type, component_tuple in component_dict.items():
            for idx, (component, extent) in enumerate(component_tuple):
                (x0, y0), (x1, y1) = extent
                left, top = x0 * self.session.CANVAS_SIZE, y0 * self.session.CANVAS_SIZE
                right, bottom = x1 * self.session.CANVAS_SIZE, y1 * self.session.CANVAS_SIZE

                active = component_type == ac_type and idx == ac_idx

                self.canvas.create_rectangle(
                    left, top, right, bottom,
                    outline="#d44" if active else "#666",
                    width=3 if active else 1
                )

                width, height = right - left, bottom - top

                if component_type == "glyph":
                    for stroke in component.strokes:
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
                else:
                    subcharacter_label = f"Character:\n{component.definition[0][1]}"
                    self.canvas.create_text(
                        left + (right - left) / 2,
                        top + (bottom - top) / 2,
                        text = subcharacter_label
                    )
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