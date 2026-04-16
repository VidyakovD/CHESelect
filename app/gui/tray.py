"""System tray icon and background-mode support."""

from PySide6.QtWidgets import QSystemTrayIcon, QMenu, QApplication
from PySide6.QtGui     import QIcon, QPixmap, QPainter, QColor, QPen, QPainterPath, QFont
from PySide6.QtCore    import Qt, QSize


def make_icon(size: int = 64, state: str = "disconnected") -> QIcon:
    """
    Draw the SelectVPN shield icon at runtime.
    state: 'disconnected' | 'connected'
    """
    pix = QPixmap(size, size)
    pix.fill(Qt.transparent)

    p = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing)

    w = h = size
    pad = size * 0.06

    # Shield path
    path = QPainterPath()
    path.moveTo(w * 0.50, pad)
    path.lineTo(w - pad,  h * 0.22)
    path.lineTo(w - pad,  h * 0.55)
    path.cubicTo(w - pad,       h * 0.80,
                 w * 0.72,      h * 0.93,
                 w * 0.50,      h * 0.99)
    path.cubicTo(w * 0.28,      h * 0.93,
                 pad,           h * 0.80,
                 pad,           h * 0.55)
    path.lineTo(pad, h * 0.22)
    path.closeSubpath()

    # Fill: dark bg
    p.setPen(Qt.NoPen)
    p.setBrush(QColor("#16161e"))
    p.drawPath(path)

    # Border: orange or grey
    border_color = QColor("#ff7220") if state == "connected" else QColor("#ff7220")
    pen = QPen(border_color, size * 0.045)
    pen.setJoinStyle(Qt.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)
    p.drawPath(path)

    # Letter "S"
    p.setPen(QColor("#ff7220"))
    font = QFont("Segoe UI", int(size * 0.40), QFont.Bold)
    p.setFont(font)
    p.drawText(pix.rect(), Qt.AlignCenter, "S")

    p.end()
    return QIcon(pix)


class TrayIcon(QSystemTrayIcon):
    def __init__(self, window, parent=None):
        super().__init__(parent)
        self.window = window

        self.setIcon(make_icon(64))
        self.setToolTip("SelectVPN")

        # Context menu
        menu = QMenu()
        menu.setStyleSheet("""
            QMenu {
                background: #13131a;
                border: 1px solid #1e1e2a;
                border-radius: 8px;
                padding: 4px;
                color: #c0c0d8;
                font-size: 13px;
            }
            QMenu::item {
                padding: 7px 20px;
                border-radius: 5px;
            }
            QMenu::item:selected {
                background: #1e1e2e;
                color: #ff7220;
            }
            QMenu::separator {
                height: 1px;
                background: #1e1e2a;
                margin: 4px 8px;
            }
        """)

        self._act_show  = menu.addAction("Открыть")
        menu.addSeparator()
        self._act_quit  = menu.addAction("Выйти")

        self._act_show.triggered.connect(self._show_window)
        self._act_quit.triggered.connect(self._quit_app)

        self.setContextMenu(menu)
        self.activated.connect(self._on_activate)

    # ------------------------------------------------------------------

    def _on_activate(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            # Single click → toggle window
            if self.window.isVisible():
                self.window.hide()
            else:
                self._show_window()

    def _show_window(self):
        self.window.show()
        self.window.raise_()
        self.window.activateWindow()

    def _quit_app(self):
        # Stop VPN synchronously before quitting
        try:
            vpn = self.window.vpn
            vpn._stop_all()
        except Exception:
            pass
        QApplication.quit()

    def update_state(self, state: str):
        """Update tray tooltip to reflect VPN state."""
        labels = {
            "connected":    "SelectVPN — Подключён",
            "disconnected": "SelectVPN — Выключен",
            "connecting":   "SelectVPN — Подключение...",
            "error":        "SelectVPN — Ошибка",
        }
        self.setToolTip(labels.get(state, "SelectVPN"))
