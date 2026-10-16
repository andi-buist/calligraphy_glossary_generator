import json
import jsbeautifier
import uuid

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

    glyphs_data = {}
    for glyph_hash, data in source_dict.items():
        if isinstance(data, dict):
            detail = data.get("detail", None)
            strokes_data = data["strokes"]
        else:
            detail = None
            strokes_data = data
        
        strokes = [[(x, y) for x, y in stroke] for stroke in strokes_data]
        glyphs_data[glyph_hash] = (detail, strokes)
    return glyphs_data

def import_glyphs_from_json() -> dict[str, Glyph]:
    return {
        glyph_hash: Glyph(
            [BrushStroke(control_points) for control_points in strokes],
            detail=detail,
        )
        for glyph_hash, (detail, strokes) in import_glyph_definitions_from_json().items()
    }

def import_characters_from_json(
    glyph_glossary_data: dict[str, Glyph] | None = None,
) -> dict[str, Character]:
    glossary_data = import_character_definitions_from_json()
    if glyph_glossary_data is None:
        glyph_glossary_data = import_glyphs_from_json()

    output_characters: dict[str, Character]={}

    for character_hash, character_data in glossary_data.items():

        glyph_collection: list[Glyph]=[]
        glyph_extent_collection: list[tuple[tuple[float,float], tuple[float,float]]]=[]

        for glyph_hash, glyph_extent in zip(character_data.get("glyphs"), character_data.get("glyph_extents")):
            try:
                glyph_collection.append(glyph_glossary_data[glyph_hash])
            except KeyError as error:
                raise KeyError(
                    f"Character {character_hash!r} references unknown glyph {glyph_hash!r}."
                ) from error
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

def export_characters_and_glyphs_to_json(
    characters: dict[str, Character],
    glyphs: dict[str, Glyph]
) -> None:
    character_data: dict[str, dict]={}

    glyph_hash_by_identity = {
        id(glyph): glyph_hash for glyph_hash, glyph in glyphs.items()
    }

    for character_hash, character in characters.items():
        character_data[character_hash] = {"definition": character.definition,
                                         "glyphs": [],
                                         "glyph_extents": character.glyph_extents
                                         }
        
        for glyph in character.glyphs:
            character_data[character_hash]["glyphs"].append(
                glyph_hash_by_identity[id(glyph)]
            )

    glyphs_data = {}
    for glyph_hash, glyph in glyphs.items():
        strokes = [stroke.control_points for stroke in glyph.strokes]
        if glyph.detail is None:
            glyphs_data[glyph_hash] = strokes
        else:
            glyphs_data[glyph_hash] = {
                "detail": glyph.detail,
                "strokes": strokes,
            }

    export_json(character_data, CHARACTERS_JSON_FP)
    export_json(glyphs_data, GLYPHS_JSON_FP)