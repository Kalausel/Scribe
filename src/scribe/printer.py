import subprocess
from dataclasses import dataclass

@dataclass
class Printer:
    name: str = "Brother_HL-L2400DW"

    def print_file(self, path):
        subprocess.run(["lp", "-d", f"{self.name}", f"{path}"], check=True)
        