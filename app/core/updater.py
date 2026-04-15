"""
Auto-updater via GitHub Releases.

Checks the latest release tag against the local version.
If a newer version exists, downloads the installer and runs it.
"""

import json
import os
import sys
import tempfile
import threading
import urllib.request
import urllib.error
from pathlib import Path

# ── Current version ───────────────────────────────────────────────
APP_VERSION = "1.0.0"

# ── GitHub repo (owner/repo) ─────────────────────────────────────
GITHUB_REPO = "VidyakovD/CHESelect"

_API_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
_HEADERS = {"Accept": "application/vnd.github.v3+json", "User-Agent": "SelectVPN-Updater"}


def _parse_version(tag: str) -> tuple:
    """'v1.2.3' or '1.2.3' → (1, 2, 3)"""
    tag = tag.lstrip("vV").strip()
    try:
        return tuple(int(x) for x in tag.split("."))
    except Exception:
        return (0, 0, 0)


def check_for_update(callback):
    """
    Check GitHub for a newer release in a background thread.

    callback(info: dict | None)
        info = {"version": "1.1.0", "url": "https://...", "notes": "..."}
        info = None  if no update or error
    """
    def _work():
        try:
            req = urllib.request.Request(_API_URL, headers=_HEADERS)
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))

            remote_tag = data.get("tag_name", "")
            remote_ver = _parse_version(remote_tag)
            local_ver  = _parse_version(APP_VERSION)

            if remote_ver <= local_ver:
                callback(None)
                return

            # Find the .exe asset (installer)
            download_url = ""
            for asset in data.get("assets", []):
                name = asset.get("name", "").lower()
                if name.endswith(".exe") and "setup" in name:
                    download_url = asset["browser_download_url"]
                    break

            if not download_url:
                # Fallback: link to the release page
                download_url = data.get("html_url", "")

            callback({
                "version": remote_tag.lstrip("vV"),
                "url":     download_url,
                "notes":   data.get("body", "")[:500],
                "is_exe":  download_url.lower().endswith(".exe"),
            })
        except Exception:
            callback(None)

    threading.Thread(target=_work, daemon=True).start()


def download_and_install(url: str, on_progress=None, on_done=None):
    """
    Download the installer .exe and run it.

    on_progress(percent: int)  — 0..100
    on_done(success: bool, error: str)
    """
    def _work():
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "SelectVPN-Updater"})
            resp = urllib.request.urlopen(req, timeout=60)

            total = int(resp.headers.get("Content-Length", 0))
            tmp = tempfile.NamedTemporaryFile(
                suffix="-SelectVPN-Setup.exe", delete=False,
                dir=tempfile.gettempdir()
            )

            downloaded = 0
            while True:
                chunk = resp.read(65536)
                if not chunk:
                    break
                tmp.write(chunk)
                downloaded += len(chunk)
                if on_progress and total:
                    on_progress(int(downloaded * 100 / total))

            tmp.close()
            installer_path = tmp.name

            # Launch installer and exit current app
            os.startfile(installer_path)
            if on_done:
                on_done(True, "")

        except Exception as e:
            if on_done:
                on_done(False, str(e))

    threading.Thread(target=_work, daemon=True).start()
