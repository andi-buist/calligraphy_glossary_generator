import tkinter as tk
from tkinter import messagebox, ttk

from src.app.components.session import AppSession
from src.app.components.hierarchies import StrokeHierarchy, CharacterHierarchy
from src.app.components.characters import CharacterDefinitions, CharacterPreview
from src.app.components.strokes import StrokeEditor

class EditorApp(tk.Frame):
    def __init__(self, parent):
        self.session = AppSession(parent)

        super().__init__(parent)

        self.glossary_editor = CharacterEditor(self, self.session)
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


class CharacterEditor(tk.Frame):
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
        self.columnconfigure(0, weight=2)
        self.columnconfigure(1, weight=3)
        self.columnconfigure(2, weight=1)
        self.rowconfigure(0, weight=1)

        self.left_pane=tk.Frame(
            self,
            padx=4,
            pady=4,
            highlightthickness=1,
            highlightbackground="black",
        )
        self.left_pane.grid(column=0, row=0, sticky="NSEW", padx=12)

        self.character_hierarchy = CharacterHierarchy(self.left_pane, self.session)
        self.character_hierarchy.pack(fill="both")

        ttk.Separator(self.left_pane).pack(fill="x", pady=8)

        self.character_definitions = CharacterDefinitions(self.left_pane, self.session)
        self.character_definitions.pack(fill="both", expand=True)

        self.stroke_editor = StrokeEditor(self, self.session)
        self.stroke_editor.grid(column=1, row=0, sticky="NSEW", padx=12)

        self.right_pane=tk.Frame(
            self,
            padx=4,
            pady=4,
            highlightthickness=1,
            highlightbackground="black"
            )
        self.right_pane.columnconfigure(0, weight=1)
        self.right_pane.grid(column=2, row=0, sticky="NSEW", padx=12)

        self.stroke_hierarchy = StrokeHierarchy(self.right_pane, self.session)
        self.stroke_hierarchy.pack(expand=True, fill="both")
        self.character_preview = CharacterPreview(self.right_pane, self.session)
        self.character_preview.pack(fill="both", pady=8)

    def _rebuild_character_fields(self):
        self.character_definitions.destroy()
        self.character_definitions = CharacterDefinitions(self.left_pane, self.session)
        self.character_definitions.pack(fill="both", expand=True)

    def refresh(self, change: str = "all"):
        match change:
            case "list":
                self.character_hierarchy.refresh()
            case "metadata":
                self.character_hierarchy.update_active_entry()
            case "preview":
                self.character_preview.refresh()
            case _:
                if change in ("selection", "all"):
                    self._rebuild_character_fields()
                    self.character_hierarchy.refresh()
                self.stroke_editor.refresh()
                self.stroke_hierarchy.refresh()
                self.character_preview.refresh()

class CompoundEditor(tk.Frame):
    def __init__(self, parent: tk.Misc, session: AppSession):
        self.session = session
        self.refresh_count: int = 0

        super().__init__(parent, padx=24, pady=24)
        self._build_layout()
        self.session.on_change.append(self.refresh)

        self.refresh()

    def _build_layout(self):
        for child in self.winfo_children():
            child.destroy()

        self.test_label=tk.Label(self, text="")
        self.test_label.grid(column=0, row=0, sticky="NEW")

    def refresh(self, change: str = "all"):
        match change:
            case _:
                self.test_label.config(text=f"{self.refresh_count} refreshes")
                self.refresh_count+=1