from django import template

from analysis.report import error_info, ssl_error_info

register = template.Library()


@register.filter
def readable_error(error, lang='sv'):
    """Läsbar text för ett sparat fel – för mallar som saknar report_errors (v1)."""
    info = error_info(error, lang=lang or 'sv')
    return info['text'] if info else ''


@register.filter
def readable_ssl_error(ssl, lang='sv'):
    info = ssl_error_info(ssl, lang or 'sv')
    return info['text'] if info else ''
