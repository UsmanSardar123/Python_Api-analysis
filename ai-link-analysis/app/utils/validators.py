"""URL validation and SSRF protection utilities."""

import ipaddress
import socket
from urllib.parse import urlparse, urlunparse

# Hostnames explicitly blocked for SSRF protection
BLOCKED_HOSTNAMES = {
    "localhost",
    "localhost.localdomain",
    "ip6-localhost",
    "ip6-loopback",
    "metadata.google.internal",
    "metadata",
    "instance-data",
    "0.0.0.0",
}

# Blocked domain suffixes indicating internal/local networks
BLOCKED_SUFFIXES = (
    ".localhost",
    ".local",
    ".internal",
    ".intranet",
    ".corp",
    ".home",
    ".lan",
)

# Allowed HTTP/HTTPS ports to prevent port-scanning internal services
ALLOWED_PORTS = {None, 80, 443, 8080, 8443}


class URLValidationError(ValueError):
    """Raised when a URL fails syntax, scheme, or format validation."""


class SSRFProtectionError(ValueError):
    """Raised when a URL targets a private IP, localhost, or internal network resource."""


def is_ip_blocked(ip_str: str) -> bool:
    """Return True if the IP address is private, loopback, link-local, reserved, or cloud metadata."""
    try:
        ip_obj = ipaddress.ip_address(ip_str)
    except ValueError:
        return True

    # Handle IPv4-mapped IPv6 addresses (e.g., ::ffff:127.0.0.1)
    if isinstance(ip_obj, ipaddress.IPv6Address) and ip_obj.ipv4_mapped:
        ip_obj = ip_obj.ipv4_mapped

    if (
        ip_obj.is_private
        or ip_obj.is_loopback
        or ip_obj.is_link_local
        or ip_obj.is_multicast
        or ip_obj.is_reserved
        or ip_obj.is_unspecified
    ):
        return True

    # Explicitly block AWS/GCP/Azure metadata IP (169.254.169.254) and CGNAT (100.64.0.0/10)
    if isinstance(ip_obj, ipaddress.IPv4Address):
        cgnat_network = ipaddress.IPv4Network("100.64.0.0/10")
        if ip_obj in cgnat_network:
            return True

    return False


def validate_and_normalize_url(raw_url: str, resolve_dns: bool = True) -> str:
    """Validate URL syntax, scheme, and SSRF safety, returning a normalized URL string.

    Args:
        raw_url: The input URL string to validate.
        resolve_dns: Whether to perform DNS resolution to verify the host does not
            resolve to private/loopback/internal IP addresses.

    Returns:
        Normalized URL string.

    Raises:
        URLValidationError: If the URL is malformed or uses an unsupported scheme.
        SSRFProtectionError: If the URL points to localhost, private IPs, or internal networks.
    """
    if not raw_url or not isinstance(raw_url, str):
        raise URLValidationError("URL must be a non-empty string.")

    cleaned_url = raw_url.strip()
    if len(cleaned_url) > 2048:
        raise URLValidationError("URL exceeds maximum allowed length of 2048 characters.")

    if any(ch in cleaned_url for ch in ("\r", "\n", "\t", " ")):
        raise URLValidationError("URL must not contain whitespace or control characters.")

    try:
        parsed = urlparse(cleaned_url)
    except Exception as exc:
        raise URLValidationError(f"Malformed URL: {exc}") from exc

    scheme = (parsed.scheme or "").lower()
    if scheme not in {"http", "https"}:
        raise URLValidationError(
            f"Unsupported URL scheme '{parsed.scheme or ''}'. Only 'http' and 'https' are allowed."
        )

    if not parsed.netloc or not parsed.hostname:
        raise URLValidationError("URL must include a valid hostname.")

    if parsed.username or parsed.password:
        raise SSRFProtectionError("URLs containing embedded credentials are not allowed.")

    try:
        port = parsed.port
    except ValueError as exc:
        raise URLValidationError(f"Invalid port in URL: {exc}") from exc

    if port not in ALLOWED_PORTS:
        raise SSRFProtectionError(
            f"Port {port} is not permitted. Only standard web ports (80, 443, 8080, 8443) are allowed."
        )

    hostname = parsed.hostname.lower().rstrip(".")
    if not hostname:
        raise URLValidationError("URL hostname cannot be empty.")

    if hostname in BLOCKED_HOSTNAMES or hostname.endswith(BLOCKED_SUFFIXES):
        raise SSRFProtectionError(
            f"Access to internal or local hostname '{hostname}' is blocked by SSRF protection."
        )

    # Check if hostname is a literal IP address (including decimal/hex/octal or IPv6)
    try:
        ip_literal = ipaddress.ip_address(hostname)
    except ValueError:
        ip_literal = None

    if ip_literal is not None:
        if is_ip_blocked(str(ip_literal)):
            raise SSRFProtectionError(
                f"Access to private, loopback, or reserved IP address '{hostname}' is blocked."
            )
    else:
        # Not a standard IP literal; check for integer/octal IP obfuscation (e.g., 2130706433 or 0x7f000001)
        if hostname.isdigit() or hostname.startswith("0x"):
            raise SSRFProtectionError(
                f"Numeric/encoded IP hostnames ('{hostname}') are blocked by SSRF protection."
            )
        # Validate domain format has at least one dot and valid characters
        if "." not in hostname:
            raise SSRFProtectionError(
                f"Single-label or unqualified internal hostnames ('{hostname}') are not allowed."
            )

    if resolve_dns:
        verify_hostname_dns_safety(hostname, port or (443 if scheme == "https" else 80))

    path = parsed.path if parsed.path else "/"
    normalized = urlunparse(
        (
            scheme,
            parsed.netloc,
            path,
            parsed.params,
            parsed.query,
            "",  # Strip URL fragment
        )
    )
    return normalized


def verify_hostname_dns_safety(hostname: str, port: int = 80) -> list[str]:
    """Resolve hostname via DNS and ensure all resolved IPs are public and routable.

    Raises:
        SSRFProtectionError: If any resolved IP is private, loopback, link-local, or reserved.
        URLValidationError: If the hostname cannot be resolved.
    """
    # If already a valid public IP literal, return directly
    try:
        ip_obj = ipaddress.ip_address(hostname)
    except ValueError:
        ip_obj = None

    if ip_obj is not None:
        if is_ip_blocked(str(ip_obj)):
            raise SSRFProtectionError(
                f"Access to non-public IP address '{hostname}' is blocked by SSRF protection."
            )
        return [str(ip_obj)]

    try:
        addr_info = socket.getaddrinfo(hostname, port, proto=socket.IPPROTO_TCP)
    except socket.gaierror as exc:
        raise URLValidationError(f"Could not resolve hostname '{hostname}': {exc}") from exc
    except Exception as exc:
        raise URLValidationError(f"DNS lookup failed for '{hostname}': {exc}") from exc

    if not addr_info:
        raise URLValidationError(f"No DNS records found for hostname '{hostname}'.")

    resolved_ips: list[str] = []
    for family, _, _, _, sockaddr in addr_info:
        ip_str = sockaddr[0]
        if is_ip_blocked(ip_str):
            raise SSRFProtectionError(
                f"Hostname '{hostname}' resolved to restricted internal/private IP '{ip_str}'. Access blocked."
            )
        if ip_str not in resolved_ips:
            resolved_ips.append(ip_str)

    return resolved_ips
