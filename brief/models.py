from django.db import models


class ProjectBrief(models.Model):
    STATUS_CHOICES = [
        ('new', 'Ny'),
        ('reviewed', 'Granskad'),
        ('quoted', 'Offerterad'),
        ('accepted', 'Accepterad'),
        ('declined', 'Avböjd'),
    ]
    GOAL_CHOICES = [
        ('leads', 'Generera leads / kundförfrågningar'),
        ('present_company', 'Presentera företaget / verksamheten'),
        ('sell_products', 'Sälja produkter eller tjänster online'),
        ('booking', 'Ta emot bokningar'),
        ('other', 'Annat'),
    ]
    HAS_EXISTING_SITE_CHOICES = [
        ('redo_needed', 'Ja – hemsidan behöver byggas om helt'),
        ('unhappy', 'Ja – men vi är missnöjda och vill förbättra'),
        ('no_new', 'Nej – vi bygger från grunden'),
        ('unsure', 'Osäker'),
    ]
    NUM_PAGES_CHOICES = [
        ('1', '1 sida (one-pager)'),
        ('3-5', '3–5 sidor'),
        ('5-10', '5–10 sidor'),
        ('10+', 'Mer än 10 sidor'),
        ('unsure', 'Osäker'),
    ]
    FEATURE_CHOICES = [
        ('startsida', 'Startsida'),
        ('kontakt', 'Kontaktformulär'),
        ('om_oss', 'Om oss-sida'),
        ('boka', 'Bokningssystem'),
        ('tjanster', 'Tjänstesidor'),
        ('blogg', 'Blogg'),
        ('galleri', 'Bildgalleri'),
        ('webbshop', 'Webbshop'),
        ('omdomen', 'Omdömen / recensioner'),
    ]
    HAS_MATERIAL_CHOICES = [
        ('all', 'Ja – texter och bilder är klara'),
        ('partial', 'Delvis – vi har en del men behöver hjälp'),
        ('none', 'Nej – vi behöver hjälp med allt'),
        ('unsure', 'Osäker'),
    ]
    STYLE_CHOICES = [
        ('modern', 'Modern & professionell'),
        ('creative', 'Kreativ & unik'),
        ('minimal', 'Minimalistisk & ren'),
        ('colorful', 'Färgstark & livfull'),
    ]
    TIMELINE_CHOICES = [
        ('asap', 'Snarast (inom 4 veckor)'),
        ('1_month', 'Inom 1 månad'),
        ('2_3_months', '2–3 månader'),
        ('no_rush', 'Ingen brådska'),
        ('specific', 'Specifikt datum'),
    ]
    BUDGET_CHOICES = [
        ('under_10k', 'Under 10 000 kr'),
        ('10k_20k', '10 000–20 000 kr'),
        ('20k_40k', '20 000–40 000 kr'),
        ('40k_plus', 'Mer än 40 000 kr'),
        ('unsure', 'Osäker / vill diskutera'),
    ]
    LANGUAGE_CHOICES = [
        ('sv', 'Svenska'),
        ('en', 'English'),
    ]

    # --- Metadata ---
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='new')
    language = models.CharField(max_length=2, choices=LANGUAGE_CHOICES, default='sv')
    referrer = models.CharField(max_length=255, blank=True)

    # --- Steg 1: Mål, budget, tidslinje ---
    goals = models.JSONField(default=list)
    goals_other = models.CharField(max_length=255, blank=True)
    budget = models.CharField(max_length=20, choices=BUDGET_CHOICES)
    timeline = models.CharField(max_length=20, choices=TIMELINE_CHOICES)
    timeline_specific = models.DateField(blank=True, null=True)

    # --- Steg 2: Befintlig sida, antal sidor, funktioner ---
    has_existing_site = models.CharField(max_length=20, choices=HAS_EXISTING_SITE_CHOICES)
    existing_site_url = models.URLField(blank=True)
    num_pages = models.CharField(max_length=10, choices=NUM_PAGES_CHOICES)
    features = models.JSONField(default=list)
    features_other = models.CharField(max_length=255, blank=True)

    # --- Steg 3: Stil, material, anteckningar, kontakt ---
    has_material = models.CharField(max_length=10, choices=HAS_MATERIAL_CHOICES)
    style_preferences = models.JSONField(default=list)
    notes = models.TextField(blank=True)
    contact_name = models.CharField(max_length=100)
    contact_email = models.EmailField()
    contact_phone = models.CharField(max_length=30, blank=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Offertbrief'
        verbose_name_plural = 'Offertbriefar'

    def __str__(self):
        return f"{self.contact_name} – {self.created_at.strftime('%Y-%m-%d')} ({self.get_status_display()})"

    def score(self):
        """Lead-score 0–100: budget (40p) + tidslinje (30p) + tydliga mål (20p) + material (10p)."""
        budget_pts = {'under_10k': 10, '10k_20k': 25, '20k_40k': 35, '40k_plus': 40, 'unsure': 5}
        timeline_pts = {'asap': 30, '1_month': 25, '2_3_months': 15, 'specific': 20, 'no_rush': 5}
        material_pts = {'all': 10, 'partial': 6, 'none': 2, 'unsure': 0}

        pts = budget_pts.get(self.budget, 0)
        pts += timeline_pts.get(self.timeline, 0)

        clear_goals = [g for g in (self.goals or []) if g != 'other']
        pts += 20 if len(clear_goals) >= 2 else (12 if len(clear_goals) == 1 else 0)

        pts += material_pts.get(self.has_material, 0)
        return min(pts, 100)
