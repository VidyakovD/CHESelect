"""
Top-level VPN controller.

Two modes:
  - Proxy mode: Xray + system HTTP proxy (domains only)
  - TUN mode:   sing-box with native TUN (domains + process names)
"""

import atexit
import ctypes
import subprocess
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


def _detect_conflicting_vpn() -> str:
    """
    Return name of a conflicting VPN adapter (AmneziaVPN, OpenVPN, WireGuard, etc.)
    that owns the default route. Empty string if none.
    """
    try:
        r = subprocess.run(
            'powershell -NoProfile -Command "'
            "(Get-NetRoute -DestinationPrefix '0.0.0.0/0' "
            "-ErrorAction SilentlyContinue | "
            "Where-Object { $_.InterfaceAlias -notlike 'Ethernet*' "
            "-and $_.InterfaceAlias -notlike 'Wi-Fi*' "
            "-and $_.InterfaceAlias -notlike 'SelectVPN*' "
            "-and $_.InterfaceAlias -notlike 'Local Area Connection*' } "
            "| Select-Object -First 1).InterfaceAlias"
            '"',
            shell=True, capture_output=True, text=True,
            encoding="cp866", errors="replace", timeout=5,
            creationflags=0x08000000,
        )
        name = r.stdout.strip()
        return name if name else ""
    except Exception:
        return ""


class VpnController:
    def __init__(self, settings, on_state_change=None, on_log=None):
        self.settings        = settings
        self.on_state_change = on_state_change or (lambda s, d: None)
        self.on_log          = on_log          or (lambda l: None)

        self._state        = "disconnected"
        self._tun_active   = False
        self._using_singbox = False
        self._retry_count  = 0      # for auto-reconnect backoff
        self._user_disconnected = False  # True if user clicked disconnect
        self._heartbeat_stop = threading.Event()
        self._heartbeat_thread = None

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
        self._user_disconnected = True   # prevent auto-reconnect
        threading.Thread(target=self._disconnect, daemon=True).start()

    def reconnect(self):
        """Safe reconnect: full stop → wait → start, all in one thread."""
        threading.Thread(target=self._reconnect, daemon=True).start()

    # ------------------------------------------------------------------
    def _connect(self):
        self._user_disconnected = False   # reset on any explicit connect
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

        # Check for conflicting VPN (AmneziaVPN, OpenVPN, WireGuard, etc.)
        if tun_mode:
            conflict = _detect_conflicting_vpn()
            if conflict:
                self._set_state("error", f"Обнаружен другой активный VPN: {conflict}.\nВыключите его перед включением TUN-режима.")
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

        self._retry_count = 0   # success → reset backoff
        self._start_heartbeat()
        self._set_state("connected")

    def _disconnect(self):
        self._set_state("disconnecting")
        self._stop_all()
        self._set_state("disconnected")

    def _reconnect(self):
        """Full stop → wait for TUN release → start."""
        self._set_state("disconnecting")
        self._stop_all()
        import time
        time.sleep(2)  # give OS time to release TUN adapter
        self._connect()

    def _stop_all(self):
        """Synchronously stop everything."""
        self._stop_heartbeat()
        if not self._tun_active:
            clear_proxy()
        if self._using_singbox:
            self._singbox.stop()
        if self._xray.is_running():
            self._xray.stop()
        self._tun_active = False
        self._using_singbox = False

    # ── Heartbeat — detect silent engine death ──────────────────
    def _start_heartbeat(self):
        self._stop_heartbeat()
        self._heartbeat_stop = threading.Event()
        self._heartbeat_thread = threading.Thread(
            target=self._heartbeat_loop, daemon=True
        )
        self._heartbeat_thread.start()

    def _stop_heartbeat(self):
        if self._heartbeat_stop:
            self._heartbeat_stop.set()
        self._heartbeat_thread = None

    def _heartbeat_loop(self):
        while not self._heartbeat_stop.wait(5):
            if self._state != "connected":
                return
            engine = self._singbox if self._using_singbox else self._xray
            if not engine.is_running():
                # Engine died silently — trigger the same path as crash
                self._on_engine_status("crashed")
                return

    # ------------------------------------------------------------------
    def _set_state(self, state: str, detail: str = ""):
        self._state = state
        self.on_state_change(state, detail)

    def _on_engine_status(self, status: str):
        if status == "crashed" and self._state == "connected":
            self._stop_all()

            # Auto-reconnect unless user explicitly disconnected
            if self._user_disconnected:
                self._set_state("disconnected")
                return

            self._retry_count += 1
            if self._retry_count > 5:
                self._set_state("error", "VPN неожиданно завершился.\nПревышено число попыток переподключения.")
                return

            # Exponential backoff: 2, 4, 8, 16, 32 seconds
            delay = 2 ** self._retry_count
            self._set_state("connecting", f"Переподключение через {delay}с...")
            import time
            time.sleep(delay)
            if not self._user_disconnected:
                self._connect()

    def _fwd_log(self, line: str):
        self.on_log(line)

    def _emergency_cleanup(self):
        try:
            clear_proxy()
        except Exception:
            pass
        try:
            if self._singbox.is_running():
                self._singbox.stop()
        except Exception:
            pass
        try:
            if self._xray.is_running():
                self._xray.stop()
        except Exception:
            pass
