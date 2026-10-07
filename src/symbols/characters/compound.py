from src.symbols import strokes
from src.symbols.characters.base import Character, CHARACTER_TYPES

GLYPH_SIZE = strokes.GLYPH_SIZE


class CompoundCharacter(Character):
    def __init__(self, character_type: CHARACTER_TYPES, definition: any, parent: Character, child: Character):
        self.character_type = character_type
        self.definition = definition

        self.parent: Character = parent.clone()
        self.child: Character = child.clone()

    def generate_glyph(self):
        pass
        # 1. get parent empty region
        
        # 2. scale child coords to that empty region
        # 3. combine BrushStroke lists of parent and child, assign to self.strokes
        # 4. run generate_glyph()
        pass