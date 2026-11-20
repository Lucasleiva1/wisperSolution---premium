"""Native Windows regression check, runnable from the shipped executable."""

import ctypes
from ctypes import wintypes
from types import SimpleNamespace
from shiboken6 import delete

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QWidget


def verify_backend():
    """Exercise the packaged decoder and GPU libraries with synthetic silence."""
    try:
        import numpy as np
        import sounddevice as sd
        from config import load_config
        from transcriber import ScribeEngine

        sd.check_input_settings(samplerate=16000, channels=1, dtype="int16")
        config = load_config()
        engine = ScribeEngine(config.get("language", "es"), config.get("model_size", "small"))
        segments, _ = engine.model.transcribe(
            np.zeros(16000, dtype=np.float32), language="es", beam_size=1,
            vad_filter=False, condition_on_previous_text=False,
        )
        list(segments)
        print(f"BACKEND_OK: modelo={engine.model_size}, dispositivo={engine.device}, microfono compatible")
        return 0
    except Exception as exc:
        print(f"BACKEND_FAILED: {exc}")
        return 5


def verify_window_topmost(app_module):
    app = QApplication([])
    app.setQuitOnLastWindowClosed(False)
    user32 = app_module.WINDOWS_USER32
    user32.GetWindow.argtypes = (wintypes.HWND, wintypes.UINT)
    user32.GetWindow.restype = wintypes.HWND
    user32.GetForegroundWindow.restype = wintypes.HWND

    def above(front, back):
        hwnd = user32.GetWindow(int(back.winId()), 3)  # GW_HWNDPREV
        while hwnd:
            if hwnd == int(front.winId()):
                return True
            hwnd = user32.GetWindow(hwnd, 3)
        return False

    panel = app_module.PremiumPanel({})
    capsule = app_module.ListeningCapsule({})
    rival, settings, visual = QWidget(), QWidget(), QWidget()
    windows = (panel, capsule, rival, settings, visual)
    for widget in (rival, settings, visual):
        widget.setWindowFlags(Qt.Window | Qt.WindowStaysOnTopHint)
        widget.setGeometry(60, 60, 350, 230)
    settings.visual_dialog = visual
    context = SimpleNamespace(
        _closing=False, application=app, panel=panel, capsule=capsule,
        settings_dialog=None,
    )
    enforce = app_module._enforce_always_on_top
    guard = lambda: app_module.ScribeFloatController._guard_visible_window_topmost(context)
    try:
        for target, hidden in ((panel, capsule), (capsule, panel)):
            hidden.hide()
            target.show()
            rival.show()
            QTest.qWait(50)
            enforce(rival, force=True)
            assert above(rival, target), "No se pudo reproducir la ventana tapada"
            assert user32.GetWindowLongW(int(target.winId()), -20) & 8
            foreground = user32.GetForegroundWindow()
            bounds = target.geometry()
            guard()
            assert above(target, rival), "No se recupero la posicion superior"
            assert foreground == user32.GetForegroundWindow(), "Se robo el foco"
            assert target.geometry() == bounds, "Se movio la ventana"
            assert not hidden.isVisible(), "Se mostro una ventana oculta"
        settings.show()
        visual.show()
        context.settings_dialog = settings
        QTest.qWait(50)
        guard()
        assert above(visual, settings) and above(settings, capsule), "Orden incorrecto de ajustes"
        print("TOPMOST_OK: panel, capsula, foco, posicion y ajustes")
        return 0
    except Exception as exc:
        print(f"TOPMOST_FAILED: {exc}")
        return 4
    finally:
        panel.allow_close()
        # Destroy widgets (and their animation timers) before QApplication.
        # close() alone leaves these top-level QObjects alive until Python GC.
        for widget in reversed(windows):
            widget.close()
            delete(widget)
        app.processEvents()
