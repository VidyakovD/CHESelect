"""
sing-box config generator.

Supports all protocols: VLESS, VMess, Shadowsocks, Trojan,
Hysteria2, TUIC, WireGuard.

Two modes:
  - TUN mode: full config with TUN inbound + routing
  - Local proxy mode: SOCKS/HTTP inbound for protocols Xray can't handle
"""

import json


def build_singbox_config(server: dict, domains: list[str], processes: list[str],
                         tun_mode: bool = True, exclusions: list[str] = None) -> dict:
    """
    Build a sing-box JSON config.

    tun_mode=True:  TUN inbound (full system capture, process routing)
    tun_mode=False: SOCKS+HTTP inbound (local proxy for sing-box-only protocols)
    """

    outbound = _build_outbound(server)
    outbound["tag"] = "proxy"

    outbounds = [outbound, {"tag": "direct", "type": "direct"}]

    # --- Route rules ------------------------------------------------------
    rules = [{"protocol": "dns", "action": "hijack-dns"}]

    # HIGHEST PRIORITY: exclusions bypass VPN entirely
    if exclusions:
        ex_domains = [e for e in exclusions if not _is_ip_like(e)]
        ex_ips     = [e for e in exclusions if _is_ip_like(e)]
        if ex_domains:
            rules.append({"domain_suffix": ex_domains, "outbound": "direct"})
        if ex_ips:
            rules.append({"ip_cidr": [_to_cidr(ip) for ip in ex_ips], "outbound": "direct"})

    if tun_mode and processes:
        names = set()
        for p in processes:
            names.add(p)
            names.add(p.lower())
            base = p.rsplit(".", 1)
            if len(base) == 2:
                names.add(base[0].capitalize() + "." + base[1])
        rules.append({"process_name": sorted(names), "outbound": "proxy"})

    if domains:
        rules.append({"domain_suffix": _to_singbox_domains(domains), "outbound": "proxy"})

    rules.append({"ip_is_private": True, "outbound": "direct"})

    # --- Inbounds ---------------------------------------------------------
    if tun_mode:
        inbounds = [{
            "tag": "tun-in", "type": "tun",
            "address": ["172.19.0.1/30"],
            "auto_route": True,
            # strict_route=False: no WFP firewall rules.
            # If sing-box crashes, OS stays clean (no "Block all DNS" leftover).
            "strict_route": False,
            "stack": "system",
            "mtu": 1500,        # standard MTU (9000 caused fragmentation issues)
            "sniff": True,
            "sniff_override_destination": True,
            "sniff_timeout": "100ms",
        }]
    else:
        inbounds = [
            {
                "tag": "socks-in", "type": "socks",
                "listen": "127.0.0.1", "listen_port": 10808,
                "sniff": True, "sniff_override_destination": True,
            },
            {
                "tag": "http-in", "type": "http",
                "listen": "127.0.0.1", "listen_port": 10809,
                "sniff": True, "sniff_override_destination": True,
            },
        ]

    # --- DNS --------------------------------------------------------------
    dns = {
        "servers": [
            {"tag": "dns-proxy",  "address": "8.8.8.8", "detour": "proxy"},
            {"tag": "dns-direct", "address": "1.1.1.1", "detour": "direct"},
        ],
        "rules": [
            *(
                [{"domain_suffix": _to_singbox_domains(domains), "server": "dns-proxy"}]
                if domains else []
            ),
        ],
        "final": "dns-direct",
        "strategy": "prefer_ipv4",
        "disable_cache": False,
        "disable_expire": False,
        "independent_cache": True,
    }

    return {
        # Warn level = less overhead, only meaningful messages
        "log": {"level": "warn", "timestamp": True},
        "dns": dns,
        "inbounds": inbounds,
        "outbounds": outbounds,
        "route": {
            "rules": rules,
            "final": "direct",
            "auto_detect_interface": True,
        },
        "experimental": {
            "cache_file": {
                "enabled": True,
                "store_fakeip": False,
            },
        },
    }


# ══════════════════════════════════════════════════════════════════
# Outbound builders — one per protocol
# ══════════════════════════════════════════════════════════════════

def _build_outbound(server: dict) -> dict:
    proto = server.get("protocol", "vless")
    builders = {
        "vless":       _out_vless,
        "vmess":       _out_vmess,
        "shadowsocks": _out_shadowsocks,
        "trojan":      _out_trojan,
        "hysteria2":   _out_hysteria2,
        "tuic":        _out_tuic,
        "wireguard":   _out_wireguard,
    }
    builder = builders.get(proto, _out_vless)
    return builder(server)


def _out_vless(s: dict) -> dict:
    # NOTE: multiplex removed — most Reality servers don't support it and
    # drop connections. Server compatibility > slight speed gain.
    out = {
        "type": "vless",
        "server": s["host"], "server_port": s["port"],
        "uuid": s.get("uuid", ""),
        "tls": _tls(s),
        "tcp_fast_open": True,
    }
    t = _transport(s)
    if t:
        out["transport"] = t
    return out


def _out_vmess(s: dict) -> dict:
    out = {
        "type": "vmess",
        "server": s["host"], "server_port": s["port"],
        "uuid": s.get("uuid", ""),
        "alter_id": s.get("alter_id", 0),
        "security": s.get("security", "auto"),
        "tcp_fast_open": True,
    }
    if s.get("tls") == "tls":
        out["tls"] = {
            "enabled": True,
            "server_name": s.get("sni", s["host"]),
            "utls": {"enabled": True, "fingerprint": s.get("fp", "chrome")},
        }
    t = _transport(s)
    if t:
        out["transport"] = t
    return out


def _out_shadowsocks(s: dict) -> dict:
    return {
        "type": "shadowsocks",
        "server": s["host"], "server_port": s["port"],
        "method": s.get("method", "aes-256-gcm"),
        "password": s.get("password", ""),
    }


def _out_trojan(s: dict) -> dict:
    out = {
        "type": "trojan",
        "server": s["host"], "server_port": s["port"],
        "password": s.get("password", ""),
        "tls": _tls(s),
        "tcp_fast_open": True,
    }
    t = _transport(s)
    if t:
        out["transport"] = t
    return out


def _out_hysteria2(s: dict) -> dict:
    out = {
        "type": "hysteria2",
        "server": s["host"], "server_port": s["port"],
        "password": s.get("password", ""),
        "tls": {
            "enabled": True,
            "server_name": s.get("sni", s["host"]),
            "insecure": s.get("insecure", False),
        },
    }
    if s.get("obfs"):
        out["obfs"] = {
            "type": s["obfs"],
            "password": s.get("obfs_password", ""),
        }
    return out


def _out_tuic(s: dict) -> dict:
    return {
        "type": "tuic",
        "server": s["host"], "server_port": s["port"],
        "uuid": s.get("uuid", ""),
        "password": s.get("password", ""),
        "congestion_control": s.get("congestion", "bbr"),
        "udp_relay_mode": s.get("udp_relay_mode", "native"),
        "tls": {
            "enabled": True,
            "server_name": s.get("sni", s["host"]),
            "alpn": s.get("alpn", ["h3"]),
            "insecure": s.get("insecure", False),
        },
    }


def _out_wireguard(s: dict) -> dict:
    """sing-box 1.12+ uses WireGuard as an endpoint, not outbound."""
    peers = [{
        "server": s["host"], "server_port": s["port"],
        "public_key": s.get("public_key", ""),
    }]
    if s.get("reserved"):
        peers[0]["reserved"] = s["reserved"]

    return {
        "type": "wireguard",
        "private_key": s.get("private_key", ""),
        "peers": peers,
        "local_address": s.get("address", ["10.0.0.2/32"]),
        "mtu": s.get("mtu", 1280),
    }


# ══════════════════════════════════════════════════════════════════
# Shared helpers
# ══════════════════════════════════════════════════════════════════

def _is_ip_like(s: str) -> bool:
    """Check if string looks like an IP (not a domain)."""
    parts = s.split(".")
    if len(parts) != 4:
        return False
    try:
        return all(0 <= int(p.split("/")[0]) <= 255 for p in parts)
    except Exception:
        return False


def _to_cidr(ip: str) -> str:
    """Convert '1.2.3.4' → '1.2.3.4/32', keep existing CIDR as-is."""
    return ip if "/" in ip else f"{ip}/32"


def _mux() -> dict:
    """Multiplex config — one connection for many streams = faster."""
    return {
        "enabled": True,
        "protocol": "smux",
        "max_streams": 16,
        "padding": True,
    }


def _tls(server: dict) -> dict:
    security = server.get("security", "none")
    if security == "reality":
        return {
            "enabled": True,
            "server_name": server.get("sni", ""),
            "utls": {"enabled": True, "fingerprint": server.get("fp", "chrome")},
            "reality": {
                "enabled": True,
                "public_key": server.get("pbk", ""),
                "short_id": server.get("sid", ""),
            },
        }
    elif security == "tls":
        return {
            "enabled": True,
            "server_name": server.get("sni", server.get("host", "")),
            "utls": {"enabled": True, "fingerprint": server.get("fp", "chrome")},
        }
    return {"enabled": False}


def _transport(server: dict) -> dict | None:
    t = server.get("type", "tcp")
    if t == "ws":
        out = {"type": "ws", "path": server.get("path", "/")}
        if server.get("host_header"):
            out["headers"] = {"Host": server["host_header"]}
        return out
    elif t == "grpc":
        return {"type": "grpc", "service_name": server.get("path", "")}
    elif t in ("xhttp", "splithttp"):
        return {
            "type": "httpupgrade",
            "path": server.get("path", "/"),
            "host": server.get("host_header", server.get("sni", "")),
        }
    return None


def _to_singbox_domains(domains: list[str]) -> list[str]:
    result = []
    for d in domains:
        d = d.strip().lower().lstrip(".")
        if d.startswith("*."): d = d[2:]
        if d.startswith("www."): d = d[4:]
        parts = d.split(".")
        if len(parts) >= 2:
            root = ".".join(parts[-2:])
            if root not in result:
                result.append(root)
        elif d and d not in result:
            result.append(d)
    return result
