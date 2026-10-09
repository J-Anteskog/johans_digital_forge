import json

from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError

from analysis.report import category_label
from analysis.tasks import collect_results
from analysis.validators import validate_target_url


class Command(BaseCommand):
    help = 'Kör analysen mot en URL och skriver ut resultatet (--dry-run: inget sparas i databasen)'
    requires_system_checks = []

    def add_arguments(self, parser):
        parser.add_argument('url')
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Kör alla kontroller men spara ingenting (krävs)',
        )
        parser.add_argument('--json', action='store_true', help='Skriv ut hela results-JSON')

    def handle(self, *args, **options):
        if not options['dry_run']:
            raise CommandError('Endast --dry-run stöds – kommandot sparar aldrig i databasen.')
        try:
            url = validate_target_url(options['url'])
        except ValidationError as e:
            raise CommandError(e.messages[0])

        results = collect_results(url)
        scores = results.pop('scores')

        if options['json']:
            self.stdout.write(json.dumps({'scores': scores, 'results': results},
                                         ensure_ascii=False, indent=2))
            return

        w = self.stdout.write
        w(f'Analys av {url} (analysversion {results["analyzer_version"]}, ej sparad)\n')
        overall = scores['overall']
        sc = results['scoring']
        w(f'Totalbetyg: {overall if overall is not None else "–"}/100 '
          f'(bygger på {sc["measured_count"]} av {sc["category_count"]} kategorier)')
        for key in ('security', 'seo', 'performance', 'mobile', 'headers', 'accessibility'):
            v = scores[key]
            w(f'  {category_label(key, results):<34} {v if v is not None else "ej mätt"}')

        http = results.get('http', {})
        res = results.get('resources') or {}
        img = results.get('images') or {}
        mob = (results.get('mobile') or {}).get('checks', {})
        a11y = results.get('accessibility') or {}
        psp = results.get('pagespeed') or {}

        w('\nDetaljer:')
        w(f'  HTTP {http.get("status_code")} · svarstid {http.get("response_time_ms")} ms · '
          f'HTML {http.get("html_bytes")} byte')
        w(f'  PageSpeed: {psp.get("status")} '
          f'{ {k: v for k, v in psp.items() if k != "status"} }')
        w(f'  CSS/JS: {res.get("css_files")} CSS · {res.get("js_files")} JS '
          f'(egen domän {res.get("css_same_site")}/{res.get("js_same_site")}, '
          f'tredjepart {res.get("css_third_party")}/{res.get("js_third_party")} {res.get("third_party_hosts")}) · '
          f'data:-skript {res.get("inline_data_scripts")} · renderblockerande {res.get("render_blocking_scripts")}')
        w(f'  Bilder: {img.get("total")} totalt · {img.get("with_alt")} med alt · '
          f'{img.get("decorative")} dekorativa (alt="") · {img.get("missing_alt")} saknar alt')
        w('  Mobil: ' + ', '.join(f'{k}={v.get("status")}' for k, v in mob.items()))
        lm = a11y.get('landmarks', {})
        hd = a11y.get('headings', {})
        w(f'  Landmärken: {lm.get("via")} · skip-länk: {a11y.get("skip_nav")}')
        w(f'  Rubriker: {hd.get("count")} st, H1={hd.get("h1_count")}, '
          f'hopp={hd.get("skipped_levels")}, tomma={hd.get("empty_count")}')
        hdr = results.get('headers') or {}
        w(f'  Säkerhetsheaders: {hdr.get("found_count")} av {len(hdr.get("headers", []))} · '
          f'certifikat: {results.get("ssl", {}).get("expiry_date")}')
