"""VLESS link parser."""

from urllib.parse import urlparse, parse_qs, unquote
import re


def parse_vless(link: str) -> dict:
    """
    Parse a vless:// link into a structured dict.
    Returns None if the link is invalid.
    """
    link = link.strip()
    if not link.startswith("vless://"):
        return None

    try:
        # Extract alias (fragment) before URL parsing
        alias = ""
        if "#" in link:
            link, fragment = link.rsplit("#", 1)
            alias = unquote(fragment)

        parsed = urlparse(link)
        if not parsed.hostname or not parsed.username:
            return None

        params = parse_qs(parsed.query)

        def param(key, default=""):
            return params.get(key, [default])[0]

        return {
            "uuid":     parsed.username,
            "host":     parsed.hostname,
            "port":     parsed.port or 443,
            "alias":    alias or parsed.hostname,
            # transport
            "type":     param("type", "tcp"),
            "path":     param("path", "/"),
            "host_header": param("host", ""),
            "mode":     param("mode", "auto"),
            # security
            "security": param("security", "none"),
            "sni":      param("sni", ""),
            "fp":       param("fp", "chrome"),
            "pbk":      param("pbk", ""),
            "sid":      param("sid", ""),
            "spx":      param("spx", "/"),
            "pqv":      param("pqv", ""),
            # encryption
            "encryption": param("encryption", "none"),
        }
    except Exception:
        return None
