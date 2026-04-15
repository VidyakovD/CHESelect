"""Dialog for managing VLESS server links."""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QListWidget, QListWidgetItem, QTextEdit,
    QWidget, QMessageBox,
)
from PySide6.QtCore import Qt
from PySide6.QtGui  import QGuiApplication

from ..core.vless import parse_vless


class ServerDialog(QDialog):
    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.setWindowTitle("Серверы")
        self.setFixedSize(420, 480)
        self.setModal(True)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 20, 20, 20)
        lay.setSpacing(12)

        # Header
        lbl = QLabel("СЕРВЕРЫ")
        lbl.setProperty("class", "section-header")
        lbl.setStyleSheet("color: #44445a; font-size: 11px; font-weight: 700; letter-spacing: 2px;")
        lay.addWidget(lbl)

        # Server list
        self.list_servers = QListWidget()
        self.list_servers.setSpacing(2)
        lay.addWidget(self.list_servers, stretch=1)
        self.list_servers.currentRowChanged.connect(self._on_select)
        self._reload()

        # Paste area
        hint = QLabel("Вставьте VLESS ссылку:")
        hint.setStyleSheet("color: #44445a; font-size: 12px;")
        lay.addWidget(hint)

        self.input = QTextEdit()
        self.input.setPlaceholderText("vless://...")
        self.input.setFixedHeight(80)
        self.input.setStyleSheet(
            "background: #14141c; border: 1px solid #1e1e2a; border-radius: 8px;"
            "padding: 8px; color: #c0c0d8; font-size: 12px;"
        )
        lay.addWidget(self.input)

        # Buttons row
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        btn_paste = QPushButton("Из буфера")
        btn_paste.clicked.connect(self._paste_from_clipboard)
        btn_row.addWidget(btn_paste)

        btn_add = QPushButton("Добавить")
        btn_add.setObjectName("btn_add")
        btn_add.clicked.connect(self._add_server)
        btn_row.addWidget(btn_add)

        btn_remove = QPushButton("Удалить")
        btn_remove.clicked.connect(self._remove_server)
        btn_row.addWidget(btn_remove)

        lay.addLayout(btn_row)

    # ------------------------------------------------------------------

    def _reload(self):
        self.list_servers.clear()
        for link in self.settings.servers:
            parsed = parse_vless(link)
            name = parsed["alias"] if parsed else link[:40]
            server_str = f"{parsed['host']}:{parsed['port']}" if parsed else ""
            item = QListWidgetItem(f"{name}\n{server_str}")
            item.setData(Qt.UserRole, link)
            self.list_servers.addItem(item)

        # Highlight active
        idx = self.settings.active_server_index
        if self.list_servers.count() > 0:
            self.list_servers.setCurrentRow(idx)

    def _on_select(self, row: int):
        if row >= 0:
            self.settings.active_server_index = row

    def _paste_from_clipboard(self):
        cb = QGuiApplication.clipboard()
        text = cb.text().strip()
        if text.startswith("vless://"):
            self.input.setPlainText(text)
        else:
            self.input.setPlainText("")

    def _add_server(self):
        link = self.input.toPlainText().strip()
        if not link:
            return
        parsed = parse_vless(link)
        if not parsed:
            QMessageBox.warning(self, "Ошибка", "Неверная VLESS ссылка.")
            return
        self.settings.add_server(link)
        self.input.clear()
        self._reload()

    def _remove_server(self):
        row = self.list_servers.currentRow()
        if row >= 0:
            self.settings.remove_server(row)
            self._reload()
