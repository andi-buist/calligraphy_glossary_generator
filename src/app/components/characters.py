import tkinter as tk
from tkinter import ttk
import typing

from src.app.components.session import CharacterEditorSession
from src.symbols.characters.base import CHARACTER_TYPES

class CharacterDefinitions(tk.Frame):
    def __init__(self, parent, session: CharacterEditorSession):
        super().__init__(parent)
        self.session: CharacterEditorSession=session
        self.columnconfigure(0, weight=1)

        remove_character_button=tk.Button(self, text="Remove Character", command=lambda hash=self.session.character_hash: self.session.remove_character(hash))
        remove_character_button.pack(fill="x", side="bottom")

        self.entries_frame = tk.Frame(self)
        self.entries_frame.columnconfigure(0, weight=1)
        self.entries_frame.columnconfigure(1, weight=3)
        self.entries_frame.columnconfigure(2, weight=3)

        character_defs_increase=tk.Button(self, command=self.add_character_def, text="+")
        character_defs_increase.pack(fill="x")
        self.entries_frame.pack(fill="both", expand=True)

        self.refresh()

    def refresh(self):
        for child in self.entries_frame.winfo_children():
            child.destroy()

        for idx in range(len(self.session.character_defs_vars)):
            tk.Label(self.entries_frame, text=f"Def {idx}:").grid(column=0, row=idx)
            entry_type_field=tk.OptionMenu(
                self.entries_frame,
                self.session.character_defs_vars[idx][0],
                *typing.get_args(CHARACTER_TYPES)
                )
            entry_type_field.grid(column=1, row=idx, sticky="EW")
            entry_def_field=ttk.Entry(self.entries_frame, textvariable=self.session.character_defs_vars[idx][1])
            entry_def_field.bind("<Return>", self.session.update_treeview)
            entry_def_field.grid(column=2, row=idx, sticky="EW")

            if idx > 0:
                remove_def_button=tk.Button(self.entries_frame, text="-", command=lambda idx=idx: self.remove_character_def(idx))
                remove_def_button.grid(column=3, row=idx)

    def add_character_def(self):
        type_var=tk.StringVar(self.session.master, value=self.session.character_defs_vars[-1][0].get())
        definition_var=tk.StringVar(self.session.master, value="")
        self.session.character_defs_vars.append((type_var, definition_var))

        self.session.commit_active_character_to_memory()
        self.session.refresh("metadata")
        self.refresh()

    def remove_character_def(self, idx: int):
        _=self.session.character_defs_vars.pop(idx)

        self.session.commit_active_character_to_memory()
        self.session.refresh("metadata")
        self.refresh()

class CharacterPreview(tk.Frame):
    def __init__(self, parent, session: CharacterEditorSession):
        self.session = session

        super().__init__(parent)
        self.columnconfigure(0, weight=1)

        self.refresh()

    def refresh(self):
        for child in self.winfo_children():
            child.destroy()

        if self.session.character_object_cache is None:
            return

        tk.Label(self, text="Rendered Glyph").grid(column=0, row=0, sticky="NEW")
        image_label=tk.Label(
            self,
            image=self.session.character_object_cache[1],
            highlightthickness=1,
            highlightbackground="black",
        )
        image_label.grid(column=0, row=1)