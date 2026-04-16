"""Main application window."""

import sys
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QListWidget, QListWidgetItem,
    QLineEdit, QTabWidget, QFrame, QSizePolicy, QCheckBox,
)
from PySide6.QtCore  import Qt, Signal, QObject, QTimer, Slot
from PySide6.QtGui   import QFont, QPainter, QColor, QPen, QBrush, QPainterPath

from .styles          import DARK
from .power_button    import PowerButton
from .server_dialog   import ServerDialog
from .process_picker  import ProcessPicker
from .tray            import TrayIcon, make_icon
from ..core.updater   import APP_VERSION, check_for_update, download_and_install


# ── Logo widget ────────────────────────────────────────────────────────────

class LogoWidget(QWidget):
    """Small 'S' shield logo drawn with QPainter."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(36, 36)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        w, h = self.width(), self.height()

        # Shield path
        path = QPainterPath()
        path.moveTo(w * 0.5, h * 0.04)
        path.lineTo(w * 0.95, h * 0.22)
        path.lineTo(w * 0.95, h * 0.55)
        path.cubicTo(w * 0.95, h * 0.80,
                     w * 0.72, h * 0.93,
                     w * 0.50, h * 0.99)
        path.cubicTo(w * 0.28, h * 0.93,
                     w * 0.05, h * 0.80,
                     w * 0.05, h * 0.55)
        path.lineTo(w * 0.05, h * 0.22)
        path.closeSubpath()

        # Fill
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#1c1c28"))
        p.drawPath(path)

        # Orange border
        pen = QPen(QColor("#ff7220"), 2.0)
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        p.drawPath(path)

        # "S" letter
        p.setPen(QColor("#ff7220"))
        font = QFont("Segoe UI", int(h * 0.38), QFont.Bold)
        p.setFont(font)
        p.drawText(self.rect(), Qt.AlignCenter, "S")
        p.end()


# ── Thread-safe signal bridge ──────────────────────────────────────────────

class _Bridge(QObject):
    state_changed = Signal(str, str)


# ── Main Window ────────────────────────────────────────────────────────────

class MainWindow(QMainWindow):
    def __init__(self, vpn, settings):
        super().__init__()
        self.vpn      = vpn
        self.settings = settings
        self._bridge  = _Bridge()
        self._bridge.state_changed.connect(self._on_state_changed)

        self.vpn.on_state_change = lambda s, d: self._bridge.state_changed.emit(s, d)

        self.setWindowTitle("SelectVPN")
        self.setFixedSize(380, 620)
        self.setStyleSheet(DARK)
        self.setWindowIcon(make_icon(64))

        self._build_ui()
        self._refresh_server_label()

        # Tray
        self._tray = TrayIcon(self)
        self._tray.show()

        # Check for updates at startup
        self._update_info = None
        check_for_update(self._on_update_check)

    # ── UI construction ────────────────────────────────────────────────

    def _build_ui(self):
        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(24, 24, 24, 20)
        layout.setSpacing(0)

        # ── Header: logo + title ───────────────────────────────────
        header = QHBoxLayout()
        header.setSpacing(10)
        logo = LogoWidget()
        header.addWidget(logo)
        title = QLabel("SelectVPN")
        title.setStyleSheet("font-size: 15px; font-weight: 700; color: #606080; letter-spacing: 1px;")
        header.addWidget(title)
        header.addStretch()
        layout.addLayout(header)
        layout.addSpacing(20)

        # ── Power button + status ──────────────────────────────────
        top = QVBoxLayout()
        top.setSpacing(14)
        top.setAlignment(Qt.AlignCenter)

        self.btn_power = PowerButton()
        self.btn_power.clicked.connect(self._toggle_vpn)
        top.addWidget(self.btn_power, alignment=Qt.AlignCenter)

        self.lbl_status = QLabel("ВЫКЛЮЧЕН")
        self.lbl_status.setObjectName("lbl_status")
        self.lbl_status.setAlignment(Qt.AlignCenter)
        self._refresh_state_style(self.lbl_status, "disconnected")
        top.addWidget(self.lbl_status)

        self.lbl_server = QLabel("нет сервера")
        self.lbl_server.setObjectName("lbl_server")
        self.lbl_server.setAlignment(Qt.AlignCenter)
        top.addWidget(self.lbl_server)

        layout.addLayout(top)
        layout.addSpacing(16)

        # ── TUN mode toggle ───────────────────────────────────────
        tun_row = QHBoxLayout()
        tun_row.setContentsMargins(4, 0, 4, 0)
        self.chk_tun = QCheckBox("TUN-режим")
        self.chk_tun.setChecked(self.settings.tun_mode)
        self.chk_tun.setStyleSheet(
            "QCheckBox { color: #555570; font-size: 12px; spacing: 6px; }"
            "QCheckBox::indicator { width: 16px; height: 16px; border-radius: 3px;"
            "  border: 1px solid #333348; background: #13131a; }"
            "QCheckBox::indicator:checked { background: #ff7220; border-color: #ff7220; }"
        )
        self.chk_tun.toggled.connect(self._toggle_tun_mode)
        tun_row.addWidget(self.chk_tun)

        tun_hint = QLabel("права админа · роутинг по приложениям")
        tun_hint.setStyleSheet("color: #2a2a3a; font-size: 10px;")
        tun_row.addWidget(tun_hint)
        tun_row.addStretch()
        layout.addLayout(tun_row)
        layout.addSpacing(8)

        # ── Divider ────────────────────────────────────────────────
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        layout.addWidget(line)
        layout.addSpacing(4)

        # ── Tabs ──────────────────────────────────────────────────
        tabs = QTabWidget()
        tabs.setDocumentMode(True)
        tabs.addTab(self._build_domain_tab(),  "ДОМЕНЫ")
        tabs.addTab(self._build_process_tab(), "ПРИЛОЖЕНИЯ")
        layout.addWidget(tabs, stretch=1)

        layout.addSpacing(10)

        # ── Bottom buttons ─────────────────────────────────────────
        bottom_row = QHBoxLayout()
        bottom_row.setSpacing(0)

        btn_servers = QPushButton("  Серверы")
        btn_servers.setStyleSheet(
            "QPushButton { text-align: left; padding-left: 14px; color: #555570; }"
            "QPushButton:hover { color: #9090b0; }"
        )
        btn_servers.clicked.connect(self._open_servers)
        bottom_row.addWidget(btn_servers)

        self.btn_update = QPushButton(f"v{APP_VERSION}")
        self.btn_update.setStyleSheet(
            "QPushButton { color: #2a2a3a; font-size: 11px; border: none; padding: 4px 10px; }"
            "QPushButton:hover { color: #555570; }"
        )
        self.btn_update.setVisible(True)
        self.btn_update.clicked.connect(self._on_update_click)
        self._update_info = None
        bottom_row.addWidget(self.btn_update)

        layout.addLayout(bottom_row)

        # ── Error label ────────────────────────────────────────────
        self.lbl_error = QLabel("")
        self.lbl_error.setObjectName("lbl_error")
        self.lbl_error.setWordWrap(True)
        self.lbl_error.setVisible(False)
        layout.addSpacing(6)
        layout.addWidget(self.lbl_error)

    def _build_domain_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 10, 0, 0)
        lay.setSpacing(8)

        hint = QLabel("Только эти домены пойдут через VPN")
        hint.setStyleSheet("color: #2a2a3a; font-size: 11px;")
        lay.addWidget(hint)

        self.list_domains = QListWidget()
        self.list_domains.setSpacing(1)
        lay.addWidget(self.list_domains, stretch=1)
        self._reload_domains()

        row = QHBoxLayout()
        row.setSpacing(8)
        self.input_domain = QLineEdit()
        self.input_domain.setPlaceholderText("youtube.com")
        self.input_domain.returnPressed.connect(self._add_domain)
        row.addWidget(self.input_domain)

        btn = QPushButton("+")
        btn.setObjectName("btn_add")
        btn.setFixedSize(38, 38)
        btn.clicked.connect(self._add_domain)
        row.addWidget(btn)
        lay.addLayout(row)
        return w

    def _build_process_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 10, 0, 0)
        lay.setSpacing(8)

        self.lbl_process_hint = QLabel()
        self.lbl_process_hint.setStyleSheet("color: #2a2a3a; font-size: 11px;")
        self.lbl_process_hint.setWordWrap(True)
        lay.addWidget(self.lbl_process_hint)
        self._refresh_process_hint()

        self.list_processes = QListWidget()
        self.list_processes.setSpacing(1)
        lay.addWidget(self.list_processes, stretch=1)
        self._reload_processes()

        row = QHBoxLayout()
        row.setSpacing(8)
        self.input_process = QLineEdit()
        self.input_process.setPlaceholderText("telegram.exe")
        self.input_process.returnPressed.connect(self._add_process)
        row.addWidget(self.input_process)

        btn = QPushButton("+")
        btn.setObjectName("btn_add")
        btn.setFixedSize(38, 38)
        btn.clicked.connect(self._pick_process)
        row.addWidget(btn)
        lay.addLayout(row)
        return w

    # ── TUN mode ──────────────────────────────────────────────────

    def _toggle_tun_mode(self, checked: bool):
        self.settings.tun_mode = checked
        self._refresh_process_hint()
        self._reconnect_if_active()

    def _refresh_process_hint(self):
        if self.settings.tun_mode:
            self.lbl_process_hint.setText(
                "Весь трафик этих приложений через VPN.\n"
                "Для браузеров — добавляй домены."
            )
        else:
            self.lbl_process_hint.setText(
                "Включите TUN-режим для роутинга\n"
                "по приложениям."
            )

    # ── VPN toggle ────────────────────────────────────────────────

    def _toggle_vpn(self):
        state = self.vpn.state
        if state in ("disconnected", "error"):
            self.vpn.connect()
        elif state == "connected":
            self.vpn.disconnect()

    @Slot(str, str)
    def _on_state_changed(self, state: str, detail: str):
        labels = {
            "connected":     "ПОДКЛЮЧЁН",
            "connecting":    "ПОДКЛЮЧЕНИЕ...",
            "disconnecting": "ОТКЛЮЧЕНИЕ...",
            "disconnected":  "ВЫКЛЮЧЕН",
            "error":         "ОШИБКА",
        }
        self.lbl_status.setText(labels.get(state, state.upper()))
        self._refresh_state_style(self.lbl_status, state)
        self.btn_power.set_state(state)
        self.btn_power.setEnabled(state not in ("connecting", "disconnecting"))

        if state == "error" and detail:
            self.lbl_error.setText(detail)
            self.lbl_error.setVisible(True)
        else:
            self.lbl_error.setVisible(False)

        self._tray.update_state(state)

    def _refresh_state_style(self, label, state: str):
        label.setProperty("state", state)
        label.style().unpolish(label)
        label.style().polish(label)

    # ── Update ────────────────────────────────────────────────────

    def _on_update_check(self, info):
        """Called from background thread when update check completes."""
        if info:
            self._update_info = info
            # Update button from any thread via QTimer
            QTimer.singleShot(0, self._show_update_available)

    def _show_update_available(self):
        ver = self._update_info["version"]
        self.btn_update.setText(f"Обновить до v{ver}")
        self.btn_update.setStyleSheet(
            "QPushButton { color: #ff7220; font-size: 11px; border: none; padding: 4px 10px; font-weight: 700; }"
            "QPushButton:hover { color: #ffaa60; }"
        )

    def _on_update_click(self):
        if not self._update_info:
            return
        info = self._update_info
        if info.get("is_exe"):
            # Download and install
            self.btn_update.setText("Скачивание...")
            self.btn_update.setEnabled(False)
            download_and_install(
                info["url"],
                on_progress=lambda p: QTimer.singleShot(0, lambda: self.btn_update.setText(f"Скачивание {p}%")),
                on_done=self._on_download_done,
            )
        else:
            # Open release page in browser
            from PySide6.QtGui import QDesktopServices
            from PySide6.QtCore import QUrl
            QDesktopServices.openUrl(QUrl(info["url"]))

    def _on_download_done(self, success, error):
        if success:
            QTimer.singleShot(0, lambda: QApplication.quit())
        else:
            QTimer.singleShot(0, lambda: self.btn_update.setText("Ошибка загрузки"))
            QTimer.singleShot(0, lambda: self.btn_update.setEnabled(True))

    # ── Domains ───────────────────────────────────────────────────

    def _add_domain(self):
        text = _clean_domain(self.input_domain.text())
        if not text:
            return
        self.input_domain.setText(text)   # show cleaned value briefly
        if self.settings.add_domain(text):
            self._add_list_item(self.list_domains, text, self._remove_domain)
            self.input_domain.clear()
            self._reconnect_if_active()

    def _remove_domain(self, domain: str, item: QListWidgetItem):
        self.settings.remove_domain(domain)
        self.list_domains.takeItem(self.list_domains.row(item))
        self._reconnect_if_active()

    def _reload_domains(self):
        self.list_domains.clear()
        for d in self.settings.domains:
            self._add_list_item(self.list_domains, d, self._remove_domain)

    # ── Processes ─────────────────────────────────────────────────

    def _pick_process(self):
        """Open process picker, or fall back to manual input if field has text."""
        manual = self.input_process.text().strip()
        if manual:
            # User typed something manually — add it directly
            self._add_process_name(manual)
            return
        dlg = ProcessPicker(parent=self)
        if dlg.exec() and dlg.selected:
            self._add_process_name(dlg.selected)

    def _add_process(self):
        text = self.input_process.text().strip()
        self._add_process_name(text)

    def _add_process_name(self, name: str):
        if self.settings.add_process(name):
            self._add_list_item(self.list_processes, name, self._remove_process)
            self.input_process.clear()
            self._reconnect_if_active()

    def _remove_process(self, name: str, item: QListWidgetItem):
        self.settings.remove_process(name)
        self.list_processes.takeItem(self.list_processes.row(item))
        self._reconnect_if_active()

    def _reload_processes(self):
        self.list_processes.clear()
        for p in self.settings.processes:
            self._add_list_item(self.list_processes, p, self._remove_process)

    # ── Helpers ───────────────────────────────────────────────────

    def _add_list_item(self, listw: QListWidget, text: str, remove_cb):
        item = QListWidgetItem()
        listw.addItem(item)

        row_widget = QWidget()
        row_widget.setStyleSheet("background: transparent;")
        row_lay = QHBoxLayout(row_widget)
        row_lay.setContentsMargins(6, 2, 4, 2)
        row_lay.setSpacing(4)

        lbl = QLabel(text)
        lbl.setStyleSheet("color: #b0b0c8; font-size: 13px; background: transparent;")
        row_lay.addWidget(lbl, stretch=1)

        btn = QPushButton("×")
        btn.setObjectName("btn_remove")
        btn.setFixedSize(22, 22)
        btn.setCursor(Qt.PointingHandCursor)
        btn.clicked.connect(lambda: remove_cb(text, item))
        row_lay.addWidget(btn)

        item.setSizeHint(row_widget.sizeHint())
        listw.setItemWidget(item, row_widget)

    def _reconnect_if_active(self):
        if self.vpn.state == "connected":
            self.vpn.disconnect()
            QTimer.singleShot(1500, self.vpn.connect)

    # ── Servers dialog ─────────────────────────────────────────────

    def _open_servers(self):
        dlg = ServerDialog(self.settings, parent=self)
        dlg.exec()
        self._refresh_server_label()

    # ── Window events ─────────────────────────────────────────────

    def closeEvent(self, event):
        """Close → hide to tray, don't quit."""
        event.ignore()
        self.hide()
        self._tray.showMessage(
            "SelectVPN",
            "Приложение свёрнуто в трей. Нажмите на иконку чтобы открыть.",
            TrayIcon.MessageIcon.Information,
            2500,
        )

    def changeEvent(self, event):
        """Minimize → hide to tray."""
        from PySide6.QtCore import QEvent
        if event.type() == QEvent.Type.WindowStateChange:
            if self.isMinimized():
                event.ignore()
                QTimer.singleShot(0, self.hide)
        super().changeEvent(event)

    # ── Server label ──────────────────────────────────────────────

    def _refresh_server_label(self):
        from ..core.vless import parse_vless
        link = self.settings.active_server
        if link:
            parsed = parse_vless(link)
            name = parsed["alias"] if parsed else link[:30]
            self.lbl_server.setText(f"↗  {name}")
        else:
            self.lbl_server.setText("нет сервера")


# ── Helpers ────────────────────────────────────────────────────────────────

def _clean_domain(raw: str) -> str:
    """
    Extract hostname from whatever user pastes:
      https://youtube.com/watch?v=xxx  →  youtube.com
      youtube.com/channel/abc          →  youtube.com
      *.google.com                     →  *.google.com   (kept as-is)
      youtube.com                      →  youtube.com
    """
    s = raw.strip()
    if not s:
        return ""

    # Keep wildcard patterns as-is
    if s.startswith("*."):
        return s.lower()

    # Add scheme so urlparse works
    if "://" not in s:
        s = "https://" + s

    from urllib.parse import urlparse
    try:
        hostname = urlparse(s).hostname or ""
        return hostname.lower().lstrip("www.") if hostname else raw.strip().lower()
    except Exception:
        return raw.strip().lower()
