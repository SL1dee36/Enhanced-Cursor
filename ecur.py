import sys
from PySide6.QtWidgets import (
    QApplication, QWidget, QSystemTrayIcon, QMenu, QDialog, QLabel,
    QSpinBox, QColorDialog, QPushButton, QVBoxLayout, QHBoxLayout,
    QCheckBox, QFileDialog, QFrame, QSlider
)
from PySide6.QtCore import Qt, QPoint, QTimer, QRect, QEasingCurve, QTime, QSettings, QSize
from PySide6.QtGui import QPainter, QColor, QPen, QScreen, QRegion, QIcon, QWheelEvent
import ctypes
from ctypes import wintypes
import win32gui
import win32con
import winreg
import os
import json


def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


path_to_the_images = resource_path('cursor.png')


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
        self.target_x = 100
        self.target_y = 100
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

        scaled_target_x = self.target_x * self.zoom_level
        scaled_target_y = self.target_y * self.zoom_level
        scaled_cursor_size = self.cursor_size * self.zoom_level
        scaled_outline_size = self.cursor_outline_size * self.zoom_level

        center_x = self.width() / 2
        center_y = self.height() / 2
        scaled_target_x = center_x
        scaled_target_y = center_y

        outline_pen = QPen(self.cursor_outline_color, 0)
        painter.setPen(outline_pen)
        painter.setBrush(self.cursor_outline_color)
        painter.drawEllipse(QPoint(scaled_target_x, scaled_target_y), scaled_outline_size, scaled_outline_size)

        pen = QPen(self.cursor_border_color, self.cursor_border_width)
        painter.setPen(pen)
        painter.setBrush(self.cursor_color)
        painter.drawEllipse(QPoint(scaled_target_x, scaled_target_y), scaled_cursor_size, scaled_cursor_size)


class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('EnhancedCursor: Settings')
        self.setWindowIcon(QIcon(path_to_the_images))
        self.settings = QSettings('CursorHighlighter', 'Settings')
        self.setMinimumSize(640, 320)
        self.setStyleSheet('QDialog {background-color: #242424;}')

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
        self.preview_widget.set_properties(
            self.size_spinbox.value(),
            self.parent().cursor_color,
            self.outline_spinbox.value(),
            self.parent().cursor_outline_color,
            self.parent().cursor_border_color,
            self.border_spinbox.value()
        )

    def choose_cursor_color(self):
        color = QColorDialog.getColor(self.parent().cursor_color, self)
        if color.isValid():
            self.parent().cursor_color = color
            self.color_button.setStyleSheet(f"background-color: {color.name()};")
            self.update_preview()

    def choose_outline_color(self):
        color = QColorDialog.getColor(self.parent().cursor_outline_color, self)
        if color.isValid():
            self.parent().cursor_outline_color = color
            self.outline_color_button.setStyleSheet(f"background-color: {color.name()};")
            self.update_preview()

    def choose_border_color(self):
        color = QColorDialog.getColor(self.parent().cursor_border_color, self)
        if color.isValid():
            self.parent().cursor_border_color = color
            self.border_color_button.setStyleSheet(f"background-color: {color.name()};")
            self.update_preview()

    def set_defaults(self):
        self.size_spinbox.setValue(4)
        self.outline_spinbox.setValue(16)
        self.parent().cursor_color = QColor(115, 115, 204, 128)
        self.parent().cursor_outline_color = QColor(169, 169, 222, 36)
        self.parent().cursor_border_color = QColor(0, 0, 0, 0)
        self.speed_spinbox.setValue(3)
        self.border_spinbox.setValue(0)
        self.animation_duration_spinbox.setValue(300)
        self.start_on_login_checkbox.setChecked(False)
        self.color_button.setStyleSheet(f"background-color: {self.parent().cursor_color.name()};")
        self.outline_color_button.setStyleSheet(f"background-color: {self.parent().cursor_outline_color.name()};")
        self.border_color_button.setStyleSheet(f"background-color: {self.parent().cursor_border_color.name()};")
        self.color_opacity_spinbox.setValue(128)
        self.outline_opacity_spinbox.setValue(36)
        self.border_opacity_spinbox.setValue(0)
        self.update_preview()

    def open_log_file(self):
        try:
            if os.path.exists('log.txt'):
                os.startfile('log.txt')
        except Exception as e:
            print(e)

    def load_settings(self):
        self.size_spinbox.setValue(self.settings.value('cursor_size', 4, type=int))
        self.outline_spinbox.setValue(self.settings.value('cursor_outline_size', 16, type=int))
        self.speed_spinbox.setValue(self.settings.value('speed', 3, type=int))
        self.border_spinbox.setValue(self.settings.value('border_width', 0, type=int))
        self.animation_duration_spinbox.setValue(self.settings.value('animation_duration', 300, type=int))
        self.start_on_login_checkbox.setChecked(self.settings.value('start_on_login', False, type=bool))
        color_str = self.settings.value('cursor_color', '#7373cc80', type=str)
        self.parent().cursor_color = QColor(color_str)
        color_str = self.settings.value('cursor_outline_color', '#a9a9de24', type=str)
        self.parent().cursor_outline_color = QColor(color_str)
        color_str = self.settings.value('cursor_border_color', '#00000000', type=str)
        self.parent().cursor_border_color = QColor(color_str)
        self.color_opacity_spinbox.setValue(self.settings.value('cursor_opacity', 128, type=int))
        self.outline_opacity_spinbox.setValue(self.settings.value('cursor_outline_opacity', 36, type=int))
        self.border_opacity_spinbox.setValue(self.settings.value('cursor_border_opacity', 0, type=int))
        self.color_button.setStyleSheet(f"background-color: {self.parent().cursor_color.name()};")
        self.outline_color_button.setStyleSheet(f"background-color: {self.parent().cursor_outline_color.name()};")
        self.border_color_button.setStyleSheet(f"background-color: {self.parent().cursor_border_color.name()};")
        self.update_preview()

    def save_settings(self):
        self.settings.setValue('cursor_size', self.size_spinbox.value())
        self.settings.setValue('cursor_outline_size', self.outline_spinbox.value())
        self.settings.setValue('cursor_color', self.parent().cursor_color.name())
        self.settings.setValue('cursor_outline_color', self.parent().cursor_outline_color.name())
        self.settings.setValue('cursor_border_color', self.parent().cursor_border_color.name())
        self.settings.setValue('speed', self.speed_spinbox.value())
        self.settings.setValue('border_width', self.border_spinbox.value())
        self.settings.setValue('animation_duration', self.animation_duration_spinbox.value())
        self.settings.setValue('start_on_login', self.start_on_login_checkbox.isChecked())
        self.settings.setValue('cursor_opacity', self.color_opacity_spinbox.value())
        self.settings.setValue('cursor_outline_opacity', self.outline_opacity_spinbox.value())
        self.settings.setValue('cursor_border_opacity', self.border_opacity_spinbox.value())

        self.parent().cursor_size = self.size_spinbox.value()
        self.parent().cursor_outline_size = self.outline_spinbox.value()
        self.parent().speed = self.speed_spinbox.value() / 100
        self.parent().cursor_border_width = self.border_spinbox.value()
        self.parent().animation_duration = self.animation_duration_spinbox.value()
        self.parent().cursor_color.setAlpha(self.color_opacity_spinbox.value())
        self.parent().cursor_outline_color.setAlpha(self.outline_opacity_spinbox.value())
        self.parent().cursor_border_color.setAlpha(self.border_opacity_spinbox.value())
        self.parent().update_cursor_properties()
        self.update_startup()
        self.close()

    def update_startup(self):
        app_path = os.path.abspath(sys.argv[0])
        key_path = r'Software\Microsoft\Windows\CurrentVersion\Run'
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_WRITE) as key:
                if self.start_on_login_checkbox.isChecked():
                    winreg.SetValueEx(key, 'CursorHighlighter', 0, winreg.REG_SZ, app_path)
                    print('Startup added')
                else:
                    try:
                        winreg.DeleteValue(key, 'CursorHighlighter')
                        print('Startup removed')
                    except FileNotFoundError:
                        pass
        except Exception as e:
            print(f'Error updating startup settings: {e}')


class TransparentCursorWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlag(Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setMouseTracking(True)

        hwnd = self.winId()
        win32gui.SetWindowLong(
            hwnd,
            win32con.GWL_EXSTYLE,
            win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
            | win32con.WS_EX_LAYERED
            | win32con.WS_EX_TRANSPARENT
            | win32con.WS_EX_TOPMOST
        )
        win32gui.SetWindowPos(
            hwnd,
            win32con.HWND_TOPMOST,
            0,
            0,
            0,
            0,
            win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_NOACTIVATE
        )

        self.setWindowFlag(Qt.WindowType.Tool)
        self.cursor_x = 0
        self.cursor_y = 0
        self.target_x = 0
        self.target_y = 0
        self.cursor_size = 4
        self.cursor_color = QColor(115, 115, 204, 128)
        self.cursor_border_color = QColor(0, 0, 0, 0)
        self.cursor_border_width = 0
        self.cursor_outline_size = 16
        self.cursor_outline_color = QColor(169, 169, 222, 36)
        self.speed = 0.03
        self.animation_duration = 300
        self.is_mouse_pressed = False
        self.original_cursor_size = self.cursor_size
        self.original_outline_size = self.cursor_outline_size

        self.animation_timer = QTimer(self)
        self.animation_timer.timeout.connect(self.update_animation)
        self.animation_target_size = self.cursor_size
        self.animation_target_outline_size = self.cursor_outline_size
        self.animation_start_size = self.cursor_size
        self.animation_start_outline_size = self.cursor_outline_size
        self.animation_start_time = 0

        self.user32 = ctypes.windll.user32
        self.cursor_pos = wintypes.POINT()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_cursor_pos)
        self.timer.start(1)

        self.mouse_check_timer = QTimer(self)
        self.mouse_check_timer.timeout.connect(self.check_mouse_state)
        self.mouse_check_timer.start(10)

        self.prev_mouse_state = False
        self.current_animation_target = self.original_cursor_size
        self.current_animation_target_outline = self.original_outline_size

        self.VK_LBUTTON = 1
        self.VK_RBUTTON = 2

        self.tray_icon = QSystemTrayIcon(self)
        icon = QIcon(path_to_the_images)
        self.tray_icon.setIcon(icon)
        self.tray_icon.setVisible(True)

        self.tray_menu = QMenu()
        self.settings_action = self.tray_menu.addAction('Settings')
        self.settings_action.triggered.connect(self.open_settings_dialog)
        self.exit_action = self.tray_menu.addAction('Exit')
        self.exit_action.triggered.connect(self.exit_app)
        self.tray_icon.setContextMenu(self.tray_menu)

        self.settings_dialog = SettingsDialog(self)
        self.load_settings()

    def load_settings(self):
        settings = QSettings('CursorHighlighter', 'Settings')
        self.cursor_size = settings.value('cursor_size', 3, type=int)
        self.cursor_outline_size = settings.value('cursor_outline_size', 16, type=int)
        self.speed = settings.value('speed', 3, type=int) / 100
        self.cursor_border_width = settings.value('border_width', 0, type=int)
        self.animation_duration = settings.value('animation_duration', 300, type=int)
        color_str = settings.value('cursor_color', '#7373cc80', type=str)
        self.cursor_color = QColor(color_str)
        color_str = settings.value('cursor_outline_color', '#a9a9de24', type=str)
        self.cursor_outline_color = QColor(color_str)
        color_str = settings.value('cursor_border_color', '#00000000', type=str)
        self.cursor_border_color = QColor(color_str)
        cursor_opacity = settings.value('cursor_opacity', 128, type=int)
        outline_opacity = settings.value('cursor_outline_opacity', 36, type=int)
        border_opacity = settings.value('cursor_border_opacity', 0, type=int)
        self.cursor_color.setAlpha(cursor_opacity)
        self.cursor_outline_color.setAlpha(outline_opacity)
        self.cursor_border_color.setAlpha(border_opacity)
        self.original_cursor_size = self.cursor_size
        self.original_outline_size = self.cursor_outline_size

    def update_cursor_pos(self):
        if self.user32.GetCursorPos(ctypes.byref(self.cursor_pos)):
            self.cursor_x = self.cursor_pos.x
            self.cursor_y = self.cursor_pos.y
        dx = self.cursor_x - self.target_x
        dy = self.cursor_y - self.target_y
        self.target_x += dx * self.speed
        self.target_y += dy * self.speed
        self.update()

    def check_mouse_state(self):
        left_button_down = self.user32.GetAsyncKeyState(self.VK_LBUTTON) & 0x8000
        right_button_down = self.user32.GetAsyncKeyState(self.VK_RBUTTON) & 0x8000
        current_mouse_state = left_button_down or right_button_down

        if current_mouse_state and not self.prev_mouse_state:
            self.log('Mouse button pressed')
            self.current_animation_target = self.cursor_outline_size
            self.current_animation_target_outline = 0
            self.start_size_animation()
            self.prev_mouse_state = current_mouse_state
            self.is_mouse_pressed = True
        elif not current_mouse_state and self.prev_mouse_state:
            self.log('Mouse button released')
            self.current_animation_target = self.original_cursor_size
            self.current_animation_target_outline = self.original_outline_size
            self.start_size_animation()
            self.prev_mouse_state = current_mouse_state
            self.is_mouse_pressed = False

    def start_size_animation(self):
        if self.animation_timer.isActive():
            self.animation_timer.stop()
        self.animation_start_size = self.cursor_size
        self.animation_target_size = self.current_animation_target
        self.animation_start_outline_size = self.cursor_outline_size
        self.animation_target_outline_size = self.current_animation_target_outline
        self.animation_start_time = QTime.currentTime().msecsSinceStartOfDay()
        self.animation_timer.start(1)

    def update_animation(self):
        current_time = QTime.currentTime().msecsSinceStartOfDay()
        elapsed_time = current_time - self.animation_start_time
        progress = min(1.0, elapsed_time / self.animation_duration)
        if progress >= 1.0:
            self.cursor_size = self.animation_target_size
            self.cursor_outline_size = self.animation_target_outline_size
            self.animation_timer.stop()
        else:
            easing_curve = QEasingCurve(QEasingCurve.Type.OutCubic)
            easing_progress = easing_curve.valueForProgress(progress)
            self.cursor_size = self.animation_start_size + (self.animation_target_size - self.animation_start_size) * easing_progress
            self.cursor_outline_size = self.animation_start_outline_size + (self.animation_target_outline_size - self.animation_start_outline_size) * easing_progress
        self.log(f'Animation Progress: {progress:.2f}, Cursor Size: {self.cursor_size:.2f}, Outline Size: {self.cursor_outline_size:.2f}')
        self.update()

    def update_cursor_properties(self):
        """Применяет текущие настройки курсора к отрисовке."""
        self.original_cursor_size = self.cursor_size
        self.original_outline_size = self.cursor_outline_size
        if self.is_mouse_pressed:
            self.current_animation_target = self.cursor_outline_size
            self.current_animation_target_outline = 0
        else:
            self.current_animation_target = self.original_cursor_size
            self.current_animation_target_outline = self.original_outline_size
        self.start_size_animation()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        outline_pen = QPen(self.cursor_outline_color, 0)
        painter.setPen(outline_pen)
        painter.setBrush(self.cursor_outline_color)
        painter.drawEllipse(QPoint(self.target_x, self.target_y), self.cursor_outline_size, self.cursor_outline_size)

        pen = QPen(self.cursor_border_color, self.cursor_border_width)
        painter.setPen(pen)
        painter.setBrush(self.cursor_color)
        painter.drawEllipse(QPoint(self.cursor_x, self.cursor_y), self.cursor_size, self.cursor_size)

        region = QRegion(QRect(0, 0, self.width(), self.height()))
        painter.setClipRegion(region)
        painter.fillRect(self.rect(), Qt.transparent)
        painter.setClipRegion(QRegion())

    def open_settings_dialog(self):
        self.settings_dialog.show()

    def exit_app(self):
        self.log('Exiting application')
        self.tray_icon.hide()
        QApplication.quit()

    def log(self, message):
        with open('log.txt', 'a') as file:
            file.write(f"{QTime.currentTime().toString('hh:mm:ss:zzz')}: {message}\n")


if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = TransparentCursorWindow()
    screen = app.primaryScreen()
    screen_rect = screen.geometry()
    window.setGeometry(screen_rect)
    window.show()
    sys.exit(app.exec())

