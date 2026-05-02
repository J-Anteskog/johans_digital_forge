import uuid
from django.db import models
from django.urls import reverse


class SiteAnalysis(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Väntar'),
        ('running', 'Körs'),
        ('complete', 'Klar'),
        ('error', 'Fel'),
    ]

    # UUID som primärnyckel → delbar token i URL
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    url = models.URLField(max_length=200)
    domain = models.CharField(max_length=253, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')

    # Hela rapporten som strukturerad JSON
    results = models.JSONField(null=True, blank=True)

    # Poäng 0–100 per kategori + samlat
    score_overall = models.SmallIntegerField(null=True, blank=True)
    score_performance = models.SmallIntegerField(null=True, blank=True)
    score_mobile = models.SmallIntegerField(null=True, blank=True)
    score_seo = models.SmallIntegerField(null=True, blank=True)
    score_security = models.SmallIntegerField(null=True, blank=True)
    score_headers = models.SmallIntegerField(null=True, blank=True)
    score_accessibility = models.SmallIntegerField(null=True, blank=True)

    error_message = models.TextField(blank=True)

    # E-post (fylls antingen i formuläret eller via post-resultat opt-in)
    email = models.EmailField(blank=True)

    # GDPR-samtycke
    marketing_consent = models.BooleanField(null=True, blank=True)
    consent_timestamp = models.DateTimeField(null=True, blank=True)

    # Tracking (konverteringsmätning)
    email_form_shown = models.BooleanField(default=False)
    email_submitted = models.BooleanField(default=False)

    # Uppföljningsmejl dag 3
    followup_sent = models.BooleanField(default=False)

    # För rate-limiting (30 analyser/IP/timme)
    requester_ip = models.GenericIPAddressField(null=True, blank=True)

    language = models.CharField(
        max_length=2,
        choices=[('sv', 'Svenska'), ('en', 'English')],
        default='sv',
    )

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Webbplatsanalys'
        verbose_name_plural = 'Webbplatsanalyser'

    def __str__(self):
        ts = self.created_at.strftime('%Y-%m-%d %H:%M') if self.created_at else '(ej sparad)'
        return f"{self.url} – {ts} ({self.get_status_display()})"

    def get_absolute_url(self):
        return reverse('analysis_result', kwargs={'token': self.id})

    @property
    def grade(self):
        """Returnerar bokstavsbetyg baserat på overall-poäng."""
        if self.score_overall is None:
            return '–'
        if self.score_overall >= 85:
            return 'A'
        if self.score_overall >= 70:
            return 'B'
        if self.score_overall >= 50:
            return 'C'
        return 'D'

    @property
    def grade_color(self):
        """Bootstrap-färgklass för betyget."""
        return {'A': 'success', 'B': 'info', 'C': 'warning', 'D': 'danger'}.get(self.grade, 'secondary')

    @property
    def is_done(self):
        return self.status in ('complete', 'error')
