from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('brief', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='projectbrief',
            name='existing_site_url',
            field=models.URLField(blank=True),
        ),
    ]
