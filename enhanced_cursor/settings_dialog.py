import os
import sys
from PySide6.QtWidgets import (
    QDialog, QWidget, QLabel, QSpinBox, QColorDialog,
    QPushButton, QVBoxLayout, QHBoxLayout, QCheckBox, QSlider,
    QComboBox, QScrollArea, QFrame, QGroupBox
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QIcon

from enhanced_cursor.config import ConfigManager, CursorConfig
from enhanced_cursor.logger import open_log_file, get_logger
from enhanced_cursor.win32_utils import (
    set_autostart,
    is_autostart_enabled,
    get_system_accent_color,
    is_system_dark_mode,
    is_running_as_admin,
    restart_as_admin
)
from enhanced_cursor.preview_widget import InteractivePreviewWidget

logger = get_logger()


class SettingsDialog(QDialog):
    def __init__(self, config_manager: ConfigManager, icon_path: str, parent=None):
        super().__init__(parent)
        self.config_manager = config_manager
        self.icon_path = icon_path

        self.setWindowTitle(self.tr_text("app_title"))
        if os.path.exists(self.icon_path):
            self.setWindowIcon(QIcon(self.icon_path))

        self.setMinimumSize(740, 530)
        self.setStyleSheet("""
            QDialog {
                background-color: #242424;
            }
            QLabel {
                color: #e0e0e0;
                font-size: 12px;
            }
            QSpinBox, QComboBox {
                background-color: #2f2f38;
                color: #ffffff;
                border: 1px solid #444452;
                border-radius: 4px;
                padding: 3px 8px;
                min-width: 65px;
            }
            QSpinBox:hover, QComboBox:hover {
                border-color: #5c5c6e;
            }
            QSpinBox:disabled, QComboBox:disabled {
                background-color: #222228;
                color: #666677;
                border-color: #33333d;
            }
            QPushButton {
                background-color: #383844;
                color: #ffffff;
                border: 1px solid #4e4e5e;
                border-radius: 4px;
                padding: 5px 14px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #484858;
                border-color: #646478;
            }
            QPushButton:disabled {
                background-color: #25252d;
                color: #666677;
                border-color: #33333d;
            }
            QCheckBox {
                color: #e0e0e0;
                spacing: 8px;
                font-size: 12px;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
                border-radius: 3px;
                border: 1px solid #555566;
                background-color: #2a2a34;
            }
            QCheckBox::indicator:checked {
                background-color: #0078d7;
                border-color: #3399ff;
            }
            QSlider::groove:horizontal {
                height: 5px;
                background: #33333f;
                border-radius: 2px;
            }
            QSlider::sub-page:horizontal {
                background: #0078d7;
                border-radius: 2px;
            }
            QSlider::handle:horizontal {
                background: #ffffff;
                width: 14px;
                margin-top: -5px;
                margin-bottom: -5px;
                border-radius: 7px;
            }
        """)

        # Local colors
        self.cursor_color = QColor(0, 183, 195, 200)
        self.cursor_outline_color = QColor(0, 229, 255, 50)
        self.cursor_border_color = QColor(255, 255, 255, 120)
        self.right_click_color = QColor(255, 112, 67, 220)

        # 1. Interactive Preview Widget
        self.preview_widget = InteractivePreviewWidget(self)

        # Zoom slider below preview
        self.zoom_slider = QSlider(Qt.Orientation.Horizontal)
        self.zoom_slider.setRange(40, 250)
        self.zoom_slider.setValue(100)
        self.zoom_slider.valueChanged.connect(self.update_preview_zoom)

        # 2. Controls - Style & Shape
        self.shape_label = QLabel(self.tr_text("shape_mode"))
        self.shape_combo = QComboBox()
        self.shape_combo.addItem(self.tr_text("shape_fluid_drop"), "fluid_drop")
        self.shape_combo.addItem(self.tr_text("shape_classic_circle"), "classic_circle")
        self.shape_combo.currentIndexChanged.connect(self.on_shape_changed)

        # System Accent Checkbox
        self.system_accent_checkbox = QCheckBox(self.tr_text("use_system_accent"))
        self.system_accent_checkbox.toggled.connect(self.on_accent_toggled)

        # Render Mode Checkbox (Hide Windows arrow)
        self.hide_arrow_checkbox = QCheckBox(self.tr_text("render_custom"))
        self.hide_arrow_checkbox.toggled.connect(self.update_preview)

        # Sizes
        self.size_label = QLabel(self.tr_text("cursor_size"))
        self.size_spinbox = QSpinBox()
        self.size_spinbox.setRange(2, 60)
        self.size_spinbox.valueChanged.connect(self.update_preview)

        self.border_label = QLabel(self.tr_text("border_width"))
        self.border_spinbox = QSpinBox()
        self.border_spinbox.setRange(0, 8)
        self.border_spinbox.valueChanged.connect(self.update_preview)

        # Fluid Physics
        self.tail_label = QLabel(self.tr_text("tail_length"))
        self.tail_spinbox = QSpinBox()
        self.tail_spinbox.setRange(20, 250)
        self.tail_spinbox.setSuffix("%")
        self.tail_spinbox.valueChanged.connect(self.update_preview)

        self.visc_label = QLabel(self.tr_text("viscosity"))
        self.visc_spinbox = QSpinBox()
        self.visc_spinbox.setRange(10, 100)
        self.visc_spinbox.setSuffix("%")
        self.visc_spinbox.valueChanged.connect(self.update_preview)

        self.speed_label = QLabel(self.tr_text("speed"))
        self.speed_spinbox = QSpinBox()
        self.speed_spinbox.setRange(1, 100)
        self.speed_spinbox.valueChanged.connect(self.update_preview)

        # Big Circle (Aura / Outline) Controls
        self.outline_checkbox = QCheckBox(self.tr_text("outline_enabled"))
        self.outline_checkbox.toggled.connect(self.on_outline_toggled)

        self.outline_size_label = QLabel(self.tr_text("outline_size"))
        self.outline_spinbox = QSpinBox()
        self.outline_spinbox.setRange(2, 80)
        self.outline_spinbox.valueChanged.connect(self.update_preview)

        self.outline_color_label = QLabel(self.tr_text("outline_color"))
        self.outline_color_button = QPushButton("Color")
        self.outline_color_button.clicked.connect(self.choose_outline_color)

        self.outline_opacity_label = QLabel(self.tr_text("outline_opacity"))
        self.outline_opacity_spinbox = QSpinBox()
        self.outline_opacity_spinbox.setRange(0, 255)
        self.outline_opacity_spinbox.valueChanged.connect(self.update_preview)

        # Colors & Opacities
        self.color_label = QLabel(self.tr_text("cursor_color"))
        self.color_button = QPushButton("Choose Color")
        self.color_button.clicked.connect(self.choose_cursor_color)

        self.color_opacity_label = QLabel(self.tr_text("cursor_opacity"))
        self.color_opacity_spinbox = QSpinBox()
        self.color_opacity_spinbox.setRange(0, 255)
        self.color_opacity_spinbox.valueChanged.connect(self.update_preview)

        self.border_color_label = QLabel(self.tr_text("border_color"))
        self.border_color_button = QPushButton("Choose Color")
        self.border_color_button.clicked.connect(self.choose_border_color)

        self.border_opacity_label = QLabel(self.tr_text("border_opacity"))
        self.border_opacity_spinbox = QSpinBox()
        self.border_opacity_spinbox.setRange(0, 255)
        self.border_opacity_spinbox.valueChanged.connect(self.update_preview)

        # Right-click Color
        self.rclick_color_label = QLabel(self.tr_text("right_click_color"))
        self.rclick_color_button = QPushButton("Choose Color")
        self.rclick_color_button.clicked.connect(self.choose_rclick_color)

        # Interactive Effects
        self.animation_duration_label = QLabel(self.tr_text("animation_duration"))
        self.animation_duration_spinbox = QSpinBox()
        self.animation_duration_spinbox.setRange(50, 1000)
        self.animation_duration_spinbox.setSuffix(" ms")
        self.animation_duration_spinbox.valueChanged.connect(self.update_preview)

        self.splash_checkbox = QCheckBox(self.tr_text("click_splash"))
        self.splash_checkbox.toggled.connect(self.update_preview)

        self.ripple_checkbox = QCheckBox(self.tr_text("click_ripple"))
        self.ripple_checkbox.toggled.connect(self.update_preview)

        self.shake_checkbox = QCheckBox(self.tr_text("shake_to_find"))
        self.shake_checkbox.toggled.connect(self.update_preview)

        self.squash_checkbox = QCheckBox(self.tr_text("squash_and_stretch"))
        self.squash_checkbox.toggled.connect(self.update_preview)

        # System & Startup
        self.start_on_login_checkbox = QCheckBox(self.tr_text("start_on_login"))

        # Buttons
        self.save_button = QPushButton(self.tr_text("save"))
        self.save_button.setStyleSheet("background-color: #0078d7; font-weight: bold;")
        self.save_button.clicked.connect(self.save_settings)

        self.close_button = QPushButton(self.tr_text("close"))
        self.close_button.clicked.connect(self.close)

        self.set_default_button = QPushButton(self.tr_text("set_defaults"))
        self.set_default_button.clicked.connect(self.set_defaults)

        self.log_button = QPushButton(self.tr_text("show_logs"))
        self.log_button.clicked.connect(self.open_log_file)

        # Layout Assembly
        self.build_ui_layout()
        self.load_settings()

    def tr_text(self, key: str) -> str:
        return self.config_manager.tr(key)

    def build_ui_layout(self):
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(12)

        content_h_layout = QHBoxLayout()
        content_h_layout.setSpacing(20)

        # Left Column - Form Controls inside a clean scroll area
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        scroll_widget = QWidget()
        scroll_widget.setStyleSheet("background: transparent;")
        form_layout = QVBoxLayout(scroll_widget)
        form_layout.setContentsMargins(0, 0, 10, 0)
        form_layout.setSpacing(10)

        # 1. Mode & Style Group
        shape_layout = QHBoxLayout()
        shape_layout.addWidget(self.shape_label)
        shape_layout.addWidget(self.shape_combo)
        form_layout.addLayout(shape_layout)

        form_layout.addWidget(self.hide_arrow_checkbox)
        form_layout.addWidget(self.system_accent_checkbox)

        # Divider
        form_layout.addWidget(self.create_separator())

        # 2. Sizes & Tail Physics
        size_h = QHBoxLayout()
        size_h.addWidget(self.size_label)
        size_h.addWidget(self.size_spinbox)
        size_h.addWidget(self.border_label)
        size_h.addWidget(self.border_spinbox)
        form_layout.addLayout(size_h)

        tail_h = QHBoxLayout()
        tail_h.addWidget(self.tail_label)
        tail_h.addWidget(self.tail_spinbox)
        tail_h.addWidget(self.visc_label)
        tail_h.addWidget(self.visc_spinbox)
        form_layout.addLayout(tail_h)

        speed_h = QHBoxLayout()
        speed_h.addWidget(self.speed_label)
        speed_h.addWidget(self.speed_spinbox)
        speed_h.addStretch()
        form_layout.addLayout(speed_h)

        # Divider
        form_layout.addWidget(self.create_separator())

        # 3. Outer Aura / Big Circle (Большой круг)
        form_layout.addWidget(self.outline_checkbox)

        aura_row1 = QHBoxLayout()
        aura_row1.addWidget(self.outline_size_label)
        aura_row1.addWidget(self.outline_spinbox)
        aura_row1.addWidget(self.outline_opacity_label)
        aura_row1.addWidget(self.outline_opacity_spinbox)
        form_layout.addLayout(aura_row1)

        aura_row2 = QHBoxLayout()
        aura_row2.addWidget(self.outline_color_label)
        aura_row2.addWidget(self.outline_color_button)
        aura_row2.addStretch()
        form_layout.addLayout(aura_row2)

        # Divider
        form_layout.addWidget(self.create_separator())

        # 4. Colors & Opacities
        c_layout = QHBoxLayout()
        c_layout.addWidget(self.color_label)
        c_layout.addWidget(self.color_button)
        c_layout.addWidget(self.color_opacity_label)
        c_layout.addWidget(self.color_opacity_spinbox)
        form_layout.addLayout(c_layout)

        b_layout = QHBoxLayout()
        b_layout.addWidget(self.border_color_label)
        b_layout.addWidget(self.border_color_button)
        b_layout.addWidget(self.border_opacity_label)
        b_layout.addWidget(self.border_opacity_spinbox)
        form_layout.addLayout(b_layout)

        rc_layout = QHBoxLayout()
        rc_layout.addWidget(self.rclick_color_label)
        rc_layout.addWidget(self.rclick_color_button)
        rc_layout.addStretch()
        form_layout.addLayout(rc_layout)

        # Divider
        form_layout.addWidget(self.create_separator())

        # 5. Effects & Animation
        anim_h = QHBoxLayout()
        anim_h.addWidget(self.animation_duration_label)
        anim_h.addWidget(self.animation_duration_spinbox)
        anim_h.addStretch()
        form_layout.addLayout(anim_h)

        form_layout.addWidget(self.splash_checkbox)
        form_layout.addWidget(self.ripple_checkbox)
        form_layout.addWidget(self.shake_checkbox)
        form_layout.addWidget(self.squash_checkbox)

        # Divider
        form_layout.addWidget(self.create_separator())

        # 6. System
        form_layout.addWidget(self.start_on_login_checkbox)

        # Administrator Mode indicator & button
        is_admin = is_running_as_admin()
        self.admin_button = QPushButton()
        if is_admin:
            self.admin_button.setText("Запущено с правами Администратора ✓")
            self.admin_button.setEnabled(False)
            self.admin_button.setStyleSheet("background-color: #1e3828; color: #55dd77; border: 1px solid #2e5538; padding: 5px;")
        else:
            self.admin_button.setText("🛡️ Запустить от имени Администратора")
            self.admin_button.setToolTip("Позволяет отображать курсор поверх окон Администратора и UAC")
            self.admin_button.setStyleSheet("background-color: #383424; color: #ffcc44; border: 1px solid #5a4f28; padding: 5px;")
            self.admin_button.clicked.connect(self.restart_admin)

        self.admin_hint = QLabel("Режим Администратора необходим для отрисовки поверх Диспетчера задач и UAC диалогов.")
        self.admin_hint.setStyleSheet("color: #888899; font-size: 11px;")
        self.admin_hint.setWordWrap(True)

        form_layout.addWidget(self.admin_button)
        form_layout.addWidget(self.admin_hint)

        form_layout.addStretch()

        scroll_area.setWidget(scroll_widget)
        content_h_layout.addWidget(scroll_area, 6)

        # Right Column - Preview Card and Zoom
        preview_container = QVBoxLayout()
        preview_container.setSpacing(8)

        preview_header = QLabel(self.tr_text("interactive_preview"))
        preview_header.setStyleSheet("color: #9999aa; font-weight: bold; font-size: 11px;")
        preview_container.addWidget(preview_header)

        preview_container.addWidget(self.preview_widget)

        zoom_row = QHBoxLayout()
        zoom_row.addWidget(QLabel(self.tr_text("zoom")))
        zoom_row.addWidget(self.zoom_slider)
        preview_container.addLayout(zoom_row)

        preview_container.addStretch()
        preview_container.addWidget(self.log_button)

        content_h_layout.addLayout(preview_container, 4)
        main_layout.addLayout(content_h_layout)

        # Bottom Action Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)
        btn_layout.addWidget(self.set_default_button)
        btn_layout.addStretch()
        btn_layout.addWidget(self.close_button)
        btn_layout.addWidget(self.save_button)
        main_layout.addLayout(btn_layout)

        self.setLayout(main_layout)

    def create_separator(self) -> QFrame:
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        line.setStyleSheet("color: #383844;")
        return line

    def sync_zoom_slider(self, val: int):
        self.zoom_slider.setValue(val)

    def update_preview_zoom(self):
        zoom = self.zoom_slider.value() / 100.0
        self.preview_widget.set_zoom(zoom)

    def on_shape_changed(self):
        is_fluid = self.shape_combo.currentData() == "fluid_drop"
        self.tail_spinbox.setEnabled(is_fluid)
        self.visc_spinbox.setEnabled(is_fluid)
        self.update_preview()

    def on_outline_toggled(self, checked: bool):
        self.outline_spinbox.setEnabled(checked)
        self.outline_color_button.setEnabled(checked and not self.system_accent_checkbox.isChecked())
        self.outline_opacity_spinbox.setEnabled(checked)
        self.update_preview()

    def on_accent_toggled(self, checked: bool):
        self.color_button.setEnabled(not checked)
        self.outline_color_button.setEnabled(not checked and self.outline_checkbox.isChecked())
        if checked:
            sys_accent = get_system_accent_color()
            self.color_button.setStyleSheet(f"background-color: {sys_accent}; color: #ffffff;")
            self.outline_color_button.setStyleSheet(f"background-color: {sys_accent}; color: #ffffff;")
        else:
            self.color_button.setStyleSheet(f"background-color: {self.cursor_color.name()}; color: #ffffff;")
            self.outline_color_button.setStyleSheet(f"background-color: {self.cursor_outline_color.name()}; color: #ffffff;")
        self.update_preview()

    def choose_cursor_color(self):
        color = QColorDialog.getColor(self.cursor_color, self, "Cursor Color")
        if color.isValid():
            self.cursor_color = color
            self.color_button.setStyleSheet(f"background-color: {color.name()};")
            self.update_preview()

    def choose_outline_color(self):
        color = QColorDialog.getColor(self.cursor_outline_color, self, "Outline Color")
        if color.isValid():
            self.cursor_outline_color = color
            self.outline_color_button.setStyleSheet(f"background-color: {color.name()};")
            self.update_preview()

    def choose_border_color(self):
        color = QColorDialog.getColor(self.cursor_border_color, self, "Border Color")
        if color.isValid():
            self.cursor_border_color = color
            self.border_color_button.setStyleSheet(f"background-color: {color.name()};")
            self.update_preview()

    def choose_rclick_color(self):
        color = QColorDialog.getColor(self.right_click_color, self, "Right-click Color")
        if color.isValid():
            self.right_click_color = color
            self.rclick_color_button.setStyleSheet(f"background-color: {color.name()};")
            self.update_preview()

    def update_preview(self):
        cfg = CursorConfig()
        cfg.shape_mode = self.shape_combo.currentData()
        cfg.render_mode = "custom" if self.hide_arrow_checkbox.isChecked() else "aura"
        cfg.use_system_accent = self.system_accent_checkbox.isChecked()

        cfg.cursor_size = self.size_spinbox.value()
        cfg.outline_enabled = self.outline_checkbox.isChecked()
        cfg.outline_size = self.outline_spinbox.value()
        cfg.cursor_border_width = self.border_spinbox.value()

        cfg.tail_length = self.tail_spinbox.value() / 100.0
        cfg.viscosity = self.visc_spinbox.value() / 100.0
        cfg.speed = max(0.01, self.speed_spinbox.value() / 100.0)

        cfg.cursor_color = self.cursor_color.name()
        cfg.cursor_opacity = self.color_opacity_spinbox.value()
        cfg.outline_color = self.cursor_outline_color.name()
        cfg.outline_opacity = self.outline_opacity_spinbox.value()
        cfg.cursor_border_color = self.cursor_border_color.name()
        cfg.cursor_border_opacity = self.border_opacity_spinbox.value()
        cfg.right_click_color = self.right_click_color.name()

        cfg.animation_duration = self.animation_duration_spinbox.value()
        cfg.click_splash = self.splash_checkbox.isChecked()
        cfg.click_ripple = self.ripple_checkbox.isChecked()
        cfg.shake_to_find = self.shake_checkbox.isChecked()
        cfg.squash_and_stretch = self.squash_checkbox.isChecked()

        self.preview_widget.set_config(cfg)

    def load_settings(self):
        cfg = self.config_manager.config

        # Shape
        idx = self.shape_combo.findData(cfg.shape_mode)
        if idx >= 0:
            self.shape_combo.setCurrentIndex(idx)

        self.hide_arrow_checkbox.setChecked(cfg.render_mode == "custom")
        self.system_accent_checkbox.setChecked(cfg.use_system_accent)

        self.size_spinbox.setValue(cfg.cursor_size)
        self.outline_checkbox.setChecked(cfg.outline_enabled)
        self.outline_spinbox.setValue(cfg.outline_size)
        self.border_spinbox.setValue(cfg.cursor_border_width)

        self.tail_spinbox.setValue(int(cfg.tail_length * 100))
        self.visc_spinbox.setValue(int(cfg.viscosity * 100))
        self.speed_spinbox.setValue(int(cfg.speed * 100))

        self.cursor_color = QColor(cfg.cursor_color)
        self.cursor_outline_color = QColor(cfg.outline_color)
        self.cursor_border_color = QColor(cfg.cursor_border_color)
        self.right_click_color = QColor(cfg.right_click_color)

        self.color_opacity_spinbox.setValue(cfg.cursor_opacity)
        self.outline_opacity_spinbox.setValue(cfg.outline_opacity)
        self.border_opacity_spinbox.setValue(cfg.cursor_border_opacity)

        self.animation_duration_spinbox.setValue(cfg.animation_duration)
        self.splash_checkbox.setChecked(cfg.click_splash)
        self.ripple_checkbox.setChecked(cfg.click_ripple)
        self.shake_checkbox.setChecked(cfg.shake_to_find)
        self.squash_checkbox.setChecked(cfg.squash_and_stretch)

        self.start_on_login_checkbox.setChecked(is_autostart_enabled())

        # Update button colors
        self.color_button.setStyleSheet(f"background-color: {self.cursor_color.name()};")
        self.outline_color_button.setStyleSheet(f"background-color: {self.cursor_outline_color.name()};")
        self.border_color_button.setStyleSheet(f"background-color: {self.cursor_border_color.name()};")
        self.rclick_color_button.setStyleSheet(f"background-color: {self.right_click_color.name()};")

        self.on_outline_toggled(cfg.outline_enabled)
        self.on_accent_toggled(cfg.use_system_accent)
        self.update_preview()

    def save_settings(self):
        cfg = self.config_manager.config
        cfg.shape_mode = self.shape_combo.currentData()
        cfg.render_mode = "custom" if self.hide_arrow_checkbox.isChecked() else "aura"
        cfg.use_system_accent = self.system_accent_checkbox.isChecked()

        cfg.cursor_size = self.size_spinbox.value()
        cfg.outline_enabled = self.outline_checkbox.isChecked()
        cfg.outline_size = self.outline_spinbox.value()
        cfg.cursor_border_width = self.border_spinbox.value()

        cfg.tail_length = self.tail_spinbox.value() / 100.0
        cfg.viscosity = self.visc_spinbox.value() / 100.0
        cfg.speed = max(0.01, self.speed_spinbox.value() / 100.0)

        cfg.cursor_color = self.cursor_color.name()
        cfg.cursor_opacity = self.color_opacity_spinbox.value()
        cfg.outline_color = self.cursor_outline_color.name()
        cfg.outline_opacity = self.outline_opacity_spinbox.value()
        cfg.cursor_border_color = self.cursor_border_color.name()
        cfg.cursor_border_opacity = self.border_opacity_spinbox.value()
        cfg.right_click_color = self.right_click_color.name()

        cfg.animation_duration = self.animation_duration_spinbox.value()
        cfg.click_splash = self.splash_checkbox.isChecked()
        cfg.click_ripple = self.ripple_checkbox.isChecked()
        cfg.shake_to_find = self.shake_checkbox.isChecked()
        cfg.squash_and_stretch = self.squash_checkbox.isChecked()

        cfg.start_on_login = self.start_on_login_checkbox.isChecked()
        set_autostart(self.start_on_login_checkbox.isChecked())

        self.config_manager.update_config(cfg, save=True)

        # Visual feedback on Save button without closing window
        self.save_button.setText(self.tr_text("saved_feedback"))
        QTimer.singleShot(1500, lambda: self.save_button.setText(self.tr_text("save")))

    def restart_admin(self):
        self.save_settings()
        restart_as_admin()

    def set_defaults(self):
        # Apply default Fluid Accent preset
        self.config_manager.apply_preset("Системный акцент (Капля)")
        self.load_settings()

    def open_log_file(self):
        open_log_file()
