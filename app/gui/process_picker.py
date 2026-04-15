"""
Dialog showing currently running processes so user can pick one.
Uses 'tasklist' — no extra dependencies needed.
"""

import subprocess
import csv
import io
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QListWidget, QListWidgetItem, QLineEdit,
)
from PySide6.QtCore import Qt, QSortFilterProxyModel
from PySide6.QtGui  import QIcon


# Process names to hide — system noise
_SKIP = {
    "system", "registry", "smss.exe", "csrss.exe", "wininit.exe",
    "winlogon.exe", "services.exe", "lsass.exe", "svchost.exe",
    "fontdrvhost.exe", "dwm.exe", "sihost.exe", "taskhostw.exe",
    "runtimebroker.exe", "searchhost.exe", "startmenuexperiencehost.exe",
    "shellexperiencehost.exe", "textinputhost.exe", "securityhealthsystray.exe",
    "ctfmon.exe", "conhost.exe", "dllhost.exe", "msdtc.exe",
    "spoolsv.exe", "wlanext.exe", "dashost.exe", "audiodg.exe",
    "ntoskrnl.exe", "cmd.exe", "pythonw.exe", "python.exe",
    "tasklist.exe", "wsl.exe", "wslhost.exe",
}


def _get_running_processes() -> list[str]:
    """Return sorted unique list of user-visible process names."""
    try:
        result = subprocess.run(
            ["tasklist", "/FO", "CSV", "/NH"],
            capture_output=True, text=True,
            encoding="cp866", errors="replace",
            timeout=5,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        names = set()
        reader = csv.reader(io.StringIO(result.stdout))
        for row in reader:
            if row:
                name = row[0].strip().strip('"').lower()
                if name and name not in _SKIP:
                    names.add(name)
        return sorted(names)
    except Exception:
        return []


class ProcessPicker(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Выбор приложения")
        self.setFixedSize(340, 460)
        self.setModal(True)
        self.selected: str | None = None

        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(10)

        # Header
        lbl = QLabel("Запущенные приложения")
        lbl.setStyleSheet("color: #44445a; font-size: 11px; font-weight: 700; letter-spacing: 1px;")
        lay.addWidget(lbl)

        # Search
        self.search = QLineEdit()
        self.search.setPlaceholderText("Поиск...")
        self.search.textChanged.connect(self._filter)
        lay.addWidget(self.search)

        # List
        self.listw = QListWidget()
        self.listw.setSpacing(1)
        self.listw.itemDoubleClicked.connect(self._confirm)
        lay.addWidget(self.listw, stretch=1)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        self.btn_ok = QPushButton("Добавить")
        self.btn_ok.setObjectName("btn_add")
        self.btn_ok.setEnabled(False)
        self.btn_ok.clicked.connect(self._confirm)
        btn_row.addWidget(self.btn_ok)

        btn_cancel = QPushButton("Отмена")
        btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(btn_cancel)
        lay.addLayout(btn_row)

        self.listw.currentItemChanged.connect(
            lambda cur, _: self.btn_ok.setEnabled(cur is not None)
        )

        self._processes = _get_running_processes()
        self._populate(self._processes)

    # ------------------------------------------------------------------

    def _populate(self, names: list[str]):
        self.listw.clear()
        for name in names:
            item = QListWidgetItem(name)
            self.listw.addItem(item)

    def _filter(self, text: str):
        text = text.strip().lower()
        if not text:
            self._populate(self._processes)
        else:
            self._populate([n for n in self._processes if text in n])

    def _confirm(self):
        item = self.listw.currentItem()
        if item:
            self.selected = item.text()
            self.accept()
