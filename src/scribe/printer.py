import subprocess
from dataclasses import dataclass

@dataclass
class Printer:
    name: str = "Brother_HL-L2400DW"

    def print_svg(self, path):
        subprocess.run(["rsvg-convert", "-f", "pdf", "-o", f"{path[:-3] + "pdf"}", f"{path}"])
        self.print_pdf(f"{path[:-3] + "pdf"}")

    def print_pdf(self, path):
        subprocess.run(["lp", "-d", f"{self.name}", f"{path}"], check=True)
        