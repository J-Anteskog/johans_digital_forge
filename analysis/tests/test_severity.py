"""
Regel B: fynd som gäller färre än hälften av de kontrollerade sidorna sänks ett steg
(KRITISK → HÖG, HÖG → MEDEL), men inte om startsidan är berörd. Bara etikett och
sortering i fyndlistan påverkas – inte poängen.
"""

import copy

from django.test import SimpleTestCase

from analysis.report import site_findings
from analysis.scoring import seo_breakdown

from .test_site_rules import SITE, soup_seo

GOOD = soup_seo('site_sub_good.html')
NO_DESC = soup_seo('site_sub_nodesc.html')


def _site(total, without_desc, start_without_desc=False):
    """Startsida + (total − 1) undersidor, varav `without_desc` saknar metabeskrivning."""
    start = copy.deepcopy(NO_DESC if start_without_desc else GOOD)
    start.update({'robots_txt': {'found': True}, 'sitemap': {'found': True}})
    sub_missing = without_desc - (1 if start_without_desc else 0)
    pages = []
    for i in range(total - 1):
        seo = copy.deepcopy(NO_DESC if i < sub_missing else GOOD)
        seo['title'] = dict(seo['title'], value=f'{seo["title"]["value"]} {i}')   # unika titlar
        pages.append({'url': f'{SITE}sida-{i}', 'seo': seo})
    return {'seo': start, 'pages': pages, 'http': {'final_url': SITE}}


def _desc(results):
    return next(f for f in site_findings(results) if f['key'] == 'desc_missing')


class SeverityByShareTests(SimpleTestCase):

    def test_5_of_11_is_lowered_to_medium(self):
        f = _desc(_site(11, 5))
        self.assertEqual(f['text'], 'Metabeskrivning saknas på 5 av de 11 sidor som kontrollerades')
        self.assertEqual((f['base_severity'], f['severity'], f['downgraded']), ('high', 'medium', True))

    def test_6_of_11_stays_high(self):
        f = _desc(_site(11, 6))
        self.assertEqual((f['severity'], f['downgraded']), ('high', False))

    def test_exactly_half_stays_high(self):
        self.assertEqual(_desc(_site(4, 2))['severity'], 'high')    # 2 av 4 är inte "färre än hälften"

    def test_start_page_affected_stays_high(self):
        f = _desc(_site(11, 1, start_without_desc=True))
        self.assertEqual(f['pages'], [SITE])
        self.assertEqual((f['severity'], f['downgraded']), ('high', False))

    def test_1_of_1_stays_high(self):
        f = _desc(_site(1, 1, start_without_desc=True))
        self.assertEqual(f['text'], 'Metabeskrivning saknas på startsidan, den enda sida som kontrollerades')
        self.assertEqual(f['severity'], 'high')

    def test_all_pages_stays_high(self):
        f = _desc(_site(7, 7, start_without_desc=True))
        self.assertEqual(f['text'], 'Metabeskrivning saknas på 7 av de 7 sidor som kontrollerades')
        self.assertEqual(f['severity'], 'high')

    def test_critical_is_lowered_one_step_only(self):
        r = _site(11, 0)
        for page in r['pages'][:2]:
            page['seo']['title'] = {'found': False, 'value': '', 'length': 0, 'ok': False}
        f = next(f for f in site_findings(r) if f['key'] == 'title_missing')
        self.assertEqual((f['base_severity'], f['severity']), ('critical', 'high'))

    def test_lowered_findings_sort_after_unlowered_ones(self):
        r = _site(11, 2)                                                  # 2 av 11 → MEDEL
        r['seo']['h1'] = {'found': False, 'count': 0, 'unique': False, 'value': None}   # startsidan → HÖG
        order = [(f['key'], f['severity']) for f in site_findings(r)]
        self.assertEqual(order, [('h1_missing', 'high'), ('desc_missing', 'medium')])

    def test_score_is_not_affected(self):
        r = _site(11, 5)
        before = seo_breakdown(r)['score']
        site_findings(r)
        self.assertEqual(seo_breakdown(r)['score'], before)
        # 5 sidor utan metabeskrivning kostar fortfarande 30 p vardera: (5×55 + 5×85)/10 = 70
        self.assertEqual(seo_breakdown(r)['subpages_mean'], 70.0)
