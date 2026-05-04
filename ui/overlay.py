"""
ALEX -- Overlay UI (Phase 3 Redesign v2)
"Zero UI" design with 5 distinct visual states:
  IDLE:       The Sleeping Spark - single dim dot, breathing glow
  LISTENING:  Fluid Dynamics - 4 spheres act as real-time FFT equalizer
  PROCESSING: The Orbit - spheres chase in horizontal circular orbit
  SPEAKING:   The Prism - heartbeat expand/contract rhythm

Spheres have drop shadows (no glow), and bounce as equalizer bars
driven by live microphone FFT data.
"""

import sys
import math
import numpy as np
from enum import Enum
from queue import Queue, Empty

from PyQt6.QtWidgets import QApplication, QWidget, QMenu
from PyQt6.QtCore import Qt, QTimer, QPointF, QRectF
from PyQt6.QtGui import (
    QPainter, QRadialGradient, QLinearGradient,
    QColor, QPen, QBrush, QPainterPath, QFont,
)


class AssistantState(Enum):
    IDLE = "idle"
    LISTENING = "listening"
    PROCESSING = "processing"
    SPEAKING = "speaking"


# Aurora palette
SPHERE_COLORS = [
    (56, 217, 169),   # Soft teal
    (124, 58, 237),   # Deep violet
    (59, 130, 246),   # Electric blue
    (34, 211, 238),   # Cyan
]


class AlexOverlay(QWidget):
    WIN_W = 700
    WIN_H = 200
    SPHERE_R = 18
    SPHERE_SPACING = 52
    DOT_R = 2
    BLOOM_DURATION = 0.45
    COLLAPSE_DURATION = 0.35
    BREATH_PERIOD = 4.0
    EMA_ALPHA = 0.25

    def __init__(self, audio_queue: Queue, state_queue: Queue):
        super().__init__()
        self.audio_queue = audio_queue
        self.state_queue = state_queue
        self.state = AssistantState.IDLE
        self._prev_state = AssistantState.IDLE

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(self.WIN_W, self.WIN_H)

        screen = QApplication.primaryScreen().availableGeometry()
        self.move((screen.width() - self.WIN_W) // 2,
                  screen.height() - self.WIN_H)

        # Animation
        self.time = 0.0
        self.bloom_progress = 0.0
        self.collapse_progress = 0.0
        self._transitioning = False
        self._transition_dir = 1

        # Audio — 4 bands for 4 spheres
        self.band_levels = np.zeros(4)
        self.target_bands = np.zeros(4)
        self.audio_energy = 0.0
        self.target_energy = 0.0

        # Orbit
        self.orbit_angle = 0.0

        # Drag
        self._drag_pos = None

        # Dashboard
        self._dashboard = None

        # Timer 60fps
        self.anim_timer = QTimer(self)
        self.anim_timer.timeout.connect(self._tick)
        self.anim_timer.start(16)

    def set_dashboard(self, dashboard):
        self._dashboard = dashboard

    def _tick(self):
        dt = 0.016
        self.time += dt

        # Read state
        try:
            while True:
                raw = self.state_queue.get_nowait()
                new = raw if isinstance(raw, AssistantState) else AssistantState(str(raw).lower())
                if new != self.state:
                    self._prev_state = self.state
                    self.state = new
                    if self._prev_state == AssistantState.IDLE and new != AssistantState.IDLE:
                        self._transitioning = True
                        self._transition_dir = 1
                        self.bloom_progress = 0.0
                    elif new == AssistantState.IDLE and self._prev_state != AssistantState.IDLE:
                        self._transitioning = True
                        self._transition_dir = -1
                        self.collapse_progress = 0.0
        except (Empty, ValueError):
            pass

        # Read FFT → collapse 64 bins into 4 bands
        try:
            latest = None
            while True:
                latest = self.audio_queue.get_nowait()
            if latest is not None:
                fft = np.clip(latest, 0, 1)
                # Split 64 bins into 4 bands (low, low-mid, mid-hi, hi)
                self.target_bands[0] = float(np.mean(fft[0:8]))
                self.target_bands[1] = float(np.mean(fft[8:24]))
                self.target_bands[2] = float(np.mean(fft[24:48]))
                self.target_bands[3] = float(np.mean(fft[48:64]))
                self.target_energy = float(np.mean(fft[:16]))
        except Empty:
            pass

        # Smooth
        self.band_levels = 0.35 * self.target_bands + 0.65 * self.band_levels
        self.audio_energy = 0.3 * self.target_energy + 0.7 * self.audio_energy

        # Transitions
        if self._transitioning:
            if self._transition_dir == 1:
                self.bloom_progress = min(1.0, self.bloom_progress + dt / self.BLOOM_DURATION)
                if self.bloom_progress >= 1.0:
                    self._transitioning = False
            else:
                self.collapse_progress = min(1.0, self.collapse_progress + dt / self.COLLAPSE_DURATION)
                if self.collapse_progress >= 1.0:
                    self._transitioning = False
                    self.bloom_progress = 0.0

        # Orbit
        if self.state == AssistantState.PROCESSING:
            self.orbit_angle = (self.orbit_angle + 2.8 * dt) % (2 * math.pi)

        # Decay when idle
        if self.state == AssistantState.IDLE and not self._transitioning:
            self.band_levels *= 0.9
            self.audio_energy *= 0.9

        self.update()

    # ═══════════════════════════════════════════════════════════════
    # RENDERING
    # ═══════════════════════════════════════════════════════════════

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        cx, cy = self.width() / 2, self.height() * 0.6

        # Collapsing back to idle
        if self._transitioning and self._transition_dir == -1:
            t = 1.0 - self._ease_out(self.collapse_progress)
            self._draw_spheres_at(p, cx, cy, t, [0, 0, 0, 0])
            p.end()
            return

        if self.state == AssistantState.IDLE and not self._transitioning:
            self._draw_sleeping_spark(p, cx, cy)
        elif self._transitioning and self._transition_dir == 1:
            t = self._ease_out(self.bloom_progress)
            self._draw_spheres_at(p, cx, cy, t, [0, 0, 0, 0])
        elif self.state == AssistantState.LISTENING:
            self._draw_equalizer(p, cx, cy)
        elif self.state == AssistantState.PROCESSING:
            self._draw_orbit(p, cx, cy)
        elif self.state == AssistantState.SPEAKING:
            self._draw_prism(p, cx, cy)
        else:
            self._draw_spheres_at(p, cx, cy, 1.0, [0, 0, 0, 0])

        p.end()

    def _ease_out(self, t):
        return 1 - (1 - t) ** 3

    # -- IDLE: Sleeping Spark --------------------------------------

    def _draw_sleeping_spark(self, p, cx, cy):
        phase = (math.sin(self.time * 2 * math.pi / self.BREATH_PERIOD) + 1) / 2
        opacity = 0.10 + 0.20 * phase
        alpha = int(opacity * 255)
        r = self.DOT_R + 0.5 * phase

        # Subtle haze
        grad = QRadialGradient(cx, cy, r * 5)
        grad.setColorAt(0.0, QColor(255, 255, 255, alpha // 4))
        grad.setColorAt(1.0, QColor(255, 255, 255, 0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(grad))
        p.drawEllipse(QPointF(cx, cy), r * 5, r * 5)

        # Core dot
        grad2 = QRadialGradient(cx, cy, r)
        grad2.setColorAt(0.0, QColor(255, 255, 255, alpha))
        grad2.setColorAt(0.7, QColor(220, 230, 255, alpha))
        grad2.setColorAt(1.0, QColor(200, 220, 255, 0))
        p.setBrush(QBrush(grad2))
        p.drawEllipse(QPointF(cx, cy), r, r)

    # -- LISTENING: Real-time FFT Equalizer Spheres ----------------

    def _draw_equalizer(self, p, cx, cy):
        p.setPen(Qt.PenStyle.NoPen)
        total_w = self.SPHERE_SPACING * 3

        for i in range(4):
            sx = cx + (-total_w / 2 + i * self.SPHERE_SPACING)
            level = self.band_levels[i]

            # Y displacement — bounce up with FFT level
            bounce = -level * 55
            # Add subtle organic sway
            bounce += math.sin(self.time * 3.5 + i * 1.5) * 3
            sy = cy + bounce

            # Scale — grow with level
            scale = 1.0 + level * 0.6
            r = self.SPHERE_R * scale

            col = SPHERE_COLORS[i]
            self._draw_shadow_sphere(p, sx, sy, r, col, 220)

        # Listening text
        alpha = int(35 + 15 * math.sin(self.time * 3))
        p.setFont(QFont("Segoe UI", 10))
        p.setPen(QColor(180, 190, 210, alpha))
        p.drawText(QRectF(cx - 100, cy - 60, 200, 20),
                   Qt.AlignmentFlag.AlignCenter, "listening...")

    # -- PROCESSING: The Orbit -------------------------------------

    def _draw_orbit(self, p, cx, cy):
        p.setPen(Qt.PenStyle.NoPen)
        orbit_rx = 65
        orbit_ry = 12

        # Faint orbit trail
        for t in range(40):
            angle = self.orbit_angle - t * 0.05
            trail_a = max(0, 12 - t // 2)
            tx = cx + orbit_rx * math.cos(angle)
            ty = cy + orbit_ry * math.sin(angle)
            p.setBrush(QColor(80, 100, 160, trail_a))
            p.drawEllipse(QPointF(tx, ty), 4, 4)

        # 4 spheres chasing each other
        for i in range(4):
            angle = self.orbit_angle + i * (math.pi / 2)
            depth = math.sin(angle)
            scale = 0.7 + 0.3 * (depth + 1) / 2
            sx = cx + orbit_rx * math.cos(angle)
            sy = cy + orbit_ry * math.sin(angle)
            r = self.SPHERE_R * scale * 0.85
            col = SPHERE_COLORS[i]
            alpha = int(140 + 100 * scale)
            self._draw_shadow_sphere(p, sx, sy, r, col, alpha)

        # Bottom reflection
        self._draw_bottom_reflection(p, cx, self.height())

        # Thinking text
        dots = "." * (1 + int(self.time * 2) % 3)
        p.setFont(QFont("Segoe UI", 10))
        p.setPen(QColor(160, 170, 200, 45))
        p.drawText(QRectF(cx - 100, cy - 45, 200, 20),
                   Qt.AlignmentFlag.AlignCenter, f"thinking{dots}")

    # -- SPEAKING: The Prism ---------------------------------------

    def _draw_prism(self, p, cx, cy):
        p.setPen(Qt.PenStyle.NoPen)
        total_w = self.SPHERE_SPACING * 3

        beat = abs(math.sin(self.time * 3.5))

        for i in range(4):
            sx = cx + (-total_w / 2 + i * self.SPHERE_SPACING)
            s = 0.85 + 0.35 * abs(math.sin(self.time * 3.5 + i * 0.4))
            r = self.SPHERE_R * s
            col = SPHERE_COLORS[i]
            alpha = int(160 + 80 * beat)
            self._draw_shadow_sphere(p, sx, cy, r, col, alpha)

        self._draw_bottom_reflection(p, cx, self.height())

    # -- SHARED: Sphere with drop shadow (no glow) -----------------

    def _draw_shadow_sphere(self, p, x, y, r, rgb, alpha=220):
        """Draw a frosted sphere with a drop shadow beneath it."""
        cr, cg, cb = rgb

        # Drop shadow — offset down and slightly larger
        shadow_y = y + r * 0.4
        shadow_r = r * 1.1
        shadow = QRadialGradient(x, shadow_y, shadow_r)
        shadow.setColorAt(0.0, QColor(0, 0, 0, 50))
        shadow.setColorAt(0.5, QColor(0, 0, 0, 25))
        shadow.setColorAt(1.0, QColor(0, 0, 0, 0))
        p.setBrush(QBrush(shadow))
        p.drawEllipse(QPointF(x, shadow_y), shadow_r, shadow_r * 0.5)

        # Glass body
        body = QRadialGradient(x - r * 0.2, y - r * 0.2, max(1, r))
        body.setColorAt(0.0, QColor(min(255, cr + 80), min(255, cg + 60),
                                     min(255, cb + 40), alpha))
        body.setColorAt(0.35, QColor(cr, cg, cb, int(alpha * 0.9)))
        body.setColorAt(0.75, QColor(max(0, cr - 25), max(0, cg - 15),
                                     max(0, cb - 10), int(alpha * 0.65)))
        body.setColorAt(1.0, QColor(max(0, cr - 50), max(0, cg - 35),
                                     max(0, cb - 25), int(alpha * 0.35)))
        p.setBrush(QBrush(body))
        p.drawEllipse(QPointF(x, y), r, r)

        # Highlight
        spot = QRadialGradient(x - r * 0.25, y - r * 0.3, r * 0.3)
        spot.setColorAt(0.0, QColor(255, 255, 255, min(255, alpha // 2)))
        spot.setColorAt(1.0, QColor(255, 255, 255, 0))
        p.setBrush(QBrush(spot))
        p.drawEllipse(QPointF(x - r * 0.25, y - r * 0.3),
                       r * 0.25, r * 0.2)

    def _draw_spheres_at(self, p, cx, cy, t, offsets):
        """Draw 4 spheres at expansion level t (0=dot, 1=full)."""
        p.setPen(Qt.PenStyle.NoPen)
        total_w = self.SPHERE_SPACING * 3
        r = self.DOT_R + (self.SPHERE_R - self.DOT_R) * t

        for i in range(4):
            spread = (-total_w / 2 + i * self.SPHERE_SPACING) * t
            sx = cx + spread
            sy = cy
            col = SPHERE_COLORS[i]
            alpha = int(60 + 180 * t)
            self._draw_shadow_sphere(p, sx, sy, r, col, alpha)

    def _draw_bottom_reflection(self, p, cx, bottom_y):
        """Subtle colored reflection on bottom edge."""
        gw, gh = 250, 20
        y = bottom_y - gh
        grad = QLinearGradient(cx, y, cx, bottom_y)
        grad.setColorAt(0.0, QColor(0, 0, 0, 0))
        grad.setColorAt(0.5, QColor(60, 50, 160, 15))
        grad.setColorAt(1.0, QColor(40, 140, 180, 25))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(grad))
        p.drawRect(QRectF(cx - gw / 2, y, gw, gh))

    # ═══════════════════════════════════════════════════════════════
    # INTERACTION
    # ═══════════════════════════════════════════════════════════════

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.pos()
            event.accept()

    def mouseMoveEvent(self, event):
        if self._drag_pos and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event):
        self._drag_pos = None

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._dashboard:
            self._dashboard.toggle(self.x(), self.y())
            event.accept()

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #0d0d1a;
                color: #a0b0d0;
                border: 1px solid #2a2a4a;
                padding: 5px;
                font-family: 'Segoe UI';
                font-size: 12px;
            }
            QMenu::item:selected {
                background-color: #1a1a3e;
                color: #c0d0f0;
            }
        """)
        status = menu.addAction(f"State: {self.state.value.upper()}")
        status.setEnabled(False)
        menu.addSeparator()
        dash = menu.addAction("Dashboard")
        menu.addSeparator()
        quit_a = menu.addAction("Quit ALEX")

        action = menu.exec(event.globalPos())
        if action == quit_a:
            QApplication.quit()
        elif action == dash and self._dashboard:
            self._dashboard.toggle(self.x(), self.y())


# ═══════════════════════════════════════════════════════════════════
# PUBLIC LAUNCHER
# ═══════════════════════════════════════════════════════════════════

def create_overlay(audio_queue: Queue, state_queue: Queue):
    overlay = AlexOverlay(audio_queue, state_queue)
    overlay.show()
    return overlay


def launch_overlay_app(audio_queue: Queue, state_queue: Queue):
    app = QApplication.instance() or QApplication(sys.argv)
    overlay = create_overlay(audio_queue, state_queue)
    return app, overlay
