from dataclasses import dataclass
import json

from sound2font.writemodule import GCode

@dataclass
class Page:
    width: float # mm
    height: float # mm
    cursor_position: tuple[float, float] = None
    font_size: float = 8.0
    side: str = None # "left" or "right"

    def __post_init__(self):
        if self.cursor_position is None:
            self.cursor_position = (0.0, self.height() - self.font_size)
    
    def reset_cursor(self):
        self.cursor_position = (0.0, self.height - self.font_size)

class Book:
    # Book coordinate system has origin at bottom left.
    def __init__(self, width: float = 210.0, height: float = 297.0,
                 top_margin: float = 10.0, bottom_margin: float = 10.0, edge_margin: float = 10.0, center_margin: float = 20.0,
                 left_edge_position: float = 0.0, bottom_edge_position: float = 0.0, rotation: float = -90.0,
                 current_page: "Page" = None, cursor_position: tuple[float, float] = None,
                 font_size: float = 8.0):
        self.width = width
        self.height = height
        self.top_margin = top_margin
        self.bottom_margin = bottom_margin
        self.edge_margin = edge_margin
        self.center_margin = center_margin # This is the margin on one page.
        self.left_edge_position = left_edge_position # Left edge of the book. Top edge of Idraw.
        self.bottom_edge_position = bottom_edge_position # Bootom edge of the book. Left edge of Idraw.
        self.rotation = rotation
        if rotation != -90.0:
            raise NotImplementedError("rotation must be -90 degrees. Bottom of book must be along the y-carriage.")
        self.cursor_position = cursor_position
        # self.cursor_position will be set in left_page() or right_page(), if needed.
        self.font_size = font_size
        if current_page is None or current_page == "left":
            self.current_page = self.left_page()
        elif current_page == "right":
            self.current_page = self.right_page()
        elif isinstance(current_page, Page):
            self.current_page = current_page
            self.cursor_position = self.cursor_page2book()
        else:
            raise ValueError("current_page must be 'left', 'right', or a Page object.")
        # Check that the dimensions fit on the iDraw.
        assert self.bottom_edge_position + self.bottom_margin >= 1
        assert self.left_edge_position + self.edge_margin >= 1
        assert self.left_edge_position + self.width - self.edge_margin <= 311
        assert self.bottom_edge_position + self.height - self.top_margin <= 207

    def left_page(self):
        if self.cursor_position is None:
            self.cursor_position = (self.edge_margin, self.height - self.top_margin - self.font_size)
        return Page(self.width / 2 - self.edge_margin - self.center_margin, self.height - self.top_margin - self.bottom_margin,
                    cursor_position=self.cursor_book2page(side="left"), font_size=self.font_size, side="left")
    
    def right_page(self):
        if self.cursor_position is None:
            self.cursor_position = (self.width / 2 + self.center_margin, self.height - self.top_margin - self.font_size)
        return Page(self.width / 2 - self.edge_margin - self.center_margin, self.height - self.top_margin - self.bottom_margin,
                    cursor_position=self.cursor_book2page(side="right"), font_size=self.font_size, side="right")
    
    def next_page(self):
        self.cursor_position = None
        if self.current_page.side == "left":
            self.current_page = self.right_page()
        elif self.current_page.side == "right":
            self.current_page = self.left_page()
        else:
            raise ValueError("current_page.side must be 'left' or 'right'.")
    
    def reset_cursor(self):
        self.current_page.reset_cursor()
        self.cursor_position = self.cursor_page2book()

    def update_book_cursor(self):
        self.cursor_position = self.cursor_page2book()

    def cursor_book2page(self, side: str):
        if side == "left":
            return (self.cursor_position[0] - self.edge_margin
                    , self.cursor_position[1] - self.bottom_margin)
        elif side == "right":
            return (self.cursor_position[0] - self.width / 2 - self.center_margin
                    , self.cursor_position[1] - self.bottom_margin)
        else:
            raise ValueError("side must be 'left' or 'right'.")
    
    def cursor_page2book(self, page: Page = None):
        if page is None:
            page = self.current_page
        if page.side == "left":
            return (page.cursor_position[0] + self.edge_margin
                    , page.cursor_position[1] + self.bottom_margin)
        elif page.side == "right":
            return (page.cursor_position[0] + self.width / 2 + self.center_margin
                    , page.cursor_position[1] + self.bottom_margin)
        else:
            raise ValueError("page.side must be 'left' or 'right'.")

    def cursor_book2idraw(self, cursor: tuple[float] = None) -> tuple[float]:
        if cursor is None:
            cursor = self.cursor_position
        return (self.bottom_edge_position + cursor[1]
              , -self.left_edge_position - cursor[0])
    
    def transform_gcode_page2book(self, gcode: GCode):
        if self.current_page.side == "left":
            return gcode.translate((self.edge_margin, self.bottom_margin))
        elif self.current_page.side == "right":
            return gcode.translate((self.width / 2 + self.center_margin
                                    , self.bottom_margin))
        else:
            raise ValueError(f"self.current_page.side must be 'left' or 'right'. Got {self.current_page.side}.")

    def transform_gcode_book2idraw(self, gcode: GCode):
        new_gcode = gcode.rotate(self.rotation, inplace=False)
        new_gcode.translate((self.bottom_edge_position, -self.left_edge_position), inplace=True)
        return new_gcode
    
    def split_pages(self, gcode: GCode) -> list[GCode]:
        # This separates the pages, does not move self.cursor_position,
        # keeps track of self.current_page.
        # and returns a list of transformed GCode objects, which can be printed as is.
        output = []
        gcode_pages = gcode.split_pages()
        for i, gcode_page in enumerate(gcode_pages):
            if i > 0:
                self.next_page()
            gcode_page = self.transform_gcode_page2book(gcode_page)
            output.append(self.transform_gcode_book2idraw(gcode_page))
        return output
    
    def show_pages(self):
        # This method creates a GCode object containing gcode commands
        # that move through the page limits.
        # 1) Positions in book coordinates
        positions = [
            (self.edge_margin, self.bottom_margin),  # Bottom left
            (self.edge_margin, self.height - self.top_margin),  # Top left
            (self.width / 2 - self.center_margin, self.height - self.top_margin),  # Top right
            (self.width / 2 - self.center_margin, self.bottom_margin),  # Bottom right
            (self.width / 2 + self.center_margin, self.bottom_margin),  # Bottom left of right page
            (self.width / 2 + self.center_margin, self.height - self.top_margin),  # Top left of right page
            (self.width - self.edge_margin, self.height - self.top_margin),  # Top right of right page
            (self.width - self.edge_margin, self.bottom_margin)  # Bottom right of right page
        ]
        # 2) Convert to idraw coordinates
        idraw_positions = [self.cursor_book2idraw(pos) for pos in positions]

        # 3) Create GCode commands
        gcode_commands = "$H\n"
        for pos in idraw_positions:
            gcode_commands += f"G1 X{pos[0]} Y{pos[1]} F3000\n"
        # gcode_commands += "$H" This line resulted in grbl error 8, homing error, even before the physical execution of the gcode.
        # According to the grbl documentation, homing should be done before sending any other commands.
        # 4) Create a GCode object
        return GCode(gcode_commands)



    def save(self, filename: str):
        data = self.__dict__.copy()
        data["current_page"] = self.current_page.__dict__
        with open(filename, "w") as f:
            json.dump(data, f)
    
    @classmethod
    def load(cls, filename: str):
        with open(filename, "r") as f:
            data = json.load(f)
            if "current_page" in data:
                current_page_data = data.pop("current_page")
                current_page = Page(**current_page_data)
                return cls(current_page=current_page, **data)
            else:
                return cls(**data)