import json
import jsbeautifier
import hashlib
import pickle

from src.symbols.strokes import BrushStroke
from src.symbols.characters import Character, Glyph

CHARACTERS_JSON_FP="data/characters.json"
GLYPHS_JSON_FP="data/glyphs.json"


def import_character_definitions_from_json():
    with open(CHARACTERS_JSON_FP, "r") as file:
        source_dict: dict[str, dict]=json.load(file)

    glossary_data: dict[str, dict]={}

    for hash, data in source_dict.items():
        glossary_data[hash]=data.copy()
        glossary_data[hash]["definition"] = [(t,d) for t,d in data.get("definition")]
        glossary_data[hash]["glyphs"]=data.get("glyphs")
        glossary_data[hash]["glyph_extents"]=[tuple(tuple(el) for el in sublist) for sublist in data.get("glyph_extents")]

    return glossary_data

def import_glyph_definitions_from_json():
    with open(GLYPHS_JSON_FP, "r") as file:
        source_dict: dict[str, list[list[list[float, float]]]]=json.load(file)

    glyphs_data: dict[str, list[list[tuple]]]={}

    for hash, data in source_dict.items():
        glyphs_data[hash]=[[(x,y) for x,y in el] for el in data]

    return glyphs_data

def import_characters_from_json() -> dict[str, Character]:
    glossary_data = import_character_definitions_from_json()
    glyphs_data = import_glyph_definitions_from_json()

    output_characters: dict[str, Character]={}

    for character_hash, character_data in glossary_data.items():

        glyph_collection: list[Glyph]=[]
        glyph_extent_collection: list[tuple[tuple[float,float], tuple[float,float]]]=[]

        for glyph_hash, glyph_extent in zip(character_data.get("glyphs"), character_data.get("glyph_extents")):
            strokes = [BrushStroke(ctrl_pts) for ctrl_pts in glyphs_data[glyph_hash]]
            glyph = Glyph(strokes)

            glyph_collection.append(glyph)
            glyph_extent_collection.append(glyph_extent)

        output_characters[character_hash]=Character(
            definition=character_data.get("definition", []),
            glyphs=glyph_collection,
            glyph_extents=glyph_extent_collection
        )

    return output_characters

def export_json(data: dict, filepath: str):
    with open(filepath, "w") as file:
        options = jsbeautifier.default_options()
        options.indent_size = 2
        options.wrap_line_length = 64

        file.write(jsbeautifier.beautify(json.dumps(data), options))

def export_characters_to_json(characters: dict[str, Character]) -> None:
    glossary_data: dict[str, dict]={}
    glyphs_data: dict[str, list[list[tuple[float,float]]]]={}

    for character_hash, character in characters.items():
        glossary_data[character_hash] = {"definition": character.definition,
                                         "glyphs": [],
                                         "glyph_extents": character.glyph_extents
                                         }
        
        for glyph in character.glyphs:
            ctrl_pts: list[list[tuple[float,float]]] = []
            for stroke in glyph.strokes:
                ctrl_pts.append(stroke.control_points)

            if ctrl_pts not in glyphs_data.values():
                new_glyph_hash = hashlib.md5(pickle.dumps(ctrl_pts)).hexdigest()
                glyphs_data[new_glyph_hash] = ctrl_pts
        
                glossary_data[character_hash]["glyphs"].append(new_glyph_hash)
            else:
                existing_glyph_hash = list(glyphs_data.keys())[list(glyphs_data.values()).index(ctrl_pts)]

                glossary_data[character_hash]["glyphs"].append(existing_glyph_hash)

    export_json(glossary_data, CHARACTERS_JSON_FP)
    export_json(glyphs_data, GLYPHS_JSON_FP)