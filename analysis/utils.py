from django.urls import reverse


def build_brief_initial_from_analysis(analysis) -> dict:
    """
    Builds an initial-dict for ProjectBriefForm from a completed SiteAnalysis.
    Never raises — caller is responsible for passing a valid analysis object.

    Score thresholds for has_existing_site:
      >= 80  → not set (site is good, let user decide)
      60–79  → 'unhappy'
      < 60   → 'redo_needed'
    """
    overall = analysis.score_overall or 0

    if overall >= 80:
        has_existing = None
    elif overall >= 60:
        has_existing = 'unhappy'
    else:
        has_existing = 'redo_needed'

    try:
        report_path = reverse('analysis_result', kwargs={'token': analysis.id})
        report_line = f'Rapport: https://www.johans-digital-forge.se{report_path}'
    except Exception:
        report_line = ''

    lines = [
        f'Kommer från webbplatsanalys av {analysis.url}.',
        f'Övergripande betyg: {analysis.grade} ({analysis.score_overall}/100).',
        (
            f'Säkerhet: {analysis.score_security}/100, '
            f'SEO: {analysis.score_seo}/100, '
            f'Prestanda: {analysis.score_performance}/100, '
            f'Mobil: {analysis.score_mobile}/100.'
        ),
        report_line,
    ]
    analysis_summary = '\n'.join(line for line in lines if line)

    initial = {'analysis_summary': analysis_summary}
    if has_existing is not None:
        initial['has_existing_site'] = has_existing
    return initial, analysis_summary
