import json
import jsbeautifier

from src.symbols.strokes import BrushStroke
from src.symbols.characters import Character, Glyph

CHARACTERS_JSON_FP="data/characters.json"
GLYPHS_JSON_FP="data/glyphs.json"


def import_character_definitions_from_json(filepath: str):
    with open(filepath, "r") as file:
        source_dict: dict[str, dict]=json.load(file)

    glossary_data: dict[str, dict]={}

    for hash, data in source_dict.items():
        glossary_data[hash]=data.copy()
        glossary_data[hash]["definition"] = [(t,d) for t,d in data.get("definition")]
        glossary_data[hash]["index_path"] = data.get("index_path") or ""
        glossary_data[hash]["glyphs"]=data.get("glyphs")
        glossary_data[hash]["glyph_extents"]=[tuple(tuple(el) for el in sublist) for sublist in data.get("glyph_extents")]
        glossary_data[hash]["subcharacters"]=data.get("subcharacters",[])
        glossary_data[hash]["subcharacter_extents"]=[tuple(tuple(el) for el in sublist) for sublist in data.get("subcharacter_extents",[])]

    return glossary_data

def import_glyph_definitions_from_json(filepath: str):
    with open(filepath, "r") as file:
        source_dict: dict[str, list[list[list[float, float]]]]=json.load(file)

    glyphs_data = {}
    for glyph_hash, data in source_dict.items():
        if isinstance(data, dict):
            index_path = data.get("index_path", data.get("detail")) or ""
            strokes_data = data["strokes"]
        else:
            index_path = ""
            strokes_data = data
        
        strokes = [[(x, y) for x, y in stroke] for stroke in strokes_data]
        glyphs_data[glyph_hash] = (index_path, strokes)
    return glyphs_data

def import_glyphs_from_json(filepath: str) -> dict[str, Glyph]:
    return {
        glyph_hash: Glyph(
            [BrushStroke(control_points) for control_points in strokes],
            index_path=index_path,
        )
        for glyph_hash, (index_path, strokes) in import_glyph_definitions_from_json(filepath).items()
    }

def import_characters_and_glyphs_from_json(
    characters_filepath: str,
    glyphs_filepath: str,
) -> tuple[dict[str, Character], dict[str, Glyph]]:
    glossary_data = import_character_definitions_from_json(characters_filepath)
    glyph_glossary_data = import_glyphs_from_json(glyphs_filepath)

    output_characters: dict[str, Character] = {
        character_hash: Character(
            definition=character_data.get("definition", []),
            index_path=character_data.get("index_path", ""),
            glyphs=[],
            glyph_extents=character_data.get("glyph_extents", []),
            subcharacters=[],
            subcharacter_extents=character_data.get("subcharacter_extents", []),
        )
        for character_hash, character_data in glossary_data.items()
    }

    for character_hash, character_data in glossary_data.items():
        character = output_characters[character_hash]

        for glyph_hash, glyph_extent in zip(
            character_data.get("glyphs", []),
            character_data.get("glyph_extents", []),
        ):
            try:
                character.glyphs.append(glyph_glossary_data[glyph_hash])
            except KeyError as error:
                raise KeyError(
                    f"Character {character_hash!r} references unknown glyph {glyph_hash!r}."
                ) from error
            character.glyph_extents.append(glyph_extent)

        for subcharacter_hash, subcharacter_extent in zip(
            character_data.get("subcharacters", []),
            character_data.get("subcharacter_extents", []),
        ):
            try:
                character.subcharacters.append(output_characters[subcharacter_hash])
            except KeyError as error:
                raise KeyError(
                    f"Character {character_hash!r} references unknown "
                    f"subcharacter {subcharacter_hash!r}."
                ) from error
            character.subcharacter_extents.append(subcharacter_extent)

    return output_characters, glyph_glossary_data


def export_json(data: dict, filepath: str):
    with open(filepath, "w") as file:
        options = jsbeautifier.default_options()
        options.indent_size = 2
        options.wrap_line_length = 64

        file.write(jsbeautifier.beautify(json.dumps(data), options))

def export_characters_and_glyphs_to_json(
    characters: dict[str, Character],
    glyphs: dict[str, Glyph],
    characters_filepath: str,
    glyphs_filepath: str
) -> None:
    character_data: dict[str, dict]={}

    glyph_hash_by_identity = {
        id(glyph): glyph_hash for glyph_hash, glyph in glyphs.items()
    }
    character_hash_by_identity = {
        id(character): character_hash for character_hash, character in characters.items()
    }

    for character_hash, character in characters.items():
        character_data[character_hash] = {"definition": character.definition,
                                         "index_path": character.index_path,
                                         "glyphs": [],
                                         "glyph_extents": character.glyph_extents,
                                         "subcharacters": [],
                                         "subcharacter_extents": character.subcharacter_extents
                                         }
        
        for glyph in character.glyphs:
            character_data[character_hash]["glyphs"].append(
                glyph_hash_by_identity[id(glyph)]
            )

        for subcharacter in character.subcharacters:
            character_data[character_hash]["subcharacters"].append(
                character_hash_by_identity[id(subcharacter)]
            )

    glyphs_data = {}
    for glyph_hash, glyph in glyphs.items():
        strokes = [stroke.control_points for stroke in glyph.strokes]
        if not glyph.index_path:
            glyphs_data[glyph_hash] = strokes
        else:
            glyphs_data[glyph_hash] = {
                "index_path": glyph.index_path,
                "strokes": strokes,
            }

    export_json(character_data, characters_filepath)
    export_json(glyphs_data, glyphs_filepath)