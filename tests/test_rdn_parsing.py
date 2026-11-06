"""
Offline tests for the RDN scraper / data processor.

Fixtures in tests/fixtures/ are trimmed copies of the live rdn.ca pages (Nov 2026).
If the site changes, re-save them and update these expectations.
"""
from pathlib import Path

import pandas as pd
from bs4 import BeautifulSoup

from lib.rdn.scraper import BASE_URL, LISTING_URL, _parse_contact, parse_detail, parse_listing

FIXTURES = Path(__file__).parent / "fixtures"


def _fixture(name):
    return (FIXTURES / name).read_text(encoding="utf-8")


def test_listing_url_is_new_domain():
    assert LISTING_URL == "https://www.rdn.ca/government/current-bid-opportunities"


def test_parse_listing_columns_and_rows():
    df = parse_listing(_fixture("rdn_listing.html"))

    assert list(df.columns) == ['Bid Opportunity', 'Status', 'Posted', 'Updated', 'Closing', 'Closing ISO', 'Opportunity Url']
    assert len(df) == 3

    first = df.iloc[0]
    assert first['Bid Opportunity'] == "26-040 Regional Employment Lands Demand & Supply Strategy"
    assert first['Status'] == "Open"
    assert first['Posted'] == "November 4, 2026"
    assert first['Closing'] == "November 20, 2026 at 3:00 PM"
    assert first['Closing ISO'] == "2026-11-20T22:00:00Z"
    assert first['Opportunity Url'] == f"{BASE_URL}/government/current-bid-opportunities/26-040-regional-employment-lands-demand-supply-strategy"

    # Every row needs a link and a parseable post date, or nothing downstream works
    assert df['Opportunity Url'].str.startswith(BASE_URL).all()
    assert pd.to_datetime(df['Posted']).notna().all()


def test_parse_listing_raises_when_view_missing():
    try:
        parse_listing("<html><body><table><tr><td>old layout</td></tr></table></body></html>")
    except ValueError:
        return
    raise AssertionError("parse_listing should fail loudly when the bid view is missing")


def test_parse_listing_empty_view_is_ok():
    df = parse_listing('<div class="view view-bid-opportunities"><div class="view-empty">None</div></div>')
    assert df.empty


def test_parse_detail_multiline_contact():
    details = parse_detail(_fixture("rdn_detail_26-040.html"))

    assert details['description'].startswith("The purpose of this Request for Proposal")
    assert details['contact_name'] == "Angela Buick"
    assert details['job_title'] == "Senior Planner, Long Range Planning"
    assert details['email'] == "abuick@rdn.bc.ca"
    assert details['phone'] == "250-390-6531"
    assert details['document_url'].startswith(f"{BASE_URL}/sites/default/files/")


def test_parse_detail_comma_contact_and_empty_first_paragraph():
    details = parse_detail(_fixture("rdn_detail_26-005.html"))

    assert details['description'].startswith("Between January 1, 2026")
    assert details['contact_name'] == "Kurtis Felker"
    assert details['job_title'] == "Purchasing Manager"
    assert details['email'] == "kfelker@rdn.bc.ca"


def test_parse_contact_old_mailto_layout():
    p = BeautifulSoup(
        '<p>Keona Wiley, Parks Planner<br>Email: <a href="mailto:kwiley@rdn.bc.ca">kwiley@rdn.bc.ca</a></p>',
        "html.parser",
    ).p
    contact = _parse_contact(p)
    assert contact['contact_name'] == "Keona Wiley"
    assert contact['job_title'] == "Parks Planner"
    assert contact['email'] == "kwiley@rdn.bc.ca"


def test_processor_maps_scraped_record():
    """End-to-end: listing + detail -> CSV round trip -> API payload mapping."""
    from lib.rdn.dataprocessor import _get_closing_datetime, _map_rdn_tender_entry

    row = parse_listing(_fixture("rdn_listing.html")).iloc[0].to_dict()
    row['Parsed Date'] = "2026-11-04"
    row.update(parse_detail(_fixture("rdn_detail_26-040.html")))

    # The workflow passes data between jobs as CSV, so mimic that
    from io import StringIO
    buf = StringIO()
    pd.DataFrame([row]).to_csv(buf, index=False)
    buf.seek(0)
    record = pd.read_csv(buf).to_dict('records')[0]

    closing = _get_closing_datetime(record)
    assert (closing.year, closing.month, closing.day, closing.hour) == (2026, 11, 20, 15)

    entry = _map_rdn_tender_entry(record, {}, {})['entry']
    assert entry['ys_permit'] == "26-040"
    assert entry['ys_description'].startswith("The purpose of this Request for Proposal")
    assert entry['review_date'] == "2026-12-20"
    body = entry['ys_body']
    assert body['ys_closing'].startswith("11/20/2026 - 3")
    assert "Angela Buick" in body['ys_enquiries']
    assert "abuick@rdn.bc.ca" in body['ys_enquiries']
    assert body['ys_documents_drawings_link'].startswith(BASE_URL)
