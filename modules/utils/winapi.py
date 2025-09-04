import ctypes
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO

class COORD(ctypes.Structure):
    _fields_ = [("X", ctypes.c_short), ("Y", ctypes.c_short)]

class SMALL_RECT(ctypes.Structure):
    _fields_ = [("Left", ctypes.c_short), ("Top", ctypes.c_short),
                ("Right", ctypes.c_short), ("Bottom", ctypes.c_short)]

class CHAR_INFO(ctypes.Structure):
    _fields_ = [("Char", ctypes.c_wchar),  
                ("Attributes", ctypes.c_ushort)]  

class CONSOLE_SCREEN_BUFFER_INFO(ctypes.Structure):
    _fields_ = [("Size", COORD),
                ("CursorPosition", COORD),
                ("Attributes", ctypes.c_ushort),
                ("Window", SMALL_RECT),
                ("MaximumWindowSize", COORD)]
    
class RECT(ctypes.Structure):
    _fields_ = [("left", ctypes.c_long),
                ("top", ctypes.c_long),
                ("right", ctypes.c_long),
                ("bottom", ctypes.c_long)]
    
class WinApi:
    def render_console_buffer(self, img_width = 993, img_height = 519, char_width = 8, char_height = 16) -> bytes:
        STD_OUTPUT_HANDLE = -11
        h_console = ctypes.windll.kernel32.GetStdHandle(STD_OUTPUT_HANDLE)

        csbi = CONSOLE_SCREEN_BUFFER_INFO()
        ctypes.windll.kernel32.GetConsoleScreenBufferInfo(h_console, ctypes.byref(csbi))

        left, top, right, bottom = csbi.Window.Left, csbi.Window.Top, csbi.Window.Right, csbi.Window.Bottom
        width = right - left + 1
        height = bottom - top + 1

        buffer = (CHAR_INFO * (width * height))()
        
        rect = SMALL_RECT(left, top, right, bottom)
        
        ctypes.windll.kernel32.ReadConsoleOutputW(h_console, buffer, COORD(width, height), COORD(0, 0), ctypes.byref(rect))
        
        COLOR_MAP = {
            0: (0, 0, 0), 1: (0, 0, 128), 2: (0, 128, 0), 3: (0, 128, 128),
            4: (128, 0, 0), 5: (128, 0, 128), 6: (128, 128, 0), 7: (192, 192, 192),
            8: (128, 128, 128), 9: (0, 0, 255), 10: (0, 255, 0), 11: (0, 255, 255),
            12: (255, 0, 0), 13: (255, 0, 255), 14: (255, 255, 0), 15: (255, 255, 255)
        }

        try:
            font = ImageFont.truetype("C:\\Windows\\Fonts\\consola.ttf", 16)
        except IOError:
            font = ImageFont.load_default()

        image = Image.new("RGB", (img_width, img_height), "black")
        draw = ImageDraw.Draw(image)
        
        for y in range(height):
            for x in range(width):
                char_info = buffer[y * width + x]
                char = char_info.Char or " "
                attr = char_info.Attributes
                fg_color = COLOR_MAP[attr & 0x0F]
                draw.text((x * char_width, y * char_height), char, fill=fg_color, font=font)

        image_buffer = BytesIO()
        image.save(image_buffer, format="PNG")
        return image_buffer.getvalue()
    

WINAPI = WinApi()