"""
Fakta om sidan som flera kontroller använder.
"""

from bs4 import BeautifulSoup
from bs4.dammit import EncodingDetector


def parse_html(content: bytes, declared_encoding: str | None = None):
    """
    Parsar HTML från råa bytes med samma ordning som webbläsare:
    HTTP-headerns charset → <meta charset> → UTF-8 om giltigt → windows-1252.
    (Tidigare användes requests standardgissning ISO-8859-1 när headern saknade
    charset, vilket gav fel tecken på UTF-8-sidor.)
    """
    encoding = declared_encoding or EncodingDetector.find_declared_encoding(content, is_html=True)
    if not encoding:
        try:
            content.decode('utf-8')
            encoding = 'utf-8'
        except UnicodeDecodeError:
            encoding = 'windows-1252'
    return BeautifulSoup(content, 'lxml', from_encoding=encoding)
