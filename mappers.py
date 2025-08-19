import dateparser
import requests
import os
import json
from process_project_data import get_project_type_id
from datetime import date, timedelta, datetime
from typing import List, Dict
from dateutil.relativedelta import relativedelta # Import this
from zoneinfo import ZoneInfo

from validate_tenders import send_discord_message # Use standard library for timezones
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
        'RFT': 'Tender Call',
        'Tender': 'Tender Call',
        'Request for Standing Offer': 'Standing Offer',
    }
    # Find a key that is contained within the tender_type_str
    for key, value in type_mapping.items():
        if key.upper() in tender_type_str.upper():
            return value
    # Return original if no mapping is found
    return tender_type_str

def _map_tender_entry(tender_record: dict, params: dict) -> dict:
    """
    Maps a single tender data record to the required API structure. For crd bid tenders.

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
    ys_component_id = os.getenv('YS_COMPONENTID', 10)
    hide_tiny_url_str = params.get('hide_tiny_url', False)
    if isinstance(hide_tiny_url_str, str):
        if hide_tiny_url_str.lower() == 'true':
            hide_tiny_url = True
        elif hide_tiny_url_str.lower() == 'false':
            hide_tiny_url = False
        # You might want to add an else here for unexpected string values
        # For now, if it's a string but not 'true' or 'false', it will remain False
    else:
        # If it's not a string (e.g., already a boolean False from the default),
        # just assign its value directly.
        # This covers the case where params.get already returned a boolean False.
        hide_tiny_url = bool(hide_tiny_url_str)
    # 1. Map top-level 'entry' fields
    entry['ys_description'] = tender_record.get('Title', '')[:100].replace("'", "''")
    entry['ys_permit'] = tender_record.get('Project #') or info_table.get('Project ID')
    entry['ys_component'] = int(ys_component_id)
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
            try:
                if parsed_date_close:
                    review_date_obj = parsed_date_close.date() + relativedelta(months=+1)
                else:
                    review_date_obj = date.today() + relativedelta(months=+1)
            except ValueError:
                # Fallback for non-Windows systems
                review_date_obj = date.today() + relativedelta(months=+1)
            entry['review_date'] = review_date_obj.strftime("%Y-%m-%d")
            # hard coded value
            entry['project_step_id'] = 1001
    fmt_date = date.today().strftime("%B %d/%y")
    ys_body['ys_no_tiny_urls'] = hide_tiny_url
    ys_body['ys_internal_note'] = f"LA - {fmt_date} AUTOBOT"
    entry['ys_body'] = ys_body
    return {'entry': entry}

def _map_tender_entry_campbellriver(tender_record: dict, params: dict) -> dict:
    """
    Maps a single tender data record from Campbell River's bid system to the
    required API structure.

    Args:
        tender_record: A dictionary containing the scraped data for a single tender.
        params: The original parameters dictionary, used to access config like 'tender_authority'.

    Returns:
        A dictionary containing the mapped 'entry' and 'ys_body' data.
    """
    entry = {}
    ys_body = {}

    # Helper function to safely get a value from the tender_record
    def get_tender_value(key: str, default='') -> str:
        return str(tender_record.get(key, default)).strip()

    # Get environment variable and parameter settings
    ys_component_id = os.getenv('YS_COMPONENTID', 10)
    hide_tiny_url_str = params.get('hide_tiny_url', False)
    hide_tiny_url = False
    if isinstance(hide_tiny_url_str, str) and hide_tiny_url_str.lower() == 'true':
        hide_tiny_url = True
    elif isinstance(hide_tiny_url_str, bool):
        hide_tiny_url = hide_tiny_url_str
    
    # 1. Map top-level 'entry' fields
    entry['ys_description'] = get_tender_value('Bid Name')[:100].replace("'", "''")
    entry['ys_permit'] = get_tender_value('Bid Number')
    entry['ys_component'] = int(ys_component_id)

    # Use dateparser for robust date handling from various formats
    published_date_str = get_tender_value('Published Date')
    if published_date_str:
        parsed_published_date = dateparser.parse(published_date_str)
        if parsed_published_date:
            entry['ys_date'] = parsed_published_date.strftime('%Y-%m-%d')
    
    # Set a default review date
    review_date_obj = date.today() + relativedelta(months=+1)
    entry['review_date'] = review_date_obj.strftime("%Y-%m-%d")
    entry['project_step_id'] = 1001

    # 2. Map 'ys_body' fields
    ys_body['ys_project'] = get_tender_value('Bid Name').replace(" - ", " &ndash; ", 1)
    ys_body['ys_documents_drawings_link'] = get_tender_value('Documents URL')
    ys_body['ys_sector'] = 'Public'
    ys_body['ys_reference'] = entry['ys_permit']
    if params.get('tender_authority'):
        ys_body['ys_tender_authority'] = params['tender_authority']
    
    # Map stage from Bid Status
    bid_status = get_tender_value('Bid Status')
    ys_body['ys_stage'] = _map_tender_type_to_stage(bid_status)

    # Format bid submission details into ys_enquiries
    submission_type = get_tender_value('Submission Type')
    submission_address = get_tender_value('Submission Address')
    
    enquiries_info = []
    if submission_type:
        enquiries_info.append(f"Submission Type: {submission_type}")
    if submission_address and submission_address != "Online Submissions Only":
        enquiries_info.append(f"Submission Address: {submission_address}")
    
    # Use Question Deadline for an enquiries date
    question_deadline = get_tender_value('Question Deadline')
    if question_deadline:
        enquiries_info.append(f"Question Deadline: {question_deadline}")
        
    ys_body['ys_enquiries'] = ", ".join(enquiries_info)

    # Map the description to ys_description_full
    ys_body['ys_description_full'] = get_tender_value('Description')

    # Format the closing date
    closing_date_str = get_tender_value('Bid Closing Date')
    if closing_date_str:
        parsed_date_close = dateparser.parse(closing_date_str)
        if parsed_date_close:
            try:
                # Windows-specific format codes ('#')
                ys_body['ys_closing'] = parsed_date_close.strftime("%#m/%#d/%Y - %-I %p")
            except ValueError:
                # Fallback for non-Windows systems
                ys_body['ys_closing'] = parsed_date_close.strftime("%m/%d/%Y - %I %p")
    
    # Additional fields from the data
    ys_body['ys_bid_number'] = get_tender_value('Bid Number')
    ys_body['ys_bid_type'] = get_tender_value('Bid Type')
    ys_body['ys_classification'] = get_tender_value('Bid Classification')
    ys_body['ys_language'] = get_tender_value('Language for Bid Submissions')

    fmt_date = date.today().strftime("%B %d/%y")
    ys_body['ys_no_tiny_urls'] = hide_tiny_url
    ys_body['ys_internal_note'] = f"LA - {fmt_date} AUTOBOT"
    
    entry['ys_body'] = ys_body
    return {'entry': entry}

def _filter_campbell_tenders_by_recent_date(tender_records: List[Dict]) -> List[Dict]:
    """
    Filters a list of tender records to include only those published
    today or yesterday.

    Args:
        tender_records: A list of raw tender record dictionaries.

    Returns:
        A new list containing only the tender records published on
        the required dates.
    """
    pst_timezone = ZoneInfo("America/Vancouver") # Use a specific IANA timezone for PST
    
    # Get the current datetime in PST
    now_pst = datetime.now(pst_timezone)
    today_pst = now_pst.date()
    # 1. Define the date range
    today = date.today()
    # yesterday = today - timedelta(days=1)
    target_dates = [today_pst, today]

    print(f"Filtering records for dates: {today} and {today_pst}")
    
    filtered_records = []

    # 2. Loop through each record and check its PublishedDate
    for record in tender_records:
        date_str = record.get('Published Date')

        if not date_str:
            continue

        # 3. Parse the date and compare
        try:
            parsed_datetime = dateparser.parse(date_str)
            if parsed_datetime and parsed_datetime.date() in target_dates:
                filtered_records.append(record)
        except Exception as e:
            # Handle potential parsing errors if necessary
            print(f"Could not parse date for record. Error: {e}")

    print(f"Found {len(filtered_records)} matching records.")
    return filtered_records

def _filter_tenders_by_recent_date(tender_records: List[Dict]) -> List[Dict]:
    """
    Filters a list of tender records to include only those published
    today or yesterday.

    Args:
        tender_records: A list of raw tender record dictionaries.

    Returns:
        A new list containing only the tender records published on
        the required dates.
    """
    pst_timezone = ZoneInfo("America/Vancouver") # Use a specific IANA timezone for PST
    
    # Get the current datetime in PST
    now_pst = datetime.now(pst_timezone)
    today_pst = now_pst.date()
    # 1. Define the date range
    today = date.today()
    # yesterday = today - timedelta(days=1)
    target_dates = [today_pst, today]

    print(f"Filtering records for dates: {today} and {today_pst}")
    
    filtered_records = []

    # 2. Loop through each record and check its PublishedDate
    for record in tender_records:
        # Safely access the nested date string
        info_table = record.get('Details', {}).get('info_table', {})
        date_str = info_table.get('PublishedDate')

        if not date_str:
            continue

        # 3. Parse the date and compare
        try:
            parsed_datetime = dateparser.parse(date_str)
            if parsed_datetime and parsed_datetime.date() in target_dates:
                filtered_records.append(record)
        except Exception as e:
            # Handle potential parsing errors if necessary
            print(f"Could not parse date for record. Error: {e}")

    print(f"Found {len(filtered_records)} matching records.")
    return filtered_records


def process_and_send_campbell_tenders(params: dict):
    """
    Orchestrates the mapping, classification, and API submission for tender data.
    
    Workflow:
    1. Maps each raw tender record using `map_tender_entry`.
    2. Classifies the original record to get a `ys_project_type`.
    3. Inserts the `ys_project_type` into the mapped entry.
    4. Packages all entries and sends them to the API endpoints.
    """
    tender_records = params.get('data', [])
    discord_webhook_url = os.getenv('DISCORD_WEBHOOK_URL')
    if not tender_records:
        print("No tender records to process.")
        send_discord_message("No tender records to process for campbell river.", discord_webhook_url)
        return

    api_url = os.getenv('YS_APIURL', 'http://localhost')
    user_id = os.getenv('YS_USERID', '2025060339')
    agent_id = os.getenv('YS_AGENTID', 'AutoHarvest')
    file_prefix = params.get('file_prefix', 'tender')
    region_name = params.get('region_name', 'campbell river')
    
    final_mapped_data = []
    print(f"⚙️ Starting processing for {len(tender_records)} tender records...")

    # --- filter tenders by date ---
    tender_records = _filter_campbell_tenders_by_recent_date(tender_records)
    print("records", tender_records)
    # --- Step 1 & 2: Map each record, then classify and insert ys_project_type ---
    for record in tender_records:
        try:
            # Step 1: Map the tender using the existing function
            mapped_result = _map_tender_entry_campbellriver(record, params)
            
            # Step 2: Classify the original record and insert the project type ID
            project_type_id = get_project_type_id(record)
            mapped_result['entry']['ys_project_type'] = project_type_id
            final_mapped_data.append(mapped_result['entry'])

        except Exception as e:
            project_id = record.get('Project #', 'N/A')
            print(f"⚠️ Failed to process tender {project_id}. Error: {e}")

    if not final_mapped_data:
        print("No data was successfully mapped. Exiting.")
        return

    print(f"✅ Successfully mapped and classified {len(final_mapped_data)} records.")

    # --- Step 3: Package and send the data to APIs ---
    current_date_str = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
    file_name_base = f"{file_prefix}_{agent_id}_{current_date_str}_{region_name}"

    # Prepare payload for the 'api_fill_entries.php' endpoint
    fill_payload = [{
        'filename': f"{file_name_base}.json",
        "pdf_type": "api",
        "region": region_name,
        "file_type": "json",
        "data": final_mapped_data,
        'user_id': user_id
    }]
    if not os.path.exists("data"):
        os.makedirs("data")
    try:
        # First API call to fill entries
        fill_url = f"{api_url}/api_fill_entries.php"
        print(f"🚀 Posting data to {fill_url}...")
        # save the output
        with open(f"data/{file_name_base}_with_mapping_all.json", "w") as f:
            json.dump(fill_payload, f, indent=4)
        fill_resp = requests.post(fill_url, json=fill_payload)
        fill_resp.raise_for_status()
        filled_entries = fill_resp.json()

        # Second API call to insert data
        insert_url = f"{api_url}/api_insert_into_data.php"
        with open(f"data/{file_name_base}_with_fill.json", "w") as f:
            json.dump(filled_entries, f, indent=4)
        print(f"🚀 Posting filled entries to {insert_url}...")
        insert_resp = requests.post(insert_url, json=filled_entries)
        insert_resp.raise_for_status()
        
        print("🎉 API submission successful!")
        print(insert_resp.json())
        send_discord_message("🎉 API submission successful! for campbell river", discord_webhook_url)

    except requests.HTTPError as http_err:
        print(f"❌ HTTP error occurred: {http_err}")
        print(f"Response Text: {http_err.response.text}")
        raise e
    except Exception as e:
        print(f"❌ An unexpected error occurred: {e}")
        raise e

def process_and_send_tenders(params: dict):
    """
    Orchestrates the mapping, classification, and API submission for tender data.
    
    Workflow:
    1. Maps each raw tender record using `map_tender_entry`.
    2. Classifies the original record to get a `ys_project_type`.
    3. Inserts the `ys_project_type` into the mapped entry.
    4. Packages all entries and sends them to the API endpoints.
    """
    discord_webhook_url = os.getenv('DISCORD_WEBHOOK_URL')
    tender_records = params.get('data', [])
    if not tender_records:
        print("No tender records to process.")
        send_discord_message("No tender records to process for crd.", discord_webhook_url)
        return

    api_url = os.getenv('YS_APIURL', 'http://localhost')
    user_id = os.getenv('YS_USERID', '2025060339')
    agent_id = os.getenv('YS_AGENTID', 'AutoHarvest')
    file_prefix = params.get('file_prefix', 'tender')
    region_name = params.get('region_name', 'Capital Regional District')
    
    final_mapped_data = []
    print(f"⚙️ Starting processing for {len(tender_records)} tender records...")

    # --- filter tenders by date ---
    tender_records = _filter_tenders_by_recent_date(tender_records)
    print("records", tender_records)
    # --- Step 1 & 2: Map each record, then classify and insert ys_project_type ---
    for record in tender_records:
        try:
            # Step 1: Map the tender using the existing function
            mapped_result = _map_tender_entry(record, params)
            
            # Step 2: Classify the original record and insert the project type ID
            project_type_id = get_project_type_id(record)
            mapped_result['entry']['ys_project_type'] = project_type_id

            
            final_mapped_data.append(mapped_result['entry'])

        except Exception as e:
            project_id = record.get('Project #', 'N/A')
            print(f"⚠️ Failed to process tender {project_id}. Error: {e}")

    if not final_mapped_data:
        print("No data was successfully mapped. Exiting.")
        return

    print(f"✅ Successfully mapped and classified {len(final_mapped_data)} records.")

    # --- Step 3: Package and send the data to APIs ---
    current_date_str = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
    file_name_base = f"{file_prefix}_{agent_id}_{current_date_str}_{region_name}"

    # Prepare payload for the 'api_fill_entries.php' endpoint
    fill_payload = [{
        'filename': f"{file_name_base}.json",
        "pdf_type": "api",
        "region": region_name,
        "file_type": "json",
        "data": final_mapped_data,
        'user_id': user_id
    }]
    if not os.path.exists("data"):
        os.makedirs("data")
    try:
        # First API call to fill entries
        fill_url = f"{api_url}/api_fill_entries.php"
        print(f"🚀 Posting data to {fill_url}...")
        # save the output
        with open(f"data/{file_name_base}_with_mapping_all.json", "w") as f:
            json.dump(fill_payload, f, indent=4)
        fill_resp = requests.post(fill_url, json=fill_payload)
        fill_resp.raise_for_status()
        filled_entries = fill_resp.json()

        # Second API call to insert data
        insert_url = f"{api_url}/api_insert_into_data.php"
        with open(f"data/{file_name_base}_with_fill.json", "w") as f:
            json.dump(filled_entries, f, indent=4)
        print(f"🚀 Posting filled entries to {insert_url}...")
        insert_resp = requests.post(insert_url, json=filled_entries)
        insert_resp.raise_for_status()
        
        print("🎉 API submission successful!")
        send_discord_message("🎉 API submission successful crd.", discord_webhook_url)

    except requests.HTTPError as http_err:
        print(f"❌ HTTP error occurred: {http_err}")
        print(f"Response Text: {http_err.response.text}")
        raise e
    except Exception as e:
        print(f"❌ An unexpected error occurred: {e}")
        raise e
