import platform
import traceback
from datetime import date, datetime
import json
import pandas as pd
from dateutil.relativedelta import relativedelta
import os
from typing import Dict, List
import dateparser
import requests
import unidecode
import re
from lib.discord import send_discord_embed, send_discord_message
from lib.utils import dash_pattern, unrelated_phrases, unrelated_commodities, unrelated_organizations, \
    load_city_mapping, find_bcbid_city_match, DEFAULT_CITY
from lib.timing import filter_tenders_by_last_run
from mappers import _map_tender_type_to_stage
from process_project_data import get_project_type_id

def canada_buys_city_match(tender_record: dict, city_mapping: dict) -> str:
    """
    Searches for a valid city name primarily in the 'Address' field of CanadaBuys data. 
    Falls back to 'Organization', 'Buying organization(s)', or 'Description'.
    Returns DEFAULT_CITY if no match is found.
    """
    check_fields =[
        tender_record.get('Address', ''),
        tender_record.get('Organization', ''),
        tender_record.get('Buying organization(s)', ''),
        tender_record.get('Description', ''),
        tender_record.get('Title', '')
    ]
    
    # Sort cities by length descending so "North Vancouver" matches before "Vancouver"
    sorted_cities = sorted(city_mapping.keys(), key=len, reverse=True)
    
    for field in check_fields:
        # Ignore empty strings, None types, or pandas "nan" string values
        if not field or not isinstance(field, str) or field.lower() == 'nan':
            continue
            
        field_lower = field.lower()
        for city_name in sorted_cities:
            # Use regex boundaries \b to ensure we don't match 'Hope' inside 'Hopewell'
            if re.search(rf'\b{re.escape(city_name.lower())}\b', field_lower):
                return city_name
                
    return DEFAULT_CITY


def _map_canadabuys_tender_entry(tender_record: dict, params: dict, city_mapping: dict) -> dict:
    """
    Maps a single tender data record from CanadaBuys system to the required API structure.
    """
    entry = {}
    ys_body = {}

    ys_component_id = os.getenv('YS_COMPONENTID', 10)
    hide_tiny_url_str = params.get('hide_tiny_url', False)
    hide_tiny_url = str(hide_tiny_url_str).lower() == 'true'

    link = str(tender_record.get('link', ''))
    opp_id = link.split('/')[-1] if link else ''

    # 1. Map top-level 'entry' fields
    # Use 'Description' if available, otherwise fallback to 'Title'
    description: str = str(tender_record.get('Description', tender_record.get('Title', '')))
    
    if description.startswith(opp_id):
        description = description[len(opp_id):]
    try:
        description = unidecode(description)
    except Exception:
        pass

    entry['ys_description'] = description[:97].replace("'", "''")
    entry['ys_permit'] = opp_id
    entry['ys_component'] = int(ys_component_id)

    # Dates
    issue_date_str = str(tender_record.get('Publication date', ''))
    if issue_date_str and issue_date_str.lower() != 'nan':
        parsed_open_date = dateparser.parse(issue_date_str)
        if parsed_open_date:
            entry['ys_date'] = parsed_open_date.strftime('%Y-%m-%d')

    # Get City Location using helper logic by trying to extract City from Address
    address_str = str(tender_record.get('Address', ''))
    city_guess = ""
    if address_str and address_str.lower() != "nan":
        # Usually address format is "Line, City, Country". We'll grab the second to last part.
        parts = [p.strip() for p in address_str.split(',')]
        if len(parts) >= 2:
            city_guess = parts[-2]
        elif len(parts) == 1:
            city_guess = parts[0]
            
    # Inject guessed city into record so the original helper can evaluate it properly
    tender_record['City'] = city_guess 
    matched_city = canada_buys_city_match(tender_record, city_mapping)
    
    entry['city_name'] = matched_city
    entry['ys_address'] = address_str if address_str and address_str.lower() != "nan" else matched_city

    try:
        address = unidecode(entry.get('ys_address', ''))
    except Exception:
        address = entry.get('ys_address', '')

    # 2. Logic to cap at 75, ensuring we don't break a word
    if len(address) > 75:
        # Find the last space within the first 76 characters
        # (Using 76 ensures that if index 75 is a space, we keep the full 75 chars)
        last_space = address[:76].rfind(' ')
        
        if last_space != -1:
            address = address[:last_space].rstrip()
        else:
            # Fallback: If no space exists at all, force a hard cut at 75
            address = address[:75]

    entry['ys_address'] = address

    # 2. Map 'ys_body' fields
    project_title = str(tender_record.get('Title', ''))
    ys_body['ys_project'] = re.sub(dash_pattern, '-', project_title).replace('–', '-')

    # cap to 90 characters
    ys_body['ys_project'] = ys_body['ys_project'][:97]
    try:
        ys_body['ys_project'] = unidecode(ys_body.get('ys_project', ''))
    except Exception:
        pass
        
    ys_body['ys_sector'] = 'Public'
    ys_body['ys_reference'] = entry['ys_permit']
    
    # Authority
    org_main = str(tender_record.get('Organization', '')).strip()
    org_buying = str(tender_record.get('Buying organization(s)', '')).strip()
    
    # Priority on direct Organization, fallback to Buying organization
    if org_main and org_main.lower() != 'nan':
        ys_body['ys_tender_authority'] = org_main
    else:
        ys_body['ys_tender_authority'] = org_buying if org_buying.lower() != 'nan' else 'Unknown Authority'

    ys_body['ys_documents_drawings_link'] = link

    tender_type = str(tender_record.get('Notice type', ''))
    # Stage
    ys_body['ys_stage'] = _map_tender_type_to_stage(tender_type)

    if ys_body['ys_stage'] == tender_type:
        ys_body['ys_stage'] = 'Request for Proposals'

    # Enquiries Information
    contact_name = str(tender_record.get('Contracting authority name', ''))
    contact_email = str(tender_record.get('Contracting authority email', ''))

    contact_parts =[]
    if contact_name and contact_name.lower() != "nan":
        contact_parts.append(contact_name)
    if contact_email and contact_email.lower() != "nan":
        contact_parts.append(contact_email)
        
    if contact_parts:
        ys_body['ys_enquiries'] = " ".join(contact_parts)
    elif org_buying and org_buying.lower() != "nan":
        ys_body['ys_enquiries'] = f"Buying Org: {org_buying}"
    else:
        ys_body['ys_enquiries'] = "Issued For"
    # cap the size of the enquiries field to 100 characters
    ys_body['ys_enquiries'] = ys_body['ys_enquiries'][:90]
    is_windows = platform.system() == "Windows"
    
    # Parse Closing date
    closing_date_str = str(tender_record.get('Closing date and time', ''))
    if closing_date_str and closing_date_str.lower() != "nan":
        parsed_date_close = dateparser.parse(closing_date_str)
        if parsed_date_close:
            if is_windows:
                fmt = "%#m/%#d/%Y - %#I %p"
            else:
                fmt = "%-m/%-d/%Y - %-I %p"
            
            ys_body['ys_closing'] = parsed_date_close.strftime(fmt)
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


def process_and_send_canadabuys_tenders(params: dict):
    """
    Orchestrates the mapping, classification, and API submission for CanadaBuys tender data.
    """
    tender_records = params.get('data',[])
    discord_webhook_url = os.getenv('DISCORD_WEBHOOK_URL')
    api_url = os.getenv('YS_APIURL', 'http://localhost')
    user_id = os.getenv('YS_USERID', '2025060339')
    agent_id = os.getenv('YS_AGENTID', 'AutoHarvest')
    file_prefix = params.get('file_prefix', 'canadabuys_tender')
    region_name = params.get('region_name', 'victoria')
    
    if not tender_records:
        print("No CanadaBuys tender records to process.")
        send_discord_message(f"No tender records to process for {region_name}.", discord_webhook_url)
        return

    # Load City Mapping
    city_mapping = load_city_mapping('data/city.csv')

    print(f"⚙️ Starting processing for {len(tender_records)} CanadaBuys tender records...")

    # Filter by Execution Window
    tender_records = filter_tenders_by_last_run(tender_records, date_field='Open/amendment date')
    
    # Pre-process keywords for filtering
    unrelated_phrases_lower = [phrase.lower() for phrase in unrelated_phrases]
    unrelated_commodities_lower = [comm.lower() for comm in unrelated_commodities]
    unrelated_organizations_lower =[org.lower() for org in unrelated_organizations]
    
    # Filter out unrelated records
    filtered_tender_records =[]
    for record in tender_records:
        description = str(record.get('Description', '')).lower()
        title = str(record.get('Title', '')).lower()
        desc_title_combined = f"{title} {description}"
        
        org_issued_by = str(record.get('Organization', '')).lower()
        
        # 1. Get raw category/commodity string
        raw_commodity = str(record.get('Category', ''))
        if raw_commodity.lower() == 'nan':
            raw_commodity = ''
            
        # 2. Split on the boundary between a lowercase letter and an uppercase letter
        split_commodities = re.split(r'(?<=[a-z])(?=[A-Z])', raw_commodity)
        split_commodities_lower =[comm.lower() for comm in split_commodities]

        # Check conditions
        is_unrelated_desc = any(phrase in desc_title_combined for phrase in unrelated_phrases_lower)
        is_unrelated_comm = any(comm in unrelated_commodities_lower for comm in split_commodities_lower)
        is_unrelated_org = any(org in org_issued_by for org in unrelated_organizations_lower)
        
        opp_id = record.get('link', 'Unknown').split('/')[-1] if record.get('link') else 'Unknown ID'
        
        if is_unrelated_desc:
            print(f"⏭️ Skipping unrelated tender {opp_id} due to keyword match.")
            print(f"Title/Desc matched exclusion rule.")
        elif is_unrelated_comm:
            print(f"⏭️ Skipping unrelated tender {opp_id} due to exact commodity match.")
            print(f"Commodity: {raw_commodity}\n")
        elif is_unrelated_org:
            print(f"⏭️ Skipping unrelated tender {opp_id} due to excluded organization.")
            print(f"Organization: {record.get('Organization')}\n")
        else:
            filtered_tender_records.append(record)

    # Save filtered tender records to file for debugging
    if not os.path.exists("data"):
        os.makedirs("data")
        
    with open(f'data/{file_prefix}_filtered.json', 'w') as f:
        json.dump(filtered_tender_records, f, indent=4)
        
    print(f"✅ Filtered down to {len(filtered_tender_records)} relevant records from {len(tender_records)}.")
    final_mapped_data =[]

    for record in filtered_tender_records:
        try:
            # Map the record using CanadaBuys logic and inject city_mapping
            mapped_result = _map_canadabuys_tender_entry(record, params, city_mapping)
            
            # Use original project_type mapping helper
            project_type_id = get_project_type_id(record) 
            mapped_result['entry']['ys_project_type'] = project_type_id
            mapped_result['entry']['project_type'] = project_type_id
            
            final_mapped_data.append(mapped_result['entry'])

        except Exception as e:
            traceback.print_exc()
            link_id = record.get('link', 'N/A').split('/')[-1]
            print(f"⚠️ Failed to process CanadaBuys tender {link_id}. Error: {e}")

    print(f"✅ Successfully mapped and classified {len(final_mapped_data)} CanadaBuys records.")
    
    # --- Group by City and Send Data ---
    grouped_data = {}
    total_found = len(final_mapped_data)
    total_success = 0
    total_failed = 0
    regions_processed = []
    regions_failed =[]

    for entry in final_mapped_data:
        # Fallback to 'Various Locations' or base city if missing
        city = entry.get('city_name', 'victoria') 
        
        if city not in grouped_data:
            grouped_data[city] = []
        grouped_data[city].append(entry)

    print(f"📦 Grouped data into {len(grouped_data)} distinct cities/regions.")

    # Iterate through each city and send separate API requests
    for city_name, city_entries in grouped_data.items():
        current_date_str = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
        file_name_base = f"{file_prefix}_{agent_id}_{current_date_str}_{city_name}_{region_name.replace(' ', '_')}"

        fill_payload =[{
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
            
            # Attempt to extract exact stats
            resp_data = insert_resp.json()
            if isinstance(resp_data, dict):
                current_success = len(resp_data.get("inserted_entries",[]))
                current_failed = len(resp_data.get("failed_entries",[]))
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
                regions_failed.append(f"❌ **{city_name}**: {current_failed} failed")
                
            print(f"🎉 CanadaBuys API submission successful for {city_name}!")

        except requests.HTTPError as http_err:
            print(f"❌ HTTP error occurred: {http_err}")
            if hasattr(http_err, 'response'):
                print(f"Response Text: {http_err.response.text}")
            total_failed += len(city_entries)
            regions_failed.append(f"❌ **{city_name}**: HTTP Error")
            
        except Exception as e:
            print(f"❌ An unexpected error occurred: {e}")
            total_failed += len(city_entries)
            regions_failed.append(f"❌ **{city_name}**: Exception {e}")
        
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
            title="🤖 CanadaBuys Harvester: Run Complete",
            description="Automated run finished processing CanadaBuys tenders.",
            fields=embed_fields,
            color=color_code
        )
    else:
        send_discord_embed(
            webhook_url=discord_webhook_url,
            title="🤖 CanadaBuys Harvester: Zero Tenders",
            description="Run completed successfully, but no new tenders were found for CanadaBuys.",
            fields={"💤 Status": "All regions empty or no records matched date filters."},
            color=9807270 # Grey
        )


if __name__ == "__main__":
    FILE_DIR = os.environ.get("FILE_DIR") or "screenshots_canadabuys"
    FILE_NAME = "canadabuys_final_details.csv"
    potential_paths = [
        os.path.join(FILE_DIR, FILE_NAME),    # Check in specific folder
        os.path.join(os.getcwd(), FILE_NAME)  # Check in root directory
    ]

    # Find the first path that actually exists
    OUTPUT_CSV = next((path for path in potential_paths if os.path.exists(path)), None)
    
    # check if csv exists
    if not os.path.exists(OUTPUT_CSV):
        print(f"Error: The file {OUTPUT_CSV} was not found.")
        # if saturday or sunday, ignore the errors else raise
        weekday = datetime.now().weekday()
        print("Weekday:", weekday)
        if weekday in [5, 6]:
            print("Ignoring error on Saturday or Sunday.")
            exit(0)
        raise ValueError("No File Found")
    else:
        print(f"Processing {OUTPUT_CSV}...")
        tender_records = pd.read_csv(OUTPUT_CSV)
        # make into json objects
        tender_records = tender_records.to_dict('records')
        params = {
            'data': tender_records,
            'hide_tiny_url': os.getenv('HIDE_TINY_URL', False),
            'region_name': 'Canada Buys',
            'file_prefix': 'canadabuys_tender'
        }
        try:
            # Prevent re-upload issues with safe execution loop handling
            process_and_send_canadabuys_tenders(params)
        except Exception as e:
            print(f"❌ An unexpected error occurred in __main__: {e}")
            try:
                discord_webhook_url = os.getenv('DISCORD_WEBHOOK_URL')
                send_discord_embed(
                    webhook_url=discord_webhook_url,
                    title="🤖 CanadaBuys Harvester: Failure",
                    description=f"CSV processing failed for {OUTPUT_CSV}.",
                    fields={"🚨 Error": str(e)[:1024]},
                    color=15158332 # Red
                )
            except Exception as d_e:
                print(f"❌ An unexpected error occurred while sending Discord error embed: {d_e}")
