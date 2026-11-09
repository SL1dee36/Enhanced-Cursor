import math
import time
import ctypes
from ctypes import wintypes
from typing import List, Optional, Set
import win32gui
import win32con

from PySide6.QtWidgets import QWidget, QApplication
from PySide6.QtCore import Qt, QPointF, QRect, QRectF, QTimer, QEasingCurve, QTime
from PySide6.QtGui import QPainter, QColor, QPen, QBrush, QRegion

from enhanced_cursor.config import CursorConfig, ConfigManager
from enhanced_cursor.logger import get_logger
from enhanced_cursor.win32_utils import (
    get_virtual_desktop_rect,
    register_global_hotkey,
    unregister_global_hotkey,
    is_fullscreen_window_active,
    is_ibeam_cursor_active,
)

logger = get_logger()
user32 = ctypes.windll.user32


class RippleParticle:
    def __init__(self, pos: QPointF, max_radius: float, color: QColor, duration_ms: float = 350.0):
        self.pos = pos
        self.max_radius = max_radius
        self.base_color = color
        self.duration_ms = duration_ms
        self.start_time = time.perf_counter()
        self.finished = False

    def get_state(self):
        elapsed = (time.perf_counter() - self.start_time) * 1000.0
        progress = min(1.0, elapsed / self.duration_ms)
        if progress >= 1.0:
            self.finished = True
        # Ease out quad
        eased = 1.0 - (1.0 - progress) * (1.0 - progress)
        current_radius = self.max_radius * eased
        alpha = int(self.base_color.alpha() * (1.0 - progress))
        color = QColor(self.base_color)
        color.setAlpha(max(0, min(255, alpha)))
        return current_radius, color


class CursorOverlayWindow(QWidget):
    def __init__(self, config_manager: ConfigManager):
        super().__init__()
        self.config_manager = config_manager
        self.config: CursorConfig = config_manager.config

        # Setup frameless transparent overlay
        self.setWindowFlag(Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint)
        self.setWindowFlag(Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setMouseTracking(True)

        # Apply Win32 ExStyle
        hwnd = int(self.winId())
        ex_style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
        win32gui.SetWindowLong(
            hwnd,
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

        # Positions and animation state (sub-pixel floating point)
        self.cursor_pos = wintypes.POINT()
        self.real_x = 0.0
        self.real_y = 0.0
        self.target_x = 0.0
        self.target_y = 0.0

        # Velocity tracking for squash and stretch
        self.prev_real_x = 0.0
        self.prev_real_y = 0.0
        self.velocity_x = 0.0
        self.velocity_y = 0.0
        self.speed_magnitude = 0.0

        # Click animation state
        self.is_mouse_pressed = False
        self.click_progress = 0.0
        self.click_anim_start_time = 0.0
        self.click_anim_start_val = 0.0
        self.click_anim_target_val = 0.0
        self.is_click_animating = False

        # Idle & visibility state
        self.last_move_time = time.perf_counter()
        self.visibility_alpha = 1.0  # 0.0 to 1.0

        # External state tracking
        self.is_game_fullscreen = False
        self.is_ibeam = False
        self.last_env_check = 0.0

        # Active ripples
        self.ripples: List[RippleParticle] = []

        # Previous bounding box for efficient partial updates
        self.last_dirty_rect = QRect()

        # Main render loop timer (target ~100-120 FPS, 8ms)
        self.render_timer = QTimer(self)
        self.render_timer.setInterval(8)
        self.render_timer.timeout.connect(self.tick)
        self.render_timer.start()

        # Global hotkey
        self.hotkey_id = 999
        self.register_hotkey()

        # Connect config changes
        self.config_manager.config_changed.connect(self.on_config_changed)

        logger.info("CursorOverlayWindow initialized successfully.")

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
        hwnd = int(self.winId())
        # Ctrl (0x0002) + Alt (0x0001) + 'H' (0x48)
        register_global_hotkey(hwnd, self.hotkey_id, 0x0001 | 0x0002, 0x48)

    def unregister_hotkey(self):
        hwnd = int(self.winId())
        unregister_global_hotkey(hwnd, self.hotkey_id)

    def nativeEvent(self, event_type, message):
        # Handle WM_HOTKEY (0x0312)
        if event_type == b"windows_generic_MSG":
            msg = wintypes.MSG.from_address(int(message))
            if msg.message == 0x0312:  # WM_HOTKEY
                self.toggle_enabled()
                return True, 0
        return super().nativeEvent(event_type, message)

    def toggle_enabled(self):
        self.config.enabled = not self.config.enabled
        self.config_manager.update_config(self.config, save=True)
        status = "enabled" if self.config.enabled else "paused"
        logger.info(f"Cursor highlight toggled: {status}")
        self.update()

    def on_config_changed(self, new_config: CursorConfig):
        self.config = new_config
        self.update()

    def tick(self):
        if not self.config.enabled:
            if self.last_dirty_rect.isValid():
                self.update(self.last_dirty_rect)
                self.last_dirty_rect = QRect()
            return

        now = time.perf_counter()

        # 1. Update mouse position
        if user32.GetCursorPos(ctypes.byref(self.cursor_pos)):
            # Translate global screen coordinates to widget-relative coordinates
            win_top_left = self.geometry().topLeft()
            new_real_x = float(self.cursor_pos.x - win_top_left.x())
            new_real_y = float(self.cursor_pos.y - win_top_left.y())

            dx = new_real_x - self.real_x
            dy = new_real_y - self.real_y

            if abs(dx) > 0.01 or abs(dy) > 0.01:
                self.last_move_time = now
                self.real_x = new_real_x
                self.real_y = new_real_y
                # Smooth velocity
                raw_speed = math.hypot(dx, dy)
                self.speed_magnitude = 0.65 * self.speed_magnitude + 0.35 * raw_speed
                self.velocity_x = 0.65 * self.velocity_x + 0.35 * dx
                self.velocity_y = 0.65 * self.velocity_y + 0.35 * dy
            else:
                self.speed_magnitude *= 0.8
                self.velocity_x *= 0.8
                self.velocity_y *= 0.8

        # 2. Smooth trailing follow physics (lerp)
        follow_speed = max(0.01, min(1.0, self.config.speed))
        tdx = self.real_x - self.target_x
        tdy = self.real_y - self.target_y
        self.target_x += tdx * follow_speed
        self.target_y += tdy * follow_speed

        # 3. Mouse button states (Left=1, Right=2, Middle=4)
        l_down = bool(user32.GetAsyncKeyState(1) & 0x8000)
        r_down = bool(user32.GetAsyncKeyState(2) & 0x8000)
        m_down = bool(user32.GetAsyncKeyState(4) & 0x8000)
        mouse_down = l_down or r_down or m_down

        if mouse_down and not self.is_mouse_pressed:
            self.is_mouse_pressed = True
            self.last_move_time = now
            self.start_click_animation(target_val=1.0)
            if self.config.click_ripple:
                # Add ripple particle
                ripple_color = QColor(self.config.outline_color)
                ripple_color.setAlpha(min(255, self.config.outline_opacity * 2))
                max_rad = max(20.0, self.config.outline_size * 2.2)
                self.ripples.append(RippleParticle(QPointF(self.target_x, self.target_y), max_rad, ripple_color))
        elif not mouse_down and self.is_mouse_pressed:
            self.is_mouse_pressed = False
            self.start_click_animation(target_val=0.0)

        # 4. Progress click animation
        if self.is_click_animating:
            anim_dur = max(50.0, float(self.config.animation_duration))
            elapsed = (now - self.click_anim_start_time) * 1000.0
            p = min(1.0, elapsed / anim_dur)
            # OutCubic easing
            eased_p = 1.0 - (1.0 - p) ** 3
            self.click_progress = self.click_anim_start_val + (self.click_anim_target_val - self.click_anim_start_val) * eased_p
            if p >= 1.0:
                self.click_progress = self.click_anim_target_val
                self.is_click_animating = False

        # 5. Periodic check for fullscreen game & I-beam cursor (~every 250ms)
        if now - self.last_env_check > 0.25:
            self.last_env_check = now
            if self.config.game_detection:
                self.is_game_fullscreen = is_fullscreen_window_active({int(self.winId())})
            else:
                self.is_game_fullscreen = False

            if self.config.hide_while_typing:
                self.is_ibeam = is_ibeam_cursor_active()
            else:
                self.is_ibeam = False

        # 6. Idle fade & visibility calculation
        target_alpha = 1.0
        if self.is_game_fullscreen or self.is_ibeam:
            target_alpha = 0.0
        elif self.config.idle_fade:
            idle_elapsed = now - self.last_move_time
            if idle_elapsed > self.config.idle_timeout_sec:
                # Fade out smoothly over 0.5 sec
                fade_progress = min(1.0, (idle_elapsed - self.config.idle_timeout_sec) / 0.5)
                target_alpha = 1.0 - fade_progress

        # Smooth alpha transition
        self.visibility_alpha += (target_alpha - self.visibility_alpha) * 0.2
        if self.visibility_alpha < 0.01:
            self.visibility_alpha = 0.0

        # 7. Update ripples
        self.ripples = [r for r in self.ripples if not r.finished]

        # 8. Compute Dirty Rect (efficient partial update)
        if self.visibility_alpha > 0.0 or self.last_dirty_rect.isValid():
            max_element_size = max(self.config.cursor_size, self.config.outline_size, 30) * 3 + self.config.cursor_border_width
            for r in self.ripples:
                if r.max_radius * 2 > max_element_size:
                    max_element_size = r.max_radius * 2

            min_x = min(self.real_x, self.target_x) - max_element_size
            min_y = min(self.real_y, self.target_y) - max_element_size
            max_x = max(self.real_x, self.target_x) + max_element_size
            max_y = max(self.real_y, self.target_y) + max_element_size

            current_rect = QRect(int(min_x), int(min_y), int(max_x - min_x), int(max_y - min_y))
            update_rect = self.last_dirty_rect.united(current_rect)
            self.last_dirty_rect = current_rect
            self.update(update_rect)

    def start_click_animation(self, target_val: float):
        self.click_anim_start_val = self.click_progress
        self.click_anim_target_val = target_val
        self.click_anim_start_time = time.perf_counter()
        self.is_click_animating = True

    def paintEvent(self, event):
        if not self.config.enabled or self.visibility_alpha <= 0.0:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        alpha_mult = self.visibility_alpha

        # 1. Draw ripples
        for ripple in self.ripples:
            radius, rcolor = ripple.get_state()
            if radius > 0 and rcolor.alpha() > 0:
                final_rcolor = QColor(rcolor)
                final_rcolor.setAlpha(int(final_rcolor.alpha() * alpha_mult))
                rpen = QPen(final_rcolor, 1.5)
                painter.setPen(rpen)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawEllipse(ripple.pos, radius, radius)

        # 2. Draw Trailing Outline
        # When clicked, outline collapses/shrinks
        outline_size = self.config.outline_size * (1.0 - 0.45 * self.click_progress)
        if outline_size > 0.5:
            outline_color = QColor(self.config.outline_color)
            outline_color.setAlpha(int(self.config.outline_opacity * alpha_mult))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(outline_color))
            painter.drawEllipse(QPointF(self.target_x, self.target_y), outline_size, outline_size)

        # 3. Draw Main Cursor (with Squash & Stretch when moving fast)
        # When clicked, main cursor circle grows slightly
        base_cursor_size = self.config.cursor_size * (1.0 + 0.35 * self.click_progress)
        cursor_color = QColor(self.config.cursor_color)
        cursor_color.setAlpha(int(self.config.cursor_opacity * alpha_mult))

        border_color = QColor(self.config.cursor_border_color)
        border_color.setAlpha(int(self.config.cursor_border_opacity * alpha_mult))
        border_pen = QPen(border_color, self.config.cursor_border_width) if self.config.cursor_border_width > 0 else Qt.PenStyle.NoPen

        painter.save()
        painter.translate(self.real_x, self.real_y)

        if self.config.squash_and_stretch and self.speed_magnitude > 2.5:
            angle = math.degrees(math.atan2(self.velocity_y, self.velocity_x))
            stretch = min(1.4, 1.0 + (self.speed_magnitude / 120.0))
            squash = 1.0 / math.sqrt(stretch)
            painter.rotate(angle)
            painter.scale(stretch, squash)

        painter.setPen(border_pen)
        painter.setBrush(QBrush(cursor_color))
        painter.drawEllipse(QPointF(0, 0), base_cursor_size, base_cursor_size)
        painter.restore()

