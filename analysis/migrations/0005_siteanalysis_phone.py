from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('analysis', '0004_siteanalysis_consent_timestamp_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='siteanalysis',
            name='phone',
            field=models.CharField(blank=True, max_length=30),
        ),
    ]
