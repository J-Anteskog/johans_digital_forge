from unittest.mock import patch
from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from analysis.validators import validate_target_url


def _addr(ip: str):
    """Bygg ett getaddrinfo-svar för ett givet IP."""
    family = 10 if ':' in ip else 2  # AF_INET6 / AF_INET
    return [(family, 1, 6, '', (ip, 0))]


class ValidateTargetUrlSchemeTests(SimpleTestCase):

    def test_https_ok(self):
        with patch('analysis.validators.socket.getaddrinfo',
                   return_value=_addr('93.184.216.34')):
            result = validate_target_url('https://example.com')
        self.assertTrue(result.startswith('https://'))

    def test_http_ok(self):
        with patch('analysis.validators.socket.getaddrinfo',
                   return_value=_addr('93.184.216.34')):
            result = validate_target_url('http://example.com')
        self.assertTrue(result.startswith('http://'))

    def test_ftp_rejected(self):
        with self.assertRaises(ValidationError):
            validate_target_url('ftp://example.com')

    def test_file_rejected(self):
        with self.assertRaises(ValidationError):
            validate_target_url('file:///etc/passwd')


class ValidateTargetUrlLocalhostTests(SimpleTestCase):

    def test_localhost_rejected(self):
        with self.assertRaises(ValidationError):
            validate_target_url('http://localhost')

    def test_localhost_with_port_rejected(self):
        with self.assertRaises(ValidationError):
            validate_target_url('http://localhost:8080/admin/')

    def test_localhost_localdomain_rejected(self):
        with self.assertRaises(ValidationError):
            validate_target_url('http://localhost.localdomain')

    def test_zero_host_rejected(self):
        with self.assertRaises(ValidationError):
            validate_target_url('http://0.0.0.0')


class ValidateTargetUrlPrivateIPTests(SimpleTestCase):

    def _blocked(self, ip):
        with patch('analysis.validators.socket.getaddrinfo',
                   return_value=_addr(ip)):
            with self.assertRaises(ValidationError):
                validate_target_url('http://internal.example.com')

    def test_loopback_127(self):
        with self.assertRaises(ValidationError):
            validate_target_url('http://127.0.0.1')

    def test_loopback_127_0_0_2(self):
        with patch('analysis.validators.socket.getaddrinfo',
                   return_value=_addr('127.0.0.2')):
            with self.assertRaises(ValidationError):
                validate_target_url('http://example.com')

    def test_private_10(self):
        self._blocked('10.0.0.5')

    def test_private_192_168(self):
        self._blocked('192.168.1.1')

    def test_private_172_16(self):
        self._blocked('172.16.0.1')

    def test_link_local_169_254(self):
        with self.assertRaises(ValidationError):
            validate_target_url('http://169.254.169.254')

    def test_link_local_domain_resolves_to_private(self):
        self._blocked('169.254.169.254')

    def test_cloud_metadata_aws(self):
        with self.assertRaises(ValidationError):
            validate_target_url('http://169.254.169.254/latest/meta-data/')

    def test_domain_resolving_to_private_rejected(self):
        """DNS resolvar till privat IP — ska blockeras (SSRF via DNS)."""
        self._blocked('10.0.0.1')

    def test_ipv6_loopback_rejected(self):
        self._blocked('::1')

    def test_ipv6_private_rejected(self):
        self._blocked('fd00::1')


class ValidateTargetUrlPortTests(SimpleTestCase):

    def _url(self, port):
        return f'https://example.com:{port}/path'

    def test_port_22_rejected(self):
        with self.assertRaises(ValidationError):
            validate_target_url(self._url(22))

    def test_port_8080_rejected(self):
        with self.assertRaises(ValidationError):
            validate_target_url(self._url(8080))

    def test_port_3306_rejected(self):
        with self.assertRaises(ValidationError):
            validate_target_url(self._url(3306))

    def test_port_443_ok(self):
        with patch('analysis.validators.socket.getaddrinfo',
                   return_value=_addr('93.184.216.34')):
            result = validate_target_url('https://example.com:443/path')
        self.assertIn('example.com', result)

    def test_port_80_ok(self):
        with patch('analysis.validators.socket.getaddrinfo',
                   return_value=_addr('93.184.216.34')):
            result = validate_target_url('http://example.com:80/path')
        self.assertIn('example.com', result)


class ValidateTargetUrlNormalisationTests(SimpleTestCase):

    def test_uppercase_host_lowercased(self):
        with patch('analysis.validators.socket.getaddrinfo',
                   return_value=_addr('93.184.216.34')):
            result = validate_target_url('https://EXAMPLE.COM/Path')
        self.assertTrue(result.startswith('https://example.com'))

    def test_fragment_stripped(self):
        with patch('analysis.validators.socket.getaddrinfo',
                   return_value=_addr('93.184.216.34')):
            result = validate_target_url('https://example.com/page#section')
        self.assertNotIn('#', result)

    def test_path_preserved(self):
        with patch('analysis.validators.socket.getaddrinfo',
                   return_value=_addr('93.184.216.34')):
            result = validate_target_url('https://example.com/some/path?q=1')
        self.assertIn('/some/path', result)
        self.assertIn('q=1', result)

    def test_empty_path_becomes_slash(self):
        with patch('analysis.validators.socket.getaddrinfo',
                   return_value=_addr('93.184.216.34')):
            result = validate_target_url('https://example.com')
        self.assertTrue(result.endswith('/'))

    def test_dns_failure_raises(self):
        import socket as _socket
        with patch('analysis.validators.socket.getaddrinfo',
                   side_effect=_socket.gaierror('NXDOMAIN')):
            with self.assertRaises(ValidationError):
                validate_target_url('https://this-domain-does-not-exist-xyz.example')
