from django.db import models

class Service(models.Model):
    title_sv = models.CharField(max_length=100, verbose_name="Titel (svenska)")
    title_en = models.CharField(max_length=100, verbose_name="Title (English)")
    description_sv = models.TextField(verbose_name="Beskrivning (svenska)")
    description_en = models.TextField(verbose_name="Description (English)")
    icon = models.CharField(max_length=50, blank=True, help_text="Font Awesome-ikon, t.ex. 'fa-solid fa-globe'")
    price = models.DecimalField(max_digits=6, decimal_places=2, verbose_name="Pris i SEK")

    extra_info_sv = models.TextField(blank=True, null=True)
    extra_info_en = models.TextField(blank=True, null=True)

    is_active = models.BooleanField(default=True, verbose_name="Synlig")

    class Meta:
        verbose_name = "Tjänst"
        verbose_name_plural = "Tjänster"

    def __str__(self):
        return self.title_sv
