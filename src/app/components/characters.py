import tkinter as tk
from tkinter import ttk
import typing

from src.app.components.session import CharacterEditorSession
from src.symbols.characters.base import CHARACTER_TYPES

class CharacterType(tk.Frame):
    def __init__(self, parent, session: CharacterEditorSession):
        super().__init__(parent)
        self.session: CharacterEditorSession=session

        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=3)

        tk.Label(self, text="Type:").grid(column=0, row=0, sticky="NSEW")

        character_type_input=tk.OptionMenu(
            self,
            self.session.character_type_var,
            *typing.get_args(CHARACTER_TYPES),
        )
        character_type_input.grid(column=1, row=0, sticky="NSEW")

class CharacterDefinitions(tk.Frame):
    def __init__(self, parent, session: CharacterEditorSession):
        super().__init__(parent)
        self.session: CharacterEditorSession=session
        self.columnconfigure(0, weight=1)

        inc_dec_button_row=tk.Frame(self)
        inc_dec_button_row.columnconfigure(0, weight=1)
        inc_dec_button_row.columnconfigure(1, weight=1)
        inc_dec_button_row.grid(column=0, row=0, sticky="NEW")

        character_defs_decrease=tk.Button(inc_dec_button_row, command=lambda: self.add_or_remove_character_defs(-1), text="-")
        character_defs_increase=tk.Button(inc_dec_button_row, command=lambda: self.add_or_remove_character_defs(1), text="+")
        character_defs_decrease.grid(column=0, row=0, sticky="NSEW")
        character_defs_increase.grid(column=1, row=0, sticky="NSEW")

        self.entries_frame = tk.Frame(self)
        self.entries_frame.columnconfigure(0, weight=1)
        self.entries_frame.columnconfigure(1, weight=3)
        self.entries_frame.grid(column=0, row=1, sticky="NSEW")
        self.refresh()

    def refresh(self):
        for child in self.entries_frame.winfo_children():
            child.destroy()

        for idx in range(len(self.session.character_defs_vars)):
            tk.Label(self.entries_frame, text=f"Def {idx}:").grid(column=0, row=idx)
            entry_field=ttk.Entry(self.entries_frame, textvariable=self.session.character_defs_vars[idx])
            entry_field.grid(column=1, row=idx, sticky="EW")

    def add_or_remove_character_defs(self, value: int):
        if value > 0:
            definition_var=tk.StringVar(self.session.master, value="")
            definition_var.trace_add("write", self.session.update_treeview)
            self.session.character_defs_vars.append(definition_var)
        elif len(self.session.character_defs_vars) > 1:
            _ = self.session.character_defs_vars.pop()
        else:
            print(f"Character must have at least 1 definition")
            return
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