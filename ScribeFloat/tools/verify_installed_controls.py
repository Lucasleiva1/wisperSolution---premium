"""Exercise the exact Python UI payload extracted from the installed executable.

The build environment supplies Qt's test runner. Application modules, assets,
configuration and model come from the installed package. OS paste is isolated.
"""

import importlib.abc
import importlib.util
import json
import marshal
import os
from pathlib import Path
import sys
import time
import types

from PyInstaller.archive.readers import CArchiveReader
from PySide6.QtCore import QMimeData, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QPushButton
from shiboken6 import delete


installed = Path(os.environ["LOCALAPPDATA"]) / "Whisper-Solution"
work = Path(__file__).resolve().parent.parent / "build_pyinstaller"
archive = CArchiveReader(str(installed / "Whisper-Solution.exe"))
pyz = archive.open_embedded_archive("PYZ.pyz")
application_modules = {
    "app_paths", "config", "settings_ui", "utils", "version", "updater",
    "transcriber", "audio_stream", "release_checks",
}


class InstalledModules(importlib.abc.MetaPathFinder, importlib.abc.Loader):
    def find_spec(self, fullname, path=None, target=None):
        if fullname in application_modules:
            return importlib.util.spec_from_loader(fullname, self)

    def create_module(self, spec):
        return None

    def exec_module(self, module):
        module.__file__ = str(installed / "src" / f"{module.__name__}.py")
        exec(pyz.extract(module.__name__), module.__dict__)


sys.meta_path.insert(0, InstalledModules())
module = types.ModuleType("installed_controls_test")
module.__file__ = str(installed / "src" / "main.py")
sys.modules[module.__name__] = module
exec(marshal.loads(archive.extract("main")), module.__dict__)
assert module.ASSETS_DIR == installed / "assets"
# Keep test view changes out of the user's preferences and exports.
module.save_config = lambda config: None
module.EXPORTS_DIR = work / "test-exports-v1.1.4"
os.environ["HF_HUB_OFFLINE"] = "1"
app = QApplication([])
app.setQuitOnLastWindowClosed(False)
clipboard_backup = QMimeData()
for format_name in app.clipboard().mimeData().formats():
    clipboard_backup.setData(format_name, app.clipboard().mimeData().data(format_name))
controller = module.ScribeFloatController(app)
checks = []


def wait_for(condition, label, timeout=60):
    deadline = time.monotonic() + timeout
    while not condition():
        if time.monotonic() >= deadline:
            raise AssertionError(f"Tiempo agotado: {label}")
        QTest.qWait(20)


def click(widget):
    assert widget.isEnabled(), f"Boton deshabilitado: {widget.text()}"
    QTest.mouseClick(widget, Qt.LeftButton)
    QTest.qWait(50)


def button(parent, text):
    return next(item for item in parent.findChildren(QPushButton) if item.text() == text)


def capture_paste(text):
    # No Ctrl+V is sent to the user's foreground application during tests.
    controller._finish_recording("Prueba de pegado aislada", text)


controller._paste_text = capture_paste
result = {"version": module.APP_VERSION, "payload": "installed executable", "checks": checks}
try:
    wait_for(lambda: controller.scribe_engine is not None, "cargar modelo")
    wait_for(lambda: controller.state == module.UiState.IDLE, "modelo preparado")
    assert controller._sounds_enabled
    checks.append("startup and sound enabled")

    click(controller.capsule.microphone_button)
    wait_for(lambda: controller.audio_capture is not None, "microfono de capsula")
    assert controller.is_recording and controller.audio_capture.is_recording
    QTest.qWait(1000)
    click(controller.capsule.microphone_button)
    wait_for(lambda: not controller._paste_after_stop and controller._pending_segments == 0, "detener capsula")
    assert not controller.is_recording and controller.audio_capture is None
    assert controller.state in (module.UiState.IDLE, module.UiState.READY_WITH_TEXT)
    checks.append("capsule microphone click starts; second click stops real capture")

    controller.capsule._animate_controls(True)
    QTest.qWait(250)
    controller.capsule.open_button.click()
    wait_for(controller.panel.isVisible, "abrir panel")
    checks.append("open panel from capsule")

    click(controller.panel.rec_button)
    wait_for(lambda: controller.audio_capture is not None, "REC del panel")
    assert controller.is_recording and controller.audio_capture.is_recording
    QTest.qWait(1000)
    click(controller.panel.rec_button)
    wait_for(lambda: not controller._paste_after_stop and controller._pending_segments == 0, "detener panel")
    assert not controller.is_recording and controller.audio_capture is None
    checks.append("panel REC starts and stops real capture")

    fixture = "Prueba de botones v1.1.4."
    controller.full_transcript = fixture
    controller.panel.set_transcription(fixture)
    click(button(controller.panel, "Copiar"))
    assert app.clipboard().text() == fixture
    checks.append("copy to clipboard")
    before_exports = set(module.EXPORTS_DIR.glob("*.txt"))
    click(button(controller.panel, "Guardar"))
    new_exports = set(module.EXPORTS_DIR.glob("*.txt")) - before_exports
    assert any(fixture in item.read_text(encoding="utf-8") for item in new_exports)
    checks.append("save transcription")
    click(button(controller.panel, "Limpiar"))
    assert controller.full_transcript == "" and controller.panel.transcript.toPlainText() == ""
    checks.append("clear transcription")

    click(controller.panel.settings_button)
    wait_for(lambda: controller.settings_dialog is not None, "configuracion")
    dialog = controller.settings_dialog
    click(button(dialog, "Abrir ajustes"))
    wait_for(lambda: dialog.visual_dialog is not None and dialog.visual_dialog.isVisible(), "ajustes visuales")
    click(button(dialog.visual_dialog, "Cancelar"))
    click(button(dialog, "Cancelar"))
    wait_for(lambda: controller.settings_dialog is None, "cerrar configuracion")
    checks.append("settings, visual settings and cancel buttons")

    click(button(controller.panel, "MODO CAPSULA"))
    assert controller.capsule.isVisible() and not controller.panel.isVisible()
    controller.capsule._animate_controls(True)
    QTest.qWait(250)
    controller.capsule.open_button.click()
    wait_for(controller.panel.isVisible, "volver al panel")
    click(button(controller.panel, "-"))
    assert controller.capsule.isVisible() and not controller.panel.isVisible()
    checks.append("capsule mode and minimize return to capsule")
    click(controller.capsule.close_button)
    assert controller._closing
    checks.append("capsule close")
    result["ok"] = True
except Exception as exc:
    result.update(ok=False, error=str(exc))
    raise
finally:
    if not controller._closing:
        controller.shutdown()
    controller._segment_worker_thread.join(timeout=3)
    app.clipboard().setMimeData(clipboard_backup)
    for widget in reversed(app.topLevelWidgets()):
        delete(widget)
    app.processEvents()
    (work / "controls-installed-v1.1.4.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result))
