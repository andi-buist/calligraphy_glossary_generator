import tkinter as tk
from tkinter import messagebox, ttk

from src.app.components.session import AppSession
from src.app.components.hierarchies import CharacterHierarchy, CharacterComponentHierarchy
from src.app.components.characters import CharacterDefinitions, CharacterPreview
from src.app.components.character_editor import CharacterEditor
from src.app.components.glyph_editor import GlyphEditor

class EditorApp(tk.Frame):
    def __init__(self, parent):
        self.session = AppSession(parent)

        super().__init__(parent)

        self.glossary_editor = GlossaryEditor(self, self.session)
        self.glossary_editor.pack(fill="both", expand=True)

    def on_app_close(self):
        answer=messagebox.askyesno(
            "Exit",
            "Are you sure you want to exit?",
            parent=self.winfo_toplevel(),
        )
        if answer:
            self.session.export_glossary_json()
            self.winfo_toplevel().destroy()


class GlossaryEditor(tk.Frame):
    GRID_BREAKS = AppSession.GRID_BREAKS
    CELL_SIZE = AppSession.CELL_SIZE
    canvas_size = AppSession.CANVAS_SIZE

    def __init__(self, parent: tk.Misc, session: AppSession):
        self.session = session

        super().__init__(parent, padx=24, pady=24)
        self._build_layout()
        self.session.on_change.append(self.refresh)

        self.refresh("all")

    def _build_layout(self):
        self.views=ttk.Notebook(self)
        self.views.pack(fill="both", padx=4, pady=4)
        self.views.bind("<<NotebookTabChanged>>", self.update_current_page)

        self.character_view=tk.Frame(self.views)
        self.glyph_view=tk.Frame(self.views)

        self.views.add(self.character_view, text="Character")
        self.views.add(self.glyph_view, text="Glyph")

        # Character Editor ---------
        self.character_view.columnconfigure(0, weight=2)
        self.character_view.columnconfigure(1, weight=3)
        self.character_view.columnconfigure(2, weight=1)
        self.character_view.rowconfigure(0, weight=1)

        self.character_left_pane=tk.Frame(
            self.character_view,
            padx=4,
            pady=4,
            highlightthickness=1,
            highlightbackground="black",
        )
        self.character_left_pane.grid(column=0, row=0, sticky="NSEW", padx=12)

        self.character_hierarchy = CharacterHierarchy(self.character_left_pane, self.session)
        self.character_hierarchy.pack(fill="both")

        ttk.Separator(self.character_left_pane).pack(fill="x", pady=8)

        self.character_definitions = CharacterDefinitions(self.character_left_pane, self.session)
        self.character_definitions.pack(fill="both", expand=True)

        self.character_editor = CharacterEditor(self.character_view, self.session)
        self.character_editor.grid(column=1, row=0, sticky="NSEW", padx=12)

        self.character_right_pane=tk.Frame(
            self.character_view,
            padx=4,
            pady=4,
            highlightthickness=1,
            highlightbackground="black"
            )
        self.character_right_pane.columnconfigure(0, weight=1)
        self.character_right_pane.grid(column=2, row=0, sticky="NSEW", padx=12)

        self.character_component_hierarchy = CharacterComponentHierarchy(self.character_right_pane, self.session)
        self.character_component_hierarchy.pack(expand=True, fill="both")
        self.character_preview = CharacterPreview(self.character_right_pane, self.session)
        self.character_preview.pack(fill="both", pady=8)


        # Glyph Editor ---------------
        self.glyph_view.columnconfigure(0, weight=2)
        self.glyph_view.columnconfigure(1, weight=3)
        self.glyph_view.columnconfigure(2, weight=1)
        self.glyph_view.rowconfigure(0, weight=1)

        self.glyph_left_pane=tk.Frame(
            self.glyph_view,
            padx=4,
            pady=4,
            highlightthickness=1,
            highlightbackground="black",
        )
        self.glyph_left_pane.grid(column=0, row=0, sticky="NSEW", padx=12)

        self.glyph_hierarchy = CharacterHierarchy(self.glyph_left_pane, self.session)
        self.glyph_hierarchy.pack(fill="both")

        ttk.Separator(self.glyph_left_pane).pack(fill="x", pady=8)

        self.glyph_definitions = CharacterDefinitions(self.glyph_left_pane, self.session)
        self.glyph_definitions.pack(fill="both", expand=True)

        self.glyph_editor = GlyphEditor(self.glyph_view, self.session)
        self.glyph_editor.grid(column=1, row=0, sticky="NSEW", padx=12)

        self.glyph_right_pane=tk.Frame(
            self.glyph_view,
            padx=4,
            pady=4,
            highlightthickness=1,
            highlightbackground="black"
            )
        self.glyph_right_pane.columnconfigure(0, weight=1)
        self.glyph_right_pane.grid(column=2, row=0, sticky="NSEW", padx=12)

        self.glyph_component_hierarchy = CharacterComponentHierarchy(self.glyph_right_pane, self.session)
        self.glyph_component_hierarchy.pack(expand=True, fill="both")
        self.glyph_preview = CharacterPreview(self.glyph_right_pane, self.session)
        self.glyph_preview.pack(fill="both", pady=8)

    def _rebuild_character_fields(self):
        self.character_definitions.refresh()

    def update_current_page(self, _event: tk.Event | None = None):
        self.session.current_page = self.views.tab(self.views.select(), "text")

    def refresh(self, change: str = "all"):
        match change:
            case "list":
                self.character_hierarchy.refresh()
            case "metadata":
                self.character_hierarchy.update_active_entry()
            case "preview":
                self.character_preview.refresh()
            case "selection" | "all":
                self._rebuild_character_fields()
                self.character_hierarchy.refresh()
                self.character_editor.refresh()
                self.glyph_editor.refresh()
                self.character_component_hierarchy.refresh()
                self.character_preview.refresh()
            case "glyphs":
                self.character_editor.refresh()
                self.glyph_editor.refresh()
                self.character_component_hierarchy.refresh()
                self.character_preview.refresh()
            case "glyph-selection":
                self.character_editor.refresh()
                self.glyph_editor.refresh()
                self.character_component_hierarchy.refresh()
            case "stroke":
                self.character_editor.refresh()
                self.glyph_editor.refresh()
                self.character_component_hierarchy.refresh()
                self.character_preview.refresh()
            case _:
                self.character_preview.refresh()