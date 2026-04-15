"""
Resolves the bin/ directory correctly both in development and in
a PyInstaller bundle (where sys._MEIPASS points to _internal/).
"""

import sys
from pathlib import Path


def get_bin_dir() -> Path:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        # PyInstaller bundle — files are in _MEIPASS/bin/
        return Path(sys._MEIPASS) / "bin"
    # Development — bin/ is at the project root
    return Path(__file__).parent.parent.parent / "bin"


BIN_DIR = get_bin_dir()
