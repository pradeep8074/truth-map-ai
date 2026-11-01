import ipaddress
import socket
from urllib.parse import urlparse
from backend.config import (
    ALLOWED_SCHEMES,
    BLOCKED_IP_NETWORKS,
    BLOCKED_HOSTNAMES,
)

# Parse IP networks once
PARSED_BLOCKED_NETWORKS = [ipaddress.ip_network(net) for net in BLOCKED_IP_NETWORKS]


def is_ip_blocked(ip_str: str) -> bool:
    """Checks whether an IP address belongs to any blocked/private network range."""
    try:
        ip = ipaddress.ip_address(ip_str)
        return any(ip in net for net in PARSED_BLOCKED_NETWORKS)
    except ValueError:
        return True


def is_safe_url(url: str) -> tuple[bool, str]:
    """
    Validates a URL against SSRF vulnerabilities:
    1. Validates presence and scheme (http/https).
    2. Validates hostname is not in blocked hostnames list.
    3. Resolves DNS and ensures resolved IP is not in loopback, private, or metadata ranges.
    Returns (is_safe, error_reason).
    """
    if not url or not isinstance(url, str):
        return False, "URL cannot be empty"

    url = url.strip()
    try:
        parsed = urlparse(url)
    except Exception as e:
        return False, f"Malformed URL: {str(e)}"

    # 1. Scheme check
    if not parsed.scheme or parsed.scheme.lower() not in ALLOWED_SCHEMES:
        return False, f"Invalid URL scheme '{parsed.scheme}'. Only HTTP and HTTPS are permitted."

    hostname = parsed.hostname
    if not hostname:
        return False, "URL is missing a valid hostname"

    hostname_lower = hostname.lower()

    # 2. Blocked hostnames check
    if hostname_lower in BLOCKED_HOSTNAMES or hostname_lower.endswith(".localhost"):
        return False, f"Access to blocked hostname '{hostname}' is prohibited (SSRF prevention)."

    # 3. Check if hostname is directly an IP literal
    try:
        ip_obj = ipaddress.ip_address(hostname_lower)
        if is_ip_blocked(str(ip_obj)):
            return False, f"Access to private/loopback IP '{hostname}' is prohibited (SSRF prevention)."
        return True, ""
    except ValueError:
        pass  # Hostname is a domain name, proceed to DNS resolution

    # 4. Resolve DNS to verify resolved IPs
    try:
        # getaddrinfo resolves both IPv4 and IPv6
        addr_info = socket.getaddrinfo(hostname, parsed.port or (443 if parsed.scheme == "https" else 80))
        for item in addr_info:
            sockaddr = item[4]
            ip_str = sockaddr[0]
            if is_ip_blocked(ip_str):
                return False, f"Hostname '{hostname}' resolves to blocked private/local IP '{ip_str}' (SSRF prevention)."
    except socket.gaierror as e:
        return False, f"DNS resolution failed for hostname '{hostname}': {str(e)}"
    except Exception as e:
        return False, f"Security check failed during DNS lookup: {str(e)}"

    return True, ""


def sanitize_text(text: str) -> str:
    """Sanitizes text by stripping control characters while preserving standard whitespace."""
    if not text:
        return ""
    # Strip null bytes and control chars except newline, tab, carriage return
    clean_chars = [c for c in text if c in "\n\r\t" or (ord(c) >= 32 and ord(c) != 127)]
    return "".join(clean_chars).strip()
