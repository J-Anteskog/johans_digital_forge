from django.db import models

class Project(models.Model):
    title_sv = models.CharField(max_length=100)
    title_en = models.CharField(max_length=100)
    description_sv = models.TextField()
    description_en = models.TextField()
    technologies = models.CharField(max_length=200, help_text="Ex: Django, JavaScript, Bootstrap")
    github_url = models.URLField(blank=True, null=True)
    live_url = models.URLField(blank=True, null=True)
    image = models.ImageField(upload_to='portfolio/', blank=True, null=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.title_sv
