"""
Запуск GUI без проверки прав администратора (для просмотра интерфейса).
TUN не поднимается, но весь UI работает.
"""
import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

from app.storage.settings import Settings
from app.core.vpn import VpnController
from app.gui.main_window import MainWindow
from app.gui.styles import DARK

app = QApplication(sys.argv)
app.setApplicationName("SelectVPN")
app.setStyleSheet(DARK)
app.setQuitOnLastWindowClosed(False)
app.setHighDpiScaleFactorRoundingPolicy(
    Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
)

settings   = Settings()
controller = VpnController(settings)
window     = MainWindow(controller, settings)
window.show()
window.raise_()
window.activateWindow()

sys.exit(app.exec())
