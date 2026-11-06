"""
Live "canary" checks for the Single Day Schedule scrapers (RDN, Port Hardy, SRD/SCR, CanadaBuys).

Each test fetches the real page with plain HTTP and asserts that the HTML hooks the
scraper depends on are still there. A failure here usually means the site's layout
or styling changed and the matching scraper needs updating.

Selectors mirror:
  - lib/rdn/scraper.py          (parse_listing / parse_detail are called directly)
  - lib/hardy/scraper.py        (div.post, a.secondary-heading, div.small-heading, div.blog-content)
  - lib/scr/scraper.py          (bid table with Title / Closing date + "Issue Date:", h1.page-title)
  - lib/canadabuys_scraper.py   (results table + detail field selectors)

Run: pytest -m live
"""
import os
import re
import urllib.parse
from io import StringIO

import pandas as pd
import pytest
import requests
from bs4 import BeautifulSoup

pytestmark = pytest.mark.live

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/130.0 Safari/537.36",
    "Accept-Language": "en-CA,en;q=0.9",
}


def fetch(url):
    proxy = os.environ.get("SCRAPER_TEST_PROXY")
    proxies = None
    if proxy:
        if "://" not in proxy:
            proxy = f"http://{proxy}"
        proxies = {"http": proxy, "https": proxy}
    resp = requests.get(url, headers=HEADERS, timeout=45, proxies=proxies)
    assert resp.status_code == 200, f"{url} returned HTTP {resp.status_code}"
    return resp.text


# ---------------------------------------------------------------- RDN

RDN_URL = "https://www.rdn.ca/government/current-bid-opportunities"


@pytest.fixture(scope="module")
def rdn_listing():
    from lib.rdn.scraper import parse_listing
    html = fetch(RDN_URL)
    return html, parse_listing(html)  # raises if the bid view is missing


def test_rdn_listing_structure(rdn_listing):
    html, df = rdn_listing
    if df.empty:
        assert 'view-empty' in html, "RDN: no bids parsed and no 'view-empty' message - list item markup likely changed"
        return
    assert (df['Bid Opportunity'].str.len() > 0).all(), "RDN: bid titles missing"
    assert df['Opportunity Url'].str.startswith("https://www.rdn.ca/").all(), "RDN: bid links missing"
    assert pd.to_datetime(df['Posted'], errors='coerce').notna().all(), f"RDN: 'Post Date' format changed: {df['Posted'].tolist()}"
    assert (df['Closing'].str.len() > 0).all(), "RDN: 'Closing Time' field missing"
    assert df['Bid Opportunity'].str.match(r"^\d{2}-\d{3}").all(), "RDN: titles no longer start with the bid number (ys_permit relies on it)"


def test_rdn_detail_core_fields(rdn_listing):
    from lib.rdn.scraper import parse_detail
    _, df = rdn_listing
    if df.empty:
        pytest.skip("RDN has no bids posted right now")
    url = df.iloc[0]['Opportunity Url']
    details = parse_detail(fetch(url))
    assert details['description'], f"RDN: description not found on {url}"
    assert details['email'], f"RDN: contact email not found on {url}"
    assert details['contact_name'], f"RDN: contact name not found on {url}"


# ---------------------------------------------------------- Port Hardy

PORT_HARDY_URL = "https://porthardy.ca/municipal-hall/staff/tender-and-bid-opportunities/"


@pytest.fixture(scope="module")
def port_hardy_soup():
    return BeautifulSoup(fetch(PORT_HARDY_URL), "html.parser")


def test_port_hardy_listing_structure(port_hardy_soup):
    assert port_hardy_soup.find('div', class_='post-list'), "Port Hardy: 'post-list' container missing"
    posts = port_hardy_soup.find_all('div', class_='post')
    assert posts, "Port Hardy: no div.post entries found - layout likely changed"
    for post in posts:
        heading = post.find('a', class_='secondary-heading')
        assert heading and heading.get('href', '').startswith('http'), "Port Hardy: a.secondary-heading link missing"
        date_div = post.find('div', class_='small-heading')
        assert date_div, "Port Hardy: div.small-heading (posted date) missing"
        posted = date_div.get_text(strip=True).replace('Posted:', '').strip()
        assert pd.notna(pd.to_datetime(posted, errors='coerce')), f"Port Hardy: posted date format changed: {posted!r}"


def test_port_hardy_detail_structure(port_hardy_soup):
    link = port_hardy_soup.find('div', class_='post').find('a', class_='secondary-heading')['href']
    soup = BeautifulSoup(fetch(link), "html.parser")
    content = soup.find('div', class_='blog-content')
    assert content, f"Port Hardy: div.blog-content missing on {link}"
    assert content.find('p') and content.get_text(strip=True), f"Port Hardy: no paragraph text in blog-content on {link}"


# ------------------------------------------------------------ SRD (scr)

SRD_URL = "https://www.srd.ca/government/bid-opportunities"


def _srd_table(html):
    soup = BeautifulSoup(html, "html.parser")
    view = soup.find('div', class_='view-bid-opportunities')
    assert view, "SRD: bid opportunities view missing"
    return view, view.find('table')


def test_srd_listing_structure():
    # The scraper hits the default (Open) view; when nothing is open there's no table at all.
    view, table = _srd_table(fetch(SRD_URL))
    if table is None:
        assert view.find(class_='view-empty'), "SRD: no table and no empty-results message - layout changed"
        return
    df = pd.read_html(StringIO(str(table)))[0]
    assert 'Title' in df.columns and 'Closing date' in df.columns, f"SRD: table headers changed: {list(df.columns)}"
    assert df['Title'].str.contains('Issue Date:').all(), "SRD: 'Issue Date:' missing from Title column"
    # Open bids must link to a detail page or the scraper can't enrich them
    rows = table.select('tbody tr')
    missing = [r.td.get_text(" ", strip=True)[:60] for r in rows if not r.td.find('a', href=True)]
    assert not missing, f"SRD: open bids without a detail link: {missing}"


def test_srd_table_format_with_all_statuses():
    # Closed bids keep the table populated year-round, so this always exercises the layout.
    _, table = _srd_table(fetch(f"{SRD_URL}?s=&type=All&status=All"))
    assert table is not None, "SRD: bid table missing even with all statuses"
    df = pd.read_html(StringIO(str(table)))[0]
    assert {'Title', 'Type', 'Status', 'Closing date'} <= set(df.columns), f"SRD: table headers changed: {list(df.columns)}"
    issue_dates = df['Title'].str.split('Issue Date:').str[1].str.strip()
    assert pd.to_datetime(issue_dates, errors='coerce').notna().all(), "SRD: 'Issue Date' format changed"


# ------------------------------------------------------------ CanadaBuys

CANADABUYS_FILTERS = {
    "search_filter": "", "pub[2]": "2", "status[87]": "87",
    "location[1925]": "1925", "location[1556]": "1556", "location[1563]": "1563",
    "location[1594]": "1594", "location[1618]": "1618", "location[1580]": "1580",
    "location[1593]": "1593", "Apply_filters": "Apply filters",
    "record_per_page": "50", "current_tab": "t", "words": "",
}
CANADABUYS_URL = "https://canadabuys.canada.ca/en/tender-opportunities?" + urllib.parse.urlencode(CANADABUYS_FILTERS)


@pytest.fixture(scope="module")
def canadabuys_links():
    dfs = pd.read_html(StringIO(fetch(CANADABUYS_URL)), extract_links="all")
    assert dfs, "CanadaBuys: results table missing"
    df = dfs[0]
    columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
    assert columns[0] == 'Title' and 'Category' in columns, f"CanadaBuys: table headers changed: {columns}"
    return [cell[1] for cell in df.iloc[:, 0]
            if isinstance(cell, tuple) and cell[1] and '/en/tender-opportunities' in cell[1]]


def test_canadabuys_listing_structure(canadabuys_links):
    assert canadabuys_links, "CanadaBuys: no tender links in results table"


def test_canadabuys_detail_structure(canadabuys_links):
    url = "https://canadabuys.canada.ca" + canadabuys_links[0]
    soup = BeautifulSoup(fetch(url), "html.parser")
    selectors = {
        'Publication date': '.field--name-field-tender-publication-date time',
        'Closing date': '.closing-date-field .field--item',
        'Notice type': '.views-field-field-tender-notice-type .field-content',
        'Description': '.tender-detail-description',
        'Contact section': '#edit-group-contact-information',
        'Contact email': '.field--name-field-tender-contact-email .field--item',
    }
    missing = [name for name, sel in selectors.items() if not soup.select_one(sel)]
    assert not missing, f"CanadaBuys: selectors no longer match on {url}: {missing}"
    pub = soup.select_one(selectors['Publication date']).get_text(strip=True)
    assert re.match(r"\d{4}/\d{2}/\d{2}", pub), f"CanadaBuys: publication date format changed: {pub!r}"
