"""
Windows System Proxy manager.

Sets / clears the WinINet system proxy so that all apps that
respect the OS proxy setting (browsers, Telegram, etc.) route
through Xray's local HTTP proxy.

Xray listens on 127.0.0.1:10809 (HTTP) and 127.0.0.1:10808 (SOCKS5).
Its routing rules decide: domain/process in the list → VPN server,
everything else → direct.
"""

import ctypes
import winreg
from ctypes import wintypes


HTTP_PORT  = 10809   # Xray HTTP inbound
SOCKS_PORT = 10808   # Xray SOCKS5 inbound

_REG_PATH = r"Software\Microsoft\Windows\CurrentVersion\Internet Settings"

# WinINet option constants
_INTERNET_OPTION_SETTINGS_CHANGED = 39
_INTERNET_OPTION_REFRESH          = 37


def _notify_wininet():
    """Tell WinINet to reload proxy settings immediately."""
    try:
        wininet = ctypes.windll.Wininet
        wininet.InternetSetOptionW(0, _INTERNET_OPTION_SETTINGS_CHANGED, None, 0)
        wininet.InternetSetOptionW(0, _INTERNET_OPTION_REFRESH,          None, 0)
    except Exception:
        pass


def set_proxy(host: str = "127.0.0.1", port: int = HTTP_PORT):
    """Enable system proxy pointing to Xray's HTTP inbound."""
    proxy_str = f"{host}:{port}"
    # Bypass list: local addresses should never go through proxy
    bypass = "localhost;127.*;10.*;172.16.*;172.17.*;172.18.*;172.19.*;172.20.*;172.21.*;172.22.*;172.23.*;172.24.*;172.25.*;172.26.*;172.27.*;172.28.*;172.29.*;172.30.*;172.31.*;192.168.*;<local>"
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, _REG_PATH,
            0, winreg.KEY_SET_VALUE
        )
        winreg.SetValueEx(key, "ProxyEnable",   0, winreg.REG_DWORD, 1)
        winreg.SetValueEx(key, "ProxyServer",   0, winreg.REG_SZ,    proxy_str)
        winreg.SetValueEx(key, "ProxyOverride", 0, winreg.REG_SZ,    bypass)
        winreg.CloseKey(key)
        _notify_wininet()
        return True
    except Exception as e:
        return False


def clear_proxy():
    """Disable system proxy."""
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, _REG_PATH,
            0, winreg.KEY_SET_VALUE
        )
        winreg.SetValueEx(key, "ProxyEnable", 0, winreg.REG_DWORD, 0)
        winreg.CloseKey(key)
        _notify_wininet()
    except Exception:
        pass
