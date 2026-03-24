import os
import platform
import re
from datetime import datetime
from bs4 import BeautifulSoup
import dateparser
from dateutil.relativedelta import relativedelta
from unidecode import unidecode

# Assuming dash_pattern, _map_tender_type_to_stage, etc., are imported from your lib

def extract_rdn_tender_data(html_content: str) -> dict:
    """
    Parses the raw HTML from the RDN procurement page to extract key tender details.
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # 1. Extract Title & Opportunity ID
    title_elem = soup.find('h1', class_='title')
    title = title_elem.text.strip() if title_elem else ""
    
    # Assuming ID is the first token (e.g., "26-019")
    opp_id = title.split(' ')[0] if title else ""
    
    # 2. Extract Closing Date (using the ISO datetime attribute for accuracy)
    closing_elem = soup.find('time', class_='datetime')
    closing_date_str = closing_elem['datetime'] if closing_elem else ""
    
    # 3. Extract Description
    body_elem = soup.find('div', class_='field--name-body')
    description_text = body_elem.text.strip() if body_elem else ""
    
    # 4. Extract Document Link
    doc_elem = soup.find('div', class_='views-field-field-documents')
    doc_link = ""
    if doc_elem:
        a_tag = doc_elem.find('a')
        if a_tag and 'href' in a_tag.attrs:
            # Append base URL if it's a relative path
            href = a_tag['href']
            doc_link = href if href.startswith('http') else f"https://www.rdn.bc.ca{href}"
            
    return {
        'Opportunity ID': opp_id,
        'Opportunity Description': title,
        'Description Body': description_text,
        'Closing Date and Time (Pacific Time)': closing_date_str,
        'Opportunity Url': doc_link,
        'Organization (Issued by)': 'Regional District of Nanaimo',
        'Type': 'Request for Proposal' # Explicitly stated in the description
    }

def _map_rdn_tender_entry(tender_record: dict, params: dict, city_mapping: dict) -> dict:
    """
    Maps the parsed RDN tender data into the required system payload structure.
    """
    entry = {}
    ys_body = {}

    ys_component_id = os.getenv('YS_COMPONENTID', 10)
    opp_id = tender_record.get('Opportunity ID', '')
    
    # 1. Map top-level 'entry' fields
    description = tender_record.get('description', '')
    bid_opportunity = ''
    try:
        description = unidecode(description)
    except Exception:
        pass

    entry['ys_description'] = description[:97].replace("'", "''")
    # bid opportunity , split by first space
    try:
        bid_opportunity = tender_record.get('Bid Opportunity', '')
        bid_opportunity = bid_opportunity.split(' ', 1)[0]
        entry['ys_permit'] = bid_opportunity
    except Exception:
        entry['ys_permit'] = description
        pass
    entry['ys_component'] = int(ys_component_id)

    # Set City Location (Defaulting to Nanaimo for RDN if not found via city_mapping)
    matched_city = "Nanaimo RD" # Or run through find_bcbid_city_match(tender_record, city_mapping)
    entry['city_name'] = matched_city
    entry['ys_address'] = matched_city

    # 2. Map 'ys_body' fields
    # Format the project name, clean up dashes, cap length
    raw_project = re.sub(r'\s*-\s*', '-', description).replace('–', '-')
    ys_body['ys_project'] = unidecode(raw_project[:97])
    
    ys_body['ys_sector'] = 'Public'
    ys_body['ys_reference'] = entry['ys_permit']
    ys_body['ys_tender_authority'] = tender_record.get('Organization (Issued by)', '')
    ys_body['ys_documents_drawings_link'] = tender_record.get('Opportunity Url', '')
    
    # Include the scraped description body as enquiries/extra info
    contact_name = tender_record.get('contact_name', '')
    job_title = tender_record.get('job_title', '')
    email = tender_record.get('email', '')
    enquiries = []
    if job_title:
        enquiries.append(f"{job_title} -")
    if contact_name:
        enquiries.append(f"{contact_name}")
    if email:
        enquiries.append(f"Phone: {email}")
    ys_body['ys_enquiries'] = " ".join(enquiries)

    tender_type = tender_record.get('Type', '')
    ys_body['ys_stage'] = tender_type # Hardcoded to Request for Proposal in extractor

    # 3. Handle Dates
    # For RDN, we only have closing date in the HTML provided, issue date might be inferred by runtime
    entry['ys_date'] = datetime.now().strftime('%Y-%m-%d') # Fallback to today if issue date isn't on page
    
    is_windows = platform.system() == "Windows"
    closing_date_str = tender_record.get('Parsed Date')
    
    if closing_date_str:
        parsed_date_close = dateparser.parse(closing_date_str)
        if parsed_date_close:
            if is_windows:
                fmt = "%#m/%#d/%Y - %#I %p"
            else:
                fmt = "%-m/%-d/%Y - %-I %p"
            
            ys_body['ys_closing'] = parsed_date_close.strftime(fmt)
            review_date_obj = parsed_date_close.date() + relativedelta(months=+1)
            entry['review_date'] = review_date_obj.strftime("%Y-%m-%d")

    return {
        'entry': entry,
        'ys_body': ys_body
    }