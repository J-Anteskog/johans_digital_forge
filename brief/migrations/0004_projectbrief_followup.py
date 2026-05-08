from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('brief', '0003_add_promo_code'),
    ]

    operations = [
        migrations.AddField(
            model_name='projectbrief',
            name='followup_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='projectbrief',
            name='followup_note',
            field=models.CharField(blank=True, max_length=255),
        ),
    ]
