import math
import time
from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Qt, QPointF, QTimer, QRectF
from PySide6.QtGui import (
    QPainter, QColor, QPen, QBrush, QWheelEvent,
    QMouseEvent, QPainterPath
)

from enhanced_cursor.config import CursorConfig
from enhanced_cursor.fluid_physics import FluidCursorEngine
from enhanced_cursor.win32_utils import get_system_accent_color, is_system_dark_mode


class InteractivePreviewWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(260, 260)
        self.setMouseTracking(True)

        self.config = CursorConfig()
        self.zoom_level = 1.0

        # Fluid physics engine
        self.engine = FluidCursorEngine()
        self.last_frame_time = time.perf_counter()

        # Target coordinates inside widget
        self.center_x = 130.0
        self.center_y = 130.0
        self.target_x = self.center_x
        self.target_y = self.center_y
        self.is_l_down = False
        self.is_r_down = False

        self.system_accent_hex = get_system_accent_color()
        self.is_dark_mode = is_system_dark_mode()

        # Update timer (~100 FPS)
        self.timer = QTimer(self)
        self.timer.setInterval(10)
        self.timer.timeout.connect(self.tick)
        self.timer.start()

    def set_config(self, config: CursorConfig):
        self.config = config
        self.system_accent_hex = get_system_accent_color()
        self.is_dark_mode = is_system_dark_mode()
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

        parent_dialog = self.window()
        if hasattr(parent_dialog, "sync_zoom_slider"):
            parent_dialog.sync_zoom_slider(int(self.zoom_level * 100))

    def mouseMoveEvent(self, event: QMouseEvent):
        pos = event.position()
        self.target_x = pos.x()
        self.target_y = pos.y()

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self.is_l_down = True
        elif event.button() == Qt.MouseButton.RightButton:
            self.is_r_down = True

    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self.is_l_down = False
        elif event.button() == Qt.MouseButton.RightButton:
            self.is_r_down = False

    def leaveEvent(self, event):
        self.is_l_down = False
        self.is_r_down = False

    def tick(self):
        now = time.perf_counter()
        dt = now - self.last_frame_time
        self.last_frame_time = now

        # If not hovered, drift gently around center
        if not self.underMouse():
            self.target_x += (self.width() / 2.0 - self.target_x) * min(1.0, 5.0 * dt)
            self.target_y += (self.height() / 2.0 - self.target_y) * min(1.0, 5.0 * dt)

        head_color = QColor(self.system_accent_hex if self.config.use_system_accent else self.config.cursor_color)
        self.engine.update(
            self.target_x,
            self.target_y,
            dt,
            self.is_l_down,
            self.is_r_down,
            self.config,
            head_color
        )
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Draw card background
        rect = QRectF(0.5, 0.5, self.width() - 1, self.height() - 1)
        path = QPainterPath()
        path.addRoundedRect(rect, 10, 10)
        painter.fillPath(path, QColor("#1c1c22"))
        painter.setPen(QPen(QColor("#32323c"), 1))
        painter.drawPath(path)

        # Subtle grid dots
        painter.setPen(QPen(QColor("#292934"), 1, Qt.PenStyle.DotLine))
        step = 26
        for x in range(step, self.width(), step):
            painter.drawLine(x, 10, x, self.height() - 10)
        for y in range(step, self.height(), step):
            painter.drawLine(10, y, self.width() - 10, y)

        painter.setClipPath(path)

        # Render simulated fluid drop or circle
        self.engine.draw(
            painter,
            self.config,
            self.system_accent_hex,
            self.is_dark_mode,
            zoom=self.zoom_level,
            alpha_mult=1.0
        )
