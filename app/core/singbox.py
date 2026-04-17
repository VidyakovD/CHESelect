"""
sing-box process manager.

Runs sing-box with TUN mode for process-based routing.
sing-box handles TUN natively — no tun2socks needed.
"""

import json
import os
import subprocess
import tempfile
import threading
import time
from pathlib import Path

from ._paths import BIN_DIR

SINGBOX_EXE = BIN_DIR / "sing-box.exe"

# Debug log with rotation
_LOG_DIR = Path(os.environ.get("APPDATA", Path.home())) / "SelectVPN"
_LOG_FILE = _LOG_DIR / "singbox_debug.log"
_LOG_MAX_BYTES = 2 * 1024 * 1024   # 2 MB


def _debug(msg: str):
    try:
        _LOG_DIR.mkdir(parents=True, exist_ok=True)
        # Rotate if too large
        if _LOG_FILE.exists() and _LOG_FILE.stat().st_size > _LOG_MAX_BYTES:
            old = _LOG_DIR / "singbox_debug.log.old"
            if old.exists():
                old.unlink()
            _LOG_FILE.rename(old)
        with open(_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"{msg}\n")
    except Exception:
        pass


class SingBoxManager:
    def __init__(self, on_status=None, on_log=None):
        self._proc = None
        self._thread = None
        self._config_file = None
        self.on_status = on_status or (lambda s: None)
        self.on_log    = on_log    or (lambda l: None)

    def start(self, config: dict) -> bool:
        if self.is_running():
            self.stop()
            time.sleep(1)  # give OS time to release TUN interface

        _debug("--- sing-box start() ---")
        _debug(f"SINGBOX_EXE: {SINGBOX_EXE}")
        _debug(f"SINGBOX_EXE exists: {SINGBOX_EXE.exists()}")

        if not SINGBOX_EXE.exists():
            _debug("ERROR: sing-box.exe not found!")
            self.on_log(f"sing-box.exe не найден: {SINGBOX_EXE}")
            self.on_status("error")
            return False

        # Write config to temp file
        tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        )
        json.dump(config, tmp, indent=2, ensure_ascii=False)
        tmp.close()
        self._config_file = tmp.name
        _debug(f"Config: {self._config_file}")

        try:
            self._proc = subprocess.Popen(
                [str(SINGBOX_EXE), "run", "-c", self._config_file],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                cwd=str(BIN_DIR),
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            _debug(f"Popen OK, PID: {self._proc.pid}")
        except Exception as e:
            _debug(f"Popen EXCEPTION: {e}")
            self.on_log(f"Не удалось запустить sing-box: {e}")
            self.on_status(f"error: {e}")
            return False

        self._thread = threading.Thread(target=self._reader, daemon=True)
        self._thread.start()

        # Wait and verify
        time.sleep(2.0)
        if self._proc.poll() is not None:
            code = self._proc.returncode
            try:
                leftover = self._proc.stdout.read()
            except Exception:
                leftover = ""
            _debug(f"sing-box DIED, exit code: {code}")
            _debug(f"Output: {leftover[:2000]}")
            self.on_log(f"sing-box завершился (код {code}): {leftover[:500]}")
            self.on_status("crashed")
            return False

        _debug("sing-box alive after 2s — OK")
        self.on_status("running")
        return True

    def stop(self):
        if self._proc:
            try:
                self._proc.terminate()
                self._proc.wait(timeout=5)
            except Exception:
                try:
                    self._proc.kill()
                    self._proc.wait(timeout=3)
                except Exception:
                    pass
            self._proc = None
            time.sleep(1)  # let OS release TUN interface

        if self._config_file and os.path.exists(self._config_file):
            try:
                os.unlink(self._config_file)
            except Exception:
                pass
            self._config_file = None

        self.on_status("stopped")

    def is_running(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    def _reader(self):
        try:
            for line in self._proc.stdout:
                line = line.rstrip()
                if line:
                    _debug(f"[sing-box] {line}")
                    self.on_log(line)
        except Exception as e:
            _debug(f"[reader] exception: {e}")

        if self._proc and self._proc.poll() is not None:
            self.on_status("crashed")
