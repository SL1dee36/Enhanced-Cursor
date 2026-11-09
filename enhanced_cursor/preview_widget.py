import math
import time
from typing import List
from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Qt, QPointF, QTimer, QRectF
from PySide6.QtGui import QPainter, QColor, QPen, QBrush, QWheelEvent, QMouseEvent, QPainterPath

from enhanced_cursor.config import CursorConfig
from enhanced_cursor.overlay import RippleParticle


class InteractivePreviewWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(260, 260)
        self.setMouseTracking(True)

        self.config = CursorConfig()
        self.zoom_level = 1.0

        # Local positions
        self.center_x = 130.0
        self.center_y = 130.0
        self.real_x = self.center_x
        self.real_y = self.center_y
        self.target_x = self.center_x
        self.target_y = self.center_y

        # Velocity
        self.velocity_x = 0.0
        self.velocity_y = 0.0
        self.speed_magnitude = 0.0

        # Click state
        self.is_mouse_pressed = False
        self.click_progress = 0.0
        self.click_anim_start_val = 0.0
        self.click_anim_target_val = 0.0
        self.click_anim_start_time = 0.0
        self.is_click_animating = False

        self.ripples: List[RippleParticle] = []

        # Update timer
        self.timer = QTimer(self)
        self.timer.setInterval(12)  # ~80 FPS
        self.timer.timeout.connect(self.tick)
        self.timer.start()

    def set_config(self, config: CursorConfig):
        self.config = config
        self.update()

    def set_zoom(self, zoom: float):
        self.zoom_level = max(0.4, min(3.0, zoom))
        self.update()

    def wheelEvent(self, event: QWheelEvent):
        delta = event.angleDelta().y()
        if delta > 0:
            self.set_zoom(self.zoom_level + 0.1)
        elif delta < 0:
            self.set_zoom(self.zoom_level - 0.1)

        # Notify parent zoom slider if present
        parent_dialog = self.window()
        if hasattr(parent_dialog, "sync_zoom_slider"):
            parent_dialog.sync_zoom_slider(int(self.zoom_level * 100))

    def mouseMoveEvent(self, event: QMouseEvent):
        pos = event.position()
        dx = pos.x() - self.real_x
        dy = pos.y() - self.real_y
        self.real_x = pos.x()
        self.real_y = pos.y()

        raw_speed = math.hypot(dx, dy)
        self.speed_magnitude = 0.65 * self.speed_magnitude + 0.35 * raw_speed
        self.velocity_x = 0.65 * self.velocity_x + 0.35 * dx
        self.velocity_y = 0.65 * self.velocity_y + 0.35 * dy

    def mousePressEvent(self, event: QMouseEvent):
        self.is_mouse_pressed = True
        self.start_click_anim(1.0)
        if self.config.click_ripple:
            rcolor = QColor(self.config.outline_color)
            rcolor.setAlpha(min(255, self.config.outline_opacity * 2))
            self.ripples.append(RippleParticle(QPointF(self.target_x, self.target_y), self.config.outline_size * 2.2 * self.zoom_level, rcolor))

    def mouseReleaseEvent(self, event: QMouseEvent):
        self.is_mouse_pressed = False
        self.start_click_anim(0.0)

    def leaveEvent(self, event):
        # Gently ease back to center when cursor leaves widget
        self.is_mouse_pressed = False
        self.start_click_anim(0.0)

    def start_click_anim(self, target_val: float):
        self.click_anim_start_val = self.click_progress
        self.click_anim_target_val = target_val
        self.click_anim_start_time = time.perf_counter()
        self.is_click_animating = True

    def tick(self):
        now = time.perf_counter()

        # If not hovered, drift slowly back to center
        if not self.underMouse():
            self.real_x += (self.width() / 2.0 - self.real_x) * 0.05
            self.real_y += (self.height() / 2.0 - self.real_y) * 0.05
            self.speed_magnitude *= 0.9
            self.velocity_x *= 0.9
            self.velocity_y *= 0.9

        # Smooth trailing
        follow_speed = max(0.01, min(1.0, self.config.speed))
        tdx = self.real_x - self.target_x
        tdy = self.real_y - self.target_y
        self.target_x += tdx * follow_speed
        self.target_y += tdy * follow_speed

        # Animate click
        if self.is_click_animating:
            anim_dur = max(50.0, float(self.config.animation_duration))
            elapsed = (now - self.click_anim_start_time) * 1000.0
            p = min(1.0, elapsed / anim_dur)
            eased_p = 1.0 - (1.0 - p) ** 3
            self.click_progress = self.click_anim_start_val + (self.click_anim_target_val - self.click_anim_start_val) * eased_p
            if p >= 1.0:
                self.click_progress = self.click_anim_target_val
                self.is_click_animating = False

        self.ripples = [r for r in self.ripples if not r.finished]
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Draw widget background with rounded card effect
        rect = QRectF(0.5, 0.5, self.width() - 1, self.height() - 1)
        path = QPainterPath()
        path.addRoundedRect(rect, 10, 10)
        painter.fillPath(path, QColor("#1e1e24"))
        painter.setPen(QPen(QColor("#343440"), 1))
        painter.drawPath(path)

        # Subtle grid background inside preview
        painter.setPen(QPen(QColor("#282832"), 1, Qt.PenStyle.DotLine))
        step = 26
        for x in range(step, self.width(), step):
            painter.drawLine(x, 10, x, self.height() - 10)
        for y in range(step, self.height(), step):
            painter.drawLine(10, y, self.width() - 10, y)

        painter.setClipPath(path)

        # 1. Ripples
        for r in self.ripples:
            radius, rcolor = r.get_state()
            if radius > 0 and rcolor.alpha() > 0:
                painter.setPen(QPen(rcolor, 1.5))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawEllipse(r.pos, radius, radius)

        # 2. Outline
        scaled_outline_size = self.config.outline_size * self.zoom_level * (1.0 - 0.45 * self.click_progress)
        if scaled_outline_size > 0.5:
            outline_color = QColor(self.config.outline_color)
            outline_color.setAlpha(self.config.outline_opacity)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(outline_color))
            painter.drawEllipse(QPointF(self.target_x, self.target_y), scaled_outline_size, scaled_outline_size)

        # 3. Main Cursor
        base_cursor_size = self.config.cursor_size * self.zoom_level * (1.0 + 0.35 * self.click_progress)
        cursor_color = QColor(self.config.cursor_color)
        cursor_color.setAlpha(self.config.cursor_opacity)

        border_color = QColor(self.config.cursor_border_color)
        border_color.setAlpha(self.config.cursor_border_opacity)
        b_width = self.config.cursor_border_width * self.zoom_level
        border_pen = QPen(border_color, b_width) if b_width > 0 else Qt.PenStyle.NoPen

        painter.save()
        painter.translate(self.real_x, self.real_y)

        if self.config.squash_and_stretch and self.speed_magnitude > 2.0:
            angle = math.degrees(math.atan2(self.velocity_y, self.velocity_x))
            stretch = min(1.35, 1.0 + (self.speed_magnitude / 100.0))
            squash = 1.0 / math.sqrt(stretch)
            painter.rotate(angle)
            painter.scale(stretch, squash)

        painter.setPen(border_pen)
        painter.setBrush(QBrush(cursor_color))
        painter.drawEllipse(QPointF(0, 0), base_cursor_size, base_cursor_size)
        painter.restore()

