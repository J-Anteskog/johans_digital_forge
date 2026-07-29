from django.db import migrations


def set_site_domain(apps, schema_editor):
    Site = apps.get_model('sites', 'Site')
    Site.objects.update_or_create(
        pk=1,
        defaults={
            'domain': 'www.johans-digital-forge.se',
            'name': "Johan's Digital Forge",
        },
    )


def reverse_noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('sites', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(set_site_domain, reverse_noop),
    ]
