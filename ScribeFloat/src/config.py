"""ScribeFloat Premium - Configuracion persistente."""
import json

from app_paths import CONFIG_FILE

DEFAULT_CONFIG = {
    "hotkey": "ctrl+space",
    "language": "es",
    "model_size": "small",
    "panel_position": None,
    "capsule_position": None,
    "last_view": "capsule",
    "capsule_width": 141,
    "capsule_height": 44,
    "wave_speed": 19,
    "wave_response": 90,
    "wave_amplitude": 18,
    "wave_detail": 4,
    "microphone_size": 86,
    "indicator_size": 126,
    "wave_width": 119,
    "open_button_size": 86,
    "open_button_width": 79,
    "open_button_height": 100,
    "open_button_offset": -9,
    "open_button_animation_tenths": 2,
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
