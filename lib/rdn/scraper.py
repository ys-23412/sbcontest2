import asyncio
import os
import re
import time
import random
from datetime import datetime, timedelta
from urllib.parse import urljoin

import pandas as pd
from bs4 import BeautifulSoup
from pydoll.browser.chromium import Chrome
from pydoll.browser.options import ChromiumOptions

FILE_DIR = os.environ.get("FILE_DIR") or "screenshots_rdn"

# The RDN site moved from rdn.bc.ca to rdn.ca (old URLs redirect here).
BASE_URL = "https://www.rdn.ca"
LISTING_URL = f"{BASE_URL}/government/current-bid-opportunities"

EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
PHONE_RE = re.compile(r"(?:Phone|Tel|Telephone)\s*:?\s*([\d().\s-]{7,})", re.IGNORECASE)
# Lines inside the contact paragraph that are not the person's name / title
CONTACT_SKIP_RE = re.compile(r"^(phone|tel|telephone|fax|cell|email|e-mail)\b", re.IGNORECASE)


def get_browser_options(headless=False):
    """
    Returns a configured ChromiumOptions object with stealth settings.
    """
    options = ChromiumOptions()
    current_time = int(time.time())
    number_last = random.randint(3, 10)
    options.browser_preferences = {
        'profile': {
            'last_engagement_time': str(current_time - (number_last * 60 * 60)),  # 3 hours ago
            'exited_cleanly': True,
            'exit_type': 'Normal',
        },
        'safebrowsing': {'enabled': True},
    }

    proxy_url = os.environ.get("PROXY_URL")
    if proxy_url:
        options.add_argument(f'--proxy-server={proxy_url}')

    options.browser_preferences.update({
        'credentials_enable_service': False,
        'profile.password_manager_enabled': False
    })
    return options


# --- Parsing helpers (pure functions, no browser needed) ---

def _field_text(container, field_name):
    """Text of a Drupal field (e.g. 'post-date') inside container, or ''."""
    field = container.find('div', class_=f'field--name-field-{field_name}')
    if not field:
        return ""
    item = field.find(class_='field__item')
    return item.get_text(" ", strip=True) if item else ""


def _field_datetime(container, field_name):
    """ISO datetime attribute of a Drupal date field, or ''."""
    field = container.find('div', class_=f'field--name-field-{field_name}')
    if not field:
        return ""
    time_tag = field.find('time')
    return time_tag.get('datetime', '') if time_tag else ""


def parse_listing(html):
    """
    Parse the RDN "Current Bid Opportunities" page into a DataFrame.

    The page is a Drupal view (div.view-bid-opportunities) of div.list-item cards,
    each holding a title link plus Status / Post Date / Updated Date / Closing Time fields.
    Column names match the old table layout so the data processor keeps working.
    """
    soup = BeautifulSoup(html, 'html.parser')
    view = soup.find('div', class_='view-bid-opportunities')
    if view is None:
        # Fail loudly: an empty result here would be mistaken for "no new bids".
        raise ValueError("RDN bid listing view not found - the page structure has likely changed again.")

    rows = []
    for item in view.find_all('div', class_='list-item'):
        link = item.find('a', class_='list-item__link') or item.find('a', href=True)
        if not link:
            continue
        rows.append({
            'Bid Opportunity': link.get_text(" ", strip=True),
            'Status': _field_text(item, 'status'),
            'Posted': _field_text(item, 'post-date'),
            'Updated': _field_text(item, 'updated-date'),
            'Closing': _field_text(item, 'closing-time'),
            'Closing ISO': _field_datetime(item, 'closing-time'),
            'Opportunity Url': urljoin(BASE_URL, link.get('href', '')),
        })

    columns = ['Bid Opportunity', 'Status', 'Posted', 'Updated', 'Closing', 'Closing ISO', 'Opportunity Url']
    return pd.DataFrame(rows, columns=columns)


def _parse_contact(paragraph):
    """
    Pull name / title / email / phone out of the contact paragraph.

    Handles both layouts seen on RDN pages:
      - "Name, Job Title<br>Email: x@rdn.bc.ca"
      - "<strong>Header:</strong><br>Name<br>Job Title<br>Department<br>Phone: ...<br>Email: ..."
    """
    for strong in paragraph.find_all(['strong', 'b']):
        strong.decompose()  # header such as "Submissions and Questions are to be directed to:"
    for br in paragraph.find_all('br'):
        br.replace_with('\n')

    text = paragraph.get_text()
    lines = [line.strip() for line in text.split('\n') if line.strip()]

    mailto = paragraph.find('a', href=lambda h: h and h.lower().startswith('mailto:'))
    if mailto:
        email = mailto.get_text(strip=True) or mailto['href'][len('mailto:'):]
    else:
        match = EMAIL_RE.search(text)
        email = match.group(0) if match else ""

    phone_match = PHONE_RE.search(text)
    phone = phone_match.group(1).strip() if phone_match else ""

    people_lines = [l for l in lines if not CONTACT_SKIP_RE.match(l) and not EMAIL_RE.search(l)]
    contact_name, job_title = "", ""
    if people_lines:
        first = people_lines[0]
        if ',' in first:
            contact_name, job_title = (part.strip() for part in first.split(',', 1))
        else:
            contact_name = first
            job_title = people_lines[1] if len(people_lines) > 1 else "N/A"

    return {'contact_name': contact_name, 'job_title': job_title, 'email': email, 'phone': phone}


def parse_detail(html):
    """Extract description, contact info and document link from a single bid page."""
    soup = BeautifulSoup(html, 'html.parser')
    for aside in soup.find_all('aside'):
        aside.decompose()

    result = {
        'description': "",
        'contact_name': "",
        'job_title': "",
        'email': "",
        'phone': "",
        'document_url': "",
    }

    body_div = soup.find('div', class_='field--name-body')
    if body_div:
        paragraphs = body_div.find_all('p')
        # First paragraph with real text (some pages start with an empty <p>)
        for p in paragraphs:
            text = p.get_text(" ", strip=True)
            if text:
                result['description'] = text
                break

        contact_p = None
        for p in paragraphs:
            if p.find('a', href=lambda h: h and h.lower().startswith('mailto:')) or EMAIL_RE.search(p.get_text()):
                contact_p = p
                break
        if contact_p is not None:
            result.update(_parse_contact(contact_p))

    doc_field = soup.find('div', class_='views-field-field-documents')
    if doc_field:
        a_tag = doc_field.find('a', href=True)
        if a_tag:
            result['document_url'] = urljoin(BASE_URL, a_tag['href'])

    return result


def _parse_date(date_str):
    try:
        clean_str = str(date_str).replace('Posted:', '').strip()
        return pd.to_datetime(clean_str)
    except Exception:
        return pd.NaT


# --- Main Scraper Logic ---
async def main():
    opts = get_browser_options()

    async with Chrome(options=opts) as browser:
        print("Starting browser...")
        tab = await browser.start()

        if not os.path.exists(FILE_DIR):
            os.mkdir(FILE_DIR)

        print(f"Navigating to {LISTING_URL}...")
        await tab.go_to(LISTING_URL)

        # Give the page time to settle
        await asyncio.sleep(random.uniform(3.0, 5.0))

        page_source = await tab.page_source()

        print("Extracting bid list...")
        target_df = parse_listing(page_source)
        target_df['Parsed Date'] = target_df['Posted'].apply(_parse_date)

        print(f"Found {len(target_df)} total bids.")

        # Define "newly" posted as within the last N days
        days_threshold = 5
        cutoff_date = pd.to_datetime(datetime.now() - timedelta(days=days_threshold))

        new_bids = target_df[target_df['Parsed Date'] >= cutoff_date].copy()
        print(f"Found {len(new_bids)} new bids posted in the last {days_threshold} days.")

        new_bids.to_csv(f"{FILE_DIR}/rdn_new_bids_raw.csv", index=False)

        enriched_results = []

        for index, row in new_bids.iterrows():
            link = row.get('Opportunity Url')
            title = row['Bid Opportunity']
            record = row.to_dict()

            if pd.notna(link) and str(link).startswith('http'):
                print(f"Navigating to new bid: {str(title)[:35]}... -> {link}")
                await tab.go_to(link)

                await asyncio.sleep(random.uniform(2.0, 4.0))

                safe_title = "".join([c for c in str(title) if c.isalnum() or c == ' ']).rstrip()[:25]
                await tab.take_screenshot(f'{FILE_DIR}/bid_{index}_{safe_title.replace(" ", "_")}.png', quality=90, beyond_viewport=True)

                details = parse_detail(await tab.page_source())
                record.update(details)

                print(f"Extracted -> Name: {details['contact_name']} | Title: {details['job_title']} | Email: {details['email']}")

            enriched_results.append(record)

        enriched_df = pd.DataFrame(enriched_results)
        enriched_df.to_csv(f"{FILE_DIR}/rdn_enriched_bids.csv", index=False)

        print(f"Scraping task complete. Saved {len(enriched_df)} enriched records.")


if __name__ == "__main__":
    asyncio.run(main())
