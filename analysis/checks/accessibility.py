def check_accessibility(soup) -> dict:
    """Grundläggande tillgänglighetskontroll baserad på parsad HTML."""
    result = {
        'lang': {'found': False, 'value': ''},
        'landmarks': {'found': False, 'count': 0, 'tags': []},
        'skip_nav': {'found': False},
        'images_without_alt': {'count': 0, 'total': 0},
        'interactive_divs': {'count': 0},
        'score': 0,
    }

    pts = 0

    # lang-attribut på <html>
    html_tag = soup.find('html')
    if html_tag and html_tag.get('lang', '').strip():
        result['lang']['found'] = True
        result['lang']['value'] = html_tag['lang']
        pts += 20

    # ARIA-landmarks: <main>, <nav>, <header>, <footer>, <aside>
    landmark_tags = ['main', 'nav', 'header', 'footer', 'aside']
    found_landmarks = []
    for tag in landmark_tags:
        if soup.find(tag):
            found_landmarks.append(tag)
    if found_landmarks:
        result['landmarks']['found'] = True
        result['landmarks']['count'] = len(found_landmarks)
        result['landmarks']['tags'] = found_landmarks
        pts += 20

    # Skip-nav-länk (href med #main, #content, #skip, osv.)
    skip_targets = {'#main', '#content', '#main-content', '#skip', '#skipnav', '#skip-nav'}
    for a in soup.find_all('a', href=True):
        if a['href'].lower() in skip_targets:
            result['skip_nav']['found'] = True
            pts += 15
            break

    # Bilder utan alt-text
    all_images = soup.find_all('img')
    images_without_alt = [
        img for img in all_images
        if not img.get('alt') and img.get('alt') != ''
    ]
    result['images_without_alt']['total'] = len(all_images)
    result['images_without_alt']['count'] = len(images_without_alt)
    if len(all_images) == 0 or len(images_without_alt) == 0:
        pts += 25

    # <div> eller <span> med onclick men utan role
    bad_interactive = soup.find_all(
        lambda tag: tag.name in ('div', 'span')
        and tag.get('onclick')
        and not tag.get('role')
    )
    result['interactive_divs']['count'] = len(bad_interactive)
    if len(bad_interactive) == 0:
        pts += 20

    result['score'] = min(100, pts)
    return result
