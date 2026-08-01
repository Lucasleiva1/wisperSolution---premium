"""Filesystem locations owned by this Whisper Solution copy."""

import sys
from pathlib import Path


def _application_dir():
    """Return the source root or the installed Nuitka distribution root."""
    if "__compiled__" in globals() or getattr(sys, "frozen", False):
        return Path(sys.argv[0]).resolve().parent
    return Path(__file__).resolve().parent.parent


APP_DIR = _application_dir()
ASSETS_DIR = APP_DIR / "assets"
CONFIG_FILE = APP_DIR / "config.json"
MODELS_DIR = APP_DIR / "models"
TEMP_AUDIO_DIR = APP_DIR / "temp_audio"
EXPORTS_DIR = APP_DIR / "exports"
