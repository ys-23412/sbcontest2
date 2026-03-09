import csv
import traceback
from datetime import date, datetime
import json
import pandas as pd
from dateutil.relativedelta import relativedelta
import os
from typing import Dict, List
from zoneinfo import ZoneInfo
import dateparser
import requests
import unidecode
import re
from lib.discord import send_discord_embed, send_discord_message
from lib.utils import dash_pattern
from lib.timing import get_execution_window
from mappers import _map_tender_type_to_stage
from process_project_data import get_project_type_id

def load_city_mapping(filepath="city.csv") -> dict:
    """Loads city.csv into a dictionary mapped by city_name -> city_id."""
    city_mapping = {}
    try:
        with open(filepath, mode='r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                city_mapping[row['city_name'].strip()] = row['city_id'].strip()
    except Exception as e:
        print(f"Error loading {filepath}: {e}")
    return city_mapping


def find_bcbid_city_match(tender_record: dict, city_mapping: dict) -> str:
    """
    Searches for a valid city name in the 'Organization (Issued for)' or 
    'Organization (Issued by)' fields. Falls back to 'Opportunity Description'.
    """
    check_fields = [
        tender_record.get('Organization (Issued for)', ''),
        tender_record.get('Organization (Issued by)', ''),
        tender_record.get('Opportunity Description', '')
    ]
    
    # Sort cities by length descending so "North Vancouver" matches before "Vancouver"
    sorted_cities = sorted(city_mapping.keys(), key=len, reverse=True)
    
    for field in check_fields:
        if not field or not isinstance(field, str):
            continue
            
        field_lower = field.lower()
        for city_name in sorted_cities:
            # Use regex boundaries \b to ensure we don't match 'Hope' inside 'Hopewell'
            if re.search(rf'\b{re.escape(city_name.lower())}\b', field_lower):
                return city_name
                
    return "victoria" # Default if no match is found

def _filter_bcbid_tenders_by_last_run(tender_records: List[Dict]) -> List[Dict]:
    """
    Filters BC Bid records based on the calculated execution window.
    Looks specifically at 'Issue Date and Time (Pacific Time)'.
    """
    pst_timezone = ZoneInfo("America/Vancouver")
    now_pst = datetime.now(pst_timezone)
    
    start_dt, end_dt = get_execution_window(now_pst)

    print(f"--- BC Bid Run Configuration ({now_pst.strftime('%H:%M')}) ---")
    print(f"Target Window: {start_dt.strftime('%m-%d %H:%M')} TO {end_dt.strftime('%m-%d %H:%M')}")
    
    filtered_records = []

    for record in tender_records:
        date_str = record.get('Issue Date and Time (Pacific Time)')
        if not date_str:
            continue

        try:
            parsed_datetime = dateparser.parse(
                date_str, 
                settings={'TIMEZONE': 'America/Vancouver', 'TO_TIMEZONE': 'America/Vancouver', 'RETURN_AS_TIMEZONE_AWARE': True}
            )
            
            if not parsed_datetime:
                continue
            
            if start_dt < parsed_datetime <= end_dt:
                filtered_records.append(record)
            elif (parsed_datetime.hour == 0 and parsed_datetime.minute == 0):
                is_morning_run = (end_dt.hour == 8)
                if parsed_datetime.date() == end_dt.date() and is_morning_run:
                     filtered_records.append(record)

        except Exception as e:
            print(f"Date parse error on record {record.get('Opportunity ID')}: {e}")

    print(f"BC Bid Filter complete. Kept {len(filtered_records)} records.")
    return filtered_records

def _map_bcbid_tender_entry(tender_record: dict, params: dict, city_mapping: dict) -> dict:
    """
    Maps a single tender data record from BC Bid's system to the required API structure.
    """
    entry = {}
    ys_body = {}

    ys_component_id = os.getenv('YS_COMPONENTID', 10)
    hide_tiny_url_str = params.get('hide_tiny_url', False)
    hide_tiny_url = str(hide_tiny_url_str).lower() == 'true'

    # 1. Map top-level 'entry' fields
    description = tender_record.get('Opportunity Description', '')
    entry['ys_description'] = description[:100].replace("'", "''")
    try:
        entry['ys_description'] = unidecode(entry['ys_description'])
    except Exception as e:
        pass

    entry['ys_permit'] = tender_record.get('Opportunity ID', '')
    entry['ys_component'] = int(ys_component_id)

    # Dates
    issue_date_str = tender_record.get('Issue Date and Time (Pacific Time)')
    if issue_date_str:
        parsed_open_date = dateparser.parse(issue_date_str)
        if parsed_open_date:
            entry['ys_date'] = parsed_open_date.strftime('%Y-%m-%d')

    # Get City Location using the helper logic
    matched_city = find_bcbid_city_match(tender_record, city_mapping)
    entry['city_name'] = matched_city
    entry['ys_address'] = matched_city

    # 2. Map 'ys_body' fields
    ys_body['ys_project'] = re.sub(dash_pattern, '-', description)
    # cap to 90 characters
    ys_body['ys_project'] = ys_body['ys_project'][:99]
    try:
        ys_body['ys_project'] = unidecode(ys_body.get('ys_project', ''))
    except:
        pass
        
    ys_body['ys_sector'] = 'Public'
    ys_body['ys_reference'] = entry['ys_permit']
    
    # Authority (Fallback to 'Issued for' if 'Issued by' is missing)
    org_by = str(tender_record.get('Organization (Issued by)', '')).strip()
    org_for = str(tender_record.get('Organization (Issued for)', '')).strip()
    ys_body['ys_tender_authority'] = org_by if org_by else org_for
    ys_body['ys_documents_drawings_link'] = tender_record.get('Opportunity Url', '')
    
    # Stage
    ys_body['ys_stage'] = _map_tender_type_to_stage(tender_record.get('Type', ''))

    # Build Enquiries
    # enquiries_info = []
    if org_for and org_for != org_by:
        ys_body['ys_enquiries'] = f"Issued For: {org_for}"
    
    # Extra Info for description
    # ys_body['ys_description_full'] = f"Commodities: {tender_record.get('Commodities', 'N/A')}"

    # Parse Closing date
    closing_date_str = tender_record.get('Closing Date and Time (Pacific Time)')
    if closing_date_str:
        parsed_date_close = dateparser.parse(closing_date_str)
        if parsed_date_close:
            try:
                ys_body['ys_closing'] = parsed_date_close.strftime("%#m/%#d/%Y - %-I %p")
            except ValueError:
                ys_body['ys_closing'] = parsed_date_close.strftime("%m/%d/%Y - %I %p")
            
            review_date_obj = parsed_date_close.date() + relativedelta(months=+1)
            entry['review_date'] = review_date_obj.strftime("%Y-%m-%d")

    # Fallback review date
    if 'review_date' not in entry:
        entry['review_date'] = (date.today() + relativedelta(months=+1)).strftime("%Y-%m-%d")
        
    entry['project_step_id'] = 1001

    fmt_date = date.today().strftime("%B %d/%y")
    ys_body['ys_no_tiny_urls'] = hide_tiny_url
    ys_body['ys_internal_note'] = f"LA - {fmt_date} AUTOBOT"
    
    entry['ys_body'] = ys_body

    return {'entry': entry}

def process_and_send_bcbid_tenders(params: dict):
    """
    Orchestrates the mapping, classification, and API submission for BC Bid tender data.
    """
    tender_records = params.get('data', [])
    discord_webhook_url = os.getenv('DISCORD_WEBHOOK_URL')
    api_url = os.getenv('YS_APIURL', 'http://localhost')
    user_id = os.getenv('YS_USERID', '2025060339')
    agent_id = os.getenv('YS_AGENTID', 'AutoHarvest')
    file_prefix = params.get('file_prefix', 'bcbid_tender')
    region_name = params.get('region_name', 'BC Bid Provincial')
    
    if not tender_records:
        print("No BC Bid tender records to process.")
        send_discord_message(f"No tender records to process for {region_name}.", discord_webhook_url)
        return

    # Load City Mapping
    city_mapping = load_city_mapping('data/city.csv')

    print(f"⚙️ Starting processing for {len(tender_records)} BC Bid tender records...")

    # Filter by Execution Window
    tender_records = _filter_bcbid_tenders_by_last_run(tender_records)
    
    final_mapped_data = []

    for record in tender_records:
        try:
            # Map the record using BC Bid logic and inject city_mapping
            mapped_result = _map_bcbid_tender_entry(record, params, city_mapping)
            
            # Note: Ensure get_project_type_id can handle BC Bid dict structure!
            project_type_id = get_project_type_id(record) 
            mapped_result['entry']['ys_project_type'] = project_type_id
            mapped_result['entry']['project_type'] = project_type_id
            
            final_mapped_data.append(mapped_result['entry'])

        except Exception as e:
            traceback.print_exc()
            project_id = record.get('Opportunity ID', 'N/A')
            print(f"⚠️ Failed to process BC Bid tender {project_id}. Error: {e}")


    print(f"✅ Successfully mapped and classified {len(final_mapped_data)} BC Bid records.")
    grouped_data = {}
    # --- Step 3: Group by City and Send Data  and Track Stats ---

    total_found = len(final_mapped_data)
    total_success = 0
    total_failed = 0
    regions_processed = []
    regions_failed = []
    regions_empty = []

    for entry in final_mapped_data:
        # Fallback to 'Various Locations' if city is somehow missing
        city = entry.get('city_name', 'victoria') 
        
        if city not in grouped_data:
            grouped_data[city] = []
        grouped_data[city].append(entry)
    # --- Step 3: Package and send the data to APIs ---
            
    if not os.path.exists("data"):
        os.makedirs("data")

    print(f"📦 Grouped data into {len(grouped_data)} distinct cities/regions.")

    # 2. Iterate through each city and send separate API requests
    for city_name, city_entries in grouped_data.items():
        print(f"\n--- Processing API Submission for: {city_name} ({len(city_entries)} records) ---")
        current_date_str = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
        file_name_base = f"{file_prefix}_{agent_id}_{current_date_str}_{city_name}_{region_name.replace(' ', '_')}"

        fill_payload = [{
            'filename': f"{file_name_base}.json",
            "pdf_type": "api",
            "region": region_name,
            "file_type": "json",
            "data": city_entries,
            'user_id': user_id
        }]

            
        try:
            fill_url = f"{api_url}/api_fill_entries.php"
            num_records = len(city_entries)
            print(f"\n--- Processing API Submission for: {city_name} ({num_records} records) ---")
            with open(f"data/{file_name_base}_with_mapping_all.json", "w") as f:
                json.dump(fill_payload, f, indent=4)
                
            fill_resp = requests.post(fill_url, json=fill_payload)
            fill_resp.raise_for_status()
            filled_entries = fill_resp.json()

            insert_url = f"{api_url}/api_insert_into_data.php"
            with open(f"data/{file_name_base}_with_fill.json", "w") as f:
                json.dump(filled_entries, f, indent=4)
                
            print(f"🚀 Posting filled entries to {insert_url}...")
            insert_resp = requests.post(insert_url, json=filled_entries)
            insert_resp.raise_for_status()
            
            # Attempt to extract exact stats if your API returns them
            resp_data = insert_resp.json()
            if isinstance(resp_data, dict):
                current_success = len(resp_data.get("inserted_entries", []))
                current_failed = len(resp_data.get("failed_entries", []))
            else:
                current_success = num_records
                current_failed = 0
            
            # If total API error
            if isinstance(resp_data, dict) and resp_data.get("status") == "api_error" and current_success == 0:
                current_failed = num_records

            total_success += current_success
            total_failed += current_failed

            if current_failed == 0:
                regions_processed.append(f"✅ **{city_name}**: {current_success} sent")
            else:
                regions_processed.append(f"⚠️ **{city_name}**: {current_success} success, {current_failed} failed")
                
            print(f"🎉 BC Bid API submission successful for {city_name}!")

        except requests.HTTPError as http_err:
            print(f"❌ HTTP error occurred: {http_err}")
            print(f"Response Text: {http_err.response.text}")
            raise http_err
        except Exception as e:
            print(f"❌ An unexpected error occurred: {e}")
            raise e
        
    if total_found > 0 or regions_failed:
        color_code = 3066993 if total_failed == 0 else 15158332 # Green if all good, Red if any failures
        
        embed_fields = {
            "📊 Run Summary": f"**Total Found:** {total_found}\n**Total Success:** {total_success}\n**Total Failed:** {total_failed}",
        }
        
        if regions_processed:
            embed_fields["🚀 Processed Cities"] = "\n".join(regions_processed)
            
        if regions_failed:
            embed_fields["🚨 Failed Cities"] = "\n".join(regions_failed)

        send_discord_embed(
            webhook_url=discord_webhook_url,
            title="🤖 BC Bid Harvester: Run Complete",
            description="Automated run finished processing BC Bid tenders.",
            fields=embed_fields,
            color=color_code
        )
    else:
        send_discord_embed(
            webhook_url=discord_webhook_url,
            title="🤖 BC Bid Harvester: Zero Tenders",
            description="Run completed successfully, but no new tenders were found for BC Bid.",
            fields={"💤 Status": "All regions empty or no records matched date filters."},
            color=9807270 # Grey
        )


if __name__ == "__main__":
    MAIN_DIR = "screenshots"
    # check if csv exists
    if not os.path.exists(f"{MAIN_DIR}/bid_recent.csv"):
        print(f"Error: The file {MAIN_DIR}/bid_recent.csv was not found.")
        raise ValueError("No File Found")
    else:
        print(f"Processing {MAIN_DIR}/bid_recent.csv...")
        tender_records = pd.read_csv(f"{MAIN_DIR}/bid_recent.csv")
        # make into json objects
        tender_records = tender_records.to_dict('records')
        params = {
            'data': tender_records,
            'hide_tiny_url': os.getenv('HIDE_TINY_URL', False),
        }
        try:
            # we dont want to reupload the entire file if anything goes wrong
            process_and_send_bcbid_tenders(params)
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
