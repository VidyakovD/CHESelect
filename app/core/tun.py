"""
TUN interface manager for Windows.

Uses tun2socks to create a virtual TUN adapter (via wintun.dll)
and route all its traffic to Xray's local SOCKS5 port.

Flow:
  System → TUN adapter → tun2socks → SOCKS5 127.0.0.1:10808 → Xray
"""

import subprocess
import threading
import time
from pathlib import Path

from ._paths import BIN_DIR

TUN2SOCKS_EXE = BIN_DIR / "tun2socks.exe"

TUN_NAME    = "SelectVPN"
TUN_ADDR    = "10.89.0.2"
TUN_GW      = "10.89.0.1"
TUN_MASK    = "255.255.255.0"
SOCKS5_ADDR = "127.0.0.1:10808"


class TunManager:
    def __init__(self, on_status=None, on_log=None):
        self._proc        = None
        self._thread      = None
        self._last_error  = ""
        self.on_status    = on_status or (lambda s: None)
        self.on_log       = on_log    or (lambda l: None)

    # ------------------------------------------------------------------

    def start(self) -> tuple[bool, str]:
        """Returns (success, error_message)."""

        if not TUN2SOCKS_EXE.exists():
            msg = f"Файл не найден: {TUN2SOCKS_EXE}"
            self.on_log(f"[tun] {msg}")
            return False, msg

        # wintun.dll must be in the same directory as tun2socks.exe
        wintun = BIN_DIR / "wintun.dll"
        if not wintun.exists():
            msg = f"Файл не найден: {wintun}"
            self.on_log(f"[tun] {msg}")
            return False, msg

        self._last_error = ""

        try:
            self._proc = subprocess.Popen(
                [
                    str(TUN2SOCKS_EXE),
                    "-device",   f"wintun://{TUN_NAME}",
                    "-proxy",    f"socks5://{SOCKS5_ADDR}",
                    "-loglevel", "info",
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                cwd=str(BIN_DIR),           # wintun.dll must be findable here
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
        except Exception as e:
            msg = f"Не удалось запустить tun2socks: {e}"
            self.on_log(f"[tun] {msg}")
            return False, msg

        # Start reader thread to collect output
        self._thread = threading.Thread(target=self._reader, daemon=True)
        self._thread.start()

        # Wait for the adapter to come up (or fail)
        time.sleep(2.0)

        if not self._proc or self._proc.poll() is not None:
            code = self._proc.returncode if self._proc else -1
            err  = self._last_error or f"tun2socks завершился (код {code})"
            self.on_log(f"[tun] failed: {err}")
            return False, err

        ok, msg = self._setup_routes()
        if not ok:
            self.stop()
            return False, msg

        self.on_status("tun_up")
        return True, ""

    def stop(self):
        self._teardown_routes()
        if self._proc:
            try:
                self._proc.terminate()
                self._proc.wait(timeout=5)
            except Exception:
                try:
                    self._proc.kill()
                except Exception:
                    pass
            self._proc = None
        self.on_status("tun_down")

    def is_running(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    # ------------------------------------------------------------------
    # Route management
    # ------------------------------------------------------------------

    def _setup_routes(self) -> tuple[bool, str]:
        cmds = [
            f'netsh interface ip set address name="{TUN_NAME}" static {TUN_ADDR} {TUN_MASK} {TUN_GW}',
            f'route add 0.0.0.0 mask 0.0.0.0 {TUN_GW} metric 5',
        ]
        for cmd in cmds:
            ok, out = self._run_cmd(cmd)
            if not ok:
                return False, f"Ошибка маршрутизации: {out}"
        return True, ""

    def _teardown_routes(self):
        self._run_cmd(f'route delete 0.0.0.0 mask 0.0.0.0 {TUN_GW}')

    def _run_cmd(self, cmd: str) -> tuple[bool, str]:
        try:
            r = subprocess.run(
                cmd, shell=True,
                capture_output=True, text=True,
                encoding="cp866", errors="replace",
                timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            out = (r.stdout + r.stderr).strip()
            if r.returncode != 0:
                self.on_log(f"[tun] cmd failed ({r.returncode}): {cmd}\n  {out}")
                return False, out
            return True, out
        except Exception as e:
            self.on_log(f"[tun] cmd error: {e}")
            return False, str(e)

    def _reader(self):
        try:
            for line in self._proc.stdout:
                line = line.rstrip()
                if line:
                    self.on_log(f"[tun2socks] {line}")
                    # Capture last meaningful error line
                    low = line.lower()
                    if any(w in low for w in ("error", "fatal", "fail", "denied", "access")):
                        self._last_error = line
        except Exception:
            pass
