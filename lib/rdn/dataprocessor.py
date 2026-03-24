import json
import os
import platform
import re
from datetime import datetime
import traceback
from bs4 import BeautifulSoup
import dateparser
from dateutil.relativedelta import relativedelta
import pandas as pd
import requests
from unidecode import unidecode
from lib.discord import send_discord_embed, send_discord_message
from lib.timing import filter_tenders_by_last_run
from process_project_data import get_project_type_id
FILE_DIR = os.environ.get("FILE_DIR") or "screenshots_rdn"

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

def process_and_send_rdn_tenders(params: dict):
    """
    Maps, packages, and sends the extracted Regional District of Nanaimo (RDN)
    tender data to the APIs for a single targeted region, and tracks success/failure via Discord.
    """
    tender_records = params.get('data', [])
    discord_webhook_url = os.getenv('DISCORD_WEBHOOK_URL')
    api_url = os.getenv('YS_APIURL', 'http://localhost')
    user_id = os.getenv('YS_USERID', '2025060339')
    agent_id = os.getenv('YS_AGENTID', 'AutoHarvest')
    
    # Hardcoded values since this is scoped specifically to ONE region
    region_name = "Regional District of Nanaimo"
    city_name = "Nanaimo RD"
    file_prefix = "rdn_tender"

    # 1. Early Exit if No Data
    if not tender_records:
        print(f"No tender records to process for {region_name}.")
        send_discord_embed(
            webhook_url=discord_webhook_url,
            title=f"🤖 {region_name} Harvester: Zero Tenders",
            description=f"Run completed successfully, but no new tenders were found.",
            fields={"💤 Status": "No records matched filters or extraction resulted empty."},
            color=9807270 # Grey
        )
        return

    print(f"⚙️ Starting processing for {len(tender_records)} {region_name} tender records...")
    
    tender_records = filter_tenders_by_last_run(tender_records, date_field='Closing')
    # Note: If you have a city_mapping requirement, load it here.
    # city_mapping = load_city_mapping('data/city.csv')
    city_mapping = {}

    final_mapped_data = []

    # 2. Map the Extracted Records
    for record in tender_records:
        try:
            mapped_result = _map_rdn_tender_entry(record, params, city_mapping)
            entry = mapped_result['entry']
            
            # Use external function to classify project_type_id if available
            try:
                project_type_id = get_project_type_id(record) 
                entry['ys_project_type'] = project_type_id
                entry['project_type'] = project_type_id
            except NameError:
                pass # get_project_type_id not imported/available in this scope
            
            final_mapped_data.append(entry)

        except Exception as e:
            traceback.print_exc()
            opp_id = record.get('Opportunity ID', 'Unknown ID')
            print(f"⚠️ Failed to map RDN tender {opp_id}. Error: {e}")

    total_found = len(final_mapped_data)
    total_success = 0
    total_failed = 0

    if total_found == 0:
        print("All records failed mapping. Exiting.")
        return

    # 3. Setup Payload & Save Locally (For Debugging)
    if not os.path.exists("data"):
        os.makedirs("data")

    current_date_str = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
    file_name_base = f"{file_prefix}_{agent_id}_{current_date_str}_{city_name.replace(' ', '_')}"

    fill_payload = [{
        'filename': f"{file_name_base}.json",
        "pdf_type": "api",
        "region": region_name,
        "file_type": "json",
        "data": final_mapped_data,
        'user_id': user_id
    }]

    print(f"\n--- Processing API Submission for: {city_name} ({total_found} records) ---")

    try:
        # --- Step 4: API Fill Phase ---
        fill_url = f"{api_url}/api_fill_entries.php"
        
        with open(f"data/{file_name_base}_with_mapping_all.json", "w", encoding='utf-8') as f:
            json.dump(fill_payload, f, indent=4)
            
        print(f"🚀 Posting to fill API: {fill_url}...")
        fill_resp = requests.post(fill_url, json=fill_payload)
        fill_resp.raise_for_status()
        filled_entries = fill_resp.json()

        # --- Step 5: API Insert Phase ---
        insert_url = f"{api_url}/api_insert_into_data.php"
        
        with open(f"data/{file_name_base}_with_fill.json", "w", encoding='utf-8') as f:
            json.dump(filled_entries, f, indent=4)
            
        print(f"🚀 Posting filled entries to {insert_url}...")
        insert_resp = requests.post(insert_url, json=filled_entries)
        insert_resp.raise_for_status()
        
        # --- Step 6: Validate & Track Results ---
        resp_data = insert_resp.json()
        
        if isinstance(resp_data, dict):
            total_success = len(resp_data.get("inserted_entries", []))
            total_failed = len(resp_data.get("failed_entries", []))
            
            # Handle total API failure with 0 success
            if resp_data.get("status") == "api_error" and total_success == 0:
                total_failed = total_found
        else:
            # Fallback if API doesn't return dictionaries for tracking
            total_success = total_found
            total_failed = 0

        print(f"🎉 {region_name} API submission finished! Success: {total_success}, Failed: {total_failed}")

    except requests.HTTPError as http_err:
        print(f"❌ HTTP error occurred: {http_err}")
        print(f"Response Text: {http_err.response.text}")
        total_failed = total_found
        
    except Exception as e:
        print(f"❌ An unexpected error occurred during API Submission: {e}")
        total_failed = total_found

    # --- Step 7: Send Discord Embed ---
    color_code = 3066993 if total_failed == 0 else 15158332 # Green if all good, Red if any failures
    
    status_icon = "✅" if total_failed == 0 else "⚠️"
    status_msg = f"{status_icon} **{city_name}**: {total_success} success, {total_failed} failed"

    embed_fields = {
        "📊 Run Summary": f"**Total Extracted:** {total_found}\n**Total Success:** {total_success}\n**Total Failed:** {total_failed}",
        "🚀 Region Status": status_msg
    }

    try:
        send_discord_embed(
            webhook_url=discord_webhook_url,
            title=f"🤖 {region_name} Harvester: Run Complete",
            description=f"Automated run finished processing {region_name} tenders.",
            fields=embed_fields,
            color=color_code
        )
    except Exception as e:
        print(f"❌ Failed to send Discord webhook: {e}")

        send_discord_message(
            message=f"🤖 {region_name} Harvester: Run Complete\nAutomated run finished processing {region_name} tenders. exeception",
            webhook_url=discord_webhook_url
        )

# main to read and send files
if __name__ == "__main__":
    main_csv = f"{FILE_DIR}/rdn_enriched_bids.csv"
    if not os.path.exists(main_csv):
        print(f"Error: The file {main_csv} was not found.")
        # if saturday, ignore the errors else raise
        weekday = datetime.now().weekday()
        print("Weekday:", weekday)
        if datetime.now().weekday() == 5 or datetime.now().weekday() == 6:
            print("Ignoring error on Saturday or Sunday.")
            exit(0)
        raise ValueError("No File Found")
    else:
        print(f"Processing {main_csv}")
        tender_records = pd.read_csv(main_csv)
        # make into json objects
        tender_records = tender_records.to_dict('records')
        params = {
            'data': tender_records,
            'hide_tiny_url': os.getenv('HIDE_TINY_URL', False),
        }
        try:
            # we dont want to reupload the entire file if anything goes wrong
            process_and_send_rdn_tenders(params)
        except Exception as e:
            print(f"❌ An unexpected error occurred: {e}")
            try:
                discord_webhook_url = os.getenv('DISCORD_WEBHOOK_URL')
                send_discord_embed(
                    webhook_url=discord_webhook_url,
                    title="🤖 BC Bid Harvester: Failure",
                    description="Csv processing failed, csv should exist.",
                    fields={"💤 Status": "BAD THINGS HAPPENED"},
                    color=9807270 # Grey
                )
            except Exception as e:
                print(f"❌ An unexpected error occurred: {e}")