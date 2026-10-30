
from dataclasses import dataclass
import json

@dataclass
class Sheet:
    width: float # mm
    height: float # mm
    cursor_position: tuple[float, float] = None
    font_size: float = 8.0

    def __post_init__(self):
        if self.cursor_position is None:
            self.cursor_position = (0.0, self.height - self.font_size)
    
    def reset_cursor(self):
        self.cursor_position = (0.0, self.height - self.font_size)

    def split_pages(self, gcode: 'GCode') -> list['GCode']:
        # This method is just a middleman to gcode.split_pages.
        # It is needed in Scribe, however.
        # This separates the pages, does not move self.cursor_position,
        return gcode.split_pages()    

    def save(self, filename: str):
        data = self.__dict__.copy()
        with open(filename, "w") as f:
            json.dump(data, f)
    
    @classmethod
    def load(cls, filename: str):
        with open(filename, "r") as f:
            data = json.load(f)
            return cls(**data)