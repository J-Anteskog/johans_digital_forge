"""Regel 7: landmärken, skip-länk och rubrikhierarki letar efter rätt saker."""

from django.test import SimpleTestCase

from analysis.checks.accessibility import POINTS, check_accessibility

from .helpers import soup_from


class LandmarkTests(SimpleTestCase):

    def test_html5_elements(self):
        lm = check_accessibility(soup_from('a11y_html5.html'))['landmarks']
        self.assertEqual(lm['found'], ['main', 'nav', 'header', 'footer'])
        self.assertTrue(lm['has_main'])
        self.assertEqual(lm['via']['main'], '<main>')

    def test_aria_roles_count_as_landmarks(self):
        lm = check_accessibility(soup_from('a11y_roles.html'))['landmarks']
        self.assertEqual(lm['found'], ['main', 'nav', 'header', 'footer'])
        self.assertEqual(lm['via']['main'], 'role="main"')
        self.assertEqual(lm['via']['header'], 'role="banner"')

    def test_wordpress_fixture_really_has_no_landmarks(self):
        """enbloms-liknande: bara <div>:ar – 'saknas' är korrekt, inte ett fel i kontrollen."""
        lm = check_accessibility(soup_from('wordpress_mesmerize.html'))['landmarks']
        self.assertEqual(lm['found'], [])


class SkipLinkTests(SimpleTestCase):

    def test_wordpress_skip_link_is_found(self):
        """Tidigare: '#page-content' fanns inte i den hårdkodade listan → 'Skip navigation saknas'."""
        skip = check_accessibility(soup_from('wordpress_mesmerize.html'))['skip_nav']
        self.assertTrue(skip['found'])
        self.assertEqual(skip['href'], '#page-content')
        self.assertEqual(skip['text'], 'Hoppa till innehåll')

    def test_english_skip_link_with_any_id(self):
        skip = check_accessibility(soup_from('a11y_roles.html'))['skip_nav']
        self.assertTrue(skip['found'])
        self.assertEqual(skip['href'], '#main-content')

    def test_logo_to_top_and_link_to_missing_id_do_not_count(self):
        skip = check_accessibility(soup_from('a11y_bad.html'))['skip_nav']
        self.assertFalse(skip['found'])


class HeadingTests(SimpleTestCase):

    def test_correct_hierarchy(self):
        hd = check_accessibility(soup_from('a11y_roles.html'))['headings']
        self.assertEqual(hd['h1_count'], 1)
        self.assertEqual(hd['skipped_levels'], [])
        self.assertEqual(hd['empty_count'], 0)   # rubrik med bara bild + alt räknas inte som tom

    def test_skipped_levels_and_empty_headings(self):
        hd = check_accessibility(soup_from('a11y_bad.html'))['headings']
        self.assertEqual(hd['h1_count'], 0)
        self.assertEqual(hd['skipped_levels'], ['H2 → H4'])
        self.assertEqual(hd['empty_count'], 1)

    def test_wordpress_fixture_without_h1(self):
        hd = check_accessibility(soup_from('wordpress_mesmerize.html'))['headings']
        self.assertEqual(hd['h1_count'], 0)
        self.assertEqual(hd['first_level'], 3)
        self.assertIn('H2 → H5', hd['skipped_levels'])
        self.assertEqual(hd['empty_count'], 1)   # <h4> med bara en ikon


class ScoreTests(SimpleTestCase):

    def test_points_sum_to_100(self):
        self.assertEqual(sum(POINTS.values()), 100)

    def test_good_page_scores_full(self):
        self.assertEqual(check_accessibility(soup_from('a11y_roles.html'))['score'], 100)

    def test_wordpress_fixture_score(self):
        a = check_accessibility(soup_from('wordpress_mesmerize.html'))
        # lang 15 + skip 10 + alt (inga saknade) 20 + interaktiva 15 = 60
        self.assertEqual(a['score'], 60)
        self.assertFalse(a['passed']['landmark_main'])
        self.assertFalse(a['passed']['h1'])
