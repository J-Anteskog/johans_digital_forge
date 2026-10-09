from django.db import migrations, models


class Migration(migrations.Migration):
    """
    Lägger till analyzer_version. Befintliga rapporter får 1 (skapade med den
    gamla analysen); nya analyser sätter versionen i tasks.run_analysis.
    Inga befintliga resultat eller poäng ändras.
    """

    dependencies = [
        ('analysis', '0005_siteanalysis_phone'),
    ]

    operations = [
        migrations.AddField(
            model_name='siteanalysis',
            name='analyzer_version',
            field=models.PositiveSmallIntegerField(default=1),
        ),
    ]
