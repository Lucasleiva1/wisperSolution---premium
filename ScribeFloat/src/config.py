"""ScribeFloat Premium - Configuracion persistente."""
import json

from app_paths import CONFIG_FILE

DEFAULT_CONFIG = {
    "hotkey": "ctrl+space",
    "language": "es",
    "model_size": "small",
    "panel_position": None,
    "capsule_position": None,
    "last_view": "panel",
    "capsule_width": 340,
    "capsule_height": 60,
    "wave_speed": 55,
    "wave_response": 62,
    "wave_amplitude": 25,
    "wave_detail": 2,
    "microphone_size": 100,
    "indicator_size": 100,
    "wave_width": 100,
}

def load_config():
    if CONFIG_FILE.exists():
        try:
            with CONFIG_FILE.open("r", encoding="utf-8") as f:
                cfg = json.load(f)
            for k, v in DEFAULT_CONFIG.items():
                cfg.setdefault(k, v)
            return cfg
        except Exception:
            pass
    return dict(DEFAULT_CONFIG)

def save_config(cfg):
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with CONFIG_FILE.open("w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)
