import os
import threading
import getpass
import time
import subprocess
from time import sleep
from datetime import datetime
from sound2font.audiomodule import Microphone, AudioData, Speaker
from sound2font.speech2text import Speech2Text, Speech2Text_fw
from sound2font.textmodule import GrammarAdder
from sound2font.text2font import Text2Font
from src.scribe.book import Page, Book
from src.scribe.gcodesender import GCodeSender

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

def log(text: str):
    print(text)
    with open("scribe_log", "a") as file:
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

def loop(gcode_page, sender, check_sym_pos):
    gcode_page.save('temp', pure=True) # GCode.save stores its commandstr in the file, which is just text.
    success, got_pos = sender.send_gcode("temp", settings=None, check_sym_pos=check_sym_pos, return_check_pos=True)
    log(f"LOOP: sym_pos check {'un' if not success else ''}successful. Expected: {check_sym_pos}. Got: {got_pos}")
    if not success:
        sender.send_gcode("home", settings=None)
        sender.send_gcode("temp", settings=None, check_sym_pos=False)
        log("LOOP: Sending gcode after homing complete.")

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


log("Retrieving saved books...")
files = [os.path.join('./data/books', x) for x in os.listdir('./data/books')]
key_list_str = ""
files.sort() # Sort alphabetically.
for i, key in enumerate(files):
    key_list_str += f"{i}: {key}\n"
led_on("yellow")
key_idx = input(f"Please choose the book index from the following list.\n" + key_list_str)
led_off("yellow")
key_idx = int(key_idx)
BOOK = Book.load(files[key_idx]) # Starts where the last session ended.
if FONT_SIZE is not None:
    BOOK.font_size = FONT_SIZE
log(f"Chose book {key_idx}: {files[key_idx]}.")

mic = Microphone()
# if LANGUAGE in ['fwt', 'fwb', 'fws']:
speech2text = Speech2Text_fw(MODEL_SIZE, mic.kwargs['rate'], language=LANGUAGE)
#else:
#    speech2text = Speech2Text(MODEL_PATH, mic.kwargs['rate'])
#    grammar_adder = GrammarAdder(GRAMMAR_PATH, language=LANGUAGE)
page = BOOK.current_page
text2font = Text2Font(page.width, page.height
                      , FONT_PATH, connected=True
                      , font_size=BOOK.font_size, line_spacing=3
                      , char_spacing=2
                      , string_alphabet=True
                      , initial_position=page.cursor_position)

log('Initialising plotter...')
settings = {"11": "0.02"
            , "20": "1"
            , "32": "0"
            , "130": f"{BOOK.bottom_edge_position+BOOK.height-BOOK.top_margin+1}"
            , "131": f"{BOOK.left_edge_position+BOOK.width-BOOK.edge_margin+1}"}
            # I am adding 1mm tolerance because
            # 1) I am leaving 1mm to spare in the BOOK sanity checks.
            # 2) to account for rounding errors that would lead to an iDraw error, if e.g. Y=+1e-14 (this just happened).
sender = GCodeSender("/dev/idraw", baudrate=115200) # The idraw needs to be setup to point to the correct port.

with open("temp", "w") as f:
    f.write("F5000\n$H")
sender.send_gcode("temp", settings)
log(f"Sending initial settings complete.\nInitial settings:\n{settings}")

check_sym_pos_first_page = [0.0,0.0,0.0] # Right after homing

while True:
    log("Ready for new selection and recording.")
    led_on("blue")
    selection = input("Enter 'space' to continue." + \
          "\nEnter 'nl' to continue on a new line." + \
          "\nEnter 'np' to continue on a new page." + \
          "\nEnter 'h' to home." + \
          "\nEnter 's' to show the book's edges.\n")
    led_off("blue")
    log(f"Selected {selection}.")

    if selection == 'h':
        sender.send_gcode("home", settings=None)
        check_sym_pos_first_page = [0.0,0.0,0.0] # Right after homing
        continue

    if selection == 's':
        log("Selected 's'. Showing book edges.")
        led_on("blue")
        led_on("red")
        led_on("green") 
        BOOK.show_pages().save("temp_show_book", pure=True)
        sender.send_gcode("temp_show_book", settings=None, check_sym_pos=False)
        time.sleep(40)  # Wait for the plotter to finish.
        log("Showing book edges complete. Now homing...")
        sender.send_gcode("home", settings=None)
        check_sym_pos_first_page = [0.0,0.0,0.0] # Right after homing
        log("Homed.")
        led_off("blue")
        led_off("red")
        led_off("green")
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
    # if LANGUAGE in ['fwt', 'fwb', 'fws']:
    punct_text = text
    # else:
    #     log('Adding capitalisation and grammar...')
    #     punct_text = grammar_adder.add_grammar_rcp(text)
    
    if selection == 'nl':
        punct_text = "\n" + punct_text
    elif selection == 'np':
        punct_text = "NEWPAGE\n" + punct_text
    else: # space
        pass
    log('Finished converting to text.\nGenerating GCode...')
    log(f"{text2font.current_position = }")
    font = text2font.convert(punct_text)
    log(f"{text2font.current_position = }")
    font.curves2g1(interval=BOOK.font_size/20, inplace=True)
    font.add_feed_rate(3000, inplace=True) # Specify feed rate in every G1 command.
    first_page = BOOK.current_page.side
    gcode_pages = BOOK.split_pages(font)
    BOOK.current_page.cursor_position = text2font.current_position
    BOOK.update_book_cursor() # based on page cursor
    log(f"{BOOK.__dict__ = }")
    BOOK.save(files[key_idx])
    log('Saved new state of book.')
    log('Finished generating GCode.')

    log(f"Start looping. {len(gcode_pages)=} {first_page=}")
    for i, gcode_page in enumerate(gcode_pages):
        log(f"LOOPING: Looping index {i}/{len(gcode_pages)}")
        # Ask for page turning, if the page is left and not the first page
        # The first page will always contain at least PEN['UP].
        # Even if the first writing action is a new page, this will technically be the second page.
        if first_page == "left" and i % 2 == 0 or first_page == "right" and i % 2 == 1: # if left page
            if i > 0:
                log("LOOPING: Page turning")
                led_on("red")
                input("Continuing on left page. Please turn the page and press 'Enter'.")
                led_off("red")
        if i == 0:
            check_sym_pos = check_sym_pos_first_page
        elif first_page == "left" and i % 2 == 0 or first_page == "right" and i % 2 == 1: # if left page
            # In this case, the sym position should be the last position on the right page.
            check_sym_pos = [*gcode_pages[i-1].last_position(), 0.0]
            log(f"LOOPING: Checking sym_pos before continuing on left page. Expected position {check_sym_pos}" + \
                f"\n{gcode_pages[i-1].last_position() = }.")
        else: # if right page
            # In this case, the sym position should be the last position on the left page.
            check_sym_pos = [*gcode_pages[i-1].last_position(), 0.0]
            log(f"LOOPING: Checking sym_pos before continuing on right page. Expected position {check_sym_pos}" + \
                f"\n{gcode_pages[i-1].last_position() = }.")

        if i == len(gcode_pages) - 1 and False: # remove 'and False' to revert to the threading behaviour.
            # Threading made problems with the 'np' option.
            # Make sure that the last thread is finished.
            try:
                fred.join()
            except NameError:
                # If this is the first thread of the loop, there is no loop to join/terminate.
                pass
            log("Starting new thread for looping over last page of the lot.")
            fred = threading.Thread(target=loop, args=(gcode_page, sender, check_sym_pos))
            fred.start()
        else:
            loop(gcode_page, sender, check_sym_pos)

    check_sym_pos_first_page = [*BOOK.cursor_book2idraw(BOOK.cursor_position), 0.0]