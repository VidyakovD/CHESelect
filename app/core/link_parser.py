"""
Universal proxy link parser.

Supports: vless://, vmess://, ss://, trojan://, hysteria2://, hy2://, tuic://, wireguard://

Every parser returns a dict with at least:
    protocol, host, port, alias
Plus protocol-specific fields.
Returns None on invalid input.
"""

import base64
import json
from urllib.parse import urlparse, parse_qs, unquote


# ── XRAY-compatible protocols (work in both Xray and sing-box) ────
_XRAY_PROTOCOLS = {"vless", "vmess", "shadowsocks", "trojan"}

# ── sing-box only protocols ───────────────────────────────────────
_SINGBOX_ONLY = {"hysteria2", "tuic", "wireguard"}


def parse_link(link: str) -> dict | None:
    """Parse any supported proxy link. Returns dict or None."""
    link = link.strip()
    if not link:
        return None

    scheme = link.split("://")[0].lower() if "://" in link else ""

    parsers = {
        "vless":     _parse_vless,
        "vmess":     _parse_vmess,
        "ss":        _parse_shadowsocks,
        "trojan":    _parse_trojan,
        "hysteria2": _parse_hysteria2,
        "hy2":       _parse_hysteria2,
        "tuic":      _parse_tuic,
        "wireguard": _parse_wireguard,
        "wg":        _parse_wireguard,
    }

    parser = parsers.get(scheme)
    if not parser:
        return None
    return parser(link)


def needs_singbox(server: dict) -> bool:
    """Check if this protocol requires sing-box (not supported by Xray)."""
    return server.get("protocol") in _SINGBOX_ONLY


# ══════════════════════════════════════════════════════════════════
# VLESS
# ══════════════════════════════════════════════════════════════════

def _parse_vless(link: str) -> dict | None:
    try:
        alias = ""
        if "#" in link:
            link, fragment = link.rsplit("#", 1)
            alias = unquote(fragment)

        parsed = urlparse(link)
        if not parsed.hostname or not parsed.username:
            return None

        params = parse_qs(parsed.query)
        p = lambda k, d="": params.get(k, [d])[0]

        return {
            "protocol": "vless",
            "host":     parsed.hostname,
            "port":     parsed.port or 443,
            "alias":    alias or parsed.hostname,
            "uuid":     parsed.username,
            "type":     p("type", "tcp"),
            "path":     p("path", "/"),
            "host_header": p("host", ""),
            "mode":     p("mode", "auto"),
            "security": p("security", "none"),
            "sni":      p("sni", ""),
            "fp":       p("fp", "chrome"),
            "pbk":      p("pbk", ""),
            "sid":      p("sid", ""),
            "spx":      p("spx", "/"),
            "pqv":      p("pqv", ""),
            "encryption": p("encryption", "none"),
        }
    except Exception:
        return None


# ══════════════════════════════════════════════════════════════════
# VMess
# ══════════════════════════════════════════════════════════════════

def _parse_vmess(link: str) -> dict | None:
    """vmess://base64json"""
    try:
        raw = link.replace("vmess://", "", 1)
        # Fix padding
        raw += "=" * (-len(raw) % 4)
        data = json.loads(base64.b64decode(raw).decode("utf-8"))

        return {
            "protocol":  "vmess",
            "host":      data.get("add", ""),
            "port":      int(data.get("port", 443)),
            "alias":     data.get("ps", data.get("add", "")),
            "uuid":      data.get("id", ""),
            "alter_id":  int(data.get("aid", 0)),
            "security":  data.get("scy", "auto"),
            "type":      data.get("net", "tcp"),
            "path":      data.get("path", "/"),
            "host_header": data.get("host", ""),
            "tls":       data.get("tls", ""),
            "sni":       data.get("sni", ""),
            "fp":        data.get("fp", "chrome"),
        }
    except Exception:
        return None


# ══════════════════════════════════════════════════════════════════
# Shadowsocks
# ══════════════════════════════════════════════════════════════════

def _parse_shadowsocks(link: str) -> dict | None:
    """
    ss://base64(method:password)@host:port#name
    or ss://base64(method:password@host:port)#name
    """
    try:
        alias = ""
        if "#" in link:
            link, fragment = link.rsplit("#", 1)
            alias = unquote(fragment)

        raw = link.replace("ss://", "", 1)

        # Try SIP002 format: base64(method:password)@host:port
        if "@" in raw:
            userinfo, hostport = raw.rsplit("@", 1)
            # Decode userinfo
            userinfo += "=" * (-len(userinfo) % 4)
            try:
                decoded = base64.b64decode(userinfo).decode("utf-8")
                method, password = decoded.split(":", 1)
            except Exception:
                # Maybe it's already plain text
                method, password = userinfo.split(":", 1)

            parsed = urlparse(f"ss://{hostport}")
            host = parsed.hostname or hostport.split(":")[0]
            port = parsed.port or 443
        else:
            # Legacy format: base64(method:password@host:port)
            raw += "=" * (-len(raw) % 4)
            decoded = base64.b64decode(raw).decode("utf-8")
            method_pass, hostport = decoded.rsplit("@", 1)
            method, password = method_pass.split(":", 1)
            host, port_s = hostport.rsplit(":", 1)
            port = int(port_s)

        return {
            "protocol": "shadowsocks",
            "host":     host,
            "port":     port,
            "alias":    alias or host,
            "method":   method,
            "password": password,
        }
    except Exception:
        return None


# ══════════════════════════════════════════════════════════════════
# Trojan
# ══════════════════════════════════════════════════════════════════

def _parse_trojan(link: str) -> dict | None:
    """trojan://password@host:port?sni=...&type=...#name"""
    try:
        alias = ""
        if "#" in link:
            link, fragment = link.rsplit("#", 1)
            alias = unquote(fragment)

        parsed = urlparse(link)
        if not parsed.hostname:
            return None

        params = parse_qs(parsed.query)
        p = lambda k, d="": params.get(k, [d])[0]

        return {
            "protocol":  "trojan",
            "host":      parsed.hostname,
            "port":      parsed.port or 443,
            "alias":     alias or parsed.hostname,
            "password":  unquote(parsed.username or ""),
            "type":      p("type", "tcp"),
            "path":      p("path", "/"),
            "host_header": p("host", ""),
            "security":  p("security", "tls"),
            "sni":       p("sni", parsed.hostname),
            "fp":        p("fp", "chrome"),
        }
    except Exception:
        return None


# ══════════════════════════════════════════════════════════════════
# Hysteria2
# ══════════════════════════════════════════════════════════════════

def _parse_hysteria2(link: str) -> dict | None:
    """hysteria2://password@host:port?sni=...&obfs=...#name"""
    try:
        alias = ""
        if "#" in link:
            link, fragment = link.rsplit("#", 1)
            alias = unquote(fragment)

        # Normalize scheme
        link = link.replace("hy2://", "hysteria2://", 1)
        parsed = urlparse(link)
        if not parsed.hostname:
            return None

        params = parse_qs(parsed.query)
        p = lambda k, d="": params.get(k, [d])[0]

        return {
            "protocol":  "hysteria2",
            "host":      parsed.hostname,
            "port":      parsed.port or 443,
            "alias":     alias or parsed.hostname,
            "password":  unquote(parsed.username or ""),
            "sni":       p("sni", parsed.hostname),
            "obfs":      p("obfs", ""),
            "obfs_password": p("obfs-password", ""),
            "insecure":  p("insecure", "0") == "1",
        }
    except Exception:
        return None


# ══════════════════════════════════════════════════════════════════
# TUIC
# ══════════════════════════════════════════════════════════════════

def _parse_tuic(link: str) -> dict | None:
    """tuic://uuid:password@host:port?sni=...#name"""
    try:
        alias = ""
        if "#" in link:
            link, fragment = link.rsplit("#", 1)
            alias = unquote(fragment)

        parsed = urlparse(link)
        if not parsed.hostname:
            return None

        params = parse_qs(parsed.query)
        p = lambda k, d="": params.get(k, [d])[0]

        uuid = unquote(parsed.username or "")
        password = unquote(parsed.password or "")

        return {
            "protocol":         "tuic",
            "host":             parsed.hostname,
            "port":             parsed.port or 443,
            "alias":            alias or parsed.hostname,
            "uuid":             uuid,
            "password":         password,
            "sni":              p("sni", parsed.hostname),
            "congestion":       p("congestion_control", "bbr"),
            "alpn":             p("alpn", "h3").split(","),
            "udp_relay_mode":   p("udp_relay_mode", "native"),
            "insecure":         p("allow_insecure", "0") == "1",
        }
    except Exception:
        return None


# ══════════════════════════════════════════════════════════════════
# WireGuard
# ══════════════════════════════════════════════════════════════════

def _parse_wireguard(link: str) -> dict | None:
    """wireguard://private_key@host:port?publickey=...&address=...#name"""
    try:
        alias = ""
        if "#" in link:
            link, fragment = link.rsplit("#", 1)
            alias = unquote(fragment)

        link = link.replace("wg://", "wireguard://", 1)
        parsed = urlparse(link)
        if not parsed.hostname:
            return None

        params = parse_qs(parsed.query)
        p = lambda k, d="": params.get(k, [d])[0]

        return {
            "protocol":    "wireguard",
            "host":        parsed.hostname,
            "port":        parsed.port or 51820,
            "alias":       alias or parsed.hostname,
            "private_key": unquote(parsed.username or ""),
            "public_key":  p("publickey", p("peer", "")),
            "address":     p("address", "10.0.0.2/32").split(","),
            "mtu":         int(p("mtu", "1280")),
            "reserved":    [int(x) for x in p("reserved", "").split(",") if x],
        }
    except Exception:
        return None
