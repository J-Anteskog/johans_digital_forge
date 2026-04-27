from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='ProjectBrief',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('status', models.CharField(
                    choices=[('new', 'Ny'), ('reviewed', 'Granskad'), ('quoted', 'Offerterad'),
                             ('accepted', 'Accepterad'), ('declined', 'Avböjd')],
                    default='new', max_length=20,
                )),
                ('language', models.CharField(
                    choices=[('sv', 'Svenska'), ('en', 'English')],
                    default='sv', max_length=2,
                )),
                ('referrer', models.CharField(blank=True, max_length=255)),
                ('goals', models.JSONField(default=list)),
                ('goals_other', models.CharField(blank=True, max_length=255)),
                ('budget', models.CharField(
                    choices=[('under_10k', 'Under 10 000 kr'), ('10k_20k', '10 000–20 000 kr'),
                             ('20k_40k', '20 000–40 000 kr'), ('40k_plus', 'Mer än 40 000 kr'),
                             ('unsure', 'Osäker / vill diskutera')],
                    max_length=20,
                )),
                ('timeline', models.CharField(
                    choices=[('asap', 'Snarast (inom 4 veckor)'), ('1_month', 'Inom 1 månad'),
                             ('2_3_months', '2–3 månader'), ('no_rush', 'Ingen brådska'),
                             ('specific', 'Specifikt datum')],
                    max_length=20,
                )),
                ('timeline_specific', models.DateField(blank=True, null=True)),
                ('has_existing_site', models.CharField(
                    choices=[('redo_needed', 'Ja – hemsidan behöver byggas om helt'),
                             ('unhappy', 'Ja – men vi är missnöjda och vill förbättra'),
                             ('no_new', 'Nej – vi bygger från grunden'), ('unsure', 'Osäker')],
                    max_length=20,
                )),
                ('num_pages', models.CharField(
                    choices=[('1', '1 sida (one-pager)'), ('3-5', '3–5 sidor'),
                             ('5-10', '5–10 sidor'), ('10+', 'Mer än 10 sidor'), ('unsure', 'Osäker')],
                    max_length=10,
                )),
                ('features', models.JSONField(default=list)),
                ('features_other', models.CharField(blank=True, max_length=255)),
                ('has_material', models.CharField(
                    choices=[('all', 'Ja – texter och bilder är klara'),
                             ('partial', 'Delvis – vi har en del men behöver hjälp'),
                             ('none', 'Nej – vi behöver hjälp med allt'), ('unsure', 'Osäker')],
                    max_length=10,
                )),
                ('style_preferences', models.JSONField(default=list)),
                ('notes', models.TextField(blank=True)),
                ('contact_name', models.CharField(max_length=100)),
                ('contact_email', models.EmailField(max_length=254)),
                ('contact_phone', models.CharField(blank=True, max_length=30)),
            ],
            options={
                'verbose_name': 'Offertbrief',
                'verbose_name_plural': 'Offertbriefar',
                'ordering': ['-created_at'],
            },
        ),
    ]
