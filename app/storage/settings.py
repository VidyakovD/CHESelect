"""
Persistent settings — saved as JSON in %APPDATA%/SelectVPN/settings.json
"""

import json
import os
from pathlib import Path


def _settings_path() -> Path:
    base = Path(os.environ.get("APPDATA", Path.home())) / "SelectVPN"
    base.mkdir(parents=True, exist_ok=True)
    return base / "settings.json"


_DEFAULTS = {
    "servers":   [],   # list of VLESS link strings
    "active_server_index": 0,
    "domains":   [],   # list of domain strings
    "processes": [],   # list of process name strings
    "tun_mode":  False, # True = TUN adapter, False = HTTP system proxy
    "connected": False,
}


class Settings:
    def __init__(self):
        self._path = _settings_path()
        self._data = dict(_DEFAULTS)
        self._load()

    def _load(self):
        if self._path.exists():
            try:
                stored = json.loads(self._path.read_text(encoding="utf-8"))
                self._data.update(stored)
            except Exception:
                pass

    def save(self):
        self._path.write_text(
            json.dumps(self._data, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )

    # --- Servers ---------------------------------------------------

    @property
    def servers(self) -> list[str]:
        return self._data["servers"]

    def add_server(self, vless_link: str):
        if vless_link not in self._data["servers"]:
            self._data["servers"].append(vless_link)
            self.save()

    def remove_server(self, index: int):
        if 0 <= index < len(self._data["servers"]):
            self._data["servers"].pop(index)
            if self._data["active_server_index"] >= len(self._data["servers"]):
                self._data["active_server_index"] = max(0, len(self._data["servers"]) - 1)
            self.save()

    @property
    def active_server_index(self) -> int:
        return self._data["active_server_index"]

    @active_server_index.setter
    def active_server_index(self, value: int):
        self._data["active_server_index"] = value
        self.save()

    @property
    def active_server(self) -> str | None:
        servers = self._data["servers"]
        idx = self._data["active_server_index"]
        if servers and 0 <= idx < len(servers):
            return servers[idx]
        return None

    # --- Domains ---------------------------------------------------

    @property
    def domains(self) -> list[str]:
        return self._data["domains"]

    def add_domain(self, domain: str) -> bool:
        domain = domain.strip().lower()
        if domain and domain not in self._data["domains"]:
            self._data["domains"].append(domain)
            self.save()
            return True
        return False

    def remove_domain(self, domain: str):
        if domain in self._data["domains"]:
            self._data["domains"].remove(domain)
            self.save()

    # --- Processes -------------------------------------------------

    @property
    def processes(self) -> list[str]:
        return self._data["processes"]

    def add_process(self, name: str) -> bool:
        name = name.strip()
        if name and name not in self._data["processes"]:
            self._data["processes"].append(name)
            self.save()
            return True
        return False

    def remove_process(self, name: str):
        if name in self._data["processes"]:
            self._data["processes"].remove(name)
            self.save()

    # --- TUN mode -----------------------------------------------------

    @property
    def tun_mode(self) -> bool:
        return self._data.get("tun_mode", False)

    @tun_mode.setter
    def tun_mode(self, value: bool):
        self._data["tun_mode"] = value
        self.save()
