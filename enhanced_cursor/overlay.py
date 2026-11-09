import math
import time
import ctypes
from ctypes import wintypes
from typing import Optional, Set
import win32gui
import win32con

from PySide6.QtWidgets import QWidget, QApplication
from PySide6.QtCore import Qt, QPointF, QRect, QTimer
from PySide6.QtGui import QPainter, QColor

from enhanced_cursor.config import CursorConfig, ConfigManager
from enhanced_cursor.logger import get_logger
from enhanced_cursor.fluid_physics import FluidCursorEngine
from enhanced_cursor.win32_utils import (
    get_virtual_desktop_rect,
    register_global_hotkey,
    unregister_global_hotkey,
    is_fullscreen_window_active,
    is_ibeam_cursor_active,
    get_system_accent_color,
    is_system_dark_mode,
    hide_system_cursor,
    restore_system_cursor,
    is_system_cursor_hidden,
    init_high_resolution_timer,
    shutdown_high_resolution_timer,
    bring_window_to_topmost
)

logger = get_logger()
user32 = ctypes.windll.user32


class CursorOverlayWindow(QWidget):
    def __init__(self, config_manager: ConfigManager):
        super().__init__()
        self.config_manager = config_manager
        self.config: CursorConfig = config_manager.config

        # High-resolution 1ms timer
        init_high_resolution_timer()

        # Setup frameless transparent overlay
        self.setWindowFlag(Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint)
        self.setWindowFlag(Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setMouseTracking(True)

        # Apply Win32 ExStyle
        self.hwnd = int(self.winId())
        ex_style = win32gui.GetWindowLong(self.hwnd, win32con.GWL_EXSTYLE)
        win32gui.SetWindowLong(
            self.hwnd,
            win32con.GWL_EXSTYLE,
            ex_style
            | win32con.WS_EX_LAYERED
            | win32con.WS_EX_TRANSPARENT
            | win32con.WS_EX_TOPMOST
            | win32con.WS_EX_NOACTIVATE
        )

        # Reposition overlay to cover all connected monitors
        self.update_geometry_to_virtual_desktop()

        # Connect screen topology changes
        app = QApplication.instance()
        if app:
            app.screenAdded.connect(self.on_screens_changed)
            app.screenRemoved.connect(self.on_screens_changed)

        # Physics & Graphics Engine
        self.engine = FluidCursorEngine()
        self.cursor_pos = wintypes.POINT()
        self.last_frame_time = time.perf_counter()

        # System Accent & Theme
        self.system_accent_hex = get_system_accent_color()
        self.is_dark_mode = is_system_dark_mode()
        self.last_theme_check = 0.0

        # Idle & visibility state
        self.last_move_time = time.perf_counter()
        self.visibility_alpha = 1.0  # 0.0 to 1.0

        # External state tracking
        self.is_game_fullscreen = False
        self.last_env_check = 0.0
        self.last_foreground_hwnd = 0

        # Previous bounding box for efficient partial updates
        self.last_dirty_rect = QRect()
        self.last_zorder_check = 0.0

        # Main render loop timer (~165 FPS, 6ms interval)
        self.render_timer = QTimer(self)
        self.render_timer.setInterval(6)
        self.render_timer.timeout.connect(self.tick)
        self.render_timer.start()

        # Global hotkey
        self.hotkey_id = 999
        self.register_hotkey()

        # Connect config changes
        self.config_manager.config_changed.connect(self.on_config_changed)

        logger.info("CursorOverlayWindow initialized successfully with FluidEngine.")

    def update_geometry_to_virtual_desktop(self):
        vrect = get_virtual_desktop_rect()
        self.setGeometry(vrect)
        hwnd = int(self.winId())
        win32gui.SetWindowPos(
            hwnd,
            win32con.HWND_TOPMOST,
            vrect.x(),
            vrect.y(),
            vrect.width(),
            vrect.height(),
            win32con.SWP_NOACTIVATE | win32con.SWP_SHOWWINDOW
        )

    def on_screens_changed(self, *args):
        logger.info("Screen configuration changed, updating overlay geometry.")
        self.update_geometry_to_virtual_desktop()

    def register_hotkey(self):
        # Ctrl (0x0002) + Alt (0x0001) + 'H' (0x48)
        register_global_hotkey(self.hwnd, self.hotkey_id, 0x0001 | 0x0002, 0x48)

    def unregister_hotkey(self):
        unregister_global_hotkey(self.hwnd, self.hotkey_id)

    def nativeEvent(self, event_type, message):
        # Handle WM_HOTKEY (0x0312), WM_SETTINGCHANGE (0x001A), WM_DWMCOLORIZATIONCOLORCHANGED (0x0320)
        if event_type == b"windows_generic_MSG":
            msg = wintypes.MSG.from_address(int(message))
            if msg.message == 0x0312:  # WM_HOTKEY
                self.toggle_enabled()
                return True, 0
            elif msg.message in (0x001A, 0x0320):  # Setting change / theme accent change
                self.refresh_system_theme()
        return super().nativeEvent(event_type, message)

    def refresh_system_theme(self):
        self.system_accent_hex = get_system_accent_color()
        self.is_dark_mode = is_system_dark_mode()
        self.update()

    def toggle_enabled(self):
        self.config.enabled = not self.config.enabled
        self.config_manager.update_config(self.config, save=True)
        status = "enabled" if self.config.enabled else "paused"
        logger.info(f"Cursor highlight toggled: {status}")
        self.update_cursor_visibility()
        self.update()

    def on_config_changed(self, new_config: CursorConfig):
        self.config = new_config
        self.update_cursor_visibility()
        self.update()

    def update_cursor_visibility(self):
        should_hide = (
            self.config.enabled
            and self.config.render_mode == "custom"
            and self.visibility_alpha > 0.05
            and not self.is_game_fullscreen
        )
        if should_hide:
            if not is_system_cursor_hidden():
                hide_system_cursor()
        else:
            if is_system_cursor_hidden():
                restore_system_cursor()

    def tick(self):
        now = time.perf_counter()
        dt = now - self.last_frame_time
        self.last_frame_time = now

        if not self.config.enabled:
            self.update_cursor_visibility()
            if self.last_dirty_rect.isValid():
                self.update(self.last_dirty_rect)
                self.last_dirty_rect = QRect()
            return

        # Keep overlay on top of any newly opened system modals, popups, or dialogs
        fg_hwnd = user32.GetForegroundWindow()
        if fg_hwnd != self.last_foreground_hwnd or (now - self.last_zorder_check > 0.05):
            self.last_foreground_hwnd = fg_hwnd
            self.last_zorder_check = now
            bring_window_to_topmost(self.hwnd)

        # 1. Update mouse position
        win_top_left = self.geometry().topLeft()
        if user32.GetCursorPos(ctypes.byref(self.cursor_pos)):
            real_x = float(self.cursor_pos.x - win_top_left.x())
            real_y = float(self.cursor_pos.y - win_top_left.y())
        else:
            real_x = self.engine.pos_0.x()
            real_y = self.engine.pos_0.y()

        # Motion check for idle detection
        dx = real_x - self.engine.prev_raw_x
        dy = real_y - self.engine.prev_raw_y
        if abs(dx) > 0.01 or abs(dy) > 0.01:
            self.last_move_time = now

        # 2. Mouse button states (Left=1, Right=2)
        l_down = bool(user32.GetAsyncKeyState(1) & 0x8000)
        r_down = bool(user32.GetAsyncKeyState(2) & 0x8000)
        if l_down or r_down:
            self.last_move_time = now

        # 3. Environment check (fullscreen game ~every 250ms)
        if now - self.last_env_check > 0.25:
            self.last_env_check = now
            if self.config.game_detection:
                self.is_game_fullscreen = is_fullscreen_window_active({int(self.winId())})
            else:
                self.is_game_fullscreen = False

        # 4. Periodic system theme check (~every 2.5s)
        if now - self.last_theme_check > 2.5:
            self.last_theme_check = now
            self.refresh_system_theme()

        # 5. Idle fade & visibility calculation
        target_alpha = 1.0
        if self.is_game_fullscreen:
            target_alpha = 0.0
        elif self.config.idle_fade:
            idle_elapsed = now - self.last_move_time
            if idle_elapsed > self.config.idle_timeout_sec:
                fade_progress = min(1.0, (idle_elapsed - self.config.idle_timeout_sec) / 0.4)
                target_alpha = 1.0 - fade_progress

        # Smooth alpha transition
        self.visibility_alpha += (target_alpha - self.visibility_alpha) * min(1.0, 14.0 * dt)
        if self.visibility_alpha < 0.01:
            self.visibility_alpha = 0.0

        # 6. Synchronize system cursor visibility (hide/show)
        self.update_cursor_visibility()

        # 7. Update Fluid Engine
        head_color = QColor(self.system_accent_hex if self.config.use_system_accent else self.config.cursor_color)
        self.engine.update(
            real_x, real_y, dt,
            l_down, r_down, self.config,
            head_color
        )

        # 8. Compute Dirty Rect (efficient partial update)
        if self.visibility_alpha > 0.0 or self.last_dirty_rect.isValid():
            outline_sz = self.config.outline_size if self.config.outline_enabled else 0
            max_size = max(
                self.config.cursor_size * 2.8,
                outline_sz,
                32
            ) * self.engine.shake_scale * 2.5 + self.config.cursor_border_width * 2

            for r in self.engine.ripples:
                rad, _ = r.get_state()
                if rad * 2 > max_size:
                    max_size = rad * 2

            for s in self.engine.splashes:
                s_pos, _, _ = s.get_state()
                dx_s = abs(s_pos.x() - real_x)
                dy_s = abs(s_pos.y() - real_y)
                max_s = max(dx_s, dy_s) * 2
                if max_s > max_size:
                    max_size = max_s

            all_bone_x = [b.x() for b in self.engine.bones] + [real_x]
            all_bone_y = [b.y() for b in self.engine.bones] + [real_y]
            min_x = min(all_bone_x) - max_size
            min_y = min(all_bone_y) - max_size
            max_x = max(all_bone_x) + max_size
            max_y = max(all_bone_y) + max_size

            current_rect = QRect(int(min_x), int(min_y), int(max_x - min_x), int(max_y - min_y))
            update_rect = self.last_dirty_rect.united(current_rect)
            self.last_dirty_rect = current_rect
            self.update(update_rect)

    def paintEvent(self, event):
        if not self.config.enabled or self.visibility_alpha <= 0.0:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        self.engine.draw(
            painter,
            self.config,
            self.system_accent_hex,
            self.is_dark_mode,
            zoom=1.0,
            alpha_mult=self.visibility_alpha
        )

    def closeEvent(self, event):
        restore_system_cursor()
        shutdown_high_resolution_timer()
        super().closeEvent(event)
