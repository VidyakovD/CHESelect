"""Dark theme stylesheet for SelectVPN."""

DARK = """
QWidget {
    background-color: #0f0f13;
    color: #e8e8f0;
    font-family: "Segoe UI", sans-serif;
    font-size: 14px;
}

QMainWindow {
    background-color: #0f0f13;
}

/* ── Status label ── */
QLabel#lbl_status {
    font-size: 13px;
    font-weight: 700;
    letter-spacing: 2px;
    color: #888898;
}
QLabel#lbl_status[state="connected"]    { color: #ff7220; }
QLabel#lbl_status[state="connecting"]   { color: #ffaa60; }
QLabel#lbl_status[state="disconnected"] { color: #44445a; }
QLabel#lbl_status[state="error"]        { color: #e05555; }

/* ── Server label ── */
QLabel#lbl_server {
    font-size: 12px;
    color: #44445a;
}

/* ── List widget ── */
QListWidget {
    background-color: #13131a;
    border: 1px solid #1c1c28;
    border-radius: 10px;
    padding: 4px;
    outline: none;
}
QListWidget::item {
    padding: 5px 8px;
    border-radius: 6px;
    color: #b0b0c8;
}
QListWidget::item:selected {
    background-color: #1e1e2e;
    color: #e8e8f8;
}
QListWidget::item:hover {
    background-color: #17171f;
}

/* ── Input field ── */
QLineEdit {
    background-color: #13131a;
    border: 1px solid #1c1c28;
    border-radius: 9px;
    padding: 9px 12px;
    color: #e0e0f0;
    selection-background-color: #ff7220;
}
QLineEdit:focus {
    border-color: #ff7220;
}

/* ── Buttons (generic) ── */
QPushButton {
    background-color: #18181f;
    border: 1px solid #222230;
    border-radius: 9px;
    padding: 8px 16px;
    color: #7070a0;
    font-size: 13px;
}
QPushButton:hover {
    background-color: #1e1e2c;
    color: #b0b0d0;
    border-color: #2c2c44;
}
QPushButton:pressed {
    background-color: #141420;
}

/* ── Add button (orange accent) ── */
QPushButton#btn_add {
    background-color: #271500;
    border-color: #4a2800;
    color: #ff7220;
    font-weight: 700;
    font-size: 18px;
    padding: 0px;
}
QPushButton#btn_add:hover {
    background-color: #331a00;
    border-color: #6a3800;
}

/* ── Remove button ── */
QPushButton#btn_remove {
    background-color: transparent;
    border: none;
    color: #2a2a3a;
    font-size: 15px;
    padding: 2px 6px;
    border-radius: 4px;
}
QPushButton#btn_remove:hover {
    color: #e05555;
    background-color: #1c0f0f;
}

/* ── Tabs ── */
QTabWidget::pane {
    border: none;
    background: transparent;
}
QTabBar::tab {
    background: transparent;
    border: none;
    padding: 8px 20px;
    color: #33334a;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 2px;
}
QTabBar::tab:selected {
    color: #ff7220;
    border-bottom: 2px solid #ff7220;
}
QTabBar::tab:hover {
    color: #888898;
}

/* ── Separator ── */
QFrame[frameShape="4"],
QFrame[frameShape="5"] {
    color: #18181f;
    max-height: 1px;
}

/* ── Scrollbar ── */
QScrollBar:vertical {
    background: transparent;
    width: 5px;
    margin: 0;
}
QScrollBar::handle:vertical {
    background: #222230;
    border-radius: 2px;
    min-height: 20px;
}
QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical { height: 0; }

/* ── Dialog ── */
QDialog {
    background-color: #0f0f13;
}

/* ── Error detail ── */
QLabel#lbl_error {
    color: #e05555;
    font-size: 11px;
    padding: 6px 10px;
    background: #1c0a0a;
    border-radius: 7px;
    border: 1px solid #3a1515;
}

/* ── Servers dialog list ── */
QListWidget#list_servers::item {
    padding: 10px 12px;
    border-radius: 8px;
    color: #a0a0c0;
    border-bottom: 1px solid #18181f;
}
QListWidget#list_servers::item:selected {
    background-color: #271500;
    color: #ff7220;
    border-bottom-color: transparent;
}
"""
