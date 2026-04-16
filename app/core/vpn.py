"""
Top-level VPN controller.

Two modes:
  - Proxy mode: Xray + system HTTP proxy (domains only)
  - TUN mode:   sing-box with native TUN (domains + process names)
"""

import atexit
import ctypes
import sys
import threading
from .link_parser     import parse_link, needs_singbox
from .config          import build_config
from .singbox_config  import build_singbox_config
from .xray            import XrayManager
from .singbox         import SingBoxManager
from .proxy           import set_proxy, clear_proxy


def _is_admin() -> bool:
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False


class VpnController:
    def __init__(self, settings, on_state_change=None, on_log=None):
        self.settings        = settings
        self.on_state_change = on_state_change or (lambda s, d: None)
        self.on_log          = on_log          or (lambda l: None)

        self._state        = "disconnected"
        self._tun_active   = False
        self._using_singbox = False

        self._xray    = XrayManager(on_status=self._on_engine_status, on_log=self._fwd_log)
        self._singbox = SingBoxManager(on_status=self._on_engine_status, on_log=self._fwd_log)

        atexit.register(self._emergency_cleanup)

    # ------------------------------------------------------------------
    @property
    def state(self) -> str:
        return self._state

    def connect(self):
        threading.Thread(target=self._connect, daemon=True).start()

    def disconnect(self):
        threading.Thread(target=self._disconnect, daemon=True).start()

    # ------------------------------------------------------------------
    def _connect(self):
        self._set_state("connecting")

        server_link = self.settings.active_server
        if not server_link:
            self._set_state("error", "Нет сервера. Добавьте ссылку.")
            return

        server = parse_link(server_link)
        if not server:
            self._set_state("error", "Неверная ссылка на сервер.")
            return

        tun_mode = self.settings.tun_mode
        use_singbox = tun_mode or needs_singbox(server)

        if tun_mode and not _is_admin():
            self._set_state("error", "TUN-режим требует прав администратора.\nЗапустите приложение от имени админа.")
            return

        if use_singbox:
            # ── sing-box (TUN or sing-box-only protocols) ─────
            config = build_singbox_config(
                server,
                self.settings.domains,
                self.settings.processes,
                tun_mode=tun_mode,
            )
            ok = self._singbox.start(config)
            if not ok:
                self._set_state("error", "Не удалось запустить sing-box.")
                return

            # If not TUN but sing-box-only protocol → set system proxy
            if not tun_mode:
                if not set_proxy():
                    self._singbox.stop()
                    self._set_state("error", "Не удалось установить системный прокси.")
                    return

            self._tun_active = tun_mode
            self._using_singbox = True
        else:
            # ── Xray (proxy mode, Xray-compatible protocols) ──
            config = build_config(
                server,
                self.settings.domains,
                self.settings.processes,
            )
            ok = self._xray.start(config)
            if not ok:
                self._set_state("error", "Не удалось запустить Xray.")
                return

            if not set_proxy():
                self._xray.stop()
                self._set_state("error", "Не удалось установить системный прокси.")
                return
            self._tun_active = False
            self._using_singbox = False

        self._set_state("connected")

    def _disconnect(self):
        self._set_state("disconnecting")
        if not self._tun_active:
            clear_proxy()
        if self._using_singbox:
            self._singbox.stop()
        else:
            self._xray.stop()
        self._tun_active = False
        self._using_singbox = False
        self._set_state("disconnected")

    # ------------------------------------------------------------------
    def _set_state(self, state: str, detail: str = ""):
        self._state = state
        self.on_state_change(state, detail)

    def _on_engine_status(self, status: str):
        if status == "crashed" and self._state == "connected":
            if not self._tun_active:
                clear_proxy()
            if self._using_singbox:
                self._singbox.stop()
            else:
                self._xray.stop()
            self._tun_active = False
            self._using_singbox = False
            self._set_state("error", "VPN-движок неожиданно завершился.")

    def _fwd_log(self, line: str):
        self.on_log(line)

    def _emergency_cleanup(self):
        try:
            clear_proxy()
        except Exception:
            pass
        try:
            self._singbox.stop()
        except Exception:
            pass
        try:
            self._xray.stop()
        except Exception:
            pass
