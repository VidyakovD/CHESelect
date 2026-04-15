"""
Top-level VPN controller.
Coordinates: Settings → Config → Xray → System Proxy / TUN
"""

import atexit
import ctypes
import os
import sys
import threading
from .vless  import parse_vless
from .config import build_config
from .xray   import XrayManager
from .proxy  import set_proxy, clear_proxy
from .tun    import TunManager


def _is_admin() -> bool:
    """Check if the current process has administrator privileges."""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False


def _restart_as_admin():
    """Re-launch the current process elevated (UAC prompt)."""
    try:
        exe = sys.executable
        # For frozen PyInstaller apps, sys.executable is the .exe itself
        params = " ".join(f'"{a}"' for a in sys.argv[1:])
        ctypes.windll.shell32.ShellExecuteW(
            None, "runas", exe, params, None, 1
        )
    except Exception:
        pass


class VpnController:
    def __init__(self, settings, on_state_change=None, on_log=None):
        self.settings        = settings
        self.on_state_change = on_state_change or (lambda s, d: None)
        self.on_log          = on_log          or (lambda l: None)

        self._state    = "disconnected"
        self._tun_active = False   # tracks which mode is active for disconnect

        self._xray = XrayManager(on_status=self._on_xray_status, on_log=self._fwd_log)
        self._tun  = TunManager(on_status=self._on_tun_status, on_log=self._fwd_log)

        # Safety: always clean up on exit
        atexit.register(self._emergency_cleanup)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def state(self) -> str:
        return self._state

    def connect(self):
        threading.Thread(target=self._connect, daemon=True).start()

    def disconnect(self):
        threading.Thread(target=self._disconnect, daemon=True).start()

    # ------------------------------------------------------------------
    # Internal — connect
    # ------------------------------------------------------------------

    def _connect(self):
        self._set_state("connecting")

        server_link = self.settings.active_server
        if not server_link:
            self._set_state("error", "Нет сервера. Добавьте VLESS ссылку.")
            return

        server = parse_vless(server_link)
        if not server:
            self._set_state("error", "Неверная VLESS ссылка.")
            return

        tun_mode = self.settings.tun_mode

        # TUN mode requires admin rights
        if tun_mode and not _is_admin():
            self._set_state("error", "TUN-режим требует прав администратора.\nПерезапустите приложение от имени админа.")
            return

        config = build_config(
            server,
            self.settings.domains,
            self.settings.processes,
            tun_mode=tun_mode,
        )

        # 1. Start Xray
        ok = self._xray.start(config)
        if not ok:
            self._set_state("error", "Не удалось запустить Xray.")
            return

        if tun_mode:
            # 2a. TUN mode: start tun2socks → SOCKS5 → Xray
            ok, err = self._tun.start()
            if not ok:
                self._xray.stop()
                self._set_state("error", f"Не удалось запустить TUN: {err}")
                return
            self._tun_active = True
        else:
            # 2b. Proxy mode: set system proxy → Xray HTTP inbound
            if not set_proxy():
                self._xray.stop()
                self._set_state("error", "Не удалось установить системный прокси.")
                return
            self._tun_active = False

        self._set_state("connected")

    # ------------------------------------------------------------------
    # Internal — disconnect
    # ------------------------------------------------------------------

    def _disconnect(self):
        self._set_state("disconnecting")
        if self._tun_active:
            self._tun.stop()
        else:
            clear_proxy()
        self._xray.stop()
        self._tun_active = False
        self._set_state("disconnected")

    # ------------------------------------------------------------------

    def _set_state(self, state: str, detail: str = ""):
        self._state = state
        self.on_state_change(state, detail)

    def _on_xray_status(self, status: str):
        if status == "crashed" and self._state == "connected":
            if self._tun_active:
                self._tun.stop()
            else:
                clear_proxy()
            self._tun_active = False
            self._set_state("error", "Xray неожиданно завершился.")

    def _on_tun_status(self, status: str):
        if status == "tun_down" and self._state == "connected":
            self._xray.stop()
            self._tun_active = False
            self._set_state("error", "TUN-адаптер отключился.")

    def _fwd_log(self, line: str):
        self.on_log(line)

    def _emergency_cleanup(self):
        """Called by atexit — clean up no matter what."""
        try:
            clear_proxy()
        except Exception:
            pass
        try:
            self._tun.stop()
        except Exception:
            pass
        try:
            self._xray.stop()
        except Exception:
            pass
