from django.db import models
from django.contrib.auth.models import User

class CalendarEvent(models.Model):
    title = models.CharField(max_length=200)
    start = models.DateTimeField()
    end = models.DateTimeField(blank=True, null=True)
    description = models.TextField(blank=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='calendar_events')

    def __str__(self):
        return f"{self.title} ({self.start.strftime('%Y-%m-%d %H:%M')})"
