import os
import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk
import typing
from bidict import bidict
import secrets

from src.app.components.session import AppSession
from src.symbols.characters import CHARACTER_TYPES, Character, Glyph

TREEVIEW_ICONS_FP="src/app/icons"

def build_treeview_icons(parent: tk.Misc):
    treeview_icons = {}
    for fp in os.listdir(TREEVIEW_ICONS_FP):
        if fp.endswith(".png"):
            with Image.open(os.path.join(TREEVIEW_ICONS_FP, fp)) as temp_image:
                treeview_icons[fp.removesuffix(".png")] = ImageTk.PhotoImage(temp_image.copy(), parent)

    return treeview_icons

class GlossaryHierarchy(tk.Frame):
    """Tree-based glossary browser shared by character and glyph entries."""

    DEFAULT_DIRECTORY_NAME = "unassigned"

    def __init__(self, parent, session: AppSession):
        self.session = session
        self.treeview_icons = build_treeview_icons(parent)
        self.tree_id_to_hash: dict[str, str] = {}
        self.directory_tree_ids: bidict[str, str] = bidict()

        super().__init__(parent)

        tk.Button(self, text="+ Add new entry", command=self.add_entry).pack(fill="x")
        self._build_extra_controls()

        tree_frame = ttk.Frame(self)
        tree_frame.pack(fill="both", expand=True)
        tree_frame.rowconfigure(0, weight=1)
        tree_frame.columnconfigure(0, weight=1)

        self.dictionary_treeview = ttk.Treeview(
            tree_frame,
            columns=("detail",),
            height=16,
        )
        self.dictionary_treeview.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(
            tree_frame,
            orient="vertical",
            command=self.dictionary_treeview.yview,
        )
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.dictionary_treeview.configure(yscrollcommand=scrollbar.set)
        self.dictionary_treeview.bind("<<TreeviewSelect>>", self.select_tree_item)
        self.dictionary_treeview.bind("<ButtonPress-2>", self.middleclick_entry)

        self._build_below_tree()
        self.refresh()

    def _build_extra_controls(self) -> None:
        pass

    def _refresh_extra_controls(self) -> None:
        pass

    def _build_below_tree(self) -> None:
        pass

    def _ensure_group(
        self,
        group_path: tuple[str, ...],
        label: str | None = None,
    ) -> str:
        parent_tree_id = ""
        current_path: list[str] = []
        for index, part in enumerate(group_path):
            current_path.append(part)
            path = "/".join(current_path)
            if path not in self.directory_tree_ids:
                tree_id = self.dictionary_treeview.insert(
                    parent_tree_id,
                    tk.END,
                    text=(
                        label
                        if label is not None and index == len(group_path) - 1
                        else part.title()
                    ),
                    open=True,
                    tags=("folder",),
                )
                self.directory_tree_ids[path] = tree_id
            parent_tree_id = self.directory_tree_ids[path]
        return parent_tree_id

    def _row_for_index_path(
        self,
        index_path: str | None,
    ) -> tuple[tuple[str, ...], str]:
        path_parts = [part for part in (index_path or "").split("/") if part]
        if path_parts and path_parts[0] == self.DEFAULT_DIRECTORY_NAME:
            path_parts.pop(0)
        if path_parts:
            return (
                tuple(path_parts[:-1]) or (self.DEFAULT_DIRECTORY_NAME,),
                path_parts[-1],
            )
        return ((self.DEFAULT_DIRECTORY_NAME,), "")

    def refresh(self) -> None:
        tv = self.dictionary_treeview
        tv.delete(*tv.get_children())
        self.tree_id_to_hash.clear()
        self.directory_tree_ids = bidict()

        tv.heading("#0", text=self.entry_type_label)
        tv.heading("detail", text=self.detail_column_label)
        tv.tag_configure("folder", image=self.treeview_icons["folder"])
        tv.tag_configure(
            "selected",
            background="#b2cdec",
            image=self.treeview_icons["editing"],
        )

        for path, label in self._root_groups().items():
            self._ensure_group(path, label)

        entry_rows = []
        for entry_hash, entry in self._entries().items():
            for group_path, detail in self._rows_for_entry(entry):
                if isinstance(entry, Character):
                    definition_rows = entry.definition or [("", "")]
                    for index, (definition_type, definition) in enumerate(definition_rows):
                        entry_rows.append(
                            (
                                entry_hash,
                                (*group_path, detail) if detail else group_path,
                                entry_hash if index == 0 else "",
                                f"{definition_type}: {definition}" if definition_type else "",
                            )
                        )
                else:
                    entry_rows.append(
                        (entry_hash, group_path, entry_hash, detail)
                    )

        for _, group_path, _, _ in entry_rows:
            self._ensure_group(group_path)

        for entry_hash, group_path, row_text, detail in entry_rows:
            parent_tree_id = self._ensure_group(group_path)
            tags = ("selected",) if self._is_selected(entry_hash) else ("unselected",)
            tree_id = tv.insert(
                parent_tree_id,
                tk.END,
                text=row_text,
                values=(detail,),
                tags=tags,
            )
            self.tree_id_to_hash[tree_id] = entry_hash

        self._refresh_extra_controls()

    def update_active_entry(self) -> None:
        self.session.commit_active_character_to_memory()
        self.refresh()

    def select_tree_item(self, _event: tk.Event) -> None:
        selection = self.dictionary_treeview.selection()
        if selection and selection[0] in self.tree_id_to_hash:
            self._select_entry(self.tree_id_to_hash[selection[0]])

    def middleclick_entry(self, event: tk.Event) -> None:
        tree_id = self.dictionary_treeview.identify("item", event.x, event.y)
        entry_hash = self.tree_id_to_hash.get(tree_id)
        if entry_hash is not None:
            self.add_entry(self._clone_entry(self._entries()[entry_hash]))

    def add_entry(self, entry=None) -> None:
        group_key = self.directory_tree_ids.inverse.get(
            self.dictionary_treeview.focus(),
        )
        group_path = tuple(group_key.split("/")) if group_key else self._default_group_path()

        if entry is None:
            entry = self._create_entry(group_path)

        entries = self._entries()
        entry_hash = secrets.token_hex(8)
        while entry_hash in entries:
            entry_hash = secrets.token_hex(8)

        entries[entry_hash] = entry
        self._select_entry(entry_hash)
        self.session.export_glossary_json()

class GlyphHierarchy(GlossaryHierarchy):
    DEFAULT_DIRECTORY_NAME = "unassigned"

    def _build_extra_controls(self) -> None:
        index_path_row = ttk.Frame(self)
        index_path_row.pack(fill="x", pady=4)
        ttk.Label(index_path_row, text="Index path:").pack(side="left")
        self.index_path_var = tk.StringVar()
        self.index_path_var.trace_add("write", self.update_index_path)
        self.index_path_entry = ttk.Entry(
            index_path_row,
            textvariable=self.index_path_var,
            state="normal",
            takefocus=True,
        )
        self.index_path_entry.pack(side="left", fill="x", expand=True)
        self.index_path_entry.bind("<Return>", self.save_index_path)
        ttk.Button(index_path_row, text="Save", command=self.save_index_path).pack(side="left")

    def _build_below_tree(self) -> None:
        ttk.Label(self, text="Character users").pack(anchor="w", pady=(6, 0))
        users_frame = ttk.Frame(self)
        users_frame.pack(fill="x")
        self.character_users_list = tk.Listbox(
            users_frame,
            height=4,
            exportselection=False,
        )
        self.character_users_list.pack(side="left", fill="both", expand=True)
        users_scrollbar = ttk.Scrollbar(
            users_frame,
            orient="vertical",
            command=self.character_users_list.yview,
        )
        users_scrollbar.pack(side="right", fill="y")
        self.character_users_list.configure(yscrollcommand=users_scrollbar.set)
        tk.Button(
            self,
            text="Remove Glyph",
            command=self.remove_active_glyph,
        ).pack(fill="x", side="bottom")

    def _entries(self) -> dict[str, Glyph]:
        return self.session.glyph_glossary_data

    def _root_groups(self) -> dict[tuple[str, ...], str]:
        return {(self.DEFAULT_DIRECTORY_NAME,): self.DEFAULT_DIRECTORY_NAME.title()}

    def _rows_for_entry(
        self,
        entry: Glyph,
    ) -> list[tuple[tuple[str, ...], str]]:
        return [self._row_for_index_path(entry.index_path)]

    def _default_group_path(self) -> tuple[str, ...]:
        return (self.DEFAULT_DIRECTORY_NAME,)

    def _is_selected(self, entry_hash: str) -> bool:
        return entry_hash == self.session.active_glyph_hash

    def _select_entry(self, entry_hash: str) -> None:
        self.session.select_glyph_by_hash(entry_hash)

    def _clone_entry(self, entry: Glyph) -> Glyph:
        return entry.clone()

    def _create_entry(self, group_path: tuple[str, ...]) -> Glyph:
        glyph = Glyph.DEFAULT.clone()
        detail_path = (
            ()
            if group_path == self._default_group_path()
            else group_path
        )
        glyph.index_path = "/".join((*detail_path, "example"))
        return glyph

    def _refresh_extra_controls(self) -> None:
        glyph_hash = self.session.active_glyph_hash
        glyph = self.session.glyph_glossary_data.get(glyph_hash) if glyph_hash else None
        self.index_path_var.set(glyph.index_path if glyph is not None else "")
        self.character_users_list.delete(0, tk.END)
        if glyph is None:
            return

        for character_hash, character in self.session.character_glossary_data.items():
            if any(component is glyph for component in character.glyphs):
                detail = (
                    character.definition[0][1]
                    if character.definition
                    else "(no definition)"
                )
                self.character_users_list.insert(
                    tk.END,
                    f"{character_hash}: {detail}",
                )

    def remove_active_glyph(self) -> None:
        glyph_hash = self.session.active_glyph_hash
        if glyph_hash is not None:
            self.session.remove_glyph(glyph_hash)

    def save_index_path(self, _event: tk.Event | None = None) -> None:
        glyph_hash = self.session.active_glyph_hash
        if glyph_hash is None:
            return
        index_path = self.index_path_var.get().strip()
        self.session.glyph_glossary_data[glyph_hash].index_path = index_path
        self.session.refresh("glyphs")

    def update_index_path(self, *_):
        glyph_hash = self.session.active_glyph_hash
        if glyph_hash is not None:
            self.session.glyph_glossary_data[glyph_hash].index_path = self.index_path_var.get()

    @property
    def entry_type_label(self) -> str:
        return "Glyph"

    @property
    def detail_column_label(self) -> str:
        return "Index path"


class CharacterHierarchy(GlossaryHierarchy):
    DEFAULT_DIRECTORY_NAME = "unassigned"

    def _build_extra_controls(self) -> None:
        index_path_row = ttk.Frame(self)
        index_path_row.pack(fill="x", pady=4)
        ttk.Label(index_path_row, text="Index path:").pack(side="left")
        self.index_path_var = tk.StringVar()
        self.index_path_var.trace_add("write", self.update_index_path)
        self.index_path_entry = ttk.Entry(
            index_path_row,
            textvariable=self.index_path_var,
            state="normal",
            takefocus=True,
        )
        self.index_path_entry.pack(side="left", fill="x", expand=True)
        self.index_path_entry.bind("<Return>", self.save_index_path)
        ttk.Button(index_path_row, text="Save", command=self.save_index_path).pack(side="left")

    def _entries(self) -> dict[str, Character]:
        return self.session.character_glossary_data

    def _root_groups(self) -> dict[tuple[str, ...], str]:
        return {(self.DEFAULT_DIRECTORY_NAME,): self.DEFAULT_DIRECTORY_NAME.title()}

    def _rows_for_entry(
        self,
        entry: Character,
    ) -> list[tuple[tuple[str, ...], str]]:
        path_parts = [part for part in entry.index_path.split("/") if part]
        if len(path_parts) == 1 and path_parts[0] != self.DEFAULT_DIRECTORY_NAME:
            return [(tuple(path_parts), "")]
        return [self._row_for_index_path(entry.index_path)]

    def _default_group_path(self) -> tuple[str, ...]:
        return (self.DEFAULT_DIRECTORY_NAME,)

    def _is_selected(self, entry_hash: str) -> bool:
        return entry_hash == self.session.active_character_hash

    def _select_entry(self, entry_hash: str) -> None:
        self.session.select_character(entry_hash)

    def _clone_entry(self, entry: Character) -> Character:
        return entry.clone()

    def _create_entry(self, group_path: tuple[str, ...]) -> Character:
        index_path = (
            ()
            if group_path == self._default_group_path()
            else group_path
        )
        return Character(
            definition=[(typing.get_args(CHARACTER_TYPES)[0], "example definition")],
            index_path="/".join((*index_path, "example")),
        )

    def _refresh_extra_controls(self) -> None:
        character_hash = self.session.active_character_hash
        character = (
            self.session.character_glossary_data.get(character_hash)
            if character_hash
            else None
        )
        self.index_path_var.set(character.index_path if character is not None else "")

    def save_index_path(self, _event: tk.Event | None = None) -> None:
        character_hash = self.session.active_character_hash
        if character_hash is None:
            return
        index_path = self.index_path_var.get().strip()
        self.session.character_glossary_data[character_hash].index_path = index_path
        self.session.refresh("metadata")

    def update_index_path(self, *_):
        character_hash = self.session.active_character_hash
        if character_hash is not None:
            self.session.character_glossary_data[character_hash].index_path = (
                self.index_path_var.get()
            )

    @property
    def entry_type_label(self) -> str:
        return "Character"

    @property
    def detail_column_label(self) -> str:
        return "Definition(s)"

class CharacterComponentHierarchy(tk.Frame):
    def __init__(
        self,
        parent,
        session: AppSession,
        on_page_change: typing.Callable[[str], None],
    ):
        self.session: AppSession=session
        self.on_page_change = on_page_change

        self.tree_id_to_glyph_idx: dict[str, int] = {}
        self.tree_id_to_subcharacter_idx: dict[str, int] = {}

        super().__init__(parent)
        self.treeview_icons: dict[str, ImageTk.PhotoImage]=build_treeview_icons(self)

        # Defining glyph detail information --------
        self.index_path_var = tk.StringVar()
        detail_row = tk.Frame(self)
        detail_row.pack(fill="x", pady=4)
        tk.Label(detail_row, text="Index path:").pack(side="left")
        self.index_path_entry = ttk.Entry(
            detail_row,
            textvariable=self.index_path_var,
        )
        self.index_path_entry.pack(side="left", fill="x", expand=True)
        self.index_path_entry.bind("<Return>", self.save_index_path)
        self.index_path_entry.bind("<FocusOut>", self.save_index_path)

        # Main body --------
        tree_frame = ttk.Frame(self)
        tree_frame.pack(expand=True, fill="both")
        tree_frame.rowconfigure(0, weight=1)
        tree_frame.columnconfigure(0, weight=1)

        self.treeview = ttk.Treeview(tree_frame, show="tree")
        self.treeview.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(
            tree_frame,
            orient="vertical",
            command=self.treeview.yview,
        )
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.treeview.configure(yscrollcommand=scrollbar.set)
        self.treeview.bind("<<TreeviewSelect>>", self.select_tree_item)
        self.treeview.bind("<Double-1>", self.open_component)

        tk.Button(self, text="Remove Glyph/Subcharacter", command=self.session.remove_active_component_from_character).pack(fill="x")

        self.refresh()

    def refresh(self):
        """
        Shows the active character's glyph instances and their contained strokes.
        """
        tv: ttk.Treeview = self.treeview
        tv.delete(*tv.get_children())

        self.tree_id_to_glyph_idx.clear()
        self.tree_id_to_subcharacter_idx.clear()

        if self.session.active_hierarchy_idx is None:
            ac_type, ac_idx = None, None
        else:
            ac_type, ac_idx = self.session.active_hierarchy_idx

        glyph_hash_by_identity = {
            id(glyph): glyph_hash
            for glyph_hash, glyph in self.session.glyph_glossary_data.items()
        }

        subcharacter_hash_by_identity = {
            id(character): character_hash
            for character_hash, character in self.session.character_glossary_data.items()
        }

        tv.tag_configure("glyph", font=("TkDefaultFont", 9, "italic"), image=self.treeview_icons["glyphpage"])
        tv.tag_configure("subcharacter", font=("TkDefaultFont", 9, "bold"), image=self.treeview_icons["characterpage"])

        for glyph_idx, glyph in enumerate(self.session.active_character.glyphs):
            glyph_hash = glyph_hash_by_identity[id(glyph)]
            glyph_item = tv.insert(
                "",
                tk.END,
                text=(
                    f"Glyph '{glyph.index_path}'"
                    if glyph.index_path
                    else f"Glyph {glyph_hash}"
                ),
                open=True,
                tags=tuple(
                    tag
                    for tag, enabled in (
                        ("glyph", True),
                        ("selected", ac_type == "glyph" and glyph_idx == ac_idx)
                    )
                    if enabled
                ),
            )
            self.tree_id_to_glyph_idx[glyph_item] = glyph_idx


        for subcharacter_idx, subcharacter in enumerate(self.session.active_character.subcharacters):
            subcharacter_hash = subcharacter_hash_by_identity[id(subcharacter)]
            subcharacter_item = tv.insert(
                "",
                tk.END,
                text=(
                    f"Subcharacter '{subcharacter.definition[0][1]}'"
                    if subcharacter.definition is not None
                    else f"Subcharacter {subcharacter_hash}"
                ),
                tags=tuple(
                    tag
                    for tag, enabled in (
                        ("subcharacter", True),
                        ("selected", ac_type == "subcharacter" and subcharacter_idx == ac_idx)
                    )
                    if enabled
                ),
            )
            self.tree_id_to_subcharacter_idx[subcharacter_item] = subcharacter_idx

        if ac_type == "glyph":
            self.index_path_var.set(self.session.active_component.index_path or "")
        else:
            self.index_path_var.set("")
        tv.tag_configure("selected", background="#b2cdec")

    def open_component(self, event: tk.Event):
        item = self.treeview.identify("item", event.x, event.y)
        if item in self.tree_id_to_glyph_idx:
            glyph = self.session.active_character.glyphs[
                self.tree_id_to_glyph_idx[item]
            ]
            glyph_hash = next(
                (
                    hash
                    for hash, candidate in self.session.glyph_glossary_data.items()
                    if candidate is glyph
                ),
                None,
            )
            if glyph_hash is not None:
                self.session.select_glyph_by_hash(glyph_hash)
                self.on_page_change("Glyph")
        elif item in self.tree_id_to_subcharacter_idx:
            subcharacter = self.session.active_character.subcharacters[
                self.tree_id_to_subcharacter_idx[item]
            ]
            character_hash = next(
                (
                    hash
                    for hash, candidate in self.session.character_glossary_data.items()
                    if candidate is subcharacter
                ),
                None,
            )
            if character_hash is not None:
                self.session.select_character(character_hash)
                self.on_page_change("Character")

    def save_index_path(self, _event: tk.Event | None = None):
        if (
            self.session.active_hierarchy_idx is not None
            and self.session.active_hierarchy_idx[0] == "glyph"
        ):
            index_path = self.index_path_var.get().strip()
            self.session.active_component.index_path = index_path
            self.session.refresh("glyphs")

    def select_tree_item(self, _event: tk.Event):
        selection = self.treeview.selection()
        if not selection:
            return
        item = selection[0]
        if item in self.tree_id_to_glyph_idx:
            self.session.select_glyph(self.tree_id_to_glyph_idx[item])
        elif item in self.tree_id_to_subcharacter_idx:
            self.session.select_subcharacter(self.tree_id_to_subcharacter_idx[item])
        else:
            return

        if self.session.active_hierarchy_idx[0] == "glyph":
            self.index_path_var.set(self.session.active_component.index_path or "")
        else:
            self.index_path_var.set("")


class GlyphStrokeHierarchy(tk.Frame):
    def __init__(self, parent, session: AppSession):
        self.session = session
        self._refreshing = False

        super().__init__(parent)

        ttk.Label(self, text="Glyph Strokes").pack(anchor="w")
        list_frame = ttk.Frame(self)
        list_frame.pack(fill="both", expand=True)
        self.stroke_list = tk.Listbox(
            list_frame,
            height=12,
            exportselection=False,
        )
        self.stroke_list.pack(side="left", fill="both", expand=True)
        scrollbar = ttk.Scrollbar(
            list_frame,
            orient="vertical",
            command=self.stroke_list.yview,
        )
        scrollbar.pack(side="right", fill="y")
        self.stroke_list.configure(yscrollcommand=scrollbar.set)
        self.stroke_list.bind("<<ListboxSelect>>", self.select_stroke)

        buttons = ttk.Frame(self)
        buttons.pack(fill="x", pady=(4, 0))
        self.add_stroke_button = ttk.Button(
            buttons,
            text="Add Stroke",
            command=self.add_stroke,
        )
        self.add_stroke_button.pack(
            side="left",
            fill="x",
            expand=True,
        )
        self.remove_stroke_button = ttk.Button(
            buttons,
            text="Remove Stroke",
            command=self.session.remove_active_stroke,
        )
        self.remove_stroke_button.pack(side="left", fill="x", expand=True)
        self.refresh()

    def refresh(self):
        glyph = self.session.active_glyph
        self._refreshing = True
        self.stroke_list.delete(0, tk.END)

        if glyph is not None:
            for idx, stroke in enumerate(glyph.strokes):
                self.stroke_list.insert(
                    tk.END,
                    f"Stroke {idx + 1} ({len(stroke.control_points)} points)",
                )
            self.stroke_list.insert(tk.END, "New stroke")

            active_index = min(
                self.session.active_glyph_stroke_idx,
                len(glyph.strokes),
            )
            self.stroke_list.selection_set(active_index)
            self.stroke_list.see(active_index)
            self.add_stroke_button.configure(state="normal")
            self.remove_stroke_button.configure(
                state=(
                    "normal"
                    if len(glyph.strokes) > 1
                    and active_index < len(glyph.strokes)
                    else "disabled"
                )
            )
        else:
            self.add_stroke_button.configure(state="disabled")
            self.remove_stroke_button.configure(state="disabled")

        self._refreshing = False

    def select_stroke(self, _event: tk.Event):
        if self._refreshing:
            return
        selection = self.stroke_list.curselection()
        if selection and self.session.active_glyph is not None:
            self.session.select_stroke(selection[0])

    def add_stroke(self):
        if self.session.active_glyph is not None:
            self.session.select_stroke(len(self.session.active_glyph.strokes))
