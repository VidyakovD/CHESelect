"""
Xray-core config generator.

Routing strategy:
  - Domains in the user list  → outbound "proxy"
  - Apps (process names) in the user list → outbound "proxy"
  - Everything else → outbound "direct"

TUN mode:
  - Xray listens on SOCKS5 127.0.0.1:10808
  - tun2socks feeds TUN traffic into that SOCKS5 port
  - Xray does DNS interception + SNI sniffing for domain routing
"""

import json


SOCKS_PORT = 10808
DNS_PORT   = 10853   # local DNS server (UDP) for fake-ip


def build_config(server: dict, domains: list[str], processes: list[str],
                 tun_mode: bool = False, exclusions: list[str] = None) -> dict:
    """
    Build a full xray-core JSON config.

    server    — parsed VLESS dict (from vless.py)
    domains   — list of domain strings, e.g. ["youtube.com", "*.google.com"]
    processes — list of process names, e.g. ["telegram.exe", "steam.exe"]
    """

    # --- Routing rules -------------------------------------------------
    routing_rules = []

    # HIGHEST PRIORITY: exclusions bypass VPN entirely
    if exclusions:
        ex_domains = [e for e in exclusions if not _is_ip(e)]
        ex_ips     = [e for e in exclusions if _is_ip(e)]
        if ex_domains:
            routing_rules.append({
                "type": "field",
                "domain": [f"domain:{d}" for d in ex_domains],
                "outboundTag": "direct",
            })
        if ex_ips:
            routing_rules.append({
                "type": "field",
                "ip": ex_ips,
                "outboundTag": "direct",
            })

    # Domain-based rules
    if domains:
        xray_domains = _to_xray_domains(domains)
        routing_rules.append({
            "type":        "field",
            "domain":      xray_domains,
            "outboundTag": "proxy"
        })

    # 3. Private/local traffic always goes direct
    routing_rules.append({
        "type":        "field",
        "ip":          ["geoip:private"],
        "outboundTag": "direct"
    })

    # Default: when no rule matches, Xray uses the first outbound ("direct")

    # --- Transport settings -------------------------------------------
    stream = _build_stream(server)

    # --- Full config --------------------------------------------------
    config = {
        "log": {
            "loglevel": "warning"
        },
        "dns": {
            "hosts": {
                "dns.google": "8.8.8.8"
            },
            "servers": [
                {
                    "address":  "https://8.8.8.8/dns-query",
                    "domains":  _to_xray_domains(domains) if domains else [],
                    "expectIPs": []
                },
                "localhost"
            ]
        },
        "inbounds": [
            {
                "tag":      "socks-in",
                "protocol": "socks",
                "listen":   "127.0.0.1",
                "port":     SOCKS_PORT,
                "settings": {
                    "auth": "noauth",
                    "udp":  True
                },
                "sniffing": {
                    "enabled":      True,
                    "destOverride": ["http", "tls", "quic"],
                    "routeOnly":    True
                }
            },
            {
                "tag":      "http-in",
                "protocol": "http",
                "listen":   "127.0.0.1",
                "port":     SOCKS_PORT + 1,
                "settings": {},
                "sniffing": {
                    "enabled":      True,
                    "destOverride": ["http", "tls"],
                    "routeOnly":    True
                }
            }
        ],
        "outbounds": [
            {
                "tag":      "direct",
                "protocol": "freedom",
                "settings": {}
            },
            _build_proxy_outbound(server, stream),
            {
                "tag":      "block",
                "protocol": "blackhole",
                "settings": {}
            }
        ],
        "routing": {
            "domainStrategy": "IPIfNonMatch",
            "domainMatcher":  "hybrid",
            "rules":          routing_rules
        },
        "policy": {
            "system": {
                "statsInboundUplink":   True,
                "statsInboundDownlink": True
            }
        }
    }

    return config


def build_config_json(server: dict, domains: list[str], processes: list[str]) -> str:
    return json.dumps(build_config(server, domains, processes), indent=2, ensure_ascii=False)


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _is_ip(s: str) -> bool:
    parts = s.split(".")
    if len(parts) != 4:
        return False
    try:
        return all(0 <= int(p.split("/")[0]) <= 255 for p in parts)
    except Exception:
        return False


def _to_xray_domains(domains: list[str]) -> list[str]:
    """
    Convert user-facing domain strings to Xray domain rule format.

    "youtube.com"   → "domain:youtube.com"   (matches youtube.com + all subdomains)
    "*.google.com"  → "domain:google.com"    (Xray domain: already covers subdomains)
    "www.site.com"  → "full:www.site.com"    (exact hostname)
    """
    result = []
    for d in domains:
        d = d.strip().lower().lstrip(".")
        if d.startswith("*."):
            # wildcard → parent domain (Xray domain: covers subdomains)
            result.append(f"domain:{d[2:]}")
        elif d.count(".") >= 2 and not d.startswith("domain:"):
            # looks like a full hostname, e.g. www.youtube.com
            # use domain: so subdomains also match
            root = _root_domain(d)
            result.append(f"domain:{root}")
        else:
            result.append(f"domain:{d}")
    return list(dict.fromkeys(result))   # deduplicate, preserve order


def _root_domain(hostname: str) -> str:
    """youtube.com, www.youtube.com → youtube.com"""
    parts = hostname.split(".")
    if len(parts) >= 2:
        return ".".join(parts[-2:])
    return hostname


def _build_stream(server: dict) -> dict:
    """Build streamSettings from parsed VLESS config."""
    transport_type = server["type"]   # xhttp, ws, grpc, tcp, …

    # Network-specific settings
    if transport_type == "xhttp":
        network_settings_key = "xhttpSettings"
        network_settings = {
            "path": server["path"] or "/",
            "mode": server["mode"] or "auto",
        }
        if server.get("host_header"):
            network_settings["host"] = server["host_header"]
    elif transport_type == "ws":
        network_settings_key = "wsSettings"
        network_settings = {
            "path": server["path"] or "/",
            "headers": {"Host": server["host_header"]} if server["host_header"] else {}
        }
    elif transport_type == "grpc":
        network_settings_key = "grpcSettings"
        network_settings = {
            "serviceName": server["path"] or "",
            "multiMode":   False
        }
    else:
        network_settings_key = None
        network_settings = {}

    # Security settings
    security = server["security"]
    if security == "reality":
        security_settings = {
            "serverName":  server["sni"],
            "fingerprint": server["fp"] or "chrome",
            "publicKey":   server["pbk"],
            "shortId":     server["sid"],
            "spiderX":     server["spx"] or "/",
        }
        if server.get("pqv"):
            security_settings["pqv"] = server["pqv"]
        tls_key = "realitySettings"
    elif security == "tls":
        security_settings = {
            "serverName":    server["sni"],
            "fingerprint":   server["fp"] or "chrome",
            "allowInsecure": False
        }
        tls_key = "tlsSettings"
    else:
        security_settings = {}
        tls_key = None

    stream = {
        "network":  transport_type if transport_type != "xhttp" else "xhttp",
        "security": security if security in ("tls", "reality") else "none",
    }
    if network_settings_key:
        stream[network_settings_key] = network_settings
    if tls_key:
        stream[tls_key] = security_settings

    return stream


def _build_proxy_outbound(server: dict, stream: dict) -> dict:
    """Build Xray proxy outbound for the given protocol."""
    proto = server.get("protocol", "vless")

    if proto == "vless":
        return {
            "tag": "proxy", "protocol": "vless",
            "settings": {
                "vnext": [{
                    "address": server["host"], "port": server["port"],
                    "users": [{"id": server.get("uuid", ""),
                               "encryption": server.get("encryption", "none") or "none",
                               "flow": ""}]
                }]
            },
            "streamSettings": stream, "mux": {"enabled": False}
        }

    elif proto == "vmess":
        return {
            "tag": "proxy", "protocol": "vmess",
            "settings": {
                "vnext": [{
                    "address": server["host"], "port": server["port"],
                    "users": [{"id": server.get("uuid", ""),
                               "alterId": server.get("alter_id", 0),
                               "security": server.get("security", "auto")}]
                }]
            },
            "streamSettings": stream, "mux": {"enabled": False}
        }

    elif proto == "shadowsocks":
        return {
            "tag": "proxy", "protocol": "shadowsocks",
            "settings": {
                "servers": [{
                    "address":  server["host"],
                    "port":     server["port"],
                    "method":   server.get("method", "aes-256-gcm"),
                    "password": server.get("password", ""),
                }]
            },
            "streamSettings": stream,
        }

    elif proto == "trojan":
        return {
            "tag": "proxy", "protocol": "trojan",
            "settings": {
                "servers": [{
                    "address":  server["host"],
                    "port":     server["port"],
                    "password": server.get("password", ""),
                }]
            },
            "streamSettings": stream, "mux": {"enabled": False}
        }

    # Fallback — treat as VLESS
    return _build_proxy_outbound({**server, "protocol": "vless"}, stream)
