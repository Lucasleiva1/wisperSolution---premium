"""Filesystem locations owned by this ScribeFloat Premium copy."""

from pathlib import Path


APP_DIR = Path(__file__).resolve().parent.parent
CONFIG_FILE = APP_DIR / "config.json"
MODELS_DIR = APP_DIR / "models"
TEMP_AUDIO_DIR = APP_DIR / "temp_audio"
EXPORTS_DIR = APP_DIR / "exports"
