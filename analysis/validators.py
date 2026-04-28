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


def validate_target_url(url: str) -> str:
    """
    Validates that a URL is safe to fetch from the server.
    Returns a normalised URL or raises ValidationError.
    """
    parsed = urlparse(url.strip())

    if parsed.scheme not in ('http', 'https'):
        raise ValidationError('Endast http- och https-URL:er tillåts.')

    hostname = parsed.hostname
    if not hostname:
        raise ValidationError('Ogiltig URL – saknar domännamn.')

    if hostname.lower() in _BLOCKED_HOSTNAMES:
        raise ValidationError('Lokala adresser tillåts inte.')

    if parsed.port not in _ALLOWED_PORTS:
        raise ValidationError('Endast port 80 och 443 tillåts.')

    try:
        addr_info = socket.getaddrinfo(hostname, None)
    except socket.gaierror:
        raise ValidationError('Kunde inte slå upp domänen.')

    for info in addr_info:
        ip_str = info[4][0]
        try:
            ip = ipaddress.ip_address(ip_str)
        except ValueError:
            continue

        if (ip.is_private or ip.is_loopback or ip.is_link_local
                or ip.is_reserved or ip.is_multicast or ip.is_unspecified):
            raise ValidationError(
                'Privata, interna eller reserverade IP-adresser tillåts inte.'
            )

        if ip_str in _CLOUD_METADATA_IPS:
            raise ValidationError('Cloud metadata-endpoints tillåts inte.')

    normalised = urlunparse((
        parsed.scheme,
        parsed.netloc.lower(),
        parsed.path or '/',
        parsed.params,
        parsed.query,
        '',
    ))
    return normalised
