from django.db import models


class ToolCard(models.Model):
    STATUS_LIVE = 'live'
    STATUS_FORGING = 'forging'
    STATUS_DEV = 'development'
    STATUS_CHOICES = [
        (STATUS_LIVE, 'Live'),
        (STATUS_FORGING, 'I smedjan'),
        (STATUS_DEV, 'Under utveckling'),
    ]

    title_sv = models.CharField(max_length=100, verbose_name="Titel (svenska)")
    title_en = models.CharField(max_length=100, verbose_name="Title (English)")
    description_sv = models.TextField(verbose_name="Beskrivning (svenska)")
    description_en = models.TextField(verbose_name="Description (English)")
    icon = models.CharField(
        max_length=50,
        blank=True,
        help_text="Font Awesome-ikon, t.ex. 'fas fa-comments'"
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_LIVE)
    progress_percent = models.PositiveSmallIntegerField(
        blank=True, null=True,
        verbose_name="Utveckling (%)",
        help_text="Endast relevant för 'I smedjan' / 'Under utveckling'"
    )
    features_sv = models.TextField(
        blank=True,
        verbose_name="Punktlista (svenska)",
        help_text="En rad per punkt. Börja raden med '-' för punkter som INTE är klara ännu."
    )
    features_en = models.TextField(
        blank=True,
        verbose_name="Punktlista (engelska)",
        help_text="One line per item. Start the line with '-' for items that are NOT done yet."
    )
    link_url = models.URLField(blank=True, verbose_name="Läs mer-länk (valfri)")
    order = models.PositiveIntegerField(default=0, verbose_name="Sorteringsordning")
    is_active = models.BooleanField(default=True, verbose_name="Synlig")

    class Meta:
        verbose_name = "Verktygskort"
        verbose_name_plural = "Verktygskort"
        ordering = ['order', 'id']

    def __str__(self):
        return self.title_sv

    def features_list_sv(self):
        return self._parse_features(self.features_sv)

    def features_list_en(self):
        return self._parse_features(self.features_en)

    @staticmethod
    def _parse_features(raw):
        items = []
        for line in (raw or '').splitlines():
            line = line.strip()
            if not line:
                continue
            done = not line.startswith('-')
            text = line.lstrip('-').strip()
            items.append({'text': text, 'done': done})
        return items


class BuildLogEntry(models.Model):
    date = models.DateField(verbose_name="Datum", help_text="Används för sortering, t.ex. första dagen i månaden")
    title_sv = models.CharField(max_length=100, verbose_name="Rubrik (svenska)", help_text="T.ex. 'CRM'")
    title_en = models.CharField(max_length=100, verbose_name="Rubrik (engelska)")
    description_sv = models.TextField(verbose_name="Beskrivning (svenska)")
    description_en = models.TextField(verbose_name="Beskrivning (engelska)")
    order = models.PositiveIntegerField(default=0, verbose_name="Sorteringsordning")
    is_active = models.BooleanField(default=True, verbose_name="Synlig")

    class Meta:
        verbose_name = "Byggloggspost"
        verbose_name_plural = "Byggloggsposter"
        ordering = ['-date', '-id']

    def __str__(self):
        return f"{self.date:%Y-%m} – {self.title_sv}"
