import ipaddress
import socket
import struct
import time
from urllib.parse import urlparse, urljoin

_PRIVATE_NETWORKS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("0.0.0.0/32"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
    ipaddress.ip_network("100.64.0.0/10"),
]

_CLOUD_METADATA = {
    "169.254.169.254",
    "169.254.169.253",
    "100.100.100.200",
    "169.254.169.250",
    "169.254.169.251",
    "169.254.169.252",
    "169.254.42.42",
    "192.0.2.0",
    "198.51.100.0",
    "203.0.113.0",
}


def _resolve_all_ips(hostname):
    try:
        addrinfo = socket.getaddrinfo(hostname, 80)
        ips = list(set(sockaddr[0] for _, _, _, _, sockaddr in addrinfo))
        return ips
    except OSError:
        return []


def _check_dns_rebinding(hostname):
    try:
        ips1 = _resolve_all_ips(hostname)
        if not ips1:
            return False
        time.sleep(0.5)
        ips2 = _resolve_all_ips(hostname)
        return set(ips1) != set(ips2)
    except Exception:
        return False


def is_ssrf_blocked(hostname):
    if not hostname:
        return True
    try:
        addr = ipaddress.ip_address(hostname)
        if str(addr) in _CLOUD_METADATA:
            return True
        if any(addr in net for net in _PRIVATE_NETWORKS):
            return True
        return False
    except ValueError:
        pass

    ips = _resolve_all_ips(hostname)
    if not ips:
        return True

    for ip in ips:
        try:
            addr = ipaddress.ip_address(ip)
            if str(addr) in _CLOUD_METADATA:
                return True
            if any(addr in net for net in _PRIVATE_NETWORKS):
                return True
        except ValueError:
            return True

    return False


def validate_url(url, enforce_https=False, max_length=8192):
    if len(url) > max_length:
        raise ValueError(f"URL exceeds maximum length of {max_length} characters")
    if not url.startswith(("http://", "https://")):
        if "." not in url:
            raise ValueError("Invalid URL")
        url = "https://" + url
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError("Only HTTP/HTTPS URLs are allowed")
    if enforce_https and parsed.scheme == "http":
        raise ValueError("HTTP URLs are not allowed; use HTTPS")
    if not parsed.hostname:
        raise ValueError("URL must have a valid hostname")
    if is_ssrf_blocked(parsed.hostname):
        raise ValueError("Access to internal or private network addresses is not allowed")
    if _check_dns_rebinding(parsed.hostname):
        raise ValueError("DNS rebinding attack detected for this hostname")
    return url


def safe_httpx_get(url, client, max_redirects=10, **kwargs):
    kwargs.pop("follow_redirects", None)
    kwargs.pop("allow_redirects", None)

    current_url = url
    visited = set()

    for _ in range(max_redirects):
        parsed = urlparse(current_url)
        if is_ssrf_blocked(parsed.hostname):
            raise ValueError("Redirect target is blocked")

        response = client.get(current_url, **kwargs)

        if response.is_redirect or response.has_redirect_location:
            location = response.headers.get("Location")
            if not location:
                return response
            redirect_url = urljoin(current_url, location)
            if redirect_url in visited:
                raise ValueError("Redirect loop detected")
            visited.add(redirect_url)
            validate_url(redirect_url)
            current_url = redirect_url
            continue

        return response

    raise ValueError(f"Too many redirects (>{max_redirects})")