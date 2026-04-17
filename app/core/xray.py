"""
Xray-core process manager.

Writes a temp config and runs xray.exe as a subprocess.
Emits status via a simple callback: on_status(status: str)
"""

import json
import os
import subprocess
import tempfile
import threading
import time
from pathlib import Path

from ._paths import BIN_DIR

XRAY_EXE = BIN_DIR / "xray.exe"

# Debug log with rotation (2 MB cap)
_LOG_DIR = Path(os.environ.get("APPDATA", Path.home())) / "SelectVPN"
_LOG_FILE = _LOG_DIR / "xray_debug.log"
_LOG_MAX_BYTES = 2 * 1024 * 1024


def _debug(msg: str):
    try:
        _LOG_DIR.mkdir(parents=True, exist_ok=True)
        if _LOG_FILE.exists() and _LOG_FILE.stat().st_size > _LOG_MAX_BYTES:
            old = _LOG_DIR / "xray_debug.log.old"
            if old.exists():
                old.unlink()
            _LOG_FILE.rename(old)
        with open(_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"{msg}\n")
    except Exception:
        pass


class XrayManager:
    def __init__(self, on_status=None, on_log=None):
        self._proc:    subprocess.Popen | None = None
        self._thread:  threading.Thread | None = None
        self._config_file = None
        self.on_status = on_status or (lambda s: None)
        self.on_log    = on_log    or (lambda l: None)

    # ------------------------------------------------------------------

    def start(self, config: dict) -> bool:
        if self.is_running():
            self.stop()

        _debug(f"--- start() called ---")
        _debug(f"BIN_DIR: {BIN_DIR}")
        _debug(f"XRAY_EXE: {XRAY_EXE}")
        _debug(f"XRAY_EXE exists: {XRAY_EXE.exists()}")

        if not XRAY_EXE.exists():
            _debug("ERROR: xray.exe not found!")
            self.on_log(f"xray.exe не найден: {XRAY_EXE}")
            self.on_status("error: xray.exe not found")
            return False

        # Write config to a temp file
        tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        )
        json.dump(config, tmp, indent=2, ensure_ascii=False)
        tmp.close()
        self._config_file = tmp.name
        _debug(f"Config written to: {self._config_file}")

        try:
            env = os.environ.copy()
            env["XRAY_LOCATION_ASSET"] = str(BIN_DIR)

            self._proc = subprocess.Popen(
                [str(XRAY_EXE), "run", "-config", self._config_file],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                cwd=str(BIN_DIR),
                env=env,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            _debug(f"Popen OK, PID: {self._proc.pid}")
        except Exception as e:
            _debug(f"Popen EXCEPTION: {e}")
            self.on_log(f"Не удалось запустить xray: {e}")
            self.on_status(f"error: {e}")
            return False

        self._thread = threading.Thread(target=self._reader, daemon=True)
        self._thread.start()

        # Wait and verify Xray actually started
        time.sleep(1.5)
        if self._proc.poll() is not None:
            code = self._proc.returncode
            # Capture whatever xray printed before dying
            try:
                leftover = self._proc.stdout.read()
            except Exception:
                leftover = ""
            _debug(f"Xray DIED immediately, exit code: {code}")
            _debug(f"Xray output: {leftover[:2000]}")
            self.on_log(f"Xray завершился сразу (код {code}): {leftover[:500]}")
            self.on_status("crashed")
            return False

        _debug("Xray is alive after 1.5s — OK")
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
                except Exception:
                    pass
            self._proc = None

        if self._config_file and os.path.exists(self._config_file):
            try:
                os.unlink(self._config_file)
            except Exception:
                pass
            self._config_file = None

        self.on_status("stopped")

    def is_running(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    # ------------------------------------------------------------------

    def _reader(self):
        """Read xray stdout/stderr and forward to on_log."""
        try:
            for line in self._proc.stdout:
                line = line.rstrip()
                if line:
                    _debug(f"[xray] {line}")
                    self.on_log(line)
        except Exception as e:
            _debug(f"[reader] exception: {e}")

        # Process ended unexpectedly
        if self._proc and self._proc.poll() is not None:
            self.on_status("crashed")
