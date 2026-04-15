"""SelectVPN — entry point."""

import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtCore    import Qt
from PySide6.QtNetwork import QLocalServer, QLocalSocket

from app.storage.settings import Settings
from app.core.vpn         import VpnController
from app.core.proxy       import clear_proxy
from app.gui.main_window  import MainWindow
from app.gui.styles       import DARK

_APP_KEY = "SelectVPN-SingleInstance"


def _is_already_running() -> bool:
    """Try to connect to an existing instance. Returns True if one exists."""
    sock = QLocalSocket()
    sock.connectToServer(_APP_KEY)
    if sock.waitForConnected(500):
        sock.write(b"show")
        sock.waitForBytesWritten(500)
        sock.disconnectFromServer()
        return True
    return False


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("SelectVPN")

    # ── Single instance guard ──────────────────────────────────
    if _is_already_running():
        sys.exit(0)

    # Clean up stale socket (e.g. after a crash)
    QLocalServer.removeServer(_APP_KEY)
    server = QLocalServer()
    server.listen(_APP_KEY)

    app.setStyleSheet(DARK)
    app.setQuitOnLastWindowClosed(False)
    app.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    # Clean up proxy left over from a previous crash
    clear_proxy()

    settings   = Settings()
    controller = VpnController(settings)
    window     = MainWindow(controller, settings)
    window.show()

    # When second instance sends "show", raise the window
    def _on_new_connection():
        conn = server.nextPendingConnection()
        if conn:
            conn.waitForReadyRead(500)
            window.show()
            window.raise_()
            window.activateWindow()
            conn.close()

    server.newConnection.connect(_on_new_connection)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
