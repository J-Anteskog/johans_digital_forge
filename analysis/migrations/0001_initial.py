import uuid
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True
    dependencies = []

    operations = [
        migrations.CreateModel(
            name='SiteAnalysis',
            fields=[
                ('id', models.UUIDField(
                    primary_key=True, default=uuid.uuid4,
                    editable=False, serialize=False,
                )),
                ('url', models.URLField(max_length=200)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('completed_at', models.DateTimeField(blank=True, null=True)),
                ('status', models.CharField(
                    choices=[('pending', 'Väntar'), ('running', 'Körs'),
                             ('complete', 'Klar'), ('error', 'Fel')],
                    default='pending', max_length=10,
                )),
                ('results', models.JSONField(blank=True, null=True)),
                ('score_overall', models.SmallIntegerField(blank=True, null=True)),
                ('score_performance', models.SmallIntegerField(blank=True, null=True)),
                ('score_mobile', models.SmallIntegerField(blank=True, null=True)),
                ('score_seo', models.SmallIntegerField(blank=True, null=True)),
                ('score_security', models.SmallIntegerField(blank=True, null=True)),
                ('error_message', models.TextField(blank=True)),
                ('email', models.EmailField(blank=True, max_length=254)),
                ('requester_ip', models.GenericIPAddressField(blank=True, null=True)),
            ],
            options={
                'verbose_name': 'Webbplatsanalys',
                'verbose_name_plural': 'Webbplatsanalyser',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='siteanalysis',
            index=models.Index(fields=['url', 'created_at'], name='analysis_url_created_idx'),
        ),
        migrations.AddIndex(
            model_name='siteanalysis',
            index=models.Index(fields=['requester_ip', 'created_at'], name='analysis_ip_created_idx'),
        ),
    ]
