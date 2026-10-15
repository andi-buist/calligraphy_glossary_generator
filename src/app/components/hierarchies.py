import os
import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk
import typing
from bidict import bidict
import secrets

from src.app.components.session import AppSession
from src.symbols.characters import CHARACTER_TYPES, Character

TREEVIEW_ICONS_FP="src/app/icons"

def build_treeview_icons(parent: tk.Misc):
    treeview_icons = {}
    for fp in os.listdir(TREEVIEW_ICONS_FP):
        if fp.endswith(".png"):
            with Image.open(os.path.join(TREEVIEW_ICONS_FP, fp)) as temp_image:
                treeview_icons[fp.removesuffix(".png")] = ImageTk.PhotoImage(temp_image.copy(), parent)

    return treeview_icons

class GlyphHierarchy(tk.Frame):
    def __init__(self, parent, session: AppSession):
        self.session: AppSession=session
        super().__init__(parent)

        self.glyph_detail_var = tk.StringVar()
        detail_row = tk.Frame(self)
        detail_row.pack(fill="x", pady=4)
        tk.Label(detail_row, text="Name:").pack(side="left")
        self.glyph_detail_entry = ttk.Entry(
            detail_row,
            textvariable=self.glyph_detail_var,
        )
        self.glyph_detail_entry.pack(side="left", fill="x", expand=True)
        self.glyph_detail_entry.bind("<Return>", self.save_glyph_detail)
        self.glyph_detail_entry.bind("<FocusOut>", self.save_glyph_detail)

        self.treeview = ttk.Treeview(self, show="tree")
        self.treeview.pack(expand=True, fill="both")
        self.treeview.bind("<<TreeviewSelect>>", self.select_tree_item)
        self.tree_id_to_glyph_idx: dict[str, int] = {}
        self.tree_id_to_stroke_idx: dict[str, tuple[int, int]] = {}

        self.refresh()

    def refresh(self):
        """
        Shows the active character's glyph instances and their contained strokes.
        """
        tv: ttk.Treeview = self.treeview
        tv.delete(*tv.get_children())
        self.tree_id_to_glyph_idx.clear()
        self.tree_id_to_stroke_idx.clear()

        glyph_hash_by_identity = {
            id(glyph): glyph_hash
            for glyph_hash, glyph in self.session.glyph_glossary_data.items()
        }
        tv.tag_configure("named-glyph", font=("TkDefaultFont", 9, "italic"))
        for glyph_idx, glyph in enumerate(self.session.active_character.glyphs):
            glyph_hash = glyph_hash_by_identity[id(glyph)]
            glyph_item = tv.insert(
                "",
                tk.END,
                text=(
                    f"Glyph '{glyph.detail}'"
                    if glyph.detail is not None
                    else f"Glyph {glyph_hash}"
                ),
                open=True,
                tags=tuple(
                    tag
                    for tag, enabled in (
                        ("selected", glyph_idx == self.session.active_glyph_idx),
                        ("named-glyph", glyph.detail is not None),
                    )
                    if enabled
                ),
            )
            self.tree_id_to_glyph_idx[glyph_item] = glyph_idx
            for stroke_idx in range(len(glyph.strokes)):
                stroke_item = tv.insert(
                    glyph_item,
                    tk.END,
                    text=f"Stroke {stroke_idx + 1}",
                    tags=(
                        ("selected",)
                        if glyph_idx == self.session.active_glyph_idx
                        and stroke_idx == self.session.active_stroke_idx
                        else ()
                    ),
                )
                self.tree_id_to_stroke_idx[stroke_item] = (glyph_idx, stroke_idx)
        self.glyph_detail_var.set(self.session.active_glyph.detail or "")
        tv.tag_configure("selected", background="#b2cdec")

    def save_glyph_detail(self, _event: tk.Event | None = None):
        detail = self.glyph_detail_var.get().strip()
        self.session.active_glyph.detail = detail or None
        self.refresh()

    def select_tree_item(self, _event: tk.Event):
        selection = self.treeview.selection()
        if not selection:
            return
        item = selection[0]
        if item in self.tree_id_to_stroke_idx:
            glyph_idx, stroke_idx = self.tree_id_to_stroke_idx[item]
            self.session.select_glyph(
                glyph_idx,
                stroke_idx=(
                    stroke_idx
                    if self.session.current_page == "Glyph"
                    else None
                ),
            )
        elif item in self.tree_id_to_glyph_idx:
            self.session.select_glyph(self.tree_id_to_glyph_idx[item])
        else:
            return
        self.glyph_detail_var.set(self.session.active_glyph.detail or "")

class CharacterHierarchy(tk.Frame):
    def __init__(self, parent, session: AppSession):
        self.session: AppSession=session
        self.treeview_icons: dict[str, ImageTk.PhotoImage]=build_treeview_icons(self)

        self.last_tree_id: str=None

        self.tree_id_to_character_hash: dict[str,str]={}
        self.character_type_tree_ids: bidict[str, str]=bidict({}) # bidict so we can lookup {character_type <-> tree_id}

        super().__init__(parent)

        tk.Button(self, text="+ Add new entry", command=self.add_entry).pack(fill="x")

        self.dictionary_treeview=ttk.Treeview(self, columns=("defs"), height=16)
        self.dictionary_treeview.pack(fill="x")
        self.dictionary_treeview.bind("<ButtonPress-1>", self.leftclick_entry)
        self.dictionary_treeview.bind("<ButtonPress-2>", self.middleclick_entry)

        self.refresh()

    def refresh(self):
        """
        Constructs `Character.character_type` headers and places all glossary json items under respectively against hash.
        """
        # 1. Clear the treeview --------------------------------
        tv: ttk.Treeview=self.dictionary_treeview
        tv.delete(*tv.get_children())
        self.character_type_tree_ids=bidict({})

        tv.heading("#0", text="Character")
        tv.heading("defs", text="Definition(s)")

        tv.tag_configure('heading', image=self.treeview_icons["folder"])
        tv.tag_configure('selected', background="#b2cdec", image=self.treeview_icons["editing"])

        # 2. build the character_type groups first
        for heading in list(typing.get_args(CHARACTER_TYPES)):
            tree_id=tv.insert("",
                                tk.END,
                                text=f"{heading.title()}",
                                open=True,
                                tags=('heading',)
                                )
            self.character_type_tree_ids[heading]=tree_id

        # 3. add the character items
        for hash, item in self.session.character_glossary_data.items():
            row_tags = ('selected',) if hash == self.session.active_character_hash else ('unselected',)

            for char_type, char_def in item.definition:
                tree_id=tv.insert(self.character_type_tree_ids[char_type],
                                    tk.END,
                                    text=f"{hash}",
                                    values=(f"{char_def}",),
                                    tags=row_tags
                                    )
                self.tree_id_to_character_hash[tree_id]=hash

        if self.last_tree_id:
            tv.see(item=self.last_tree_id)

    def update_active_entry(self):
        self.session.commit_active_character_to_memory()
        self.refresh()

    def leftclick_entry(self, event: tk.Event):
        """
        Operation to perform on `self.dictionary_treeview` item doubleclick - assign to current view.
        """
        tv: ttk.Treeview=self.dictionary_treeview
        item=tv.identify("item", event.x, event.y)
        hash=self.tree_id_to_character_hash.get(item, None)
        if hash is not None:
            self.session.select_character(hash, save_current=True)

    def middleclick_entry(self, event: tk.Event):
        tv: ttk.Treeview=self.dictionary_treeview
        item=tv.identify("item", event.x, event.y)
        hash=self.tree_id_to_character_hash[item]

        if hash:
            character_to_clone = self.session.character_glossary_data[hash].clone()
            self.add_entry(character_to_clone)

    # TODO: add and remove need partially bringing out to be session methods
    def add_entry(self, character: Character = None):
        tv: ttk.Treeview=self.dictionary_treeview
        hash: str=secrets.token_hex(4)

        # quick check to ensure we don't overwrite an existing entry
        while hash in self.session.character_glossary_data.keys():
            hash=secrets.token_hex(4)

        if character is None:
            # if the user has a type selected, new entry should be placed here
            # otherwise, go with the active-character's type
            focus_character_type = self.character_type_tree_ids.inverse.get(tv.focus(), None)
            if focus_character_type is None:
                    focus_character_type = typing.get_args(CHARACTER_TYPES)[0]

            character = Character(definition=[(focus_character_type,"example definition")])

        self.session.character_glossary_data[hash]=character
        self.session.select_character(hash, save_current=True)
        self.session.export_glossary_json()