"""
ALEX -- Analytics Dashboard Panel (Phase 3)
Dark-themed, neon-styled stats panel that slides out from the overlay.
Shows session stats, top functions, recent history, preferences, and tasks.
"""

import math
from PyQt6.QtWidgets import QWidget, QApplication
from PyQt6.QtCore import Qt, QTimer, QRectF, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import (
    QPainter, QColor, QPen, QBrush, QFont,
    QLinearGradient, QRadialGradient,
)


class DashboardPanel(QWidget):
    """
    Slide-out analytics panel attached to the overlay.
    Renders session statistics with neon styling.
    """

    PANEL_WIDTH = 320
    PANEL_HEIGHT = 480
    CORNER_RADIUS = 16
    BG_COLOR = QColor(12, 14, 28, 235)
    BORDER_COLOR = QColor(0, 140, 255, 120)
    ACCENT_COLOR = QColor(0, 200, 255)
    TEXT_COLOR = QColor(200, 230, 255)
    DIM_TEXT = QColor(100, 140, 180)
    BAR_COLOR = QColor(0, 180, 255, 180)
    SUCCESS_COLOR = QColor(0, 220, 120)
    ERROR_COLOR = QColor(255, 80, 80)

    def __init__(self, parent=None, memory_db=None, session_id="",
                 background_agent=None):
        super().__init__(parent)
        self._memory = memory_db
        self._session_id = session_id
        self._agent = background_agent

        # Cached data
        self._stats = {}
        self._top_funcs = []
        self._recent = []
        self._prefs = {}
        self._task_count = 0

        self.setFixedSize(self.PANEL_WIDTH, self.PANEL_HEIGHT)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.Popup
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        # Auto-refresh timer
        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self._refresh_data)
        self._refresh_timer.start(5000)

        self._refresh_data()

    def show_panel(self, anchor_x: int, anchor_y: int):
        """Show the dashboard panel anchored to the overlay position."""
        # Position to the left of the overlay
        x = anchor_x - self.PANEL_WIDTH - 15
        y = anchor_y

        # Clamp to screen
        screen = QApplication.primaryScreen().availableGeometry()
        if x < 10:
            x = anchor_x + 360  # Show to the right instead
        y = max(10, min(y, screen.height() - self.PANEL_HEIGHT - 10))

        self.move(x, y)
        self.show()
        self.raise_()

    def hide_panel(self):
        """Hide the dashboard panel."""
        self.hide()

    def toggle(self, anchor_x: int, anchor_y: int):
        """Toggle dashboard visibility."""
        if self.isVisible():
            self.hide_panel()
        else:
            self.show_panel(anchor_x, anchor_y)

    # -- Data Refresh -----------------------------------------------

    def _refresh_data(self):
        """Refresh all dashboard data from memory DB."""
        if not self._memory:
            return

        try:
            self._stats = self._memory.get_session_stats(self._session_id)
            self._top_funcs = self._memory.get_frequently_used(5)
            self._recent = self._memory.get_recent_turns(
                self._session_id, 5
            )
            self._prefs = self._memory.get_all_preferences()
            if self._agent:
                self._task_count = self._agent.get_active_count()
        except Exception:
            pass

        if self.isVisible():
            self.update()

    # -- Rendering --------------------------------------------------

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = self.width(), self.height()

        # Background
        self._draw_background(p, w, h)

        # Title bar
        y = self._draw_title(p, w, 15)

        # Session stats
        y = self._draw_stats(p, w, y + 10)

        # Top functions bar chart
        y = self._draw_top_functions(p, w, y + 8)

        # Recent history
        y = self._draw_recent(p, w, y + 8)

        # Preferences
        y = self._draw_preferences(p, w, y + 8)

        # Background tasks
        self._draw_tasks(p, w, y + 8)

        p.end()

    def _draw_background(self, p: QPainter, w: int, h: int):
        """Draw the panel background with gradient border."""
        # Drop shadow
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(0, 0, 0, 60))
        p.drawRoundedRect(4, 4, w - 4, h - 4,
                          self.CORNER_RADIUS, self.CORNER_RADIUS)

        # Main background
        bg = QLinearGradient(0, 0, 0, h)
        bg.setColorAt(0, QColor(16, 20, 38, 240))
        bg.setColorAt(1, QColor(8, 10, 22, 250))
        p.setBrush(QBrush(bg))
        p.setPen(QPen(self.BORDER_COLOR, 1.5))
        p.drawRoundedRect(1, 1, w - 2, h - 2,
                          self.CORNER_RADIUS, self.CORNER_RADIUS)

        # Top glow line
        glow = QLinearGradient(20, 1, w - 20, 1)
        glow.setColorAt(0, QColor(0, 140, 255, 0))
        glow.setColorAt(0.5, QColor(0, 200, 255, 120))
        glow.setColorAt(1, QColor(0, 140, 255, 0))
        p.setPen(QPen(QBrush(glow), 2))
        p.drawLine(20, 2, w - 20, 2)

    def _draw_title(self, p: QPainter, w: int, y: int) -> int:
        """Draw the title bar."""
        font = QFont("Segoe UI", 12, QFont.Weight.Bold)
        p.setFont(font)
        p.setPen(self.ACCENT_COLOR)
        p.drawText(18, y + 16, "ALEX Dashboard")

        # Separator
        p.setPen(QPen(QColor(0, 100, 200, 60), 1))
        y += 24
        p.drawLine(18, y, w - 18, y)

        return y

    def _draw_stats(self, p: QPainter, w: int, y: int) -> int:
        """Draw session statistics."""
        font_label = QFont("Segoe UI", 8)
        font_value = QFont("Segoe UI", 14, QFont.Weight.Bold)

        total = self._stats.get("total_commands", 0)
        success = self._stats.get("success_count", 0)
        errors = self._stats.get("error_count", 0)
        avg_ms = self._stats.get("avg_duration_ms", 0)

        # Row of stat cards
        card_w = (w - 50) // 3
        cards = [
            ("Commands", str(total), self.ACCENT_COLOR),
            ("Success", str(success), self.SUCCESS_COLOR),
            ("Errors", str(errors), self.ERROR_COLOR),
        ]

        for i, (label, value, color) in enumerate(cards):
            cx = 18 + i * (card_w + 8)

            # Card background
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(0, 60, 120, 30))
            p.drawRoundedRect(cx, y, card_w, 48, 8, 8)

            # Value
            p.setFont(font_value)
            p.setPen(color)
            p.drawText(cx + 8, y + 24, value)

            # Label
            p.setFont(font_label)
            p.setPen(self.DIM_TEXT)
            p.drawText(cx + 8, y + 40, label)

        y += 56

        # Avg response time
        p.setFont(QFont("Segoe UI", 8))
        p.setPen(self.DIM_TEXT)
        p.drawText(18, y, f"Avg response: {avg_ms:.0f}ms")

        return y + 6

    def _draw_top_functions(self, p: QPainter, w: int, y: int) -> int:
        """Draw top functions as horizontal bars."""
        p.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        p.setPen(self.ACCENT_COLOR)
        p.drawText(18, y + 10, "Top Functions")
        y += 16

        if not self._top_funcs:
            p.setFont(QFont("Segoe UI", 8))
            p.setPen(self.DIM_TEXT)
            p.drawText(18, y + 12, "No data yet")
            return y + 18

        max_count = max(c for _, c in self._top_funcs) if self._top_funcs else 1
        bar_area_w = w - 130

        p.setFont(QFont("Segoe UI", 8))

        for i, (func, count) in enumerate(self._top_funcs[:5]):
            row_y = y + i * 18

            # Function name
            p.setPen(self.TEXT_COLOR)
            name = func[:16] + ".." if len(func) > 18 else func
            p.drawText(18, row_y + 12, name)

            # Bar
            bar_w = max(4, int((count / max_count) * bar_area_w))
            bar_grad = QLinearGradient(110, 0, 110 + bar_w, 0)
            bar_grad.setColorAt(0, QColor(0, 140, 255, 180))
            bar_grad.setColorAt(1, QColor(0, 220, 255, 100))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(bar_grad))
            p.drawRoundedRect(110, row_y + 2, bar_w, 10, 3, 3)

            # Count
            p.setPen(self.DIM_TEXT)
            p.drawText(110 + bar_w + 6, row_y + 12, str(count))

        return y + len(self._top_funcs[:5]) * 18 + 2

    def _draw_recent(self, p: QPainter, w: int, y: int) -> int:
        """Draw recent command history."""
        p.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        p.setPen(self.ACCENT_COLOR)
        p.drawText(18, y + 10, "Recent")
        y += 16

        if not self._recent:
            p.setFont(QFont("Segoe UI", 8))
            p.setPen(self.DIM_TEXT)
            p.drawText(18, y + 12, "No history yet")
            return y + 18

        p.setFont(QFont("Segoe UI", 8))
        shown = [t for t in self._recent if t.get("role") == "user"][-5:]

        for i, turn in enumerate(shown):
            row_y = y + i * 16
            content = turn.get("content", "")[:35]
            if len(turn.get("content", "")) > 35:
                content += ".."

            # Status dot
            func = turn.get("function", "")
            dot_color = self.SUCCESS_COLOR if func else self.DIM_TEXT
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(dot_color)
            p.drawEllipse(18, row_y + 5, 6, 6)

            # Text
            p.setPen(self.TEXT_COLOR)
            p.drawText(30, row_y + 12, content)

        return y + len(shown) * 16 + 2

    def _draw_preferences(self, p: QPainter, w: int, y: int) -> int:
        """Draw stored preferences."""
        p.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        p.setPen(self.ACCENT_COLOR)
        p.drawText(18, y + 10, "Preferences")
        y += 16

        if not self._prefs:
            p.setFont(QFont("Segoe UI", 8))
            p.setPen(self.DIM_TEXT)
            p.drawText(18, y + 12, "None set")
            return y + 18

        p.setFont(QFont("Segoe UI", 8))
        for i, (k, v) in enumerate(list(self._prefs.items())[:4]):
            row_y = y + i * 14
            p.setPen(self.DIM_TEXT)
            p.drawText(18, row_y + 12, f"{k}:")
            p.setPen(self.TEXT_COLOR)
            val = v[:20] + ".." if len(v) > 22 else v
            p.drawText(130, row_y + 12, val)

        return y + min(len(self._prefs), 4) * 14 + 2

    def _draw_tasks(self, p: QPainter, w: int, y: int):
        """Draw background tasks count."""
        p.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        p.setPen(self.ACCENT_COLOR)
        p.drawText(18, y + 10, "Background Tasks")

        p.setFont(QFont("Segoe UI", 8))
        p.setPen(self.TEXT_COLOR)
        p.drawText(150, y + 10, f"{self._task_count} active")

    # -- Interaction ------------------------------------------------

    def mousePressEvent(self, event):
        """Close panel on any click."""
        if event.button() == Qt.MouseButton.LeftButton:
            self.hide_panel()
