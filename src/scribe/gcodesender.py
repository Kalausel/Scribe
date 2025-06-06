import subprocess
import os
from io import StringIO
import numpy as np


def extract_pos_from_out(out) -> list[float]:
    # out is the return value of subprocess.run
    return [float(x) for x in out.stderr.decode().split("MPos:")[1].split("|")[0].split(",")]

def extract_pos_mode(out) -> str:
    # Find the line starting with '[GC' and extract the mode
    for line in out.stderr.decode().splitlines():
        if line.startswith("[GC"):
            if "G90" in line:
                return "G90"
            elif "G91" in line:
                return "G91"
    return None

def extract_frame(out) -> str:
    # Find the line starting with '[GC' and extract the frame
    for line in out.stderr.decode().splitlines():
        if line.startswith("[GC"):
            for mode in ["G54", "G55", "G56", "G57", "G58", "G59"]:
                if mode in line:
                    return mode
    return None

class GCodeSender:

    def __init__(self, connection_name, baudrate):
        self.connection_name = connection_name
        self.baudrate = baudrate

    def send_gcode(self, gcode_file_path: str, settings: dict = None
                   , check_sym_pos: bool|list[float] = False, return_sym_pos: bool = False
                   , return_check_pos: bool = False):
        # check_sym_pos: Before execution of the gcode.
        # return_sym_pos: After execution of the gcode.
        # return_check_pos: Before execution of the gcode.
        if check_sym_pos or return_sym_pos and not os.path.exists("check_sym_pos_temp"):
            with open("check_sym_pos_temp", "w") as file:
                file.write("?\n$G")
        if check_sym_pos:
            out = subprocess.run(["gcode-cli", "check_sym_pos_temp", f"{self.connection_name}"], capture_output=True)
            got = extract_pos_from_out(out)
            print(f"GOT: {got}")
            modes = (extract_pos_mode(out), extract_frame(out))
            if modes[0] != "G90":
                raise ValueError(f"Expected G90 mode, got {modes[0]}")
            if modes[1] != "G54":
                raise ValueError(f"Expected G54 frame, got {modes[1]}")
            if not np.isclose(np.array(check_sym_pos), np.array(got), atol=1).all():
                #raise ValueError(f"Check sym pos failed. Expected: {check_sym_pos}, got: {got}")
                if return_check_pos:
                    return (False, got)
                else:
                    return False
        cfg_gcode = ""
        cfg_gcode_path = "cfg_temp"
        if settings is not None:
            for key, value in settings.items():
                cfg_gcode += f"${key}={value}\n"
            with open(cfg_gcode_path, "w") as file:
                file.write(cfg_gcode)
            subprocess.run(["gcode-cli", f"{cfg_gcode_path}", f"{self.connection_name}"])
        subprocess.run(["gcode-cli", f"{gcode_file_path}", f"{self.connection_name}"])
        if return_sym_pos:
            out = subprocess.run(["gcode-cli", "check_sym_pos_temp", f"{self.connection_name}"], capture_output=True)
            return extract_pos_from_out(out)
        if return_check_pos:
            return (True, got)
        return True
