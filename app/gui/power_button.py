"""Custom circular power button drawn with QPainter."""

from PySide6.QtWidgets import QAbstractButton
from PySide6.QtCore    import Qt, QRect, QPoint, QSize
from PySide6.QtGui     import (
    QPainter, QPen, QColor, QBrush,
    QRadialGradient, QPainterPath, QConicalGradient,
)
import math


# State colours
_COLORS = {
    "disconnected":  "#3a3a4a",
    "connected":     "#ff7220",
    "connecting":    "#ff9a50",
    "disconnecting": "#ff9a50",
    "error":         "#e05555",
}

_GLOW = {
    "disconnected":  None,
    "connected":     "#ff7220",
    "connecting":    "#ff9a50",
    "disconnecting": "#ff9a50",
    "error":         "#e05555",
}


class PowerButton(QAbstractButton):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._state = "disconnected"
        self._hover = False
        self.setFixedSize(130, 130)
        self.setCursor(Qt.PointingHandCursor)

    def set_state(self, state: str):
        self._state = state
        self.update()

    def enterEvent(self, e):
        self._hover = True
        self.update()

    def leaveEvent(self, e):
        self._hover = False
        self.update()

    def sizeHint(self) -> QSize:
        return QSize(130, 130)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        w, h = self.width(), self.height()
        cx, cy = w / 2, h / 2
        r = min(w, h) / 2 - 6          # outer circle radius

        color_hex = _COLORS.get(self._state, "#3a3a4a")
        glow_hex  = _GLOW.get(self._state)
        color     = QColor(color_hex)

        # ── Glow (only when active) ────────────────────────────────
        if glow_hex and self._state != "disconnected":
            glow = QRadialGradient(cx, cy, r + 18)
            gc = QColor(glow_hex)
            gc.setAlpha(70 if self._hover else 50)
            glow.setColorAt(0, gc)
            gc2 = QColor(glow_hex)
            gc2.setAlpha(0)
            glow.setColorAt(1, gc2)
            p.setPen(Qt.NoPen)
            p.setBrush(glow)
            glow_r = r + 18
            p.drawEllipse(int(cx - glow_r), int(cy - glow_r),
                          int(glow_r * 2), int(glow_r * 2))

        # ── Outer ring (arc) ───────────────────────────────────────
        ring_pen = QPen(color, 3.5)
        ring_pen.setCapStyle(Qt.RoundCap)
        p.setPen(ring_pen)
        p.setBrush(Qt.NoBrush)
        # Draw arc with gap at top (for the power stem)
        gap_deg  = 60          # degrees of gap at top
        start    = 90 + gap_deg // 2
        span     = 360 - gap_deg
        arc_rect = QRect(int(cx - r), int(cy - r), int(r * 2), int(r * 2))
        p.drawArc(arc_rect, start * 16, span * 16)

        # ── Circle fill (background) ───────────────────────────────
        inner_r = r - 5
        bg = QColor(22, 22, 30) if not self._hover else QColor(28, 28, 38)
        p.setPen(Qt.NoPen)
        p.setBrush(bg)
        p.drawEllipse(int(cx - inner_r), int(cy - inner_r),
                      int(inner_r * 2), int(inner_r * 2))

        # ── Power stem (vertical line from center upward) ──────────
        stem_pen = QPen(color, 3.5)
        stem_pen.setCapStyle(Qt.RoundCap)
        p.setPen(stem_pen)
        stem_top = cy - r + 2
        stem_bot = cy - r * 0.28
        p.drawLine(int(cx), int(stem_top), int(cx), int(stem_bot))

        p.end()
