import ipaddress
import socket
from urllib.parse import urlparse, urlunparse

from django.core.exceptions import ValidationError

_BLOCKED_HOSTNAMES = {
    'localhost',
    'localhost.localdomain',
    'ip6-localhost',
    'ip6-loopback',
    'broadcasthost',
    '0.0.0.0',
}

_CLOUD_METADATA_IPS = {'169.254.169.254', 'fd00:ec2::254'}

_ALLOWED_PORTS = {None, 80, 443}


def check_ip_allowed(ip_str: str) -> None:
    """
    Raises ValidationError om IP-adressen inte är en publik adress.
    Används både vid URL-validering och vid själva uppkopplingen (analysis.net),
    så att det är IP:t vi faktiskt ansluter till som kontrolleras.
    """
    try:
        ip = ipaddress.ip_address(ip_str.split('%', 1)[0])
    except ValueError:
        raise ValidationError('Ogiltig IP-adress.')

    # ::ffff:127.0.0.1 m.fl. – kontrollera den inbäddade IPv4-adressen
    if ip.version == 6 and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped

    if ip_str in _CLOUD_METADATA_IPS or str(ip) in _CLOUD_METADATA_IPS:
        raise ValidationError('Cloud metadata-endpoints tillåts inte.')

    if (ip.is_private or ip.is_loopback or ip.is_link_local
            or ip.is_reserved or ip.is_multicast or ip.is_unspecified
            or not ip.is_global):
        raise ValidationError(
            'Privata, interna eller reserverade IP-adresser tillåts inte.'
        )


def resolve_public_ips(hostname: str, port: int | None = None) -> list[str]:
    """
    Slår upp hostname och returnerar dess IP-adresser.
    Raises ValidationError om uppslagningen misslyckas eller om NÅGON adress
    är intern (så att en blandning av publik + privat inte kan utnyttjas).
    """
    try:
        addr_info = socket.getaddrinfo(hostname, port)
    except socket.gaierror:
        raise ValidationError('Kunde inte slå upp domänen.')

    ips = []
    for info in addr_info:
        ip_str = info[4][0]
        check_ip_allowed(ip_str)
        if ip_str not in ips:
            ips.append(ip_str)
    if not ips:
        raise ValidationError('Kunde inte slå upp domänen.')
    return ips


def validate_url_syntax(url: str):
    """Kontrollerar schema, värdnamn och port utan DNS-uppslagning."""
    parsed = urlparse(url.strip())

    if parsed.scheme not in ('http', 'https'):
        raise ValidationError('Endast http- och https-URL:er tillåts.')

    hostname = parsed.hostname
    if not hostname:
        raise ValidationError('Ogiltig URL – saknar domännamn.')

    if hostname.lower().rstrip('.') in _BLOCKED_HOSTNAMES:
        raise ValidationError('Lokala adresser tillåts inte.')

    try:
        port = parsed.port
    except ValueError:
        raise ValidationError('Ogiltig port.')
    if port not in _ALLOWED_PORTS:
        raise ValidationError('Endast port 80 och 443 tillåts.')

    return parsed


def validate_target_url(url: str) -> str:
    """
    Validates that a URL is safe to fetch from the server.
    Returns a normalised URL or raises ValidationError.
    """
    parsed = validate_url_syntax(url)
    resolve_public_ips(parsed.hostname)

    normalised = urlunparse((
        parsed.scheme,
        parsed.netloc.lower(),
        parsed.path or '/',
        parsed.params,
        parsed.query,
        '',
    ))
    return normalised
