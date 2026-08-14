"""Whisper Solution desktop UI built with PySide6."""

import ctypes
from ctypes import wintypes
import math
import os
import queue
import subprocess
import sys
import threading
import time
from enum import Enum

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import keyboard
import pygame
from PySide6.QtCore import (
    QEasingCurve,
    QEvent,
    QPoint,
    QPointF,
    QParallelAnimationGroup,
    QPropertyAnimation,
    QRect,
    QRectF,
    Qt,
    QTimer,
    QVariantAnimation,
    Signal,
    Slot,
    QObject,
)
from PySide6.QtGui import (
    QColor,
    QFont,
    QIcon,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QRadialGradient,
)
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QMessageBox,
    QTextEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import load_config, save_config
from settings_ui import SettingsPanel
from utils import clean_text, save_transcription
from app_paths import APP_DIR, ASSETS_DIR, EXPORTS_DIR
from updater import check_for_update, download_update
from version import APP_VERSION


LANGS = {
    "Espanol (es)": "es",
    "English (en)": "en",
    "Portugues (pt)": "pt",
    "Francais (fr)": "fr",
    "Deutsch (de)": "de",
    "Italiano (it)": "it",
}
START_SOUND_DELAY_MS = 350
WINDOW_TRANSITION_GUARD_MS = 120
TOPMOST_GUARD_INTERVAL_MS = 750
SINGLE_INSTANCE_MUTEX = None
RUNTIME_LOG_HANDLE = None

WINDOWS_USER32 = None
if os.name == "nt":
    WINDOWS_USER32 = ctypes.WinDLL("user32", use_last_error=True)
    WINDOWS_USER32.GetWindowLongW.argtypes = (wintypes.HWND, ctypes.c_int)
    WINDOWS_USER32.GetWindowLongW.restype = ctypes.c_long
    WINDOWS_USER32.SetWindowLongW.argtypes = (
        wintypes.HWND,
        ctypes.c_int,
        ctypes.c_long,
    )
    WINDOWS_USER32.SetWindowLongW.restype = ctypes.c_long
    WINDOWS_USER32.SetWindowPos.argtypes = (
        wintypes.HWND,
        wintypes.HWND,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        wintypes.UINT,
    )
    WINDOWS_USER32.SetWindowPos.restype = wintypes.BOOL

GWL_EXSTYLE = -20
WS_EX_TOPMOST = 0x00000008
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_APPWINDOW = 0x00040000
WS_EX_NOACTIVATE = 0x08000000
SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOZORDER = 0x0004
SWP_NOACTIVATE = 0x0010
SWP_FRAMECHANGED = 0x0020
SWP_NOOWNERZORDER = 0x0200
HWND_TOPMOST = ctypes.c_void_p(-1)


def _configure_runtime_log():
    """Keep diagnostics from windowed frozen builds in the installed folder."""
    global RUNTIME_LOG_HANDLE
    if not getattr(sys, "frozen", False) or RUNTIME_LOG_HANDLE is not None:
        return
    try:
        log_path = APP_DIR / "whisper-solution-runtime.log"
        RUNTIME_LOG_HANDLE = open(log_path, "a", encoding="utf-8", buffering=1)
        sys.stdout = RUNTIME_LOG_HANDLE
        sys.stderr = RUNTIME_LOG_HANDLE
        print(f"\n[Runtime] Inicio {time.strftime('%Y-%m-%d %H:%M:%S')} | {sys.executable}")
    except Exception:
        RUNTIME_LOG_HANDLE = None


class UiState(Enum):
    LOADING_MODEL = "loading_model"
    IDLE = "idle"
    RECORDING_CAPSULE = "recording_capsule"
    RECORDING_EXPANDED = "recording_expanded"
    FINALIZING = "finalizing"
    READY_WITH_TEXT = "ready_with_text"
    ERROR = "error"


def _color(hex_value, alpha=255):
    value = QColor(hex_value)
    value.setAlpha(alpha)
    return value


def _blend(left, right, amount, alpha=255):
    amount = max(0.0, min(1.0, amount))
    result = QColor(
        int(left.red() + ((right.red() - left.red()) * amount)),
        int(left.green() + ((right.green() - left.green()) * amount)),
        int(left.blue() + ((right.blue() - left.blue()) * amount)),
        alpha,
    )
    return result


def _acquire_single_instance():
    """Prevent duplicate windows and global hotkeys."""
    global SINGLE_INSTANCE_MUTEX
    if os.name != "nt":
        return True

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateMutexW.argtypes = (ctypes.c_void_p, ctypes.c_bool, ctypes.c_wchar_p)
    kernel32.CreateMutexW.restype = ctypes.c_void_p
    kernel32.CloseHandle.argtypes = (ctypes.c_void_p,)
    kernel32.CloseHandle.restype = ctypes.c_bool

    handle = kernel32.CreateMutexW(None, True, "Local\\WhisperSolutionSingleInstance")
    if not handle:
        return True
    if ctypes.get_last_error() == 183:
        kernel32.CloseHandle(handle)
        return False
    SINGLE_INSTANCE_MUTEX = handle
    return True


def _release_single_instance():
    global SINGLE_INSTANCE_MUTEX
    if os.name != "nt" or not SINGLE_INSTANCE_MUTEX:
        return
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.ReleaseMutex.argtypes = (ctypes.c_void_p,)
    kernel32.ReleaseMutex.restype = ctypes.c_bool
    kernel32.CloseHandle.argtypes = (ctypes.c_void_p,)
    kernel32.CloseHandle.restype = ctypes.c_bool
    kernel32.ReleaseMutex(SINGLE_INSTANCE_MUTEX)
    kernel32.CloseHandle(SINGLE_INSTANCE_MUTEX)
    SINGLE_INSTANCE_MUTEX = None


def _make_no_activate(widget):
    """Keep the live overlay from stealing the target app focus on Windows."""
    widget.setAttribute(Qt.WA_ShowWithoutActivating, True)
    if os.name != "nt":
        return
    hwnd = wintypes.HWND(int(widget.winId()))
    style = WINDOWS_USER32.GetWindowLongW(hwnd, GWL_EXSTYLE)
    WINDOWS_USER32.SetWindowLongW(
        hwnd,
        GWL_EXSTYLE,
        style | WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW,
    )


def _ensure_taskbar_window(widget):
    """Expose only the primary panel as a normal Windows taskbar window."""
    if os.name != "nt":
        return
    hwnd = wintypes.HWND(int(widget.winId()))
    style = WINDOWS_USER32.GetWindowLongW(hwnd, GWL_EXSTYLE)
    style = (style & ~WS_EX_TOOLWINDOW) | WS_EX_APPWINDOW
    WINDOWS_USER32.SetWindowLongW(hwnd, GWL_EXSTYLE, style)
    WINDOWS_USER32.SetWindowPos(
        hwnd,
        None,
        0,
        0,
        0,
        0,
        SWP_NOSIZE | SWP_NOMOVE | SWP_NOZORDER | SWP_NOACTIVATE | SWP_FRAMECHANGED,
    )


def _enforce_always_on_top(widget, force=False):
    """Keep a visible overlay in Windows' native TOPMOST z-order band."""
    if os.name != "nt" or not widget.isVisible():
        return
    hwnd = wintypes.HWND(int(widget.winId()))
    style = WINDOWS_USER32.GetWindowLongW(hwnd, GWL_EXSTYLE)
    if not force and style & WS_EX_TOPMOST:
        return
    WINDOWS_USER32.SetWindowPos(
        hwnd,
        HWND_TOPMOST,
        0,
        0,
        0,
        0,
        SWP_NOSIZE | SWP_NOMOVE | SWP_NOACTIVATE | SWP_NOOWNERZORDER,
    )


def _inside_any_screen(position, size):
    if not isinstance(position, (list, tuple)) or len(position) != 2:
        return False
    rect = QRect(int(position[0]), int(position[1]), size.width(), size.height())
    return any(screen.availableGeometry().intersects(rect) for screen in QApplication.screens())


def _clamp_widget_to_screen(widget):
    screen = QApplication.screenAt(widget.frameGeometry().center()) or QApplication.primaryScreen()
    available = screen.availableGeometry()
    x = max(available.left(), min(widget.x(), available.right() - widget.width() + 1))
    y = max(available.top(), min(widget.y(), available.bottom() - widget.height() + 1))
    widget.move(x, y)


def _place_settings_dialog(dialog, anchor):
    """Place the settings panel fully within the anchor monitor's work area."""
    screen = QApplication.screenAt(anchor.center()) or QApplication.primaryScreen()
    available = screen.availableGeometry()
    margin = 16
    x = anchor.center().x() - (dialog.width() // 2)
    y = anchor.top() - dialog.height() - 18
    if y < available.top() + margin:
        y = available.top() + margin
    max_x = available.right() - dialog.width() - margin + 1
    max_y = available.bottom() - dialog.height() - margin + 1
    x = max(available.left() + margin, min(x, max_x))
    y = max(available.top() + margin, min(y, max_y))
    dialog.move(x, y)


def _make_app_icon():
    """Load the shared brand icon used by the app, executable and installer."""
    return QIcon(str(ASSETS_DIR / "icons" / "whisper-solution-icon.png"))


def _set_windows_app_id():
    if os.name == "nt":
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                "WhisperSolution.Desktop"
            )
        except Exception:
            pass


class MeterWidget(QWidget):
    """Compact level visual used in the detailed panel."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.level = 0.0
        self.phase = 0.0
        self.recording = False
        self.setFixedSize(58, 32)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(45)

    def set_audio_level(self, level):
        self.level += (level - self.level) * 0.36

    def set_recording(self, active):
        self.recording = active
        if not active:
            self.level = 0.0
        self.update()

    def _tick(self):
        self.phase += 0.24
        if self.recording:
            self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        accent = _color("#3bdcff") if self.recording else _color("#304064")
        for index in range(5):
            pulse = abs(math.sin(self.phase + index * 0.82)) if self.recording else 0.25
            height = 8 + (18 * max(self.level, pulse * 0.32 if self.recording else 0.0))
            x = 8 + index * 10
            painter.setPen(QPen(accent, 4, Qt.SolidLine, Qt.RoundCap))
            painter.drawLine(QPointF(x, 16 - height / 2), QPointF(x, 16 + height / 2))
        painter.end()


class PremiumPanel(QWidget):
    rec_requested = Signal()
    copy_requested = Signal()
    save_requested = Signal()
    clear_requested = Signal()
    settings_requested = Signal()
    minimize_requested = Signal()
    capsule_requested = Signal()
    close_requested = Signal()
    language_selected = Signal(str)
    position_changed = Signal(QPoint)
    restore_requested = Signal()

    def __init__(self, config):
        super().__init__()
        self._drag_origin = None
        self._allow_close = False
        self._ignore_restore_requests = False
        self._window_transition_token = 0
        self.setWindowTitle("Whisper Solution")
        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setFixedSize(508, 584)

        card = QFrame(self)
        card.setObjectName("mainCard")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(14, 14, 14, 14)
        outer.addWidget(card)
        body = QVBoxLayout(card)
        body.setContentsMargins(25, 22, 25, 22)
        body.setSpacing(14)

        header = QHBoxLayout()
        title_group = QVBoxLayout()
        title_group.setSpacing(1)
        brand = QLabel("WHISPER SOLUTION")
        brand.setObjectName("brand")
        tagline = QLabel("VOICE CAPTURE  /  PREMIUM DESKTOP")
        tagline.setObjectName("tagline")
        title_group.addWidget(brand)
        title_group.addWidget(tagline)
        header.addLayout(title_group)
        header.addStretch()
        capsule_button = QPushButton("MODO CAPSULA")
        capsule_button.setObjectName("capsuleModeButton")
        capsule_button.setFixedSize(102, 31)
        capsule_button.setToolTip("Pasar a la vista compacta")
        capsule_button.clicked.connect(self.capsule_requested.emit)
        header.addWidget(capsule_button)
        for text, callback, width, tooltip in (
            ("-", self.minimize_requested.emit, 31, "Minimizar"),
            ("x", self.close_requested.emit, 31, "Cerrar"),
        ):
            button = QPushButton(text)
            button.setObjectName("windowControl")
            button.setFixedSize(width, 31)
            button.setToolTip(tooltip)
            button.clicked.connect(callback)
            header.addWidget(button)
        body.addLayout(header)

        status_card = QFrame()
        status_card.setObjectName("statusCard")
        status_row = QHBoxLayout(status_card)
        status_row.setContentsMargins(13, 10, 13, 10)
        status_row.setSpacing(10)
        self.meter = MeterWidget()
        self.status_label = QLabel("Preparando modelo...")
        self.status_label.setObjectName("statusLabel")
        self.model_badge = QLabel("MODEL  /  SMALL")
        self.model_badge.setObjectName("modelBadge")
        status_row.addWidget(self.meter)
        status_row.addWidget(self.status_label, 1)
        status_row.addWidget(self.model_badge)
        body.addWidget(status_card)

        language_row = QHBoxLayout()
        language_label = QLabel("IDIOMA")
        language_label.setObjectName("caption")
        self.language_combo = QComboBox()
        self.language_combo.setObjectName("languageCombo")
        self.language_combo.addItems(list(LANGS.keys()))
        code = config.get("language", "es")
        for display, language_code in LANGS.items():
            if language_code == code:
                self.language_combo.setCurrentText(display)
                break
        self.language_combo.currentTextChanged.connect(
            lambda value: self.language_selected.emit(LANGS.get(value, "es"))
        )
        language_row.addWidget(language_label)
        language_row.addStretch()
        language_row.addWidget(self.language_combo)
        body.addLayout(language_row)

        transcript_header = QHBoxLayout()
        transcript_title = QLabel("TRANSCRIPCION")
        transcript_title.setObjectName("caption")
        self.session_hint = QLabel("LISTO PARA ESCUCHAR")
        self.session_hint.setObjectName("sessionHint")
        transcript_header.addWidget(transcript_title)
        transcript_header.addStretch()
        transcript_header.addWidget(self.session_hint)
        body.addLayout(transcript_header)

        self.transcript = QTextEdit()
        self.transcript.setObjectName("transcript")
        self.transcript.setReadOnly(True)
        self.transcript.setPlaceholderText("Tu transcripcion aparecera aqui al finalizar.")
        body.addWidget(self.transcript, 1)

        actions = QHBoxLayout()
        actions.setSpacing(9)
        self.rec_button = QPushButton("REC")
        self.rec_button.setObjectName("recordButton")
        self.rec_button.setMinimumSize(112, 46)
        self.rec_button.clicked.connect(self.rec_requested.emit)
        actions.addWidget(self.rec_button)
        for title, name, callback in (
            ("Copiar", "actionButton", self.copy_requested.emit),
            ("Guardar", "actionButton", self.save_requested.emit),
            ("Limpiar", "actionButton", self.clear_requested.emit),
        ):
            button = QPushButton(title)
            button.setObjectName(name)
            button.setMinimumHeight(42)
            button.clicked.connect(callback)
            actions.addWidget(button)
        body.addLayout(actions)

        footer = QHBoxLayout()
        self.hotkey_label = QLabel(f"ATAJO  {config.get('hotkey', 'ctrl+space').upper()}")
        self.hotkey_label.setObjectName("footer")
        footer.addWidget(self.hotkey_label)
        footer.addStretch()
        self.settings_button = QPushButton("CONFIGURACION")
        self.settings_button.setObjectName("settingsControl")
        self.settings_button.setToolTip("Atajo y apariencia de la capsula")
        self.settings_button.setFixedSize(112, 28)
        self.settings_button.clicked.connect(self.settings_requested.emit)
        footer.addWidget(self.settings_button)
        privacy_label = QLabel("LOCAL  /  PRIVATE")
        privacy_label.setObjectName("footer")
        footer.addWidget(privacy_label)
        body.addLayout(footer)
        self.setStyleSheet(self._styles())

    def _styles(self):
        return """
        QFrame#mainCard {
            background-color: rgba(7, 11, 25, 248);
            border: 1px solid rgba(53, 76, 139, 170);
            border-radius: 28px;
        }
        QLabel { font-family: "Segoe UI"; color: #dbe7ff; }
        QLabel#brand { color: #f5f8ff; font-size: 22px; font-weight: 700; }
        QLabel#tagline { color: #596b96; font-size: 9px; }
        QLabel#caption { color: #6076a7; font-size: 10px; font-weight: 600; }
        QLabel#sessionHint { color: #38cbff; font-size: 9px; }
        QLabel#statusLabel { color: #dce6ff; font-size: 12px; font-weight: 500; }
        QLabel#modelBadge {
            color: #65dcff; background-color: rgba(13, 44, 79, 170);
            border: 1px solid rgba(29, 156, 214, 105); border-radius: 11px;
            padding: 6px 10px; font-size: 9px;
        }
        QLabel#footer { color: #53668e; font-size: 9px; }
        QFrame#statusCard {
            background-color: rgba(11, 19, 39, 220);
            border: 1px solid rgba(42, 64, 110, 160);
            border-radius: 16px;
        }
        QPushButton {
            font-family: "Segoe UI"; color: #dbe7ff; font-size: 11px;
            border-radius: 13px; border: 1px solid rgba(47, 66, 110, 145);
            background-color: rgba(13, 20, 39, 220); padding: 0 13px;
        }
        QPushButton:hover { border-color: rgba(65, 193, 255, 170); background-color: rgba(18, 29, 54, 240); }
        QPushButton#windowControl {
            padding: 0; border-radius: 15px; border: none; background: transparent;
            color: #6b7da6; font-size: 14px;
        }
        QPushButton#windowControl:hover { background-color: rgba(40, 58, 96, 130); color: #ffffff; }
        QPushButton#capsuleModeButton {
            padding: 0 9px; border-radius: 15px;
            color: #b9d9ff; font-size: 8px; font-weight: 700;
            background-color: rgba(16, 36, 72, 210);
            border: 1px solid rgba(70, 132, 215, 170);
        }
        QPushButton#capsuleModeButton:hover {
            color: #ffffff; border-color: rgba(55, 217, 255, 225);
            background-color: rgba(22, 53, 100, 235);
        }
        QPushButton#settingsControl {
            padding: 0 10px; border-radius: 15px;
            color: #a8c8ff; font-size: 9px; font-weight: 700;
            background-color: rgba(13, 27, 55, 210);
            border: 1px solid rgba(66, 106, 181, 155);
        }
        QPushButton#settingsControl:hover {
            color: #ffffff; border-color: rgba(53, 207, 255, 210);
            background-color: rgba(20, 43, 82, 235);
        }
        QPushButton#recordButton {
            color: #ffffff; font-size: 12px; font-weight: 700;
            border: 1px solid rgba(75, 209, 255, 185);
            background-color: rgba(27, 83, 160, 185);
        }
        QPushButton#recordButton:hover { background-color: rgba(34, 110, 204, 220); }
        QPushButton#recordButton[recording="true"] {
            border-color: rgba(255, 65, 121, 210);
            background-color: rgba(144, 29, 71, 210);
        }
        QTextEdit#transcript {
            color: #ebf1ff; font-family: "Segoe UI"; font-size: 13px;
            background-color: rgba(9, 15, 31, 230);
            border: 1px solid rgba(40, 60, 105, 170); border-radius: 17px;
            padding: 13px; selection-background-color: #345ddb;
        }
        QComboBox#languageCombo {
            min-width: 164px; min-height: 34px; padding: 0 12px;
            color: #dce8ff; background-color: rgba(11, 19, 39, 220);
            border: 1px solid rgba(45, 70, 123, 170); border-radius: 11px;
        }
        QComboBox#languageCombo::drop-down { border: none; width: 28px; }
        QComboBox#languageCombo QAbstractItemView {
            color: #dce8ff; background: #0d152a; border: 1px solid #273b6d;
            selection-background-color: #193a77; padding: 5px;
        }
        """

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        card = QRectF(14, 14, self.width() - 28, self.height() - 28)
        for width, alpha in ((7, 7), (3, 15), (1.3, 48)):
            gradient = QLinearGradient(card.left(), card.top(), card.right(), card.bottom())
            gradient.setColorAt(0, _color("#d63cff", alpha))
            gradient.setColorAt(0.48, _color("#3b71ff", alpha))
            gradient.setColorAt(1, _color("#17d9ff", alpha))
            painter.setPen(QPen(gradient, width))
            painter.setBrush(Qt.NoBrush)
            painter.drawRoundedRect(card, 28, 28)
        painter.end()
        super().paintEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and event.position().y() < 94:
            self._drag_origin = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._drag_origin is not None and event.buttons() & Qt.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_origin)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._drag_origin is not None:
            self.position_changed.emit(self.pos())
        self._drag_origin = None
        super().mouseReleaseEvent(event)

    def closeEvent(self, event):
        if self._allow_close:
            event.accept()
            return
        event.ignore()
        self.close_requested.emit()

    def allow_close(self):
        self._allow_close = True

    def _begin_controlled_window_transition(self):
        self._window_transition_token += 1
        token = self._window_transition_token
        self._ignore_restore_requests = True
        QTimer.singleShot(
            WINDOW_TRANSITION_GUARD_MS,
            lambda: self._end_controlled_window_transition(token),
        )

    def _end_controlled_window_transition(self, token):
        if token == self._window_transition_token:
            self._ignore_restore_requests = False

    def show_minimized_from_controller(self):
        self._begin_controlled_window_transition()
        self.showMinimized()

    def show_normal_from_controller(self):
        self._begin_controlled_window_transition()
        self.showNormal()

    def changeEvent(self, event):
        was_restored = (
            event.type() == QEvent.WindowStateChange
            and event.oldState() & Qt.WindowMinimized
            and not self.isMinimized()
        )
        if was_restored and not self._ignore_restore_requests:
            self.restore_requested.emit()
        super().changeEvent(event)

    def set_model_summary(self, summary):
        self.model_badge.setText(summary.upper())

    def set_status(self, text, recording=False):
        self.status_label.setText(text)
        self.meter.set_recording(recording)

    def set_audio_level(self, level):
        self.meter.set_audio_level(level)

    def set_rec_available(self, enabled):
        self.rec_button.setEnabled(enabled)

    def set_recording(self, active):
        self.rec_button.setText("STOP" if active else "REC")
        self.rec_button.setProperty("recording", active)
        self.rec_button.style().unpolish(self.rec_button)
        self.rec_button.style().polish(self.rec_button)

    def show_listening_placeholder(self):
        self.transcript.setPlainText("Escuchando en modo privado...\n\nLa transcripcion aparecera cuando finalice la captura.")
        self.session_hint.setText("CAPTURA ACTIVA")

    def set_transcription(self, text):
        self.transcript.setPlainText(text or "")
        self.session_hint.setText("SESION FINALIZADA" if text else "LISTO PARA ESCUCHAR")

    def displayed_text(self):
        return self.transcript.toPlainText().strip()

    def set_hotkey(self, hotkey):
        self.hotkey_label.setText(f"ATAJO  {hotkey.upper()}")


class CapsuleSurface(QWidget):
    """Front layer that always paints the capsule above its reveal controls."""

    def __init__(self, capsule):
        super().__init__(capsule)
        self.capsule = capsule
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)

    def paintEvent(self, event):
        painter = QPainter(self)
        self.capsule._paint_capsule(painter)
        painter.end()


class ListeningCapsule(QWidget):
    expand_requested = Signal()
    record_requested = Signal()
    close_requested = Signal()
    position_changed = Signal(QPoint)

    def __init__(self, config):
        super().__init__()
        self.setWindowTitle("Whisper Solution - Capsula")
        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
            | Qt.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setMouseTracking(True)
        self.phase = 0.0
        self.level = 0.0
        self.target_level = 0.0
        self.target_envelope = [0.0] * 64
        self.envelope = [0.0] * 64
        self.status_text = "LISTO"
        self.recording = False
        self.previewing = False
        self.wave_speed = 0.15
        self.wave_response = 0.42
        self.wave_amplitude = 1.0
        self.wave_detail = 3
        self.microphone_scale = 1.0
        self.microphone_hover_scale = 1.0
        self.indicator_scale = 1.0
        self.close_hover_amount = 0.0
        self.wave_width_scale = 1.0
        self._capsule_body_height = 60
        self._control_zone_height = 34
        self._open_button_size = 100
        self._open_button_width = 100
        self._open_button_height = 100
        self._open_button_offset = 0
        self._open_button_animation_ms = 200
        self._drag_origin = None
        self.apply_visual_config(config)

        self.reveal_zone = QFrame(self)
        self.reveal_zone.setObjectName("capsuleRevealZone")
        self.reveal_zone.setStyleSheet("QFrame#capsuleRevealZone { background: transparent; border: none; }")
        self.controls = QFrame(self.reveal_zone)
        controls_layout = QHBoxLayout(self.controls)
        controls_layout.setContentsMargins(0, 0, 0, 0)
        controls_layout.setSpacing(4)
        self.open_button = QToolButton()
        self.open_button.setObjectName("capsuleOpen")
        self.open_button.setText("ABRIR")
        self.open_button.setToolTip("Abrir Whisper Solution")
        self.open_button.setCursor(Qt.PointingHandCursor)
        self.open_button.clicked.connect(self.expand_requested.emit)
        controls_layout.addWidget(self.open_button)
        self._apply_open_button_geometry()
        self.controls.adjustSize()
        self.controls_effect = QGraphicsOpacityEffect(self.controls)
        self.controls.setGraphicsEffect(self.controls_effect)
        self.controls_effect.setOpacity(0.0)
        self.controls.setAttribute(Qt.WA_TransparentForMouseEvents, True)

        self.controls_opacity_animation = QPropertyAnimation(self.controls_effect, b"opacity", self)
        self.controls_slide_animation = QPropertyAnimation(self.controls, b"pos", self)
        self.controls_animation = QParallelAnimationGroup(self)
        self.controls_animation.addAnimation(self.controls_opacity_animation)
        self.controls_animation.addAnimation(self.controls_slide_animation)
        self.controls_animation.finished.connect(self._controls_animation_finished)
        self.capsule_surface = CapsuleSurface(self)
        self.wave_hover_zone = QWidget(self)
        self.wave_hover_zone.setObjectName("capsuleWaveHoverZone")
        self.wave_hover_zone.setMouseTracking(True)
        self.wave_hover_zone.setStyleSheet("background: transparent; border: none;")
        self.wave_hover_zone.installEventFilter(self)
        self.microphone_button = QToolButton(self)
        self.microphone_button.setObjectName("capsuleMicrophone")
        self.microphone_button.setCursor(Qt.PointingHandCursor)
        self.microphone_button.setFocusPolicy(Qt.NoFocus)
        self.microphone_button.setAccessibleName("Iniciar grabacion")
        self.microphone_button.setToolTip("Iniciar grabacion")
        self.microphone_button.installEventFilter(self)
        self.microphone_button.setStyleSheet(
            """
            QToolButton#capsuleMicrophone {
                background: transparent; border: none; padding: 0;
            }
            QToolButton#capsuleMicrophone:hover {
                background: transparent; border: none;
            }
            QToolButton#capsuleMicrophone:pressed {
                background: transparent; border: none;
            }
            """
        )
        self.microphone_button.clicked.connect(self.record_requested.emit)
        self.microphone_hover_animation = QVariantAnimation(self)
        self.microphone_hover_animation.setDuration(120)
        self.microphone_hover_animation.setEasingCurve(QEasingCurve.OutCubic)
        self.microphone_hover_animation.valueChanged.connect(self._set_microphone_hover_scale)
        self.close_button = QToolButton(self)
        self.close_button.setObjectName("capsuleClose")
        self.close_button.setCursor(Qt.PointingHandCursor)
        self.close_button.setFocusPolicy(Qt.NoFocus)
        self.close_button.setAccessibleName("Cerrar")
        self.close_button.setToolTip("Cerrar")
        self.close_button.installEventFilter(self)
        self.close_button.setStyleSheet(
            """
            QToolButton#capsuleClose {
                background: transparent; border: none; padding: 0;
            }
            QToolButton#capsuleClose:hover {
                background: transparent; border: none;
            }
            QToolButton#capsuleClose:pressed {
                background: transparent; border: none;
            }
            """
        )
        self.close_button.clicked.connect(self.close_requested.emit)
        self.close_hover_animation = QVariantAnimation(self)
        self.close_hover_animation.setDuration(140)
        self.close_hover_animation.setEasingCurve(QEasingCurve.OutCubic)
        self.close_hover_animation.valueChanged.connect(self._set_close_hover_amount)
        self._position_controls()
        self.controls.hide()

        self.timer = QTimer(self)
        self.timer.setInterval(24)
        self.timer.timeout.connect(self._tick)
        self.timer.start()

    def resizeEvent(self, event):
        if hasattr(self, "controls"):
            self._position_controls()
        super().resizeEvent(event)

    def eventFilter(self, watched, event):
        if watched is self.microphone_button:
            if event.type() == QEvent.Enter:
                self._animate_microphone_hover(1.10)
            elif event.type() == QEvent.Leave:
                self._animate_microphone_hover(1.0)
            elif event.type() == QEvent.MouseButtonPress:
                self._animate_microphone_hover(0.97, duration=70)
            elif event.type() == QEvent.MouseButtonRelease:
                self._animate_microphone_hover(1.10 if self.microphone_button.underMouse() else 1.0, duration=90)
        elif watched is self.close_button:
            if event.type() == QEvent.Enter:
                self._animate_close_hover(1.0)
            elif event.type() == QEvent.Leave:
                self._animate_close_hover(0.0)
        elif watched is self.wave_hover_zone:
            if event.type() == QEvent.Enter:
                self._animate_controls(True)
            elif event.type() == QEvent.Leave:
                self._schedule_controls_hide()
        return super().eventFilter(watched, event)

    def _animate_microphone_hover(self, target, duration=120):
        if not hasattr(self, "microphone_hover_animation"):
            return
        self.microphone_hover_animation.stop()
        self.microphone_hover_animation.setDuration(duration)
        self.microphone_hover_animation.setStartValue(self.microphone_hover_scale)
        self.microphone_hover_animation.setEndValue(target)
        self.microphone_hover_animation.start()

    def _set_microphone_hover_scale(self, value):
        self.microphone_hover_scale = float(value)
        self._update_capsule_visual()

    def _animate_close_hover(self, target):
        if not hasattr(self, "close_hover_animation"):
            return
        self.close_hover_animation.stop()
        self.close_hover_animation.setStartValue(self.close_hover_amount)
        self.close_hover_animation.setEndValue(target)
        self.close_hover_animation.start()

    def _set_close_hover_amount(self, value):
        self.close_hover_amount = float(value)
        self._update_capsule_visual()

    def _position_controls(self):
        if hasattr(self, "controls_animation"):
            self.controls_animation.stop()
        reveal_top = self._capsule_body_height - 6 + min(0, self._open_button_offset)
        self.reveal_zone.setGeometry(
            0,
            reveal_top,
            self.width(),
            self.height() - reveal_top,
        )
        self.controls.adjustSize()
        controls_x = max(0, int((self.reveal_zone.width() - self.controls.width()) / 2))
        self._controls_hidden_pos = QPoint(controls_x, -self.controls.height() + 2)
        self._controls_visible_pos = QPoint(controls_x, 4 + max(0, self._open_button_offset))
        is_revealed = hasattr(self, "controls_effect") and self.controls_effect.opacity() >= 0.5
        self.controls.move(self._controls_visible_pos if is_revealed else self._controls_hidden_pos)
        if hasattr(self, "capsule_surface"):
            self.capsule_surface.setGeometry(
                0,
                0,
                self.width(),
                self._capsule_body_height,
            )
            self.capsule_surface.raise_()
            self.capsule_surface.update()
        if hasattr(self, "microphone_button"):
            hit_size = max(28, round(28 * self.microphone_scale))
            center = QPoint(24, self._capsule_body_height // 2)
            self.microphone_button.setGeometry(
                center.x() - (hit_size // 2),
                center.y() - (hit_size // 2),
                hit_size,
                hit_size,
            )
            self.microphone_button.raise_()
        if hasattr(self, "close_button"):
            hit_size = max(28, round(28 * self.indicator_scale))
            center = QPoint(self.width() - 23, self._capsule_body_height // 2)
            self.close_button.setGeometry(
                center.x() - (hit_size // 2),
                center.y() - (hit_size // 2),
                hit_size,
                hit_size,
            )
            self.close_button.raise_()
        if hasattr(self, "wave_hover_zone"):
            left = self.microphone_button.geometry().right() + 1
            right = self.close_button.geometry().left() - 1
            self.wave_hover_zone.setGeometry(
                left,
                7,
                max(1, right - left + 1),
                max(1, self._capsule_body_height - 14),
            )
            self.wave_hover_zone.raise_()
            self.microphone_button.raise_()
            self.close_button.raise_()

    def _keep_inside_screen(self):
        if not self.isVisible():
            return
        screen = QApplication.screenAt(self.frameGeometry().center()) or QApplication.primaryScreen()
        available = screen.availableGeometry()
        x = max(available.left(), min(self.x(), available.right() - self.width() + 1))
        y = max(available.top(), min(self.y(), available.bottom() - self.height() + 1))
        if x != self.x() or y != self.y():
            self.move(x, y)

    def set_audio_visual(self, level, envelope):
        self.target_level = max(0.0, min(1.0, float(level)))
        if envelope:
            self.target_envelope = [max(0.0, min(1.0, float(value))) for value in envelope[:64]]
            self.target_envelope.extend([0.0] * (64 - len(self.target_envelope)))

    def apply_visual_config(self, config):
        width = max(96, min(1000, int(config.get("capsule_width", 340))))
        height = max(32, min(320, int(config.get("capsule_height", 60))))
        self._open_button_size = max(60, min(160, int(config.get("open_button_size", 100))))
        self._open_button_width = max(60, min(200, int(config.get("open_button_width", 100))))
        self._open_button_height = max(60, min(180, int(config.get("open_button_height", 100))))
        self._open_button_offset = max(-18, min(36, int(config.get("open_button_offset", 0))))
        animation_tenths = max(
            2,
            min(40, int(config.get("open_button_animation_tenths", 2))),
        )
        self._open_button_animation_ms = animation_tenths * 100
        button_width, button_height = self._open_button_dimensions(width)
        self._control_zone_height = max(34, button_height + 9) + max(0, self._open_button_offset)
        self._capsule_body_height = height
        self.setFixedSize(width, height + self._control_zone_height)
        if hasattr(self, "open_button"):
            self._apply_open_button_geometry(button_width, button_height)
        if hasattr(self, "controls"):
            self._position_controls()
        self._keep_inside_screen()
        self.wave_speed = 0.025 + (max(5, min(100, int(config.get("wave_speed", 55)))) * 0.0022)
        response = max(5, min(100, int(config.get("wave_response", 62))))
        self.wave_response = 0.08 + (response * 0.0052)
        amplitude = max(0, min(100, int(config.get("wave_amplitude", 25))))
        normalized_amplitude = amplitude / 100.0
        self.wave_amplitude = 0.025 + ((normalized_amplitude ** 1.35) * 1.2)
        self.wave_detail = max(0, min(7, int(config.get("wave_detail", 2))))
        self.microphone_scale = max(55, min(180, int(config.get("microphone_size", 100)))) / 100.0
        self.indicator_scale = max(55, min(180, int(config.get("indicator_size", 100)))) / 100.0
        self.wave_width_scale = max(35, min(175, int(config.get("wave_width", 100)))) / 100.0
        self._update_capsule_visual()

    def _open_button_dimensions(self, capsule_width=None):
        general_scale = self._open_button_size / 100.0
        width_scale = self._open_button_width / 100.0
        height_scale = self._open_button_height / 100.0
        available_width = capsule_width if capsule_width is not None else self.width()
        maximum_width = max(44, int(available_width) - 8)
        button_width = min(
            maximum_width,
            max(44, round(76 * general_scale * width_scale)),
        )
        button_height = max(16, round(25 * general_scale * height_scale))
        return button_width, button_height

    def _apply_open_button_geometry(self, button_width=None, button_height=None):
        if button_width is None or button_height is None:
            button_width, button_height = self._open_button_dimensions()
        self.open_button.setFixedSize(button_width, button_height)

        general_scale = self._open_button_size / 100.0
        radius = max(8, button_height // 2)
        font_size = max(7, min(16, round(9 * general_scale)))
        horizontal_padding = max(3, min(14, round(9 * general_scale)))
        self.controls.setStyleSheet(
            f"""
            QToolButton {{
                padding: 0 {horizontal_padding}px; border-radius: {radius}px;
                color: #c9deff; background: rgba(7, 16, 35, 242);
                border: 1px solid rgba(78, 145, 234, 190);
                font-family: "Segoe UI"; font-size: {font_size}px; font-weight: 700;
            }}
            QToolButton:hover {{
                color: #ffffff; border-color: rgba(61, 218, 255, 235);
                background: rgba(14, 39, 77, 250);
            }}
            QToolButton:pressed {{ background: rgba(25, 66, 124, 250); }}
            QToolButton#capsuleOpen {{ color: #c5ddff; }}
            """
        )

    def set_recording(self, active):
        self.recording = active
        if hasattr(self, "microphone_button"):
            action = "Detener grabacion" if active else "Iniciar grabacion"
            self.microphone_button.setToolTip(action)
            self.microphone_button.setAccessibleName(action)
        if not active:
            self.target_level = 0.0
            self.target_envelope = [0.0] * 64

    def set_previewing(self, active):
        self.previewing = bool(active) and not self.recording
        if not self.previewing and not self.recording:
            self.target_level = 0.0
            self.target_envelope = [0.0] * 64
        self._update_capsule_visual()

    def set_status(self, text):
        self.status_text = text.upper()
        self._update_capsule_visual()

    def _update_capsule_visual(self):
        if hasattr(self, "capsule_surface"):
            self.capsule_surface.update()
        else:
            self.update()

    def _tick(self):
        if self.previewing and not self.recording:
            demo_phase = self.phase * 2.6
            self.target_level = 0.36 + (0.2 * (0.5 + (0.5 * math.sin(demo_phase))))
            self.target_envelope = [
                min(
                    1.0,
                    0.14
                    + (0.38 * abs(math.sin((index * 0.27) + demo_phase)))
                    + (0.16 * abs(math.sin((index * 0.1) - (demo_phase * 0.7)))),
                )
                for index in range(64)
            ]
        self.phase += self.wave_speed if self.recording else self.wave_speed * 0.27
        response = self.wave_response if (self.recording or self.previewing) else min(0.22, self.wave_response)
        self.level += (self.target_level - self.level) * response
        for index, value in enumerate(self.target_envelope):
            self.envelope[index] += (value - self.envelope[index]) * response
        self._update_capsule_visual()

    def _animate_controls(self, visible):
        self.controls_animation.stop()
        self.controls.setAttribute(Qt.WA_TransparentForMouseEvents, not visible)
        if visible:
            self.controls.show()
            self.controls.raise_()
        duration = self._open_button_animation_ms
        easing = QEasingCurve.OutCubic if visible else QEasingCurve.InCubic
        self.controls_opacity_animation.setDuration(duration)
        self.controls_opacity_animation.setEasingCurve(easing)
        self.controls_opacity_animation.setStartValue(self.controls_effect.opacity())
        self.controls_opacity_animation.setEndValue(1.0 if visible else 0.0)
        self.controls_slide_animation.setDuration(duration)
        self.controls_slide_animation.setEasingCurve(easing)
        self.controls_slide_animation.setStartValue(self.controls.pos())
        self.controls_slide_animation.setEndValue(
            self._controls_visible_pos if visible else self._controls_hidden_pos
        )
        self.controls_animation.start()

    def _controls_animation_finished(self):
        if self.controls_effect.opacity() <= 0.01:
            self.controls.hide()

    def _controls_hover_active(self):
        return self.wave_hover_zone.underMouse() or self.controls.underMouse()

    def _schedule_controls_hide(self):
        QTimer.singleShot(
            100,
            lambda: self._animate_controls(False) if not self._controls_hover_active() else None,
        )

    def enterEvent(self, event):
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._schedule_controls_hide()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        controls_rect = QRect(
            self.reveal_zone.pos() + self.controls.pos(),
            self.controls.size(),
        )
        exposed_controls = controls_rect.intersected(
            QRect(0, self._capsule_body_height, self.width(), self.height() - self._capsule_body_height)
        )
        over_controls = self.controls_effect.opacity() > 0.05 and exposed_controls.contains(
            event.position().toPoint()
        )
        if event.button() == Qt.LeftButton and not over_controls:
            self._drag_origin = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._drag_origin is not None and event.buttons() & Qt.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_origin)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._drag_origin is not None:
            self.position_changed.emit(self.pos())
        self._drag_origin = None
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.expand_requested.emit()
        super().mouseDoubleClickEvent(event)

    def _mesh_value(self, position, layer, stream=0):
        sample_index = min(63, max(0, int(position * 63)))
        microphone = self.envelope[sample_index]
        if stream == 0:
            movement = (
                math.sin((position * 10.8) + self.phase * 3.1 + layer * 0.17)
                + 0.48 * math.sin((position * 23.5) - self.phase * 2.3 + layer * 0.31)
            )
        else:
            movement = (
                math.sin((position * 13.4) - self.phase * 2.7 + 2.15 + layer * 0.21)
                + 0.35 * math.sin((position * 26.2) + self.phase * 1.7 + layer * 0.27)
            )
        idle_amplitude = 10.0 if (self.recording or self.previewing) else 5.0
        amplitude = idle_amplitude + self.level * 42 + microphone * 32
        falloff = 0.7 + 0.3 * math.sin(math.pi * position)
        return movement * amplitude * falloff * self.wave_amplitude * (1.0 if stream == 0 else 0.78)

    def paintEvent(self, event):
        super().paintEvent(event)

    def _paint_capsule(self, painter):
        painter.setRenderHint(QPainter.Antialiasing)
        body = QRectF(7, 7, self.width() - 14, self._capsule_body_height - 14)
        body_path = QPainterPath()
        body_path.addRoundedRect(body, body.height() / 2, body.height() / 2)

        painter.setBrush(Qt.NoBrush)
        for width, alpha in ((7, 7), (3.5, 15), (1.8, 30)):
            glow = QLinearGradient(body.left(), body.center().y(), body.right(), body.center().y())
            glow.setColorAt(0, _color("#df31ff", alpha))
            glow.setColorAt(0.48, _color("#537dff", alpha))
            glow.setColorAt(1, _color("#15ddff", alpha))
            painter.setPen(QPen(glow, width))
            painter.drawPath(body_path)

        fill = QLinearGradient(body.left(), body.top(), body.right(), body.bottom())
        fill.setColorAt(0, _color("#100b24", 245))
        fill.setColorAt(0.47, _color("#071127", 248))
        fill.setColorAt(1, _color("#06161e", 244))
        painter.setPen(Qt.NoPen)
        painter.setBrush(fill)
        painter.drawPath(body_path)

        edge = QLinearGradient(body.left(), 0, body.right(), 0)
        edge.setColorAt(0, _color("#e845ff", 225))
        edge.setColorAt(0.5, _color("#6687ff", 180))
        edge.setColorAt(1, _color("#26dcff", 225))
        painter.setPen(QPen(edge, 1.45))
        painter.setBrush(Qt.NoBrush)
        painter.drawPath(body_path)
        painter.setPen(QPen(_color("#183257", 130), 1.0))
        painter.drawRoundedRect(body.adjusted(5, 5, -5, -5), (body.height() - 10) / 2, (body.height() - 10) / 2)

        painter.save()
        painter.setClipPath(body_path)
        self._draw_wave(painter, body)
        self._draw_microphone(painter, body)
        self._draw_activity_indicator(painter, body)
        painter.restore()

    def _draw_microphone(self, painter, body):
        """Render a stable microphone mark without adding an image asset."""
        center = QPointF(body.left() + 17, body.center().y())
        painter.save()
        painter.translate(center)
        visual_scale = self.microphone_scale * self.microphone_hover_scale
        painter.scale(visual_scale, visual_scale)
        painter.setBrush(Qt.NoBrush)
        painter.setPen(QPen(_color("#d9e9ff", 206), 1.25, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        capsule = QRectF(-3.25, -7.5, 6.5, 11.5)
        painter.drawRoundedRect(capsule, 3.25, 3.25)

        cradle = QPainterPath()
        cradle.moveTo(-6, -2)
        cradle.cubicTo(
            -6,
            5.5,
            6,
            5.5,
            6,
            -2,
        )
        painter.drawPath(cradle)
        painter.drawLine(QPointF(0, 5), QPointF(0, 8))
        painter.drawLine(QPointF(-4.5, 8), QPointF(4.5, 8))
        painter.restore()

    def _draw_activity_indicator(self, painter, body):
        listening = self.recording
        close_hover = self.close_hover_amount
        scale = self.indicator_scale * (1.0 + (0.12 * close_hover))
        center = QPointF(body.right() - 16, body.center().y())
        active_color = QColor("#44ff88") if listening else QColor("#e0efff")
        indicator_color = _blend(active_color, QColor("#ff365f"), close_hover)
        halo_radius = (9.2 if listening else 5.2 + (3.2 * close_hover)) * scale
        halo = QRadialGradient(center, halo_radius)
        if listening or close_hover > 0.0:
            halo.setColorAt(0, _color(indicator_color.name(), int(160 + (40 * close_hover))))
            halo.setColorAt(0.22, _color(indicator_color.name(), int(74 + (38 * close_hover))))
            halo.setColorAt(1, _color(indicator_color.name(), 0))
        else:
            halo.setColorAt(0, _color("#e0efff", 36))
            halo.setColorAt(1, _color("#e0efff", 0))
        painter.setPen(Qt.NoPen)
        painter.setBrush(halo)
        painter.drawEllipse(center, halo_radius, halo_radius)

        painter.setBrush(Qt.NoBrush)
        if listening or close_hover > 0.0:
            painter.setPen(QPen(_color(indicator_color.name(), int(92 + (70 * close_hover))), 0.85))
            painter.drawEllipse(center, 7.8 * scale, 7.8 * scale)
            painter.setPen(QPen(_color(indicator_color.name(), int(46 + (38 * close_hover))), 0.8))
            painter.drawEllipse(center, 10.8 * scale, 10.8 * scale)
        else:
            painter.setPen(Qt.NoPen)
            painter.setBrush(_color("#07131f", 220))
            painter.drawEllipse(center, 3.25 * scale, 3.25 * scale)

        painter.setPen(Qt.NoPen)
        painter.setBrush(_color(indicator_color.name(), 238 if listening or close_hover > 0.0 else 104))
        radius = (2.85 if listening or close_hover > 0.0 else 1.75) * scale
        painter.drawEllipse(center, radius, radius)

    def _draw_wave(self, painter, body):
        left_inset = max(32.0, 22.0 + (10.0 * self.microphone_scale))
        right_inset = max(32.0, 20.0 + (12.0 * self.indicator_scale))
        available_left = body.left() + left_inset
        available_right = body.right() - right_inset
        available_width = max(2.0, available_right - available_left)
        expanded_left = body.left() + max(20.0, 17.5 + (5.8 * self.microphone_scale))
        expanded_right = body.right() - max(22.0, 15.0 + (7.5 * self.indicator_scale))
        max_width = max(2.0, expanded_right - expanded_left)
        draw_width = min(max_width, available_width * self.wave_width_scale)
        midpoint = (available_left + available_right) / 2.0
        left = midpoint - (draw_width / 2.0)
        right = left + draw_width
        center = body.center().y() - 2
        samples = 64
        # A few vector curves preserve depth without thousands of particle paints.
        secondary_detail = max(0, self.wave_detail // 2)
        for stream, layers, opacity, width in (
            (0, range(-self.wave_detail, self.wave_detail + 1), 1.0, 1.05),
            (1, range(-secondary_detail, secondary_detail + 1), 0.42, 0.8),
        ):
            for layer in layers:
                depth = 1.0 - abs(layer) / float(self.wave_detail + 1)
                alpha = int((18 + (depth * 70)) * opacity)
                path = QPainterPath()
                for index in range(samples):
                    position = index / (samples - 1)
                    x = left + (right - left) * position
                    offset = self._mesh_value(position, layer, stream)
                    y = center + offset * (0.44 + depth * 0.34) + layer * 2.5
                    if index == 0:
                        path.moveTo(x, y)
                    else:
                        path.lineTo(x, y)
                line = QLinearGradient(left, center, right, center)
                line.setColorAt(0, _color("#f154ff", alpha))
                line.setColorAt(0.5, _color("#7188ff", alpha))
                line.setColorAt(1, _color("#20ddff", alpha))
                painter.setPen(QPen(line, width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
                painter.setBrush(Qt.NoBrush)
                painter.drawPath(path)

        for stream, alpha, width in ((1, 102, 1.05), (0, 232, 1.9)):
            path = QPainterPath()
            for sample in range(72):
                position = sample / 71.0
                x = left + (right - left) * position
                wave = self._mesh_value(position, 0, stream) * (0.72 if stream else 0.78)
                y = center + wave
                if sample == 0:
                    path.moveTo(x, y)
                else:
                    path.lineTo(x, y)
            line = QLinearGradient(left, center, right, center)
            line.setColorAt(0, _color("#ff54fc", alpha))
            line.setColorAt(0.5, _color("#8793ff", alpha))
            line.setColorAt(1, _color("#21dfff", alpha))
            painter.setPen(QPen(line, width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            painter.setBrush(Qt.NoBrush)
            painter.drawPath(path)


class ScribeFloatController(QObject):
    toggle_from_thread = Signal()
    audio_from_thread = Signal(float, bool, object)
    segment_finished = Signal(int, int, str, str)
    model_loaded = Signal(str, str, str)
    model_failed = Signal(str)
    update_checked = Signal(object)
    update_failed = Signal(str)
    update_progress = Signal(int)
    update_downloaded = Signal(str)

    def __init__(self, application):
        super().__init__()
        self.application = application
        self.cfg = load_config()
        self.state = UiState.LOADING_MODEL
        self.current_language = self.cfg.get("language", "es")
        self.scribe_engine = None
        self.audio_capture = None
        self.is_recording = False
        self.full_transcript = ""
        self._session_transcript = ""
        self._session_parts = {}
        self._completed_segments = set()
        self._segment_seq = 0
        self._pending_segments = 0
        self._active_session_id = 0
        self._paste_after_stop = False
        self._paste_scheduled = False
        self._session_error = ""
        self._segment_lock = threading.Lock()
        self._segment_queue = queue.Queue()
        self._last_hotkey_time = 0.0
        self._hotkey_enabled_after = time.monotonic() + 1.0
        self._hotkey_suspended = False
        self._closing = False
        self._animations = []
        self._return_to_capsule_after_recording = False
        self.settings_dialog = None
        self._settings_preview_only_capsule = False
        self._settings_status_before_preview = ""
        self._pending_update = None
        self._update_busy = False

        self.panel = PremiumPanel(self.cfg)
        self.capsule = ListeningCapsule(self.cfg)
        self._connect_ui()
        self._restore_positions()
        self._set_state(UiState.LOADING_MODEL, "Preparando modelo...")
        self.capsule.set_status("LISTO")
        self._show_capsule()

        self._topmost_guard_timer = QTimer(self)
        self._topmost_guard_timer.setInterval(TOPMOST_GUARD_INTERVAL_MS)
        self._topmost_guard_timer.timeout.connect(self._guard_visible_window_topmost)
        self._topmost_guard_timer.start()

        self._segment_worker_thread = threading.Thread(target=self._segment_worker, daemon=True)
        self._segment_worker_thread.start()
        self._sounds_enabled = False
        self._sound_paths = {}
        self._sound_effects = {}

        smoke_test = os.getenv("SCRIBEFLOAT_UI_SMOKE_TEST") == "1"
        if smoke_test:
            self.panel.set_model_summary("UI / PREVIEW")
            self.panel.set_rec_available(True)
            self._set_state(UiState.IDLE, "Vista premium lista")
        else:
            self._init_sounds()
            self._register_hotkey()
            self._init_backends()

    def _connect_ui(self):
        self.panel.rec_requested.connect(self.toggle_recording)
        self.panel.copy_requested.connect(self._copy)
        self.panel.save_requested.connect(self._save)
        self.panel.clear_requested.connect(self._clear)
        self.panel.settings_requested.connect(self._open_settings)
        self.panel.minimize_requested.connect(self._minimize_panel)
        self.panel.capsule_requested.connect(self._minimize_panel)
        self.panel.close_requested.connect(self.shutdown)
        self.panel.language_selected.connect(self._change_language)
        self.panel.position_changed.connect(lambda point: self._save_position("panel_position", point))
        self.panel.restore_requested.connect(self._restore_from_capsule)
        self.capsule.expand_requested.connect(self._restore_from_capsule)
        self.capsule.record_requested.connect(self.toggle_recording)
        self.capsule.close_requested.connect(self.shutdown)
        self.capsule.position_changed.connect(lambda point: self._save_position("capsule_position", point))
        self.toggle_from_thread.connect(self.toggle_recording)
        self.audio_from_thread.connect(self._receive_audio_visual)
        self.segment_finished.connect(self._finish_segment)
        self.model_loaded.connect(self._on_model_loaded)
        self.model_failed.connect(self._on_model_failed)
        self.update_checked.connect(self._on_update_checked)
        self.update_failed.connect(self._on_update_failed)
        self.update_progress.connect(self._on_update_progress)
        self.update_downloaded.connect(self._on_update_downloaded)

    def _restore_positions(self):
        panel_position = self.cfg.get("panel_position")
        if _inside_any_screen(panel_position, self.panel.size()):
            self.panel.move(int(panel_position[0]), int(panel_position[1]))
        else:
            self.panel.move(74, 70)
        _clamp_widget_to_screen(self.panel)

        capsule_position = self.cfg.get("capsule_position")
        if _inside_any_screen(capsule_position, self.capsule.size()):
            self.capsule.move(int(capsule_position[0]), int(capsule_position[1]))
        else:
            screen = QApplication.primaryScreen().availableGeometry()
            x = screen.left() + (screen.width() - self.capsule.width()) // 2
            y = screen.bottom() - self.capsule.height() - 42
            self.capsule.move(x, y)
        _clamp_widget_to_screen(self.capsule)

    def _save_position(self, key, position):
        self.cfg[key] = [position.x(), position.y()]
        save_config(self.cfg)

    def _guard_visible_window_topmost(self):
        """Recover if a shell/display transition drops the native topmost state."""
        _enforce_always_on_top(self.capsule)
        _enforce_always_on_top(self.panel)
        if self.settings_dialog and self.settings_dialog.isVisible():
            _enforce_always_on_top(self.settings_dialog)

    def _set_state(self, state, message):
        self.state = state
        active = state in (UiState.RECORDING_CAPSULE, UiState.RECORDING_EXPANDED, UiState.FINALIZING)
        self.panel.set_status(message, recording=active)
        self.panel.set_recording(self.is_recording)
        self.capsule.set_recording(self.is_recording)

    def _init_sounds(self):
        self._sound_paths = {
            "start": self._asset_path("start.mp3"),
            "stop": self._asset_path("stop.mp3"),
        }
        try:
            missing = [path for path in self._sound_paths.values() if not os.path.isfile(path)]
            if missing:
                raise FileNotFoundError(f"Faltan recursos de sonido: {', '.join(missing)}")
            pygame.mixer.init()
            pygame.mixer.set_num_channels(4)
            self._sound_effects = {
                name: pygame.mixer.Sound(path) for name, path in self._sound_paths.items()
            }
            self._sounds_enabled = True
            print("[Audio] Sonidos cargados: start.mp3, stop.mp3")
        except Exception as exc:
            self._sounds_enabled = False
            self._sound_effects = {}
            print(f"[Audio] Error inicializando sonidos: {exc}")

    def _asset_path(self, filename):
        return str(ASSETS_DIR / filename)

    def _play_sound(self, name):
        if not self._sounds_enabled:
            return
        try:
            self._sound_effects[name].play()
            print(f"[Audio] Sonido reproducido: {name}")
        except Exception as exc:
            print(f"[Audio] Error reproduciendo {name}: {exc}")

    def _init_backends(self):
        def load_model():
            try:
                from transcriber import ScribeEngine

                model_size = self.cfg.get("model_size", "small")
                engine = ScribeEngine(language=self.current_language, model_size=model_size)
                engine.warm_up()
                self.scribe_engine = engine
                self.model_loaded.emit(engine.device, engine.compute_type, model_size)
            except Exception as exc:
                print(f"[Init] ScribeEngine error: {exc}")
                self.model_failed.emit(str(exc))

        threading.Thread(target=load_model, daemon=True).start()

    @Slot(str, str, str)
    def _on_model_loaded(self, device, compute_type, model_size):
        self.panel.set_model_summary(f"{model_size} / {device} / {compute_type}")
        self.panel.set_rec_available(True)
        if not self.is_recording:
            self._set_state(UiState.IDLE, "Modelo listo")

    @Slot(str)
    def _on_model_failed(self, error):
        self.panel.set_rec_available(False)
        self._set_state(UiState.ERROR, f"Error del modelo: {error}")

    def _register_hotkey(self):
        if self._hotkey_suspended:
            return
        try:
            keyboard.unhook_all_hotkeys()
        except Exception:
            pass
        hotkey = self.cfg.get("hotkey", "ctrl+space")
        try:
            keyboard.add_hotkey(
                hotkey,
                self._hotkey_triggered,
                suppress=True,
                trigger_on_release=True,
            )
            self._hotkey_enabled_after = time.monotonic() + 1.0
            self.panel.set_hotkey(hotkey)
            print(f"[Hotkey] Registrado: {hotkey}")
        except Exception as exc:
            self._set_state(UiState.ERROR, f"Error del atajo: {exc}")

    def _suspend_hotkey(self):
        self._hotkey_suspended = True
        try:
            keyboard.unhook_all_hotkeys()
        except Exception:
            pass

    def _resume_hotkey(self):
        if self._closing:
            return
        self._hotkey_suspended = False
        self._register_hotkey()

    def _hotkey_triggered(self):
        now = time.monotonic()
        if now < self._hotkey_enabled_after or now - self._last_hotkey_time < 0.45:
            return
        self._last_hotkey_time = now
        self.toggle_from_thread.emit()

    @Slot()
    def toggle_recording(self):
        if self.is_recording:
            self._stop_recording()
            return
        with self._segment_lock:
            if self._pending_segments > 0:
                self._set_state(UiState.FINALIZING, "Terminando transcripcion...")
                return
        if not self.scribe_engine and os.getenv("SCRIBEFLOAT_UI_SMOKE_TEST") != "1":
            self._set_state(UiState.LOADING_MODEL, "El modelo todavia esta cargando...")
            return
        self._start_recording()

    def _start_recording(self):
        print("[Recording] Inicio solicitado")
        self._return_to_capsule_after_recording = self.cfg.get("last_view") == "capsule"
        self.capsule.set_previewing(False)
        self._reset_transcription_state(clear_display=True, clear_model_context=True)
        with self._segment_lock:
            self._active_session_id += 1
            self._segment_seq = 0
            self._pending_segments = 0
        self.is_recording = True
        self._paste_after_stop = False
        self._paste_scheduled = False
        self._session_error = ""
        if self._return_to_capsule_after_recording:
            self._set_state(UiState.RECORDING_CAPSULE, "Escuchando...")
            self.capsule.set_status("ESCUCHANDO...")
            self._show_capsule()
        else:
            self.panel.show_listening_placeholder()
            self._set_state(UiState.RECORDING_EXPANDED, "Escuchando en modo privado...")
            if not self.panel.isVisible():
                self._show_panel(passive=True)
        self._play_sound("start")
        QTimer.singleShot(START_SOUND_DELAY_MS, self._start_audio_capture)

    def _start_audio_capture(self):
        if not self.is_recording:
            return
        try:
            from audio_stream import AudioCapture

            self.audio_capture = AudioCapture(
                on_segment_ready=self._on_segment,
                on_level_update=lambda level, speech, envelope: self.audio_from_thread.emit(
                    level, speech, envelope
                ),
                finalize_on_silence=True,
            )
            self.audio_capture.start()
        except Exception as exc:
            self.is_recording = False
            self.panel.set_transcription("")
            self._set_state(UiState.ERROR, f"Error de microfono: {exc}")
            if self._return_to_capsule_after_recording:
                self.capsule.set_status("ERROR DE MICROFONO")
                self._show_capsule()
            else:
                self.capsule.hide()
                self._show_panel(passive=True)

    @Slot()
    def _stop_recording(self):
        if not self.is_recording:
            return
        print("[Recording] Fin solicitado")
        self.is_recording = False
        self._paste_after_stop = True
        self._set_state(UiState.FINALIZING, "Procesando transcripcion...")
        if self._return_to_capsule_after_recording:
            self.capsule.set_status("PROCESANDO...")
            if not self.capsule.isVisible():
                self._show_capsule()
        elif not self.panel.isVisible():
            self._show_panel(passive=True)
        if self.audio_capture:
            self.audio_capture.stop()
            self.audio_capture = None
        self._play_sound("stop")
        self._maybe_complete_session()

    def _on_segment(self, audio_path):
        if not self.scribe_engine:
            try:
                os.remove(audio_path)
            except OSError:
                pass
            return
        with self._segment_lock:
            session_id = self._active_session_id
            self._segment_seq += 1
            segment_id = self._segment_seq
            self._pending_segments += 1
        self._segment_queue.put((session_id, segment_id, audio_path))

    def _segment_worker(self):
        while True:
            item = self._segment_queue.get()
            if item is None:
                self._segment_queue.task_done()
                return
            session_id, segment_id, audio_path = item
            text = ""
            error = ""
            try:
                text = self.scribe_engine.transcribe(audio_path)
                if text.startswith("[Error:"):
                    error = text
                    text = ""
                else:
                    text = clean_text(text) if text and text.strip() else ""
            except Exception as exc:
                error = str(exc)
            finally:
                try:
                    os.remove(audio_path)
                except OSError:
                    pass
                self.segment_finished.emit(session_id, segment_id, text, error)
                self._segment_queue.task_done()

    @Slot(int, int, str, str)
    def _finish_segment(self, session_id, segment_id, text, error):
        with self._segment_lock:
            if session_id != self._active_session_id:
                return
            self._completed_segments.add(segment_id)
            if text:
                self._session_parts[segment_id] = text
            ordered = []
            for key in range(1, self._segment_seq + 1):
                if key not in self._completed_segments:
                    break
                if self._session_parts.get(key):
                    ordered.append(self._session_parts[key])
            self._session_transcript = " ".join(ordered).strip()
            self.full_transcript = self._session_transcript
            self._pending_segments = max(0, self._pending_segments - 1)
        if error:
            self._session_error = error
            self._set_state(UiState.ERROR, "Error de transcripcion")
        self._maybe_complete_session()

    def _maybe_complete_session(self):
        if not self._paste_after_stop or self.is_recording or self._paste_scheduled:
            return
        with self._segment_lock:
            pending = self._pending_segments
            text = self._session_transcript.strip()
        if pending:
            return
        if self._session_error:
            self._finish_recording("Error de transcripcion", text=text)
            return
        if not text:
            self._finish_recording("No se detecto voz", text="")
            return
        self._paste_scheduled = True
        self._set_state(UiState.FINALIZING, "Pegando texto...")
        QTimer.singleShot(70, lambda value=text: self._paste_text(value))

    def _paste_text(self, text):
        clipboard = QApplication.clipboard()
        previous_text = clipboard.text()
        clipboard.setText(text + " ")

        def send_paste():
            try:
                self._release_keyboard_keys()
                keyboard.press_and_release("ctrl+v")
                self._release_keyboard_keys()
                QTimer.singleShot(250, lambda: self._restore_clipboard_and_finish(previous_text, text))
            except Exception as exc:
                print(f"[TypeOut] Error: {exc}")
                self._finish_recording("Texto listo; no se pudo pegar", text)

        QTimer.singleShot(45, send_paste)

    def _restore_clipboard_and_finish(self, previous_text, text):
        QApplication.clipboard().setText(previous_text)
        self._finish_recording("Texto pegado correctamente", text)

    def _release_keyboard_keys(self):
        for key in ("ctrl", "left ctrl", "right ctrl", "shift", "alt", "space", "v"):
            try:
                keyboard.release(key)
            except Exception:
                pass

    def _finish_recording(self, message, text):
        self._paste_after_stop = False
        self._paste_scheduled = False
        self._session_error = ""
        self.panel.set_transcription(text)
        state = UiState.READY_WITH_TEXT if text else UiState.IDLE
        self._set_state(state, message)
        if self._return_to_capsule_after_recording:
            self.capsule.set_status("LISTO")
            self._show_capsule()
        else:
            self.capsule.hide()
            self._show_panel(passive=True)

    @Slot(float, bool, object)
    def _receive_audio_visual(self, level, has_speech, envelope):
        self.capsule.set_audio_visual(level, envelope)
        self.panel.set_audio_level(level)

    def _show_capsule(self):
        was_visible = self.capsule.isVisible()
        self._save_position("panel_position", self.panel.pos())
        self.cfg["last_view"] = "capsule"
        save_config(self.cfg)
        self.panel.hide()
        if was_visible:
            self.capsule.setWindowOpacity(1.0)
            _enforce_always_on_top(self.capsule, force=True)
            return
        self.capsule.setWindowOpacity(0.0)
        self.capsule.show()
        _make_no_activate(self.capsule)
        _enforce_always_on_top(self.capsule, force=True)
        animation = QPropertyAnimation(self.capsule, b"windowOpacity", self)
        animation.setStartValue(0.0)
        animation.setEndValue(1.0)
        animation.setDuration(220)
        animation.setEasingCurve(QEasingCurve.OutCubic)
        animation.start()
        self._animations.append(animation)

    def _show_panel(self, passive=False):
        was_visible = self.panel.isVisible() and not self.panel.isMinimized()
        self.cfg["last_view"] = "panel"
        save_config(self.cfg)
        if not self.is_recording:
            self.capsule.hide()
        self.panel.setAttribute(Qt.WA_ShowWithoutActivating, passive)
        if not was_visible:
            self.panel.show_normal_from_controller()
            _ensure_taskbar_window(self.panel)
        _enforce_always_on_top(self.panel, force=True)
        if not passive:
            self.panel.activateWindow()

    def _expand_recording(self):
        if not self.is_recording:
            return
        self._return_to_capsule_after_recording = False
        self._save_position("capsule_position", self.capsule.pos())
        self.capsule.hide()
        self.panel.show_listening_placeholder()
        self._show_panel()
        self._set_state(UiState.RECORDING_EXPANDED, "Escuchando en modo privado...")

    def _restore_from_capsule(self):
        if self.is_recording:
            self._expand_recording()
        else:
            self._show_panel()

    def _minimize_panel(self):
        if self.is_recording:
            self._return_to_capsule_after_recording = True
            self._set_state(UiState.RECORDING_CAPSULE, "Escuchando...")
            self.capsule.set_status("ESCUCHANDO...")
            self._show_capsule()
        else:
            self.capsule.set_status("LISTO")
            self._show_capsule()

    def _change_language(self, language_code):
        self.current_language = language_code
        self.cfg["language"] = language_code
        save_config(self.cfg)
        if self.scribe_engine:
            self.scribe_engine.set_language(language_code)

    def _open_settings(self):
        if self.settings_dialog and self.settings_dialog.isVisible():
            self.settings_dialog.raise_()
            self.settings_dialog.activateWindow()
            return
        summary = self.panel.model_badge.text()
        capsule_was_visible = self.capsule.isVisible()
        self._settings_status_before_preview = self.capsule.status_text
        self._settings_preview_only_capsule = not capsule_was_visible and not self.is_recording
        if not self.is_recording:
            if self._settings_preview_only_capsule:
                panel_rect = self.panel.frameGeometry()
                self.capsule.move(panel_rect.left(), panel_rect.bottom() + 10)
                self.capsule.show()
                _make_no_activate(self.capsule)
                _enforce_always_on_top(self.capsule, force=True)
            self.capsule.set_status("VISTA PREVIA")
            self.capsule.set_previewing(True)
        self.settings_dialog = SettingsPanel(
            None,
            self.cfg,
            model_summary=summary,
            on_save=self._apply_settings,
            on_preview=self._preview_visual_settings,
            on_capture_start=self._suspend_hotkey,
            on_capture_finish=self._resume_hotkey,
            on_check_updates=self._check_for_updates,
            current_version=APP_VERSION,
        )
        self.settings_dialog.finished.connect(self._settings_closed)
        self.settings_dialog.show()
        anchor = self.capsule.frameGeometry() if self.capsule.isVisible() else self.panel.frameGeometry()
        _place_settings_dialog(self.settings_dialog, anchor)
        self.settings_dialog.raise_()
        self.settings_dialog.activateWindow()

    @Slot()
    def _settings_closed(self):
        if not self.is_recording:
            self.capsule.set_previewing(False)
            self.capsule.set_status(self._settings_status_before_preview)
            if self._settings_preview_only_capsule:
                self.capsule.hide()
        if self.settings_dialog:
            self.settings_dialog.deleteLater()
            self.settings_dialog = None
        self._settings_preview_only_capsule = False

    def _preview_visual_settings(self, preview_config):
        self.capsule.apply_visual_config(preview_config)

    def _apply_settings(self, new_config):
        previous_hotkey = self.cfg.get("hotkey", "ctrl+space")
        self.cfg.update(new_config)
        self.capsule.apply_visual_config(self.cfg)
        save_config(self.cfg)
        current_hotkey = self.cfg.get("hotkey", "ctrl+space")
        if current_hotkey != previous_hotkey:
            self._register_hotkey()
        else:
            self.panel.set_hotkey(current_hotkey)

    def _set_update_status(self, text, busy=False):
        if self.settings_dialog and self.settings_dialog.isVisible():
            self.settings_dialog.set_update_status(text, busy=busy)

    def _check_for_updates(self):
        if self._update_busy:
            return
        self._update_busy = True
        self._set_update_status("Consultando la ultima version en GitHub...", busy=True)

        def worker():
            try:
                self.update_checked.emit(check_for_update(APP_VERSION))
            except Exception as exc:
                self.update_failed.emit(str(exc))

        threading.Thread(target=worker, daemon=True).start()

    @Slot(object)
    def _on_update_checked(self, update):
        self._update_busy = False
        if not update:
            self._set_update_status(f"Version {APP_VERSION}: ya esta actualizada.")
            return

        self._pending_update = update
        self._set_update_status(f"Nueva version disponible: {update['version']}")
        answer = QMessageBox.question(
            self.settings_dialog,
            "Actualizacion disponible",
            f"Esta disponible Whisper Solution {update['version']}.\n\n"
            "¿Queres descargar ahora el instalador verificado?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes,
        )
        if answer == QMessageBox.Yes:
            self._download_pending_update()

    def _download_pending_update(self):
        if self._update_busy or not self._pending_update:
            return
        update = dict(self._pending_update)
        self._update_busy = True
        self._set_update_status(f"Descargando version {update['version']}... 0%", busy=True)

        def progress(value):
            self.update_progress.emit(value)

        def worker():
            try:
                installer = download_update(update, progress_callback=progress)
                self.update_downloaded.emit(installer)
            except Exception as exc:
                self.update_failed.emit(str(exc))

        threading.Thread(target=worker, daemon=True).start()

    @Slot(int)
    def _on_update_progress(self, value):
        version = self._pending_update["version"] if self._pending_update else "nueva"
        self._set_update_status(f"Descargando version {version}... {value}%", busy=True)

    @Slot(str)
    def _on_update_downloaded(self, installer_path):
        self._update_busy = False
        self._set_update_status("Actualizacion descargada y verificada.")
        answer = QMessageBox.question(
            self.settings_dialog,
            "Instalar actualizacion",
            "La descarga paso la verificacion SHA-256.\n\n"
            "¿Queres cerrar Whisper Solution e instalarla ahora?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes,
        )
        if answer != QMessageBox.Yes:
            self._set_update_status(f"Instalador listo en: {installer_path}")
            return
        try:
            subprocess.Popen([installer_path], cwd=os.path.dirname(installer_path), close_fds=True)
        except Exception as exc:
            self._on_update_failed(f"No se pudo abrir el instalador: {exc}")
            return
        QTimer.singleShot(150, self.shutdown)

    @Slot(str)
    def _on_update_failed(self, error):
        self._update_busy = False
        self._set_update_status("No se pudo completar la actualizacion.")
        QMessageBox.warning(
            self.settings_dialog,
            "Actualizacion no disponible",
            error,
        )

    def _copy(self):
        text = self.full_transcript.strip()
        if text:
            QApplication.clipboard().setText(text)
            self._set_state(UiState.READY_WITH_TEXT, "Texto copiado")

    def _save(self):
        text = self.full_transcript.strip()
        if not text:
            return
        save_transcription(text, export_dir=str(EXPORTS_DIR))
        self._set_state(UiState.READY_WITH_TEXT, "Transcripcion guardada")

    def _clear(self):
        self._reset_transcription_state(clear_display=True, clear_model_context=True)
        self._set_state(UiState.IDLE, "Listo para escuchar")

    def _reset_transcription_state(self, clear_display=False, clear_model_context=False):
        self.full_transcript = ""
        self._session_transcript = ""
        self._session_parts = {}
        self._completed_segments = set()
        self._paste_after_stop = False
        self._paste_scheduled = False
        self._session_error = ""
        if clear_model_context and self.scribe_engine:
            self.scribe_engine.clear_context()
        if clear_display:
            self.panel.set_transcription("")

    @Slot()
    def shutdown(self):
        if self._closing:
            return
        self._closing = True
        if self.settings_dialog:
            self.settings_dialog.close()
        self.panel.allow_close()
        self.capsule.close()
        self.panel.close()
        self._save_position("panel_position", self.panel.pos())
        self._save_position("capsule_position", self.capsule.pos())
        try:
            keyboard.unhook_all_hotkeys()
        except Exception:
            pass
        if self.audio_capture:
            self.audio_capture.stop()
            self.audio_capture = None
        self._segment_queue.put(None)
        _release_single_instance()
        self.application.exit(0)


def _verify_packaged_resources():
    """Exit-code based release check used after Nuitka compilation."""
    try:
        pygame.mixer.init()
        for filename in ("start.mp3", "stop.mp3"):
            path = ASSETS_DIR / filename
            if not path.is_file():
                return 2
            pygame.mixer.Sound(str(path))
        pygame.mixer.quit()
        return 0
    except Exception:
        return 3


def main():
    if "--verify-package" in sys.argv:
        return _verify_packaged_resources()
    _configure_runtime_log()
    if not _acquire_single_instance():
        return 0
    _set_windows_app_id()
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    app.setApplicationName("Whisper Solution")
    app.setWindowIcon(_make_app_icon())
    controller = ScribeFloatController(app)
    app._scribefloat_controller = controller
    exit_code = app.exec()
    if not controller._closing:
        controller.shutdown()
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
