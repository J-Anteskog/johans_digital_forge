from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('analysis', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='siteanalysis',
            name='language',
            field=models.CharField(
                choices=[('sv', 'Svenska'), ('en', 'English')],
                default='sv',
                max_length=2,
            ),
        ),
    ]
