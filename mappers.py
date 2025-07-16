import dateparser
from dateutil.relativedelta import relativedelta # Import this

# the non bonfire mappers go here, its fine for now, we can consonslidate and refactor
# at the end.
def _map_tender_type_to_stage(tender_type_str: str) -> str:
    """Maps various tender type strings to a standardized stage name."""
    type_mapping = {
        'ITT': 'Tender Call',
        'RFP': 'Request for Proposals',
        'RFSO': 'Request for Proposals', # Request for Standing Offer maps to RFP
        'RFQ': 'Request for Quotations',
        'NRFP': 'Request for Proposals',
        'RFT': 'Tender Call'
    }
    # Find a key that is contained within the tender_type_str
    for key, value in type_mapping.items():
        if key in tender_type_str.upper():
            return value
    # Return original if no mapping is found
    return tender_type_str

def map_tender_entry(tender_record: dict, params: dict) -> dict:
    """
    Maps a single tender data record to the required API structure.

    Args:
        tender_record: A dictionary containing the scraped data for a single tender.
        params: The original parameters dictionary, used to access config like 'tender_authority'.

    Returns:
        A dictionary containing the mapped 'entry' and 'ys_body' data.
    """
    entry = {}
    ys_body = {}
    details = tender_record.get('Details', {})
    info_table = details.get('info_table', {})

    # 1. Map top-level 'entry' fields
    entry['ys_description'] = tender_record.get('Title', '')[:100].replace("'", "''")
    entry['ys_permit'] = tender_record.get('Project #') or info_table.get('Project ID')
    
    # Use dateparser for robust date handling from various formats
    open_date_str = info_table.get('PublishedDate')
    if open_date_str:
        parsed_open_date = dateparser.parse(open_date_str)
        if parsed_open_date:
            entry['ys_date'] = parsed_open_date.strftime('%Y-%m-%d')

    # 2. Map 'ys_body' fields
    ys_body['ys_project'] = tender_record.get('Title', '').replace(" - ", " &ndash; ", 1)
    ys_body['ys_documents_drawings_link'] = tender_record.get('Link')
    ys_body['ys_sector'] = 'Public' # Tenders are typically public sector
    ys_body['ys_reference'] = entry['ys_permit']
    if params.get('tender_authority'):
        ys_body['ys_tender_authority'] = params['tender_authority']
    
    # Map stage from tender type
    tender_type = info_table.get('Tender Type', '')
    ys_body['ys_stage'] = _map_tender_type_to_stage(tender_type)

    # Format contact info into ys_enquiries
    contact_name = info_table.get('Contact person', '')
    contact_phone = info_table.get('Project manager phone', '')
    enquiries = []
    if contact_name:
        enquiries.append(f"Contact: {contact_name}")
    if contact_phone:
        enquiries.append(f"Phone: {contact_phone}")
    ys_body['ys_enquiries'] = ", ".join(enquiries)

    # Parse and format the closing date
    closing_date_str = tender_record.get('Closing Date')
    if closing_date_str:
        parsed_date_close = dateparser.parse(closing_date_str)
        if parsed_date_close:
            try:
                # Windows-specific format codes ('#')
                ys_body['ys_closing'] = parsed_date_close.strftime("%#m/%#d/%Y - %-I %p")
            except ValueError:
                # Fallback for non-Windows systems
                ys_body['ys_closing'] = parsed_date_close.strftime("%m/%d/%Y - %I %p")
            
            # Set review date and project step
            review_date_obj = parsed_date_close.date() + relativedelta(months=+1)
            entry['review_date'] = review_date_obj.strftime("%Y-%m-%d")
            entry['project_step_id'] = 1001

    return {'entry': entry, 'ys_body': ys_body}