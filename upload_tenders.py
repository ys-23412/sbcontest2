import pandas as pd
from web_requests import  NewProjectSiteTypes, get_site_params
from process_project_data import map_data
from datetime import datetime, timedelta, timezone
import dateparser
import traceback
import os 
import pytz
from datetime import datetime
from zoneinfo import ZoneInfo
from lib.timing import get_execution_window
from dotenv import load_dotenv
from lib.discord import send_discord_embed
import re
import copy
import time
from lib.utils import unrelated_phrases, unrelated_commodities

# Wait before each retry of failed uploads: 5 minutes after the first failure, then 2 minutes.
# Override with e.g. BONFIRE_RETRY_DELAYS="300,120" (seconds, comma separated).
RETRY_DELAYS_SECONDS = [int(s) for s in os.getenv("BONFIRE_RETRY_DELAYS", "300,120").split(",") if s.strip()]
# After failing twice in a row, the last attempt sends the records under this city/region instead.
FALLBACK_CITY = "victoria"


def send_to_api(job, city_name):
    """Send one region's records through map_data. Raises if the upload failed before inserting."""
    entries = copy.deepcopy(job["entries"])  # map_data may modify the records it is given
    for entry in entries:
        entry['city_name'] = city_name
    return map_data({
        "data": entries,
        "region_name": city_name,
        'hide_tiny_url': os.getenv('HIDE_TINY_URL', False),
        'file_prefix': 'tenders',
        'tender_authority': job["authority"],
    })

def clean_column_names(df):
    """
    Cleans DataFrame column names by converting to lowercase and replacing spaces with underscores.
    """
    cols = df.columns
    new_cols = [col.lower().replace(' ', '_') for col in cols]
    df.columns = new_cols
    return df

def load_and_filter_tenders(base_dir, csv_file):
    """
    Loads tenders from a CSV file, cleans column names, and filters for recent entries.
    """
    csv_path = os.path.join(base_dir, csv_file)
    if not os.path.exists(csv_path):
        print(f"Error: The file {csv_path} was not found.")
        return pd.DataFrame()

    df = pd.read_csv(csv_path)
    df = clean_column_names(df)
    # Assuming the script runs at 5:00 AM, so 'today' is based on the start of the day
    pacific_tz = pytz.timezone('America/Los_Angeles') 
    
    now_pst = datetime.now(ZoneInfo("America/Vancouver"))
    start_time, _ = get_execution_window(now_pst)
    print(df['open_date'])

    start_time_utc = pd.to_datetime(start_time).tz_convert('UTC')
    df['open_date_parsed'] = df['open_date'].apply(
        lambda x: dateparser.parse(re.sub(r'(\d+)(st|nd|rd|th)', r'\1', x)) if isinstance(x, str) else None
    )

    df['open_date_parsed'] = pd.to_datetime(df['open_date_parsed'], utc=True)

    print(f"--- Filtering Strategy ---")
    print(f"Start Time (PST): {start_time}")
    print(f"Filter Boundary (UTC): {start_time_utc}")
    print("--------------------------")

    # 5. Perform Filtering
    # We filter for anything that opened AT or AFTER the last execution start_time
    try:
        df_filtered_range = df[df['open_date_parsed'] >= start_time_utc].copy()
    except Exception as e:
        print(f"Fallback filtering triggered due to: {e}")
        # Ensure comparison is possible if types drifted
        df_filtered_range = df[pd.to_datetime(df['open_date_parsed'], utc=True) >= start_time_utc].copy()
   
    print("--- Filtered DataFrame ---")
    print(df_filtered_range)

    df_filtered_range['address'] = ''
    # if any field is NaN set to ''
    df_filtered_range = df_filtered_range.fillna('')
    return df_filtered_range


def main():
    load_dotenv()
    base_dir = os.getenv('BASE_DIR', "screenshots_output")

    # Define the list of CSV files and their corresponding hardcoded city names
    csv_configs = [
        {"file_name": "bonfire_victoria_with_links.csv", "city": "victoria", "tender_authority": "City of Victoria - Purchasing"},
        {"file_name": "bonfire_saanich_with_links.csv", "city": "saanich", "tender_authority": "District of Saanich - Purchasing"},
        {"file_name": "bonfire_north_cowichan_with_links.csv", "city": "north cowichan", "tender_authority": "North Cowichan - Purchasing"},
        {"file_name": "bonfire_cvrd_with_links.csv", "city": "cowichan valley rd", "tender_authority": "Cowichan Valley Regional District - Purchasing"},
        {"file_name": "bonfire_fnha_with_links.csv", "city": "victoria", "tender_authority": "First Nations Health Authority - Purchasing"}, # Assuming 'saanich' was a typo for city in original, changed to a more descriptive name for FNHA, adjust if 'saanich' is indeed intended for city_name
        {"file_name": "bonfire_bc_transit_with_links.csv", "city": "victoria", "tender_authority": "BC Transit Procurement"}, # Assuming 'victoria' was a typo for city in original, changed to BC Transit
        {"file_name": "bonfire_uvic_with_links.csv", "city": "victoria", "tender_authority": "University of Victoria - Purchasing"}, # Assuming 'victoria' was a typo for city in original, changed to University of Victoria
        {"file_name": "bonfire_courtenay_with_links.csv", "city": "courtenay", "tender_authority": "City of Courtenay - Purchasing"},
        {"file_name": "bonfire_central_saanich_with_links.csv", "city": "central saanich", "tender_authority": "Central Saanich - Purchasing"},
        {"file_name": "bonfire_fraserhealth_with_links.csv", "city": "victoria", "tender_authority": "Fraser Health - Purchasing"},
        {"file_name": "bonfire_icbc_with_links.csv", "city": "victoria", "tender_authority": "ICBC - Purchasing"},
        {"file_name": "bonfire_phsa_with_links.csv", "city": "victoria", "tender_authority": "Provincial Health Services Authority - Purchasing"},
        {"file_name": "bonfire_comox_with_links.csv", "city": "comox", "tender_authority": "Town of Comox - Purchasing"},
        {"file_name": "bonfire_islandhealth_with_links.csv", "city": "victoria", "tender_authority": "Island Health - Purchasing"},
        {"file_name": "bonfire_viu_with_links.csv", "city": "victoria", "tender_authority": "Vancouver Island University - Purchasing"},
    ]
    
    print("--- Starting Tender Processing Script ---")
    if not os.path.exists("data"):
        os.makedirs("data")

    # --- COMPILE EXCLUSION PATTERN ---
    # Combine the lists and escape characters so regex doesn't break on special symbols (like + or -)
    all_unrelated = unrelated_phrases
    exclusion_pattern = '|'.join([re.escape(phrase) for phrase in all_unrelated])

    # --- STATS TRACKING ---
    total_found = 0
    total_success = 0
    total_failed = 0
    
    regions_processed = []
    regions_failed = []
    regions_empty = []
    upload_jobs = []  # regions with records to send, filled while reading the CSVs
    
    for config in csv_configs:
        csv_file = config["file_name"]
        city_name = config["city"]
        authority = config.get("tender_authority")
        print(f"\n--- Processing {csv_file} for {city_name.capitalize()} ---")
        
        # 1. Load and filter tenders by date
        filtered_tenders_df = load_and_filter_tenders(base_dir, csv_file)
        
        if not filtered_tenders_df.empty:
            
            # 2. Filter out unrelated phrases in 'project' and 'description' columns
            # (Note: columns are lowercased by your  function)
            cols_to_check = [col for col in ['project', 'description'] if col in filtered_tenders_df.columns]
            
            if cols_to_check:
                mask = pd.Series(True, index=filtered_tenders_df.index)
                for col in cols_to_check:
                    # Keep rows that DO NOT (~) contain the exclusion pattern in the checked column
                    mask = mask & ~filtered_tenders_df[col].astype(str).str.contains(
                        exclusion_pattern, case=False, na=False, regex=True
                    )
                
                filtered_tenders_df = filtered_tenders_df[mask]

            # Re-check if empty after applying text filters
            if filtered_tenders_df.empty:
                regions_empty.append(authority)
                print(f"All recent tenders in {csv_file} were filtered out due to unrelated phrases.")
                continue

            num_records = len(filtered_tenders_df)
            total_found += num_records
            
            # delete open_date_parsed we dont need this TimeStamp Non json parsable field anymore
            if 'open_date_parsed' in filtered_tenders_df.columns:
                del filtered_tenders_df['open_date_parsed']
                print(f"Removed 'open_date_parsed' column from the DataFrame for {csv_file}.")
            else:
                print(f"'open_date_parsed' column not found in the DataFrame for {csv_file} (perhaps already removed or not generated).")

            # apply hardcoded city_name
            filtered_tenders_df['city_name'] = city_name
            
            # Convert DataFrame to a list of dictionaries; sent after all regions are prepared
            upload_jobs.append({
                "authority": authority,
                "city_name": city_name,
                "entries": filtered_tenders_df.to_dict('records'),
                "num_records": num_records,
            })

        else:
            regions_empty.append(authority)
            print(f"No recent tenders found in {csv_file}. No data sent to map_data for {city_name.capitalize()}.")

    # --- SEND TO API, RETRYING REGIONS WHOSE UPLOAD FAILED ---
    # Attempt 1 for everyone; failures retry after 5 minutes, then after 2 more minutes
    # with FALLBACK_CITY as the city/region. map_data only raises before anything is
    # inserted, so a retry can't create duplicates.
    pending = upload_jobs
    for attempt in range(len(RETRY_DELAYS_SECONDS) + 1):
        is_last = attempt == len(RETRY_DELAYS_SECONDS)
        if attempt > 0:
            delay = RETRY_DELAYS_SECONDS[attempt - 1]
            names = ", ".join(job["authority"] for job in pending)
            note = f" using '{FALLBACK_CITY}' as the city" if is_last else ""
            print(f"\n🔁 Upload retry {attempt}/{len(RETRY_DELAYS_SECONDS)} in {delay // 60}m{delay % 60:02d}s{note} for: {names}")
            time.sleep(delay)

        still_failing = []
        for job in pending:
            authority, num_records = job["authority"], job["num_records"]
            city_for_attempt = FALLBACK_CITY if (is_last and attempt > 0) else job["city_name"]
            try:
                map_result = send_to_api(job, city_for_attempt)
            except Exception as e:
                traceback.print_exc()
                print(f"❌ Attempt {attempt + 1} failed for {authority}: {e}")
                job["last_error"] = str(e)
                still_failing.append(job)
                continue

            print("Map result:", map_result)
            current_success = map_result.get("inserted_entries", 0)
            current_failed = map_result.get("failed_entries", 0)
            # If map_data hit a total API error, ensure we account for the missing records
            if map_result.get("status") == "api_error" and current_success == 0:
                current_failed = num_records

            total_success += current_success
            total_failed += current_failed

            retry_note = f" (attempt {attempt + 1}{', as ' + city_for_attempt if city_for_attempt != job['city_name'] else ''})" if attempt > 0 else ""
            if current_failed == 0:
                regions_processed.append(f"✅ **{authority}**: {current_success} sent{retry_note}")
            else:
                regions_processed.append(f"⚠️ **{authority}**: {current_success} success, {current_failed} failed{retry_note}")

        pending = still_failing
        if not pending:
            break

    for job in pending:
        total_failed += job["num_records"]
        regions_failed.append(
            f"❌ **{job['authority']}**: Failed after {len(RETRY_DELAYS_SECONDS) + 1} attempts "
            f"({job['num_records']} records lost): {job.get('last_error', '')[:120]}"
        )

    # --- SEND DISCORD NOTIFICATION ---
    discord_webhook_url = os.getenv('DISCORD_WEBHOOK_URL')
    if total_found > 0 or regions_failed:
        color_code = 3066993 if total_failed == 0 else 15158332 # Green if all good, Red if any failures
        
        embed_fields = {
            "📊 Run Summary": f"**Total Valid Found:** {total_found}\n**Total Success:** {total_success}\n**Total Failed:** {total_failed}",
        }
        
        if regions_processed:
            embed_fields["🚀 Processed Regions"] = "\n".join(regions_processed)
            
        if regions_failed:
            embed_fields["🚨 Failed Regions"] = "\n".join(regions_failed)
            
        if regions_empty:
            # Join empty regions with a comma to save vertical space
            embed_fields["💤 No New Tenders"] = ", ".join(regions_empty)

        send_discord_embed(
            webhook_url=discord_webhook_url,
            title="🤖 Bonfire Harvester: Run Complete",
            description="Automated run finished processing Bonfire CSVs.",
            fields=embed_fields,
            color=color_code
        )
    else:
        # Optional: Send a lightweight "Nothing found" message, or stay silent to avoid spam.
        send_discord_embed(
            webhook_url=discord_webhook_url,
            title="🤖 Bonfire Harvester: Zero Tenders",
            description="Run completed successfully, but no new or relevant tenders were found in any CSVs.",
            fields={"💤 Status": "All regions empty or filtered out"},
            color=9807270 # Grey
        )
if __name__ == "__main__":
    main()
