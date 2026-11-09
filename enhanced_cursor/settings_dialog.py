import os
import sys
from PySide6.QtWidgets import (
    QDialog, QWidget, QLabel, QSpinBox, QColorDialog,
    QPushButton, QVBoxLayout, QHBoxLayout, QCheckBox, QSlider
)
from PySide6.QtCore import Qt, QPoint
from PySide6.QtGui import QPainter, QColor, QPen, QIcon, QWheelEvent

from enhanced_cursor.config import ConfigManager, CursorConfig
from enhanced_cursor.logger import open_log_file, get_logger
from enhanced_cursor.win32_utils import set_autostart, is_autostart_enabled

logger = get_logger()


class PreviewWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(200, 200)
        self.cursor_size = 4
        self.cursor_color = QColor(115, 115, 204, 128)
        self.cursor_border_color = QColor(0, 0, 0, 0)
        self.cursor_border_width = 0
        self.cursor_outline_size = 16
        self.cursor_outline_color = QColor(169, 169, 222, 36)
        self.zoom_level = 1.0
        self.setMouseTracking(True)

    def set_properties(self, cursor_size, cursor_color, cursor_outline_size, cursor_outline_color, cursor_border_color, cursor_border_width):
        self.cursor_size = cursor_size
        self.cursor_color = cursor_color
        self.cursor_outline_size = cursor_outline_size
        self.cursor_outline_color = cursor_outline_color
        self.cursor_border_color = cursor_border_color
        self.cursor_border_width = cursor_border_width
        self.update()

    def set_zoom_level(self, zoom):
        self.zoom_level = zoom
        self.update()

    def wheelEvent(self, event: QWheelEvent):
        delta = event.angleDelta().y()
        if delta > 0:
            self.zoom_level = min(self.zoom_level + 0.1, 2.0)
        elif delta < 0:
            self.zoom_level = max(self.zoom_level - 0.1, 0.2)
        self.update()
        if self.parent() and hasattr(self.parent(), 'zoom_slider'):
            self.parent().zoom_slider.setValue(int(self.zoom_level * 100))

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        scaled_cursor_size = self.cursor_size * self.zoom_level
        scaled_outline_size = self.cursor_outline_size * self.zoom_level

        center_x = self.width() / 2
        center_y = self.height() / 2

        outline_pen = QPen(self.cursor_outline_color, 0)
        painter.setPen(outline_pen)
        painter.setBrush(self.cursor_outline_color)
        painter.drawEllipse(QPoint(int(center_x), int(center_y)), int(scaled_outline_size), int(scaled_outline_size))

        pen = QPen(self.cursor_border_color, self.cursor_border_width)
        painter.setPen(pen)
        painter.setBrush(self.cursor_color)
        painter.drawEllipse(QPoint(int(center_x), int(center_y)), int(scaled_cursor_size), int(scaled_cursor_size))


class SettingsDialog(QDialog):
    def __init__(self, config_manager: ConfigManager, icon_path: str, parent=None):
        super().__init__(parent)
        self.config_manager = config_manager
        self.icon_path = icon_path

        self.setWindowTitle('EnhancedCursor: Settings')
        if os.path.exists(self.icon_path):
            self.setWindowIcon(QIcon(self.icon_path))

        self.setMinimumSize(640, 320)
        self.setStyleSheet('QDialog {background-color: #242424;} QLabel {color: #ffffff;}')

        # Local colors with alpha
        self.cursor_color = QColor(115, 115, 204, 128)
        self.cursor_outline_color = QColor(169, 169, 222, 36)
        self.cursor_border_color = QColor(0, 0, 0, 0)

        self.preview_widget = PreviewWidget(self)

        self.zoom_slider = QSlider(Qt.Orientation.Horizontal)
        self.zoom_slider.setRange(20, 200)
        self.zoom_slider.setValue(100)
        self.zoom_slider.valueChanged.connect(self.update_preview_zoom)

        self.size_label = QLabel('Cursor Size:')
        self.size_spinbox = QSpinBox()
        self.size_spinbox.setRange(1, 50)
        self.size_spinbox.valueChanged.connect(self.update_preview)

        self.outline_label = QLabel('Outline Size:')
        self.outline_spinbox = QSpinBox()
        self.outline_spinbox.setRange(1, 50)
        self.outline_spinbox.valueChanged.connect(self.update_preview)

        self.color_label = QLabel('Cursor Color:')
        self.color_button = QPushButton('Choose Color')
        self.color_button.clicked.connect(self.choose_cursor_color)

        self.color_opacity_label = QLabel('Cursor Opacity:')
        self.color_opacity_spinbox = QSpinBox()
        self.color_opacity_spinbox.setRange(0, 255)
        self.color_opacity_spinbox.valueChanged.connect(self.update_preview)

        self.outline_color_label = QLabel('Outline Color:')
        self.outline_color_button = QPushButton('Choose Color')
        self.outline_color_button.clicked.connect(self.choose_outline_color)

        self.outline_opacity_label = QLabel('Outline Opacity:')
        self.outline_opacity_spinbox = QSpinBox()
        self.outline_opacity_spinbox.setRange(0, 255)
        self.outline_opacity_spinbox.valueChanged.connect(self.update_preview)

        self.border_color_label = QLabel('Border Color:')
        self.border_color_button = QPushButton('Choose Color')
        self.border_color_button.clicked.connect(self.choose_border_color)

        self.border_opacity_label = QLabel('Border Opacity:')
        self.border_opacity_spinbox = QSpinBox()
        self.border_opacity_spinbox.setRange(0, 255)
        self.border_opacity_spinbox.valueChanged.connect(self.update_preview)

        self.speed_label = QLabel('Speed')
        self.speed_spinbox = QSpinBox()
        self.speed_spinbox.setRange(1, 100)

        self.border_label = QLabel('Border width:')
        self.border_spinbox = QSpinBox()
        self.border_spinbox.setRange(0, 10)
        self.border_spinbox.valueChanged.connect(self.update_preview)

        self.start_on_login_checkbox = QCheckBox('Start on login')
        self.start_on_login_checkbox.setStyleSheet('color: #ffffff;')

        self.animation_duration_label = QLabel('Animation Duration:')
        self.animation_duration_spinbox = QSpinBox()
        self.animation_duration_spinbox.setRange(100, 1000)

        self.save_button = QPushButton('Save')
        self.save_button.clicked.connect(self.save_settings)

        self.close_button = QPushButton('Close')
        self.close_button.clicked.connect(self.close)

        self.set_default_button = QPushButton('Set defaults')
        self.set_default_button.clicked.connect(self.set_defaults)

        self.log_button = QPushButton('Show Logs')
        self.log_button.clicked.connect(self.open_log_file)

        main_layout = QVBoxLayout()
        h_layout = QHBoxLayout()
        layout = QVBoxLayout()

        layout.addWidget(self.log_button)

        size_layout = QHBoxLayout()
        size_layout.addWidget(self.size_label)
        size_layout.addWidget(self.size_spinbox)
        layout.addLayout(size_layout)

        outline_layout = QHBoxLayout()
        outline_layout.addWidget(self.outline_label)
        outline_layout.addWidget(self.outline_spinbox)
        layout.addLayout(outline_layout)

        color_layout = QHBoxLayout()
        color_layout.addWidget(self.color_label)
        color_layout.addWidget(self.color_button)
        color_layout.addWidget(self.color_opacity_label)
        color_layout.addWidget(self.color_opacity_spinbox)
        layout.addLayout(color_layout)

        outline_color_layout = QHBoxLayout()
        outline_color_layout.addWidget(self.outline_color_label)
        outline_color_layout.addWidget(self.outline_color_button)
        outline_color_layout.addWidget(self.outline_opacity_label)
        outline_color_layout.addWidget(self.outline_opacity_spinbox)
        layout.addLayout(outline_color_layout)

        border_color_layout = QHBoxLayout()
        border_color_layout.addWidget(self.border_color_label)
        border_color_layout.addWidget(self.border_color_button)
        border_color_layout.addWidget(self.border_opacity_label)
        border_color_layout.addWidget(self.border_opacity_spinbox)
        layout.addLayout(border_color_layout)

        speed_layout = QHBoxLayout()
        speed_layout.addWidget(self.speed_label)
        speed_layout.addWidget(self.speed_spinbox)
        layout.addLayout(speed_layout)

        border_layout = QHBoxLayout()
        border_layout.addWidget(self.border_label)
        border_layout.addWidget(self.border_spinbox)
        layout.addLayout(border_layout)

        animation_duration_layout = QHBoxLayout()
        animation_duration_layout.addWidget(self.animation_duration_label)
        animation_duration_layout.addWidget(self.animation_duration_spinbox)
        layout.addLayout(animation_duration_layout)

        layout.addWidget(self.start_on_login_checkbox)

        buttons_layout = QHBoxLayout()
        buttons_layout.addWidget(self.save_button)
        buttons_layout.addWidget(self.close_button)
        buttons_layout.addWidget(self.set_default_button)
        layout.addLayout(buttons_layout)

        h_layout.addLayout(layout)
        h_layout.addWidget(self.preview_widget)
        main_layout.addLayout(h_layout)
        main_layout.addWidget(self.zoom_slider)
        self.setLayout(main_layout)

        self.load_settings()

    def update_preview_zoom(self):
        zoom_level = self.zoom_slider.value() / 100
        self.preview_widget.set_zoom_level(zoom_level)

    def update_preview(self):
        self.cursor_color.setAlpha(self.color_opacity_spinbox.value())
        self.cursor_outline_color.setAlpha(self.outline_opacity_spinbox.value())
        self.cursor_border_color.setAlpha(self.border_opacity_spinbox.value())

        self.preview_widget.set_properties(
            self.size_spinbox.value(),
            self.cursor_color,
            self.outline_spinbox.value(),
            self.cursor_outline_color,
            self.cursor_border_color,
            self.border_spinbox.value()
        )

    def choose_cursor_color(self):
        color = QColorDialog.getColor(self.cursor_color, self)
        if color.isValid():
            self.cursor_color = color
            self.color_button.setStyleSheet(f"background-color: {color.name()};")
            self.update_preview()

    def choose_outline_color(self):
        color = QColorDialog.getColor(self.cursor_outline_color, self)
        if color.isValid():
            self.cursor_outline_color = color
            self.outline_color_button.setStyleSheet(f"background-color: {color.name()};")
            self.update_preview()

    def choose_border_color(self):
        color = QColorDialog.getColor(self.cursor_border_color, self)
        if color.isValid():
            self.cursor_border_color = color
            self.border_color_button.setStyleSheet(f"background-color: {color.name()};")
            self.update_preview()

    def set_defaults(self):
        self.size_spinbox.setValue(4)
        self.outline_spinbox.setValue(16)
        self.cursor_color = QColor(115, 115, 204, 128)
        self.cursor_outline_color = QColor(169, 169, 222, 36)
        self.cursor_border_color = QColor(0, 0, 0, 0)
        self.speed_spinbox.setValue(25)
        self.border_spinbox.setValue(0)
        self.animation_duration_spinbox.setValue(300)
        self.start_on_login_checkbox.setChecked(False)
        self.color_button.setStyleSheet(f"background-color: {self.cursor_color.name()};")
        self.outline_color_button.setStyleSheet(f"background-color: {self.cursor_outline_color.name()};")
        self.border_color_button.setStyleSheet(f"background-color: {self.cursor_border_color.name()};")
        self.color_opacity_spinbox.setValue(128)
        self.outline_opacity_spinbox.setValue(36)
        self.border_opacity_spinbox.setValue(0)
        self.update_preview()

    def open_log_file(self):
        open_log_file()

    def load_settings(self):
        cfg = self.config_manager.config
        self.size_spinbox.setValue(cfg.cursor_size)
        self.outline_spinbox.setValue(cfg.outline_size)
        self.speed_spinbox.setValue(int(cfg.speed * 100))
        self.border_spinbox.setValue(cfg.cursor_border_width)
        self.animation_duration_spinbox.setValue(cfg.animation_duration)
        self.start_on_login_checkbox.setChecked(is_autostart_enabled())

        self.cursor_color = QColor(cfg.cursor_color)
        self.cursor_outline_color = QColor(cfg.outline_color)
        self.cursor_border_color = QColor(cfg.cursor_border_color)

        self.color_opacity_spinbox.setValue(cfg.cursor_opacity)
        self.outline_opacity_spinbox.setValue(cfg.outline_opacity)
        self.border_opacity_spinbox.setValue(cfg.cursor_border_opacity)

        self.cursor_color.setAlpha(cfg.cursor_opacity)
        self.cursor_outline_color.setAlpha(cfg.outline_opacity)
        self.cursor_border_color.setAlpha(cfg.cursor_border_opacity)

        self.color_button.setStyleSheet(f"background-color: {self.cursor_color.name()};")
        self.outline_color_button.setStyleSheet(f"background-color: {self.cursor_outline_color.name()};")
        self.border_color_button.setStyleSheet(f"background-color: {self.cursor_border_color.name()};")
        self.update_preview()

    def save_settings(self):
        cfg = self.config_manager.config
        cfg.cursor_size = self.size_spinbox.value()
        cfg.outline_size = self.outline_spinbox.value()
        cfg.cursor_color = self.cursor_color.name()
        cfg.cursor_outline_color = self.cursor_outline_color.name()
        cfg.cursor_border_color = self.cursor_border_color.name()
        cfg.speed = max(0.01, self.speed_spinbox.value() / 100.0)
        cfg.cursor_border_width = self.border_spinbox.value()
        cfg.animation_duration = self.animation_duration_spinbox.value()
        cfg.start_on_login = self.start_on_login_checkbox.isChecked()
        cfg.cursor_opacity = self.color_opacity_spinbox.value()
        cfg.outline_opacity = self.outline_opacity_spinbox.value()
        cfg.cursor_border_opacity = self.border_opacity_spinbox.value()

        set_autostart(self.start_on_login_checkbox.isChecked())
        self.config_manager.update_config(cfg, save=True)
        self.close()
