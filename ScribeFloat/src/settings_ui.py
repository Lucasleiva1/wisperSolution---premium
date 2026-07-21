"""Configuration and visual adjustment dialogs for ScribeFloat Premium."""

import keyboard
from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QScrollBar,
    QSlider,
    QStyle,
    QStyleOptionSlider,
    QVBoxLayout,
    QWidget,
)


DIALOG_STYLE = """
    QDialog { background-color: #090e1d; }
    QFrame#settingsCard {
        background-color: #0a0e1d;
        border: 1px solid #273765;
        border-radius: 12px;
    }
    QLabel { color: #dae6ff; font-family: "Segoe UI"; }
    QLabel#settingsTitle { color: #f5f8ff; font-size: 14px; font-weight: 700; }
    QLabel#settingsSubtitle { color: #8392b9; font-size: 11px; }
    QLabel#caption { color: #5f76ab; font-size: 10px; font-weight: 600; }
    QLabel#hotkeyHelp {
        color: #a9b9dc; font-size: 10px;
        background: rgba(13, 24, 48, 175); border-radius: 9px;
        padding: 9px 11px;
    }
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
    QPushButton#settingsOptionButton {
        color: #ffffff; font-weight: 600;
        border: 1px solid rgba(82, 151, 255, 145);
        background: rgba(31, 62, 130, 185);
    }
    QPushButton#settingsOptionButton:hover {
        border-color: rgba(61, 218, 255, 220);
        background: rgba(40, 83, 166, 225);
    }
    QPushButton#ghostButton { background: transparent; color: #8292b8; border: none; }
    QPushButton#ghostButton:hover { color: #dce7ff; background: rgba(55, 68, 105, 90); }
    QPushButton#primaryButton {
        color: #ffffff; font-weight: 600;
        border: 1px solid rgba(95, 192, 255, 130);
        background: rgba(57, 88, 208, 190);
    }
    QPushButton#primaryButton:hover { background: rgba(75, 109, 235, 225); }
    QScrollArea#settingsScroll {
        background: transparent; border: none;
    }
    QWidget#settingsScrollContent { background: transparent; }
    QScrollBar:vertical {
        width: 9px; margin: 2px 0; border: none;
        background: rgba(23, 34, 62, 150); border-radius: 4px;
    }
    QScrollBar::handle:vertical {
        min-height: 34px; background: rgba(74, 112, 191, 190); border-radius: 4px;
    }
    QScrollBar::handle:vertical:hover { background: rgba(67, 196, 239, 205); }
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
"""


class TuningSlider(QSlider):
    """Slider controlled only by deliberate clicking and dragging."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._dragging = False

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
            self._dragging = True
            self._set_from_pointer(event.position())
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._dragging and event.buttons() & Qt.LeftButton:
            self._set_from_pointer(event.position())
            event.accept()
            return
        if self._dragging and not event.buttons() & Qt.LeftButton:
            self.cancel_drag()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self._dragging:
            self._set_from_pointer(event.position())
            self.cancel_drag()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def cancel_drag(self):
        self._dragging = False
        if self.isSliderDown():
            self.setSliderDown(False)

    def hideEvent(self, event):
        self.cancel_drag()
        super().hideEvent(event)

    def wheelEvent(self, event):
        # Scroll the options list without ever altering the hovered slider.
        parent = self.parentWidget()
        while parent is not None and not isinstance(parent, QScrollArea):
            parent = parent.parentWidget()
        if isinstance(parent, QScrollArea):
            scrollbar = parent.verticalScrollBar()
            pixel_delta = event.pixelDelta().y()
            if pixel_delta:
                scrollbar.setValue(scrollbar.value() - pixel_delta)
            else:
                wheel_steps = event.angleDelta().y() / 120.0
                distance = round(wheel_steps * max(18, scrollbar.singleStep() * 3))
                scrollbar.setValue(scrollbar.value() - distance)
            event.accept()
            return
        event.ignore()


class VisualSettingsPanel(QDialog):
    """Dedicated capsule appearance editor."""

    def __init__(self, parent, config, model_summary="", on_save=None, on_preview=None):
        super().__init__(parent)
        self.config_data = dict(config)
        self._original_config = dict(config)
        self.on_save = on_save
        self.on_preview = on_preview
        self._saved = False
        self._visual_sliders = {}

        self.setWindowTitle("Ajustes visuales - ScribeFloat Premium")
        self.setWindowFlags(Qt.Dialog | Qt.WindowTitleHint | Qt.WindowCloseButtonHint | Qt.WindowStaysOnTopHint)
        self.setWindowModality(Qt.WindowModal)
        self.setMinimumSize(470, 560)
        self.resize(470, 650)

        card = QFrame(self)
        card.setObjectName("settingsCard")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(card)

        body = QVBoxLayout(card)
        body.setContentsMargins(24, 22, 24, 22)
        body.setSpacing(10)

        title = QLabel("AJUSTES")
        title.setObjectName("settingsTitle")
        body.addWidget(title)

        subtitle = QLabel(
            "Personaliza la apariencia de la capsula. Las barras solo cambian cuando las arrastras."
        )
        subtitle.setObjectName("settingsSubtitle")
        subtitle.setWordWrap(True)
        body.addWidget(subtitle)

        self.scroll_area = QScrollArea()
        self.scroll_area.setObjectName("settingsScroll")
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_content = QWidget()
        scroll_content.setObjectName("settingsScrollContent")
        controls_body = QVBoxLayout(scroll_content)
        controls_body.setContentsMargins(2, 2, 10, 6)
        controls_body.setSpacing(10)
        self.scroll_area.setWidget(scroll_content)
        body.addWidget(self.scroll_area, 1)

        capsule_label = QLabel("CAPSULA  /  AJUSTE EN VIVO")
        capsule_label.setObjectName("caption")
        controls_body.addWidget(capsule_label)

        for slider_title, key, minimum, maximum, suffix in (
            ("Ancho", "capsule_width", 96, 1000, " px"),
            ("Alto", "capsule_height", 32, 320, " px"),
            ("Tamano del microfono", "microphone_size", 55, 180, " %"),
            ("Tamano del punto", "indicator_size", 55, 180, " %"),
            ("Ancho de pantalla de voz", "wave_width", 35, 175, " %"),
            ("Altura de onda", "wave_amplitude", 0, 100, ""),
            ("Velocidad de ondas", "wave_speed", 5, 100, ""),
            ("Reaccion a la voz", "wave_response", 5, 100, ""),
            ("Densidad visual", "wave_detail", 0, 7, ""),
        ):
            self._add_visual_slider(controls_body, slider_title, key, minimum, maximum, suffix)

        button_label = QLabel("BOTON ABRIR  /  POSICION Y ANIMACION")
        button_label.setObjectName("caption")
        controls_body.addWidget(button_label)
        self._add_visual_slider(
            controls_body,
            "Posicion vertical  /  subir - bajar",
            "open_button_offset",
            -18,
            36,
            " px",
        )
        self._add_visual_slider(
            controls_body,
            "Escala general  /  todo el boton",
            "open_button_size",
            60,
            160,
            " %",
        )
        self._add_visual_slider(
            controls_body,
            "Ancho  /  alargar - acortar",
            "open_button_width",
            60,
            200,
            " %",
        )
        self._add_visual_slider(
            controls_body,
            "Alto  /  mas alto - mas fino",
            "open_button_height",
            60,
            180,
            " %",
        )
        self._add_visual_slider(
            controls_body,
            "Duracion de la animacion",
            "open_button_animation_tenths",
            2,
            40,
            " s",
            divisor=10,
        )

        if model_summary:
            model_label = QLabel(model_summary)
            model_label.setObjectName("modelHint")
            controls_body.addWidget(model_label)
        controls_body.addStretch()

        actions = QHBoxLayout()
        actions.addStretch()
        cancel_btn = QPushButton("Cancelar")
        cancel_btn.setObjectName("ghostButton")
        cancel_btn.clicked.connect(self.reject)
        save_btn = QPushButton("Guardar ajustes")
        save_btn.setObjectName("primaryButton")
        save_btn.clicked.connect(self._save)
        actions.addWidget(cancel_btn)
        actions.addWidget(save_btn)
        body.addLayout(actions)

        self.setStyleSheet(DIALOG_STYLE)

    def _add_visual_slider(self, layout, title, key, minimum, maximum, suffix, divisor=1):
        label_row = QHBoxLayout()
        title_label = QLabel(title)
        title_label.setObjectName("sliderLabel")
        value_label = QLabel()
        value_label.setObjectName("sliderValue")
        label_row.addWidget(title_label)
        label_row.addStretch()
        label_row.addWidget(value_label)

        slider = TuningSlider(Qt.Horizontal)
        slider.setFocusPolicy(Qt.NoFocus)
        slider.setRange(minimum, maximum)
        slider.setSingleStep(1)
        slider.setMinimumHeight(28)
        slider.setValue(int(self.config_data.get(key, minimum)))
        slider.valueChanged.connect(
            lambda value, item_key=key, shown=value_label, unit=suffix, scale=divisor:
            self._visual_changed(item_key, value, shown, unit, scale)
        )
        value_label.setText(self._format_slider_value(slider.value(), suffix, divisor))
        self._visual_sliders[key] = slider
        layout.addLayout(label_row)
        layout.addWidget(slider)

    @staticmethod
    def _format_slider_value(value, suffix, divisor):
        if divisor == 1:
            shown = str(value)
        else:
            shown = f"{value / divisor:.1f}".rstrip("0").rstrip(".")
        return f"{shown}{suffix}"

    def _visual_changed(self, key, value, label, suffix, divisor=1):
        self.config_data[key] = int(value)
        label.setText(self._format_slider_value(value, suffix, divisor))
        if self.on_preview:
            self.on_preview(dict(self.config_data))

    def _save(self):
        self._end_slider_interactions()
        if self.on_save:
            self.on_save(dict(self.config_data))
        self._saved = True
        self.accept()

    def reject(self):
        self._end_slider_interactions()
        if not self._saved and self.on_preview:
            self.on_preview(dict(self._original_config))
        super().reject()

    def _end_slider_interactions(self):
        for slider in self._visual_sliders.values():
            slider.cancel_drag()


class SettingsPanel(QDialog):
    """Main configuration screen with independent options."""

    hotkey_captured = Signal(str)

    def __init__(
        self,
        parent,
        config,
        model_summary="",
        on_save=None,
        on_preview=None,
        on_capture_start=None,
        on_capture_finish=None,
        on_check_updates=None,
        current_version="",
    ):
        super().__init__(parent)
        self.config_data = dict(config)
        self._original_config = dict(config)
        self.model_summary = model_summary
        self.on_save = on_save
        self.on_preview = on_preview
        self.on_capture_start = on_capture_start
        self.on_capture_finish = on_capture_finish
        self.on_check_updates = on_check_updates
        self.current_version = current_version
        self._saved = False
        self._capturing_hotkey = False
        self._keyboard_hook = None
        self.visual_dialog = None

        self.setWindowTitle("Configuracion - ScribeFloat Premium")
        self.setWindowFlags(Qt.Dialog | Qt.WindowTitleHint | Qt.WindowCloseButtonHint | Qt.WindowStaysOnTopHint)
        self.setMinimumSize(470, 500)
        self.resize(470, 500)
        self.hotkey_captured.connect(self._finish_capture)

        card = QFrame(self)
        card.setObjectName("settingsCard")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(card)

        body = QVBoxLayout(card)
        body.setContentsMargins(24, 22, 24, 22)
        body.setSpacing(12)

        title = QLabel("CONFIGURACION")
        title.setObjectName("settingsTitle")
        body.addWidget(title)

        subtitle = QLabel("Administra el atajo de voz y las opciones disponibles.")
        subtitle.setObjectName("settingsSubtitle")
        subtitle.setWordWrap(True)
        body.addWidget(subtitle)

        key_label = QLabel("ATAJO GLOBAL  /  HABLAR Y DETENER")
        key_label.setObjectName("caption")
        body.addWidget(key_label)

        shortcut = self.config_data.get("hotkey", "ctrl+space").upper()
        shortcut_help = QLabel(
            f"Usa {shortcut} para empezar a hablar y vuelve a pulsarlo para terminar. "
            "Puedes elegir cualquier otra combinacion."
        )
        shortcut_help.setObjectName("hotkeyHelp")
        shortcut_help.setWordWrap(True)
        body.addWidget(shortcut_help)

        hotkey_row = QHBoxLayout()
        hotkey_row.setSpacing(10)
        self.hotkey_entry = QLineEdit(self.config_data.get("hotkey", "ctrl+space"))
        self.hotkey_entry.setObjectName("hotkeyEntry")
        self.hotkey_entry.setReadOnly(True)
        self.capture_btn = QPushButton("Cambiar atajo")
        self.capture_btn.setObjectName("secondaryButton")
        self.capture_btn.clicked.connect(self._start_capture)
        hotkey_row.addWidget(self.hotkey_entry, 1)
        hotkey_row.addWidget(self.capture_btn)
        body.addLayout(hotkey_row)

        options_card = QFrame()
        options_card.setObjectName("visualOptionCard")
        options_layout = QHBoxLayout(options_card)
        options_layout.setContentsMargins(14, 12, 14, 12)
        options_text = QVBoxLayout()
        options_text.setSpacing(2)
        options_title = QLabel("AJUSTES")
        options_title.setObjectName("caption")
        options_description = QLabel("Tamano, onda y apariencia de la capsula")
        options_description.setObjectName("settingsSubtitle")
        options_text.addWidget(options_title)
        options_text.addWidget(options_description)
        options_layout.addLayout(options_text, 1)
        open_adjustments = QPushButton("Abrir ajustes")
        open_adjustments.setObjectName("settingsOptionButton")
        open_adjustments.clicked.connect(self._open_visual_settings)
        options_layout.addWidget(open_adjustments)
        body.addWidget(options_card)

        update_card = QFrame()
        update_card.setObjectName("visualOptionCard")
        update_layout = QHBoxLayout(update_card)
        update_layout.setContentsMargins(14, 12, 14, 12)
        update_text = QVBoxLayout()
        update_text.setSpacing(2)
        update_title = QLabel("ACTUALIZACIONES")
        update_title.setObjectName("caption")
        version_text = f"Version instalada: {self.current_version}" if self.current_version else "GitHub Releases"
        self.update_status = QLabel(version_text)
        self.update_status.setObjectName("settingsSubtitle")
        self.update_status.setWordWrap(True)
        update_text.addWidget(update_title)
        update_text.addWidget(self.update_status)
        update_layout.addLayout(update_text, 1)
        self.update_btn = QPushButton("Buscar actualizaciones")
        self.update_btn.setObjectName("settingsOptionButton")
        self.update_btn.clicked.connect(self._request_update_check)
        update_layout.addWidget(self.update_btn)
        body.addWidget(update_card)

        if model_summary:
            model_label = QLabel(model_summary)
            model_label.setObjectName("modelHint")
            body.addWidget(model_label)

        actions = QHBoxLayout()
        actions.addStretch()
        cancel_btn = QPushButton("Cancelar")
        cancel_btn.setObjectName("ghostButton")
        cancel_btn.clicked.connect(self.reject)
        save_btn = QPushButton("Guardar configuracion")
        save_btn.setObjectName("primaryButton")
        save_btn.clicked.connect(self._save)
        actions.addWidget(cancel_btn)
        actions.addWidget(save_btn)
        body.addStretch()
        body.addLayout(actions)

        self.setStyleSheet(
            DIALOG_STYLE
            + """
            QFrame#visualOptionCard {
                background: rgba(11, 22, 45, 190);
                border: 1px solid rgba(49, 76, 133, 155);
                border-radius: 11px;
            }
            """
        )

    def _request_update_check(self):
        if not self.on_check_updates:
            self.set_update_status("La busqueda de actualizaciones no esta disponible.")
            return
        self.set_update_status("Consultando la ultima version en GitHub...", busy=True)
        self.on_check_updates()

    def set_update_status(self, text, busy=False):
        self.update_status.setText(text)
        self.update_btn.setEnabled(not busy)
        self.update_btn.setText("Comprobando..." if busy else "Buscar actualizaciones")

    def _open_visual_settings(self):
        if self.visual_dialog and self.visual_dialog.isVisible():
            self.visual_dialog.raise_()
            self.visual_dialog.activateWindow()
            return
        self.visual_dialog = VisualSettingsPanel(
            self,
            self.config_data,
            model_summary=self.model_summary,
            on_save=self._visual_saved,
            on_preview=self.on_preview,
        )
        self.visual_dialog.finished.connect(self._visual_closed)
        self.visual_dialog.show()
        self.visual_dialog.raise_()
        self.visual_dialog.activateWindow()

    def _visual_saved(self, visual_config):
        self.config_data.update(visual_config)
        self._original_config.update(visual_config)
        if self.on_save:
            self.on_save(dict(self.config_data))

    @Slot()
    def _visual_closed(self):
        if self.visual_dialog:
            self.visual_dialog.deleteLater()
            self.visual_dialog = None

    def _start_capture(self):
        if self._capturing_hotkey:
            return
        self._capturing_hotkey = True
        self.hotkey_entry.setText("presiona una combinacion...")
        self.capture_btn.setText("Presiona teclas")
        self.capture_btn.setEnabled(False)
        if self.on_capture_start:
            self.on_capture_start()
        try:
            self._keyboard_hook = keyboard.hook(self._capture_event, suppress=False)
        except Exception:
            self._finish_capture("")

    def _capture_event(self, event):
        modifier_names = {
            "ctrl", "left ctrl", "right ctrl", "shift", "left shift",
            "right shift", "alt", "left alt", "right alt",
        }
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
        self.capture_btn.setText("Cambiar atajo")
        self.capture_btn.setEnabled(True)
        self.hotkey_entry.setText(value or self.config_data.get("hotkey", "ctrl+space"))
        if self.on_capture_finish:
            self.on_capture_finish()

    def _save(self):
        value = self.hotkey_entry.text().strip()
        if value and value != "presiona una combinacion...":
            self.config_data["hotkey"] = value
        if self.on_save:
            self.on_save(dict(self.config_data))
        self._saved = True
        self.accept()

    def reject(self):
        if self._capturing_hotkey:
            self._finish_capture("")
        if self.visual_dialog and self.visual_dialog.isVisible():
            self.visual_dialog.reject()
        if not self._saved and self.on_preview:
            self.on_preview(dict(self._original_config))
        super().reject()
