import json
import os
import platform
import re
from datetime import date, datetime
import traceback
from zoneinfo import ZoneInfo
import dateparser
from dateutil.relativedelta import relativedelta
import pandas as pd
import requests
from unidecode import unidecode
from lib.discord import send_discord_embed, send_discord_message
from lib.timing import filter_tenders_by_last_run
from process_project_data import get_project_type_id

FILE_DIR = os.environ.get("FILE_DIR") or "screenshots_porthardy"

def _map_porthardy_tender_entry(tender_record: dict, params: dict, city_mapping: dict) -> dict:
    """
    Maps the parsed Port Hardy tender data into the required system payload structure.
    """
    entry = {}
    ys_body = {}

    ys_component_id = os.getenv('YS_COMPONENTID', 10)
    hide_tiny_url_str = params.get('hide_tiny_url', False)
    hide_tiny_url = str(hide_tiny_url_str).lower() == 'true'
    
    # 1. Map top-level 'entry' fields
    # Prefer full description from the detail page, fallback to the brief list description
    description = tender_record.get('full_description', '')
    if not description or str(description).lower() == 'nan':
        description = tender_record.get('Brief Description', '')
        
    try:
        description = unidecode(str(description))
    except Exception:
        pass

    entry['ys_description'] = description[:97].replace("'", "''")
    
    # Extract bid opportunity reference (e.g. "RFP 1220-20-621-2026")
    try:
        bid_opportunity = tender_record.get('Bid Opportunity', '')
        parts = bid_opportunity.split(' ')
        if len(parts) >= 2 and parts[0] in ['RFP', 'RFQ', 'RFI', 'ITQ', 'ITT']:
             entry['ys_permit'] = f"{parts[0]} {parts[1]}"
        else:
             entry['ys_permit'] = bid_opportunity.split(' ', 1)[0]
    except Exception:
        entry['ys_permit'] = description[:20]
        
    entry['ys_component'] = int(ys_component_id)

    # Set City Location
    matched_city = "Port Hardy"
    entry['city_name'] = matched_city
    entry['ys_address'] = matched_city

    # 2. Map 'ys_body' fields
    # Format the project name, clean up dashes, cap length
    raw_project = re.sub(r'\s*-\s*', '-', description).replace('–', '-')
    ys_body['ys_project'] = unidecode(raw_project[:97])
    
    ys_body['ys_sector'] = 'Public'
    ys_body['ys_reference'] = entry['ys_permit']
    ys_body['ys_tender_authority'] = 'District of Port Hardy'
    ys_body['ys_documents_drawings_link'] = tender_record.get('Opportunity Url', '')
    
    # Include the scraped contact info
    contact_name = tender_record.get('contact_name', '')
    email = tender_record.get('email', '')
    enquiries = []
    if contact_name and str(contact_name).lower() != 'nan':
        enquiries.append(f"{contact_name}")
    if email and str(email).lower() != 'nan':
        enquiries.append(f"Email: {email}")
    ys_body['ys_enquiries'] = " | ".join(enquiries)

    # Determine stage based on title
    if 'RFQ' in bid_opportunity:
        ys_body['ys_stage'] = 'Request for Qualifications'
    else:
        ys_body['ys_stage'] = 'Request for Proposals'

    # 3. Handle Dates
    # Map the posted date
    parsed_date = tender_record.get('Parsed Date')
    if parsed_date and str(parsed_date) != 'NaT':
        try:
            entry['ys_date'] = datetime.fromisoformat(str(parsed_date).split(' ')[0]).strftime('%Y-%m-%d')
        except:
            entry['ys_date'] = datetime.now().strftime('%Y-%m-%d')
    else:
        entry['ys_date'] = datetime.now().strftime('%Y-%m-%d')
    
    # Map the closing date
    is_windows = platform.system() == "Windows"
    closing_date_str = tender_record.get('closing_date')
    
    if closing_date_str and str(closing_date_str).lower() not in ['nan', 'nat', '']:
        parsed_date_close = dateparser.parse(str(closing_date_str))
        if parsed_date_close:
            fmt = "%#m/%#d/%Y - %#I %p" if is_windows else "%-m/%-d/%Y - %-I %p"
            ys_body['ys_closing'] = parsed_date_close.strftime(fmt)
            review_date_obj = parsed_date_close.date() + relativedelta(months=+1)
            entry['review_date'] = review_date_obj.strftime("%Y-%m-%d")

    entry['project_step_id'] = 1001

    fmt_date = date.today().strftime("%B %d/%y")
    ys_body['ys_no_tiny_urls'] = hide_tiny_url
    ys_body['ys_internal_note'] = f"LA - {fmt_date} AUTOBOT"
    entry['ys_body'] = ys_body

    return {'entry': entry}


def process_and_send_porthardy_tenders(params: dict):
    """
    Maps, packages, and sends the extracted District of Port Hardy 
    tender data to the APIs, and tracks success/failure via Discord.
    """
    tender_records = params.get('data', [])
    discord_webhook_url = os.getenv('DISCORD_WEBHOOK_URL')
    api_url = os.getenv('YS_APIURL', 'http://localhost')
    user_id = os.getenv('YS_USERID', '2025060339')
    agent_id = os.getenv('YS_AGENTID', 'AutoHarvest')
    
    # Hardcoded values for Port Hardy
    region_name = "District of Port Hardy"
    city_name = "Port Hardy"
    file_prefix = "porthardy_tender"

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
    
    # Filter records by posted field, make sure date is today pst time
    pst_tz = ZoneInfo("America/Vancouver")
    today_pst = datetime.now(pst_tz).date()
    filtered_records = []

    for record in tender_records:
        parsed_date_str = record.get('Parsed Date')
        posted_str = record.get('Posted')
        
        record_date = None
        
        try:
            # Prefer 'Parsed Date' (e.g., '2026-03-24')
            if parsed_date_str and str(parsed_date_str) != 'NaT':
                # Strip off time component if present
                date_only_str = str(parsed_date_str).split(' ')[0]
                record_date = datetime.fromisoformat(date_only_str).date()

                print("what is record_date", record_date)
            # Fallback to textual 'Posted' date (e.g., 'March 24, 2026')
            elif posted_str:
                record_date = datetime.strptime(posted_str, "%b %d, %Y").date()
            else:
                continue # Skip if no date info is present
                
            if record_date == today_pst:
                filtered_records.append(record)
        except ValueError as e:
            print(f"⚠️ Warning: Date parsing failed for record '{record.get('Bid Opportunity', 'Unknown')}'. Error: {e}")
            continue

    tender_records = filtered_records
    city_mapping = {}
    final_mapped_data = []
    # 2. Map the Extracted Records
    for record in tender_records:
        try:
            mapped_result = _map_porthardy_tender_entry(record, params, city_mapping)
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
            opp_id = record.get('Bid Opportunity', 'Unknown ID')
            print(f"⚠️ Failed to map Port Hardy tender {opp_id}. Error: {e}")

    total_found = len(final_mapped_data)
    total_success = 0
    total_failed = 0

    if total_found == 0:
        print("No new tenders found for today, or all records failed mapping. Exiting.")
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
    main_csv = f"{FILE_DIR}/porthardy_enriched_bids.csv"
    if not os.path.exists(main_csv):
        print(f"Error: The file {main_csv} was not found.")
        # if saturday, ignore the errors else raise
        weekday = datetime.now().weekday()
        print("Weekday:", weekday)
        if datetime.now().weekday() == 5 or datetime.now().weekday() == 6:
            print("Ignoring error on Saturday or Sunday.")
            exit(0)
        # if file porthardy_new_bids_raw.csv is available then just assume no new bids
        if os.path.exists(f"{FILE_DIR}/porthardy_new_bids_raw.csv"):
            print("Ignoring error as likely no new entries were found.")
            exit(0)
        raise ValueError("No File Found")
    else:
        print(f"Processing {main_csv}")
        try:
            tender_records = pd.read_csv(main_csv)
        except pd.errors.EmptyDataError:
            exit(0)
        # make into json objects
        tender_records = tender_records.to_dict('records')
        params = {
            'data': tender_records,
            'hide_tiny_url': os.getenv('HIDE_TINY_URL', False),
        }
        try:
            # we dont want to reupload the entire file if anything goes wrong
            process_and_send_porthardy_tenders(params)
        except Exception as e:
            print(f"❌ An unexpected error occurred: {e}")
            try:
                discord_webhook_url = os.getenv('DISCORD_WEBHOOK_URL')
                send_discord_embed(
                    webhook_url=discord_webhook_url,
                    title="🤖 Port Hardy Harvester: Failure",
                    description="Csv processing failed, csv should exist.",
                    fields={"💤 Status": "BAD THINGS HAPPENED"},
                    color=9807270 # Grey
                )
            except Exception as e:
                print(f"❌ An unexpected error occurred: {e}")