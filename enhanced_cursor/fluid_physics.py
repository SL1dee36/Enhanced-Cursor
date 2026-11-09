import math
import random
import time
from typing import List, Tuple, Optional
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QPainter, QColor, QPen, QBrush, QPainterPath,
    QLinearGradient, QRadialGradient
)
from enhanced_cursor.config import CursorConfig

NUM_BONES = 14


class RippleParticle:
    def __init__(self, pos: QPointF, max_radius: float, color: QColor, duration_ms: float = 350.0):
        self.pos = pos
        self.max_radius = max_radius
        self.base_color = color
        self.duration_ms = duration_ms
        self.start_time = time.perf_counter()
        self.finished = False

    def get_state(self) -> Tuple[float, QColor]:
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


class SplashParticle:
    def __init__(self, origin: QPointF, angle: float, speed: float, radius: float, color: QColor, life_sec: float = 0.35):
        self.x = origin.x()
        self.y = origin.y()
        self.vx = math.cos(angle) * speed
        self.vy = math.sin(angle) * speed
        self.max_radius = radius
        self.color = color
        self.life_sec = life_sec
        self.age = 0.0
        self.finished = False

    def update(self, dt: float):
        self.age += dt
        if self.age >= self.life_sec:
            self.finished = True
            return

        # Air drag
        drag = math.exp(-6.5 * dt)
        self.vx *= drag
        self.vy *= drag
        self.x += self.vx * dt
        self.y += self.vy * dt

    def get_state(self) -> Tuple[QPointF, float, QColor]:
        progress = min(1.0, self.age / self.life_sec)
        current_radius = max(0.5, self.max_radius * (1.0 - 0.7 * progress))
        alpha = int(self.color.alpha() * (1.0 - progress))
        c = QColor(self.color)
        c.setAlpha(max(0, min(255, alpha)))
        return QPointF(self.x, self.y), current_radius, c


class FluidCursorEngine:
    def __init__(self):
        # 14-Bone Fluid Spine Chain (0 = Head, 13 = Tail Tip)
        self.num_bones = NUM_BONES
        self.bones: List[QPointF] = [QPointF(0, 0) for _ in range(self.num_bones)]
        self.vels: List[QPointF] = [QPointF(0, 0) for _ in range(self.num_bones)]

        # Smooth velocity and magnitude of Head
        self.smooth_vx = 0.0
        self.smooth_vy = 0.0
        self.speed = 0.0
        self.prev_speed = 0.0

        # Raw tracking for delta calculation
        self.prev_raw_x = 0.0
        self.prev_raw_y = 0.0
        self.is_initialized = False

        # Jelly bounce / wobble on stop
        self.wobble_energy = 0.0
        self.wobble_phase = 0.0

        # Shake to find (macOS style)
        self.shake_scale = 1.0
        self.shake_counter = 0
        self.last_shake_time = 0.0
        self.last_sign_x = 0

        # Click animation
        self.is_pressed = False
        self.click_button = "left"  # "left" or "right"
        self.click_progress = 0.0
        self.click_anim_target = 0.0
        self.click_anim_start = 0.0
        self.click_anim_start_time = 0.0
        self.is_click_animating = False

        # Particle lists
        self.ripples: List[RippleParticle] = []
        self.splashes: List[SplashParticle] = []

    @property
    def pos_0(self) -> QPointF:
        return self.bones[0]

    @property
    def pos_1(self) -> QPointF:
        return self.bones[min(2, self.num_bones - 1)]

    @property
    def pos_2(self) -> QPointF:
        return self.bones[-1]

    def reset_position(self, x: float, y: float):
        for i in range(self.num_bones):
            self.bones[i] = QPointF(x, y)
            self.vels[i] = QPointF(0, 0)
        self.prev_raw_x = x
        self.prev_raw_y = y
        self.smooth_vx = 0.0
        self.smooth_vy = 0.0
        self.speed = 0.0
        self.is_initialized = True

    def update(
        self,
        raw_x: float,
        raw_y: float,
        dt: float,
        is_l_down: bool,
        is_r_down: bool,
        config: CursorConfig,
        effective_head_color: QColor
    ):
        if not self.is_initialized:
            self.reset_position(raw_x, raw_y)
            return

        dt = max(0.001, min(0.05, dt))
        now = time.perf_counter()

        # 1. Update Head Position
        dx_raw = raw_x - self.prev_raw_x
        dy_raw = raw_y - self.prev_raw_y
        self.prev_raw_x = raw_x
        self.prev_raw_y = raw_y

        # Smooth velocity of head
        alpha_v = min(1.0, 18.0 * dt)
        self.smooth_vx += (dx_raw / dt - self.smooth_vx) * alpha_v
        self.smooth_vy += (dy_raw / dt - self.smooth_vy) * alpha_v
        self.prev_speed = self.speed
        self.speed = math.hypot(self.smooth_vx, self.smooth_vy)

        # Head follow rate
        if config.render_mode == "custom":
            follow_rate = min(1.0, 70.0 * dt)
        else:
            follow_rate = min(1.0, (16.0 + config.speed * 42.0) * dt)

        head_x = self.bones[0].x() + (raw_x - self.bones[0].x()) * follow_rate
        head_y = self.bones[0].y() + (raw_y - self.bones[0].y()) * follow_rate
        self.bones[0] = QPointF(head_x, head_y)

        # 2. Shake to Find Detection (fast mouse direction reversals)
        if config.shake_to_find:
            if abs(self.smooth_vx) > 350.0:
                current_sign = 1 if self.smooth_vx > 0 else -1
                if self.last_sign_x != 0 and current_sign != self.last_sign_x:
                    if now - self.last_shake_time < 0.35:
                        self.shake_counter += 1
                        if self.shake_counter >= 3:
                            self.shake_scale = 2.4
                            self.shake_counter = 0
                    else:
                        self.shake_counter = 1
                    self.last_shake_time = now
                self.last_sign_x = current_sign

        # Decay shake scale smoothly
        self.shake_scale += (1.0 - self.shake_scale) * min(1.0, 4.0 * dt)

        # 3. Jelly Bounce / Surface Wobble (when stopping from high speed)
        if self.prev_speed > 160.0 and self.speed < 40.0:
            self.wobble_energy = min(0.35, self.prev_speed / 700.0)
            self.wobble_phase = 0.0

        if self.wobble_energy > 0.005:
            self.wobble_phase += 28.0 * dt
            self.wobble_energy *= math.exp(-9.0 * dt)
        else:
            self.wobble_energy = 0.0

        # 4. Multi-Bone Fluid Spine Physics (14 Bones)
        t_len = max(0.2, min(2.5, config.tail_length))
        visc = max(0.1, min(1.0, config.viscosity))

        # Stiffness k and damping c per bone
        k_base = (55.0 / t_len) * (0.75 + 0.5 * visc)
        c_base = 15.0 * math.sqrt(visc)

        # Maximum segment distance between adjacent bones to ensure smooth fluid continuity
        base_r0 = config.cursor_size * self.shake_scale
        base_segment = max(1.5, base_r0 * 0.35) * t_len

        for i in range(1, self.num_bones):
            prev = self.bones[i - 1]
            curr = self.bones[i]
            vel = self.vels[i]

            bone_ratio = i / float(self.num_bones - 1)
            k_bone = k_base * (1.0 - 0.25 * bone_ratio)
            c_bone = c_base * (1.0 - 0.20 * bone_ratio)

            fx = (prev.x() - curr.x()) * k_bone - vel.x() * c_bone
            fy = (prev.y() - curr.y()) * k_bone - vel.y() * c_bone

            new_vx = vel.x() + fx * dt
            new_vy = vel.y() + fy * dt
            self.vels[i] = QPointF(new_vx, new_vy)

            new_x = curr.x() + new_vx * dt
            new_y = curr.y() + new_vy * dt

            # Distance constraint between adjacent bones
            dx = new_x - prev.x()
            dy = new_y - prev.y()
            dist = math.hypot(dx, dy)
            if dist > base_segment:
                ratio = base_segment / dist
                new_x = prev.x() + dx * ratio
                new_y = prev.y() + dy * ratio

            self.bones[i] = QPointF(new_x, new_y)

        # 5. Surface Tension Contraction towards Head when stopping / slow
        tail_extent = math.hypot(self.bones[-1].x() - self.bones[0].x(), self.bones[-1].y() - self.bones[0].y())
        if self.speed < 25.0:
            contract_rate = min(1.0, (28.0 - self.speed) * 2.2 * dt)
            for i in range(1, self.num_bones):
                bx = self.bones[i].x() + (self.bones[0].x() - self.bones[i].x()) * contract_rate
                by = self.bones[i].y() + (self.bones[0].y() - self.bones[i].y()) * contract_rate
                self.bones[i] = QPointF(bx, by)
                self.vels[i] = QPointF(self.vels[i].x() * 0.6, self.vels[i].y() * 0.6)

        # Snap completely to resting circle if stationary
        if self.speed < 5.0 and tail_extent < 1.8:
            for i in range(1, self.num_bones):
                self.bones[i] = QPointF(self.bones[0].x(), self.bones[0].y())
                self.vels[i] = QPointF(0, 0)

        # 6. Click Handling (Left vs Right button)
        mouse_down = is_l_down or is_r_down
        if mouse_down and not self.is_pressed:
            self.is_pressed = True
            self.click_button = "right" if is_r_down else "left"
            self.start_click_anim(1.0, config.animation_duration)

            # Spawn Ripple
            if config.click_ripple:
                r_color = QColor(config.right_click_color if (is_r_down and config.color_mode_per_click) else effective_head_color)
                r_color.setAlpha(min(255, int(config.outline_opacity * 2.2)))
                max_rad = max(24.0, config.outline_size * 2.2 * self.shake_scale)
                self.ripples.append(RippleParticle(self.bones[0], max_rad, r_color, duration_ms=config.animation_duration * 1.5))

            # Spawn Liquid Splash Particles
            if config.click_splash:
                splash_color = QColor(config.right_click_color if (is_r_down and config.color_mode_per_click) else effective_head_color)
                num_particles = random.randint(5, 7)
                for _ in range(num_particles):
                    ang = random.uniform(0, 2 * math.pi)
                    sp = random.uniform(50.0, 160.0)
                    rad = random.uniform(1.5, 3.0) * self.shake_scale
                    self.splashes.append(SplashParticle(self.bones[0], ang, sp, rad, splash_color, life_sec=random.uniform(0.25, 0.4)))

        elif not mouse_down and self.is_pressed:
            self.is_pressed = False
            self.start_click_anim(0.0, config.animation_duration * 0.8)

        # 7. Progress Click Animation
        if self.is_click_animating:
            anim_dur = max(40.0, float(config.animation_duration))
            elapsed = (now - self.click_anim_start_time) * 1000.0
            p = min(1.0, elapsed / anim_dur)
            eased_p = 1.0 - (1.0 - p) ** 3  # OutCubic
            self.click_progress = self.click_anim_start + (self.click_anim_target - self.click_anim_start) * eased_p
            if p >= 1.0:
                self.click_progress = self.click_anim_target
                self.is_click_animating = False

        # 8. Update Particles
        self.ripples = [r for r in self.ripples if not r.finished]
        for s in self.splashes:
            s.update(dt)
        self.splashes = [s for s in self.splashes if not s.finished]

    def start_click_anim(self, target_val: float, duration_ms: float):
        self.click_anim_start = self.click_progress
        self.click_anim_target = target_val
        self.click_anim_start_time = time.perf_counter()
        self.is_click_animating = True

    def build_fluid_droplet_path(
        self,
        r0: float,
        viscosity: float
    ) -> QPainterPath:
        path = QPainterPath()
        n = self.num_bones

        # 1. Distance filter: extract bones that have sufficient separation
        # This completely prevents control-point loops when stationary or bunched up
        filtered: List[QPointF] = [self.bones[0]]
        for i in range(1, n):
            prev = filtered[-1]
            curr = self.bones[i]
            d = math.hypot(curr.x() - prev.x(), curr.y() - prev.y())
            if d >= 1.6:  # Minimum 1.6px separation to avoid singularities
                filtered.append(curr)

        m = len(filtered)
        tail_extent = math.hypot(self.bones[-1].x() - self.bones[0].x(), self.bones[-1].y() - self.bones[0].y())

        # If resting or barely stretched, draw a perfectly smooth, static circular drop
        if m < 3 or tail_extent < 3.0:
            path.addEllipse(self.bones[0], r0, r0)
            return path

        # Radii tapering smoothly along the filtered spine
        radii = []
        for i in range(m):
            t = i / float(m - 1)
            r_i = max(1.2, r0 * (1.0 - (t ** 0.68) * 0.86))
            radii.append(r_i)

        left_pts: List[QPointF] = []
        right_pts: List[QPointF] = []

        for i in range(m):
            curr = filtered[i]
            if i == 0:
                dx = filtered[0].x() - filtered[1].x()
                dy = filtered[0].y() - filtered[1].y()
            elif i == m - 1:
                dx = filtered[m - 2].x() - filtered[m - 1].x()
                dy = filtered[m - 2].y() - filtered[m - 1].y()
            else:
                dx = filtered[i - 1].x() - filtered[i + 1].x()
                dy = filtered[i - 1].y() - filtered[i + 1].y()

            L = math.hypot(dx, dy)
            if L > 1e-4:
                fwd = (dx / L, dy / L)
            elif math.hypot(self.smooth_vx, self.smooth_vy) > 1e-3:
                spd = math.hypot(self.smooth_vx, self.smooth_vy)
                fwd = (self.smooth_vx / spd, self.smooth_vy / spd)
            else:
                fwd = (1.0, 0.0)

            # Orthogonal normal
            norm = (-fwd[1], fwd[0])
            r_i = radii[i]

            left_pts.append(QPointF(curr.x() + norm[0] * r_i, curr.y() + norm[1] * r_i))
            right_pts.append(QPointF(curr.x() - norm[0] * r_i, curr.y() - norm[1] * r_i))

        # Head tip and Tail tip caps
        dx0 = filtered[0].x() - filtered[1].x()
        dy0 = filtered[0].y() - filtered[1].y()
        L0 = math.hypot(dx0, dy0)
        fwd0 = (dx0 / L0, dy0 / L0) if L0 > 1e-4 else (1.0, 0.0)
        head_tip = QPointF(filtered[0].x() + fwd0[0] * radii[0], filtered[0].y() + fwd0[1] * radii[0])

        dx_last = filtered[-2].x() - filtered[-1].x()
        dy_last = filtered[-2].y() - filtered[-1].y()
        L_last = math.hypot(dx_last, dy_last)
        fwd_last = (dx_last / L_last, dy_last / L_last) if L_last > 1e-4 else fwd0
        tail_tip = QPointF(filtered[-1].x() - fwd_last[0] * radii[-1], filtered[-1].y() - fwd_last[1] * radii[-1])

        # Complete smooth closed perimeter:
        # head_tip -> left_pts[0..m-1] -> tail_tip -> right_pts[m-1..0]
        perimeter = [head_tip] + left_pts + [tail_tip] + list(reversed(right_pts))
        total_pts = len(perimeter)

        # Build smooth closed Catmull-Rom cubic spline
        path.moveTo(perimeter[0])
        for i in range(total_pts):
            p0 = perimeter[(i - 1 + total_pts) % total_pts]
            p1 = perimeter[i]
            p2 = perimeter[(i + 1) % total_pts]
            p3 = perimeter[(i + 2) % total_pts]

            c1 = QPointF(p1.x() + (p2.x() - p0.x()) / 6.0, p1.y() + (p2.y() - p0.y()) / 6.0)
            c2 = QPointF(p2.x() - (p3.x() - p1.x()) / 6.0, p2.y() - (p3.y() - p1.y()) / 6.0)
            path.cubicTo(c1, c2, p2)

        path.closeSubpath()
        return path

    def draw(
        self,
        painter: QPainter,
        config: CursorConfig,
        system_accent_hex: str,
        is_dark_mode: bool,
        zoom: float = 1.0,
        alpha_mult: float = 1.0
    ):
        if alpha_mult <= 0.0:
            return

        # 1. Determine effective colors
        if config.use_system_accent and system_accent_hex:
            head_base_color = QColor(system_accent_hex)
        else:
            head_base_color = QColor(config.cursor_color)

        # Apply right-click color modulation if active
        if self.is_pressed and self.click_button == "right" and config.color_mode_per_click:
            head_base_color = QColor(config.right_click_color)

        tail_base_color = QColor(config.outline_color) if not config.use_system_accent else head_base_color.lighter(125)

        # Border color (adaptive contrast for dark vs light backgrounds)
        if config.use_system_accent:
            border_base_color = QColor("#ffffff" if is_dark_mode else "#000000")
            border_opacity = 140 if is_dark_mode else 110
        else:
            border_base_color = QColor(config.cursor_border_color)
            border_opacity = config.cursor_border_opacity

        # 2. Draw Ripples
        for ripple in self.ripples:
            rad, r_col = ripple.get_state()
            if rad > 0 and r_col.alpha() > 0:
                final_rcol = QColor(r_col)
                final_rcol.setAlpha(int(final_rcol.alpha() * alpha_mult))
                rpen = QPen(final_rcol, 1.8 * zoom)
                painter.setPen(rpen)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawEllipse(ripple.pos, rad * zoom, rad * zoom)

        # 3. Draw Splash Particles
        for splash in self.splashes:
            pos, s_rad, s_col = splash.get_state()
            if s_rad > 0 and s_col.alpha() > 0:
                final_scol = QColor(s_col)
                final_scol.setAlpha(int(final_scol.alpha() * alpha_mult))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QBrush(final_scol))
                painter.drawEllipse(pos, s_rad * zoom, s_rad * zoom)

        # 4. Draw Trailing Aura / Glow (Big Circle) - Only if enabled!
        if config.outline_enabled and config.outline_opacity > 0:
            outline_rad = config.outline_size * zoom * self.shake_scale * (1.0 - 0.40 * self.click_progress)
            if outline_rad > 0.5:
                aura_color = QColor(tail_base_color)
                aura_color.setAlpha(int(config.outline_opacity * alpha_mult))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QBrush(aura_color))
                # Anchor aura at mid-spine
                aura_anchor = self.bones[min(2, self.num_bones - 1)]
                painter.drawEllipse(aura_anchor, outline_rad, outline_rad)

        # 5. Draw Main Cursor (Fluid Drop or Classic Circle)
        wobble_factor = 1.0 + self.wobble_energy * math.cos(self.wobble_phase)
        base_r0 = config.cursor_size * zoom * self.shake_scale * wobble_factor * (1.0 + 0.35 * self.click_progress)

        if config.shape_mode == "fluid_drop":
            # 14-Bone Fluid Teardrop Rendering
            r0 = max(2.5, base_r0)
            fluid_path = self.build_fluid_droplet_path(r0, config.viscosity)

            tail_extent = math.hypot(self.bones[-1].x() - self.bones[0].x(), self.bones[-1].y() - self.bones[0].y())
            c_start = QColor(head_base_color)
            c_start.setAlpha(int(config.cursor_opacity * alpha_mult))

            # If moving with meaningful tail, use smooth gradient; otherwise solid clean fill
            if tail_extent >= 2.5:
                grad = QLinearGradient(self.bones[0], self.bones[-1])
                c_end = QColor(tail_base_color)
                c_end.setAlpha(int(config.cursor_opacity * 0.40 * alpha_mult))
                grad.setColorAt(0.0, c_start)
                grad.setColorAt(1.0, c_end)
                fill_brush = QBrush(grad)
            else:
                fill_brush = QBrush(c_start)

            # Border pen
            b_width = max(0.5, config.cursor_border_width * zoom)
            border_c = QColor(border_base_color)
            border_c.setAlpha(int(border_opacity * alpha_mult))
            border_pen = QPen(border_c, b_width) if config.cursor_border_width > 0 else Qt.PenStyle.NoPen

            painter.setPen(border_pen)
            painter.setBrush(fill_brush)
            painter.drawPath(fluid_path)

        else:
            # Classic Circle (iPadOS style with squash & stretch)
            cursor_color = QColor(head_base_color)
            cursor_color.setAlpha(int(config.cursor_opacity * alpha_mult))

            b_width = max(0.5, config.cursor_border_width * zoom)
            border_c = QColor(border_base_color)
            border_c.setAlpha(int(border_opacity * alpha_mult))
            border_pen = QPen(border_c, b_width) if config.cursor_border_width > 0 else Qt.PenStyle.NoPen

            painter.save()
            painter.translate(self.bones[0].x(), self.bones[0].y())

            if config.squash_and_stretch and self.speed > 2.5:
                angle = math.degrees(math.atan2(self.smooth_vy, self.smooth_vx))
                stretch = min(1.4, 1.0 + (self.speed / 120.0))
                squash = 1.0 / math.sqrt(stretch)
                painter.rotate(angle)
                painter.scale(stretch, squash)

            painter.setPen(border_pen)
            painter.setBrush(QBrush(cursor_color))
            painter.drawEllipse(QPointF(0, 0), base_r0, base_r0)
            painter.restore()
