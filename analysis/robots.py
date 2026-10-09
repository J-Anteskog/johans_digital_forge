"""
robots.txt för crawlen av undersidor (Disallow och Crawl-delay för vår User-Agent).

Regler enligt RFC 9309:
  - 200      → reglerna i filen gäller (för "JDF-Webbanalys", annars "*")
  - 4xx      → ingen robots.txt: allt är tillåtet
  - 5xx/fel  → robots.txt gick inte att läsa: inga undersidor crawlas

Startsidan hämtas alltid, eftersom den är adressen som användaren själv bad oss
analysera. robots.txt styr bara vilka undersidor vi besöker på eget initiativ.
"""

from urllib.robotparser import RobotFileParser

from .net import ROBOTS_AGENT

MAX_CRAWL_DELAY = 10   # längre Crawl-delay än så följs genom att crawla färre sidor
CRAWL_TIME_BUDGET = 60  # sekunder som crawlen högst får ta med Crawl-delay


class RobotsRules:

    def __init__(self, parser=None, allow_all=False, disallow_all=False, status='ok'):
        self._parser = parser
        self._allow_all = allow_all
        self._disallow_all = disallow_all
        self.status = status   # 'ok' | 'missing' | 'unreachable'

    @classmethod
    def from_fetch(cls, res) -> 'RobotsRules':
        """res: FetchResult för /robots.txt (eller None om den inte hämtades)."""
        if res is None or res.status_code is None or res.status_code >= 500:
            return cls(disallow_all=True, status='unreachable')
        if res.status_code >= 400:
            return cls(allow_all=True, status='missing')
        if res.status_code != 200:
            return cls(allow_all=True, status='missing')
        parser = RobotFileParser()
        parser.parse(res.content.decode('utf-8', errors='replace').splitlines())
        return cls(parser=parser)

    def allowed(self, url: str) -> bool:
        if self._disallow_all:
            return False
        if self._allow_all or self._parser is None:
            return True
        return self._parser.can_fetch(ROBOTS_AGENT, url)

    @property
    def crawl_delay(self) -> float | None:
        if self._parser is None:
            return None
        delay = self._parser.crawl_delay(ROBOTS_AGENT)
        try:
            return float(delay) if delay is not None else None
        except (TypeError, ValueError):
            return None

    def max_pages(self, default: int) -> int:
        """Färre undersidor när Crawl-delay är lång, så att crawlen håller sig inom tidsbudgeten."""
        delay = self.crawl_delay
        if not delay or delay <= 1:
            return default
        return max(1, min(default, int(CRAWL_TIME_BUDGET // delay)))

    def summary(self) -> dict:
        return {'status': self.status, 'crawl_delay': self.crawl_delay}
