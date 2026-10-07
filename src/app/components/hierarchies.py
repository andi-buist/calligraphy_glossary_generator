import os
import copy
import tkinter as tk
from tkinter import messagebox, ttk
from PIL import Image, ImageTk
import typing
import secrets
from bidict import bidict

from src.app.components.session import CharacterEditorSession
from src.symbols.characters.base import CHARACTER_TYPES
from src.symbols.strokes import CurveProfile

TREEVIEW_ICONS_FP="src/app/icons"

def build_treeview_icons(parent: tk.Misc):
    treeview_icons = {}
    for fp in os.listdir(TREEVIEW_ICONS_FP):
        if fp.endswith(".png"):
            with Image.open(os.path.join(TREEVIEW_ICONS_FP, fp)) as temp_image:
                treeview_icons[fp.removesuffix(".png")] = ImageTk.PhotoImage(temp_image.copy(), parent)

    return treeview_icons

class StrokeHierarchy(tk.Frame):
    def __init__(self, parent, session: CharacterEditorSession):
        self.session: CharacterEditorSession=session
        self.treeview_icons: dict[str, ImageTk.PhotoImage]=build_treeview_icons(self)

        self.selected_stroke_idx:int=None

        self.stroke_tree_ids: bidict[int, str]=bidict({}) # bidict so we can lookup {hash <-> tree_id}

        super().__init__(parent)

        self.dictionary_treeview=ttk.Treeview(self, show="tree")
        self.dictionary_treeview.pack(expand=True, fill="both")
        self.dictionary_treeview.bind("<ButtonPress-1>", self.drag_stroke_item_start)
        self.dictionary_treeview.bind("<ButtonRelease-1>", self.drag_stroke_item_end)

        self.refresh()

    def refresh(self):
        """
        Constructs hierarchy of strokes in accordance with `self.session.character_stroke_parentage`.
        """
        # 1. Clear the treeview --------------------------------
        tv: ttk.Treeview=self.dictionary_treeview
        tv.delete(*tv.get_children())
        self.stroke_tree_ids=bidict({})

        tv.tag_configure('heading', image=self.treeview_icons["numpage"])
        tv.tag_configure('anchor', image=self.treeview_icons["anchor"])
        tv.tag_configure('selected', background="#b2cdec", image=self.treeview_icons["paint"])

        self.tree_root_id=tv.insert("",
                                    tk.END,
                                    text=f"root",
                                    open=True,
                                    tags=('heading',)
                                    )

        # 3. add the character items
        character_parentage=self.session.character_glossary_stroke_parentage_data[self.session.character_hash]
        all_parents=character_parentage.keys()
        all_children=[l1 for l0 in character_parentage.values() for l1 in l0]
        for idx, item in enumerate(self.session.character_stroke_control_points):
            if idx in all_parents:
                row_tags = ('anchor','selected') if idx == self.session.current_stroke_idx else ('anchor','unselected')
                parent_tree_id=tv.insert(self.tree_root_id,
                                tk.END,
                                text=f"{idx}",
                                open=True,
                                tags=row_tags
                                )
                self.stroke_tree_ids[idx]=parent_tree_id
                for cidx in character_parentage[idx]:
                    row_tags = ('selected',) if cidx == self.session.current_stroke_idx else ('unselected',)
                    child_tree_id=tv.insert(parent_tree_id,
                                    tk.END,
                                    text=f"{cidx}",
                                    open=True,
                                    tags=row_tags
                                    )
                    self.stroke_tree_ids[cidx]=child_tree_id
            elif idx not in all_children:
                row_tags = ('selected',) if idx == self.session.current_stroke_idx else ('unselected',)

                tree_id=tv.insert(self.tree_root_id,
                                tk.END,
                                text=f"{idx}",
                                tags=row_tags
                                )
                self.stroke_tree_ids[idx]=tree_id

        if self.session.current_stroke_idx in self.stroke_tree_ids:
            tv.see(item=self.stroke_tree_ids[self.session.current_stroke_idx])

    def drag_stroke_item_start(self, event: tk.Event):
        tv: ttk.Treeview=self.dictionary_treeview
        item=tv.identify("item", event.x, event.y)
        idx=self.stroke_tree_ids.inverse.get(item)
        if idx is not None:
            self.selected_stroke_idx=idx

    def drag_stroke_item_end(self, event: tk.Event):
        tv: ttk.Treeview=self.dictionary_treeview
        item=tv.identify("item", event.x, event.y)
        idx=self.stroke_tree_ids.inverse.get(item)
        if idx is not None:
            if idx == self.selected_stroke_idx:
                self.session.select_stroke(idx)
            else:
                self.parent_stroke(self.selected_stroke_idx, idx)
        elif item == self.tree_root_id:
            self.unparent_stroke(self.selected_stroke_idx)

    def parent_stroke(self, child_stroke_idx: int, parent_stroke_idx: int):
        current_character_parentage: dict[int, list[int]]=self.session.character_glossary_stroke_parentage_data[self.session.character_hash].copy()

        all_parents = current_character_parentage.keys()
        all_children = [l1 for l0 in current_character_parentage.values() for l1 in l0]
        if child_stroke_idx in all_parents:
            print(f"Cannot make a parent the child of another! Remove its children first if you want to do this.")
        elif parent_stroke_idx in all_children:
            print(f"Cannot make a child the parent of another! Remove its parent first if you want to do this.")
        else:
            # doesn't need to be a catch case for same -> same, as we unparent first anyway
            self.unparent_stroke(child_stroke_idx)

            parent_list = current_character_parentage.get(parent_stroke_idx,[])
            parent_list.append(child_stroke_idx)
            self.session.character_glossary_stroke_parentage_data[self.session.character_hash][parent_stroke_idx] = sorted(parent_list)

            print(f"Added child stroke {child_stroke_idx} to parent stroke {parent_stroke_idx}")
            self.refresh()

    def unparent_stroke(self, child_stroke_idx: int):
        current_character_parentage: dict[int, list[int]]=self.session.character_glossary_stroke_parentage_data[self.session.character_hash].copy()

        tmp_dict = {}
        for k,v in current_character_parentage.items():
            if child_stroke_idx in v:
                _ = v.pop(v.index(child_stroke_idx))
                print(f"Removed child stroke {child_stroke_idx} from parent stroke {k}")

            if len(v) > 0:
                tmp_dict[k] = v

        # assign a rebuilt dict, minus any 0-length list items
        self.session.character_glossary_stroke_parentage_data[self.session.character_hash] = tmp_dict
        self.refresh()

class CharacterHierarchy(tk.Frame):
    def __init__(self, parent, session: CharacterEditorSession):
        self.session: CharacterEditorSession=session
        self.treeview_icons: dict[str, ImageTk.PhotoImage]=build_treeview_icons(self)
        
        self.character_tree_ids: bidict[str, str]=bidict({}) # bidict so we can lookup {hash <-> tree_id}
        self.character_type_tree_ids: bidict[str, str]=bidict({}) # bidict so we can lookup {character_type <-> tree_id}

        super().__init__(parent)

        tk.Button(self, text="+ Add new entry", command=self.add_entry).pack(fill="x")

        self.dictionary_treeview=ttk.Treeview(self, columns=("defs"), height=16)
        self.dictionary_treeview.pack(fill="x")
        self.dictionary_treeview.bind("<ButtonPress-1>", self.leftclick_entry)
        self.dictionary_treeview.bind("<ButtonPress-2>", self.middleclick_entry)
        self.dictionary_treeview.bind("<ButtonPress-3>", self.rightclick_entry)

        self.refresh()

    def refresh(self):
        """
        Constructs `Character.character_type` headers and places all glossary json items under respectively against hash.
        """
        # 1. Clear the treeview --------------------------------
        tv: ttk.Treeview=self.dictionary_treeview
        tv.delete(*tv.get_children())
        self.character_type_tree_ids=bidict({})
        self.character_tree_ids=bidict({})

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
            char=self.session.json_to_character(item)

            row_tags = ('selected',) if hash == self.session.character_hash else ('unselected',)
            extra_defs_text = ""
            if len(char.definition) > 1:
                extra_defs_text = f" (+{len(char.definition)-1} more...)"

            tree_id=tv.insert(self.character_type_tree_ids[char.character_type],
                                tk.END,
                                text=f"{hash}",
                                values=(f"{char.definition[0]}{extra_defs_text}",),
                                tags=row_tags
                                )
            self.character_tree_ids[hash]=tree_id

        if self.session.character_hash in self.character_tree_ids.keys():
            tv.see(item=self.character_tree_ids.get(self.session.character_hash))

    def update_active_entry(self):
        self.session.commit_active_character_to_memory()
        active_hash = self.session.character_hash
        tree_id = self.character_tree_ids.get(active_hash)
        if tree_id is None:
            return

        item = self.session.character_glossary_data[active_hash]
        group_id = self.character_type_tree_ids.get(item["character_type"])
        if group_id is not None and self.dictionary_treeview.parent(tree_id) != group_id:
            self.dictionary_treeview.move(tree_id, group_id, tk.END)

        definitions = item["definition"]
        extra_defs_text = f" (+{len(definitions) - 1} more...)" if len(definitions) > 1 else ""
        self.dictionary_treeview.item(
            tree_id,
            values=(f"{definitions[0]}{extra_defs_text}",),
        )

    def leftclick_entry(self, event: tk.Event):
        """
        Operation to perform on `self.dictionary_treeview` item doubleclick - assign to current view.
        """
        tv: ttk.Treeview=self.dictionary_treeview
        item=tv.identify("item", event.x, event.y)
        hash=self.character_tree_ids.inverse.get(item)
        if hash is not None:
            self.session.select_character(hash, save_current=True)

    def middleclick_entry(self, event: tk.Event):
        tv: ttk.Treeview=self.dictionary_treeview
        item=tv.identify("item", event.x, event.y)
        hash=self.character_tree_ids.inverse.get(item, None)

        if hash:
            character_to_clone = copy.deepcopy(self.session.character_glossary_data[hash])
            self.add_entry(character_to_clone)


    def rightclick_entry(self, event: tk.Event):
        tv: ttk.Treeview=self.dictionary_treeview
        item=tv.identify("item", event.x, event.y)
        hash=self.character_tree_ids.inverse.get(item, None)

        if hash:
            answer = messagebox.askyesno("Remove entry",
                                            f"Remove the glossary entry for {hash}?",
                                            icon="question",
                                            parent=self.winfo_toplevel()
                                            )
            if answer:
                self.remove_entry(hash)

    # TODO: add and remove need partially bringing out to be session methods
    def add_entry(self, character_template: dict | None = None):
        tv: ttk.Treeview=self.dictionary_treeview
        hash: str=secrets.token_hex(4)

        if character_template is None:
            # if the user has a type selected, new entry should be placed here
            # otherwise, go with the active-character's type
            focus_character_type = self.character_type_tree_ids.inverse.get(tv.focus(), None)
            if focus_character_type is None:
                    focus_character_type = self.session.character_type_var.get()

            character_template: dict={
                "character_type": focus_character_type,
                "definition": ["example definition"],
                "stroke_control_points": [[[0.5, 0.0], [0.5, 1.0]]],
                "stroke_profile_control_points":[CurveProfile.REALISTIC.copy().control_points],
                "stroke_profile_bounds": [CurveProfile.REALISTIC.copy().bounds]
                }

        self.session.character_glossary_data[hash]=copy.deepcopy(character_template)
        self.session.character_glossary_stroke_parentage_data[hash]={}
        self.session.select_character(hash, save_current=True)
        self.session.export_glossary_json()

    def remove_entry(self, hash: str):
        self.session.commit_active_character_to_memory()

        hashes=list(self.session.character_glossary_data)
        if len(hashes) <= 1:
            messagebox.showwarning(
                "Cannot remove character",
                "At least one character must remain in the glossary.",
                parent=self.winfo_toplevel(),
            )
            return

        next_active_hash=self.session.character_hash
        removing_active = hash == self.session.character_hash
        if removing_active:
            removed_idx=hashes.index(hash)
            next_active_hash=hashes[removed_idx - 1] if removed_idx > 0 else hashes[1]

        del self.session.character_glossary_data[hash]
        del self.session.character_glossary_stroke_parentage_data[hash]

        if removing_active:
            self.session.select_character(next_active_hash, save_current=False)
        else:
            self.session.refresh("list")
        self.session.export_glossary_json()