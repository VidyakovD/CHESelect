"""
sing-box config generator for TUN mode with process-based routing.

sing-box handles TUN natively — no tun2socks needed.
It can see process names and route by them.

Architecture:
  App traffic → TUN adapter (sing-box) → routing rules → proxy or direct
  sing-box auto-detects the default interface to avoid routing loops.
"""

import json


def build_singbox_config(server: dict, domains: list[str], processes: list[str]) -> dict:
    """
    Build a sing-box JSON config for TUN mode with split-tunneling.

    server    — parsed VLESS dict (from vless.py)
    domains   — list of domain strings
    processes — list of process names, e.g. ["telegram.exe"]
    """

    # --- Outbounds --------------------------------------------------------
    outbounds = [
        {
            "tag":  "proxy",
            "type": "vless",
            "server":      server["host"],
            "server_port": server["port"],
            "uuid":        server["uuid"],
            "tls":         _build_tls(server),
            "transport":   _build_transport(server),
        },
        {
            "tag":  "direct",
            "type": "direct",
        },
    ]

    # --- Route rules ------------------------------------------------------
    rules = [
        # DNS hijack → handle by sing-box DNS module
        {"protocol": "dns", "action": "hijack-dns"},
    ]

    # Process-based rules (case-insensitive: add both original and title-case)
    if processes:
        names = set()
        for p in processes:
            names.add(p)
            names.add(p.lower())
            # Title case: telegram.exe → Telegram.exe
            base = p.rsplit(".", 1)
            if len(base) == 2:
                names.add(base[0].capitalize() + "." + base[1])
        rules.append({
            "process_name": sorted(names),
            "outbound": "proxy",
        })

    # Domain-based rules
    if domains:
        sing_domains = _to_singbox_domains(domains)
        rules.append({
            "domain_suffix": sing_domains,
            "outbound": "proxy",
        })

    # Private IPs → direct
    rules.append({
        "ip_is_private": True,
        "outbound": "direct",
    })

    # --- Full config ------------------------------------------------------
    config = {
        "log": {
            "level": "info",
            "timestamp": True,
        },
        "dns": {
            "servers": [
                {"tag": "dns-proxy",  "address": "8.8.8.8", "detour": "proxy"},
                {"tag": "dns-direct", "address": "8.8.8.8", "detour": "direct"},
            ],
            "rules": [
                *(
                    [{"domain_suffix": _to_singbox_domains(domains), "server": "dns-proxy"}]
                    if domains else []
                ),
            ],
            "final": "dns-direct",
        },
        "inbounds": [
            {
                "tag":  "tun-in",
                "type": "tun",
                "address": ["172.19.0.1/30"],
                "auto_route":    True,
                "strict_route":  True,
                "stack":         "system",
                "sniff":         True,
                "sniff_override_destination": True,
            },
        ],
        "outbounds": outbounds,
        "route": {
            "rules":              rules,
            "final":              "direct",
            "auto_detect_interface": True,
        },
    }

    return config


def build_singbox_config_json(server: dict, domains: list[str], processes: list[str]) -> str:
    return json.dumps(build_singbox_config(server, domains, processes), indent=2, ensure_ascii=False)


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _to_singbox_domains(domains: list[str]) -> list[str]:
    """Convert user domains to sing-box domain_suffix format."""
    result = []
    for d in domains:
        d = d.strip().lower().lstrip(".")
        if d.startswith("*."):
            d = d[2:]
        # strip www
        if d.startswith("www."):
            d = d[4:]
        # Extract root domain for subdomains
        parts = d.split(".")
        if len(parts) >= 2:
            root = ".".join(parts[-2:])
            if root not in result:
                result.append(root)
        elif d and d not in result:
            result.append(d)
    return result


def _build_tls(server: dict) -> dict:
    """Build TLS/Reality settings for sing-box."""
    security = server.get("security", "none")

    if security == "reality":
        return {
            "enabled":     True,
            "server_name": server.get("sni", ""),
            "utls": {
                "enabled":     True,
                "fingerprint": server.get("fp", "chrome"),
            },
            "reality": {
                "enabled":    True,
                "public_key": server.get("pbk", ""),
                "short_id":   server.get("sid", ""),
            },
        }
    elif security == "tls":
        return {
            "enabled":     True,
            "server_name": server.get("sni", ""),
            "utls": {
                "enabled":     True,
                "fingerprint": server.get("fp", "chrome"),
            },
        }
    else:
        return {"enabled": False}


def _build_transport(server: dict) -> dict | None:
    """Build transport settings for sing-box."""
    transport_type = server.get("type", "tcp")

    if transport_type == "ws":
        t = {
            "type": "ws",
            "path": server.get("path", "/"),
        }
        if server.get("host_header"):
            t["headers"] = {"Host": server["host_header"]}
        return t
    elif transport_type == "grpc":
        return {
            "type":         "grpc",
            "service_name": server.get("path", ""),
        }
    elif transport_type == "xhttp" or transport_type == "splithttp":
        return {
            "type": "httpupgrade",
            "path": server.get("path", "/"),
            "host": server.get("host_header", server.get("sni", "")),
        }
    elif transport_type == "tcp":
        return None
    else:
        return None
