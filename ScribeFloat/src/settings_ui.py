"""Premium PySide6 settings dialog for ScribeFloat Premium."""

import keyboard
from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSlider,
    QStyle,
    QStyleOptionSlider,
    QVBoxLayout,
)


class TuningSlider(QSlider):
    """Precise direct-manipulation slider with mouse capture while dragging."""

    def _set_from_pointer(self, position):
        option = QStyleOptionSlider()
        self.initStyleOption(option)
        handle_length = self.style().pixelMetric(QStyle.PM_SliderLength, option, self)
        span = max(1, self.width() - handle_length)
        pointer = max(0, min(span, round(position.x() - (handle_length / 2))))
        value = QStyle.sliderValueFromPosition(
            self.minimum(),
            self.maximum(),
            pointer,
            span,
            option.upsideDown,
        )
        self.setValue(value)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._set_from_pointer(event.position())
            self.setSliderDown(True)
            self.grabMouse()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.isSliderDown():
            self._set_from_pointer(event.position())
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self.isSliderDown():
            self._set_from_pointer(event.position())
            self.setSliderDown(False)
            self.releaseMouse()
            event.accept()
            return
        super().mouseReleaseEvent(event)


class SettingsPanel(QDialog):
    """Non-blocking hotkey settings dialog styled to match the premium UI."""

    hotkey_captured = Signal(str)

    def __init__(self, parent, config, model_summary="", on_save=None, on_preview=None):
        super().__init__(parent)
        self.config_data = dict(config)
        self._original_config = dict(config)
        self.on_save = on_save
        self.on_preview = on_preview
        self._saved = False
        self._capturing_hotkey = False
        self._keyboard_hook = None

        self.setWindowTitle("Configuracion - ScribeFloat Premium")
        self.setWindowFlags(Qt.Dialog | Qt.WindowTitleHint | Qt.WindowCloseButtonHint | Qt.WindowStaysOnTopHint)
        self.setMinimumSize(460, 600)
        self.resize(460, 600)
        self.hotkey_captured.connect(self._finish_capture)

        card = QFrame(self)
        card.setObjectName("settingsCard")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(card)

        body = QVBoxLayout(card)
        body.setContentsMargins(24, 22, 24, 22)
        body.setSpacing(11)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        title = QLabel("CONFIGURACION")
        title.setObjectName("settingsTitle")
        header.addWidget(title)
        header.addStretch()
        body.addLayout(header)

        subtitle = QLabel("Ajustes en vivo de la capsula.")
        subtitle.setObjectName("settingsSubtitle")
        subtitle.setWordWrap(True)
        body.addWidget(subtitle)

        key_label = QLabel("ATAJO GLOBAL  /  REC - STOP")
        key_label.setObjectName("caption")
        body.addWidget(key_label)

        hotkey_row = QHBoxLayout()
        hotkey_row.setSpacing(10)
        self.hotkey_entry = QLineEdit(self.config_data.get("hotkey", "ctrl+space"))
        self.hotkey_entry.setObjectName("hotkeyEntry")
        self.hotkey_entry.setReadOnly(True)
        self.capture_btn = QPushButton("Capturar")
        self.capture_btn.setObjectName("secondaryButton")
        self.capture_btn.clicked.connect(self._start_capture)
        hotkey_row.addWidget(self.hotkey_entry, 1)
        hotkey_row.addWidget(self.capture_btn)
        body.addLayout(hotkey_row)

        capsule_label = QLabel("CAPSULA  /  AJUSTE EN VIVO")
        capsule_label.setObjectName("caption")
        body.addWidget(capsule_label)
        self._visual_sliders = {}
        for title, key, minimum, maximum, suffix in (
            ("Ancho", "capsule_width", 150, 560, " px"),
            ("Alto", "capsule_height", 44, 140, " px"),
            ("Velocidad de ondas", "wave_speed", 5, 100, ""),
            ("Reaccion a la voz", "wave_response", 5, 100, ""),
            ("Densidad visual", "wave_detail", 0, 7, ""),
        ):
            self._add_visual_slider(body, title, key, minimum, maximum, suffix)

        if model_summary:
            model_label = QLabel(model_summary)
            model_label.setObjectName("modelHint")
            body.addWidget(model_label)

        actions = QHBoxLayout()
        actions.addStretch()
        cancel_btn = QPushButton("Cancelar")
        cancel_btn.setObjectName("ghostButton")
        cancel_btn.clicked.connect(self.reject)
        save_btn = QPushButton("Guardar cambios")
        save_btn.setObjectName("primaryButton")
        save_btn.clicked.connect(self._save)
        actions.addWidget(cancel_btn)
        actions.addWidget(save_btn)
        body.addStretch()
        body.addLayout(actions)

        self.setStyleSheet(
            """
            QDialog {
                background-color: #090e1d;
            }
            QFrame#settingsCard {
                background-color: #0a0e1d;
                border: 1px solid #273765;
                border-radius: 12px;
            }
            QLabel { color: #dae6ff; font-family: "Segoe UI"; }
            QLabel#settingsTitle { color: #f5f8ff; font-size: 14px; font-weight: 700; }
            QLabel#settingsSubtitle { color: #8392b9; font-size: 11px; }
            QLabel#caption { color: #5f76ab; font-size: 10px; font-weight: 600; }
            QLabel#sliderLabel { color: #a9bae0; font-size: 10px; }
            QLabel#sliderValue { color: #5fd8ff; font-family: "Consolas"; font-size: 10px; }
            QLabel#modelHint {
                color: #59d7ff; font-size: 10px; background: rgba(13, 38, 66, 130);
                border-radius: 8px; padding: 6px 10px;
            }
            QLineEdit#hotkeyEntry {
                color: #e7eeff; background: rgba(15, 23, 46, 230);
                border: 1px solid rgba(74, 102, 167, 145); border-radius: 10px;
                min-height: 30px; padding: 0 12px; font-family: "Consolas"; font-size: 12px;
            }
            QSlider::groove:horizontal {
                height: 7px; border-radius: 3px; background: rgba(44, 59, 98, 190);
            }
            QSlider::handle:horizontal {
                background: #43d8ff; border: 2px solid rgba(188, 245, 255, 210);
                width: 18px; height: 18px; margin: -7px 0; border-radius: 10px;
            }
            QSlider::sub-page:horizontal { background: #365fdc; border-radius: 3px; }
            QPushButton {
                color: #dbe8ff; font-family: "Segoe UI"; font-size: 11px;
                min-height: 30px; padding: 0 14px; border-radius: 10px;
            }
            QPushButton#secondaryButton {
                border: 1px solid rgba(37, 198, 255, 110);
                background: rgba(15, 43, 78, 150); color: #61d9ff;
            }
            QPushButton#secondaryButton:hover { background: rgba(18, 62, 101, 220); }
            QPushButton#ghostButton { background: transparent; color: #8292b8; border: none; }
            QPushButton#ghostButton:hover { color: #dce7ff; background: rgba(55, 68, 105, 90); }
            QPushButton#primaryButton {
                color: #ffffff; font-weight: 600;
                border: 1px solid rgba(95, 192, 255, 130);
                background: rgba(57, 88, 208, 190);
            }
            QPushButton#primaryButton:hover { background: rgba(75, 109, 235, 225); }
            """
        )

    def _add_visual_slider(self, layout, title, key, minimum, maximum, suffix):
        label_row = QHBoxLayout()
        title_label = QLabel(title)
        title_label.setObjectName("sliderLabel")
        value_label = QLabel()
        value_label.setObjectName("sliderValue")
        label_row.addWidget(title_label)
        label_row.addStretch()
        label_row.addWidget(value_label)
        slider = TuningSlider(Qt.Horizontal)
        slider.setRange(minimum, maximum)
        slider.setSingleStep(1)
        slider.setMinimumHeight(28)
        slider.setValue(int(self.config_data.get(key, minimum)))
        slider.valueChanged.connect(
            lambda value, item_key=key, shown=value_label, unit=suffix:
            self._visual_changed(item_key, value, shown, unit)
        )
        value_label.setText(f"{slider.value()}{suffix}")
        self._visual_sliders[key] = slider
        layout.addLayout(label_row)
        layout.addWidget(slider)

    def _visual_changed(self, key, value, label, suffix):
        self.config_data[key] = int(value)
        label.setText(f"{value}{suffix}")
        if self.on_preview:
            self.on_preview(dict(self.config_data))

    def _start_capture(self):
        if self._capturing_hotkey:
            return
        self._capturing_hotkey = True
        self.hotkey_entry.setText("presiona una combinacion...")
        self.capture_btn.setText("Esperando")
        self.capture_btn.setEnabled(False)
        try:
            self._keyboard_hook = keyboard.hook(self._capture_event, suppress=False)
        except Exception:
            self._finish_capture("")

    def _capture_event(self, event):
        modifier_names = {"ctrl", "left ctrl", "right ctrl", "shift", "left shift", "right shift", "alt", "left alt", "right alt"}
        if not self._capturing_hotkey or event.event_type != keyboard.KEY_DOWN or event.name in modifier_names:
            return
        self.hotkey_captured.emit(keyboard.get_hotkey_name() or event.name)

    @Slot(str)
    def _finish_capture(self, value):
        if not self._capturing_hotkey:
            return
        if self._keyboard_hook is not None:
            try:
                keyboard.unhook(self._keyboard_hook)
            except Exception:
                pass
            self._keyboard_hook = None
        self._capturing_hotkey = False
        self.capture_btn.setText("Capturar")
        self.capture_btn.setEnabled(True)
        self.hotkey_entry.setText(value or self.config_data.get("hotkey", "ctrl+space"))

    def _save(self):
        value = self.hotkey_entry.text().strip()
        if value and value != "presiona una combinacion...":
            self.config_data["hotkey"] = value
        if self.on_save:
            self.on_save(self.config_data)
        self._saved = True
        self.accept()

    def reject(self):
        if self._capturing_hotkey:
            self._finish_capture("")
        if not self._saved and self.on_preview:
            self.on_preview(dict(self._original_config))
        super().reject()
