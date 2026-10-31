import os
import threading
import getpass
import time
import subprocess
from time import sleep
from datetime import datetime
from sound2font.audiomodule import Microphone, AudioData, Speaker
from sound2font.speech2text import Speech2Text_fw
from sound2font.text2font import Text2Font, KEYWORDS
from src.scribe.sheet import Sheet
from src.scribe.gcodesender import GCodeSender
from src.scribe.printer import Printer

USER = getpass.getuser()
if USER == "pi":
    from gpiozero import LED
    from gpiozero.pins.lgpio import LGPIOFactory

    pf = LGPIOFactory()

print(f"{USER=}")
COLORS = {"white": 4
          , "yellow": 17
          , "blue": 18
          , "green": 27
          , "red": 22}

if USER == 'pi':
    leds = {color: LED(COLORS[color], pin_factory=pf) for color in COLORS}

def log(text: str, logfile: str = "print_log"):
    print(text)
    if not os.path.exists(logfile):
        with open(logfile, "w") as file:
            pass
    with open(logfile, "a") as file:
        file.write(f"\n{datetime.now().strftime('%Y%m%d %H:%M:%S')} {text}")

def led_on(color: str):
    if USER != "pi":
        return None
    leds[color].on()

def led_off(color: str):
    if USER != "pi":
        return None
    leds[color].off()

if USER == 'pi':
    for color in COLORS:
        led_on(color)
    sleep(2)
    for color in COLORS:
        led_off(color)
    sleep(1)

led_on("white")
LANGUAGE = input("'de'/'en'")#/'fwt'/'fwb'/'fws'...")

log(f"Chose language {LANGUAGE}")

# if LANGUAGE == 'fwt':
#     MODEL_SIZE = "tiny"
# elif LANGUAGE == 'fwb':
#     MODEL_SIZE = "base"
# elif LANGUAGE == 'fws':
#     MODEL_SIZE = "small"
MODEL_SIZE = "base"

# else:
#     models_dir = f"/home/{USER}/Documents/models"
#     MODEL_PATH = os.path.join(models_dir, 'vosk/vosk-model-small-de-0.15' if LANGUAGE == 'de' else 'vosk/vosk-model-small-en-us-0.15')
#     GRAMMAR_PATH = os.path.join(models_dir, 'vosk/vosk-recasepunc-de-0.21/checkpoint' if LANGUAGE == 'de' else 'vosk/vosk-recasepunc-en-0.22/checkpoint')
FONT_PATH = f"/home/{USER}/Documents/sound2font/data/alphabets/connected.json"

led_on("yellow")
font_size = input("Enter font size in mm ...")
if font_size == "":
    FONT_SIZE = None
else:
    FONT_SIZE = float(font_size)
led_off("yellow")
led_off("white")


log("Retrieving saved sheets...")
files = [os.path.join('./data/sheets', x) for x in os.listdir('./data/sheets')]
key_list_str = ""
files.sort() # Sort alphabetically.
for i, key in enumerate(files):
    key_list_str += f"{i}: {key}\n"
led_on("yellow")
key_idx = input(f"Please choose the sheet index from the following list.\n" + key_list_str)
led_off("yellow")
key_idx = int(key_idx)
sheet = Sheet.load(files[key_idx]) # Starts where the last session ended.
if FONT_SIZE is not None:
    sheet.font_size = FONT_SIZE
log(f"Chose sheet {key_idx}: {files[key_idx]}.")

mic = Microphone()
# if LANGUAGE in ['fwt', 'fwb', 'fws']:
speech2text = Speech2Text_fw(MODEL_SIZE, mic.kwargs['rate'], language=LANGUAGE)
#else:
#    speech2text = Speech2Text(MODEL_PATH, mic.kwargs['rate'])
#    grammar_adder = GrammarAdder(GRAMMAR_PATH, language=LANGUAGE)

text2font = Text2Font(sheet.width, sheet.height
                      , FONT_PATH, connected=True
                      , font_size=sheet.font_size, line_spacing=3
                      , char_spacing=2
                      , string_alphabet=True
                      , initial_position=sheet.cursor_position)

font = text2font.convert("")
printer = Printer()

while True:
    log("Ready for new selection and recording.")
    led_on("blue")
    selection = input("Enter 'space' to continue." + \
          "\nEnter 'nl' to continue on a new line." + \
          "\nEnter 'np' to continue on a new page." + \
          "\nEnter 'p' to print.\n")
    led_off("blue")
    log(f"Selected {selection}.")

    if selection == 'p':
        gcode_pages = sheet.split_pages(font)
        font = text2font.convert("")
        if len(gcode_pages) == 0:
            log("Tried printing. gcode_pages is an empty list.")
            continue
        for gcode_page in gcode_pages:
            gcode_page.invert_coordinate(1, inplace=True)
            gcode_page.write_svg("temp.svg", sheet.width, sheet.height, sheet.font_size/10)
            printer.print_svg("temp.svg")
            gcode_pages = gcode_pages[1:]
            if len(gcode_pages) == 0:
                break
            led_on("yellow")
            selection = input("Enter 'p' to print the next page.")
            if selection != 'p':
                break
        continue

    led_on("green")
    log("Recording...")
    audio = mic.record()
    if audio is None:
        continue
    led_off("green")
    log('Finished recording.\nConverting to text...')
    log(f"Audio size in bytes: {len(audio)}. Max size: {audio.max_var_size}.")
    text = speech2text.transcribe(audio).text()
    
    if selection == 'nl':
        text = KEYWORDS['nl'] + text
    elif selection == 'np':
        text = KEYWORDS['np'] + text
    else: # space
        pass
    log('Finished converting to text.\nGenerating GCode...')
    log(f"{text2font.current_position = }")
    font.append(text2font.convert(text))
    log(f"{text2font.current_position = }")
    font.curves2g1(interval=sheet.font_size/20, inplace=True)
    sheet.cursor_position = text2font.current_position
    log(f"{sheet.__dict__ = }")
    sheet.save(files[key_idx])
    log('Saved new state of sheet.')
    log('Finished generating GCode.')
