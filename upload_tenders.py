import pandas as pd
from web_requests import get_filtered_permits_with_contacts, NewProjectSiteTypes, get_site_params
from process_project_data import map_data
from datetime import datetime, timedelta, timezone
import dateparser
import os 
import pytz
from datetime import datetime
from zoneinfo import ZoneInfo
from lib.timing import get_execution_window
from dotenv import load_dotenv
import re
import json
import requests  # Ensure requests is imported for the Discord webhook

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

def send_discord_embed(webhook_url: str, title: str, description: str, fields: dict, color: int = 3447003):
    """
    Sends a rich embed message to a Discord channel via webhook.
    """
    if not webhook_url:
        print("Discord webhook URL not configured. Skipping Discord notification.")
        return

    # Convert the dictionary of stats into Discord's expected 'fields' array
    embed_fields = [
        {"name": str(key), "value": str(value), "inline": False} # Changed to False for better list readability
        for key, value in fields.items() if value # Only add field if it has content
    ]

    embed = {
        "title": title,
        "description": description,
        "color": color,
        "fields": embed_fields,
        "timestamp": datetime.now(ZoneInfo("UTC")).isoformat()
    }
    
    data = {"embeds": [embed]}
    
    try:
        response = requests.post(webhook_url, json=data)
        response.raise_for_status()
        print("Discord embed message sent successfully.")
    except requests.exceptions.RequestException as e:
        print(f"Failed to send Discord embed message: {e}")

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

    # --- STATS TRACKING ---
    total_found = 0
    total_success = 0
    total_failed = 0
    
    regions_processed = []
    regions_failed = []
    regions_empty = []
    for config in csv_configs:
        csv_file = config["file_name"]
        city_name = config["city"]

        print(f"\n--- Processing {csv_file} for {city_name.capitalize()} ---")
        
        # 1. Load and filter tenders from the current CSV file
        filtered_tenders_df = load_and_filter_tenders(base_dir, csv_file)
        
        if not filtered_tenders_df.empty:
            # delete open_date_parsed we dont need this TimeStamp Non json parsable field anymore
            num_records = len(filtered_tenders_df)
            total_found += num_records
            if 'open_date_parsed' in filtered_tenders_df.columns:
                del filtered_tenders_df['open_date_parsed']
                print(f"Removed 'open_date_parsed' column from the DataFrame for {csv_file}.")
            else:
                print(f"'open_date_parsed' column not found in the DataFrame for {csv_file} (perhaps already removed or not generated).")

            # apply hardcoded city_name
            filtered_tenders_df['city_name'] = city_name
            
            # Convert DataFrame to a list of dictionaries for map_data
            filtered_entries = filtered_tenders_df.to_dict('records')
            print('filtered_entries', filtered_entries)
            # Call map_data for each CSV file individually
            try:
                authority = config.get("tender_authority")
                map_result = map_data({
                    "data": filtered_entries,
                    "region_name": city_name, # Use the hardcoded city name as the region
                    'hide_tiny_url': os.getenv('HIDE_TINY_URL', False),
                    'file_prefix': 'tenders',
                    'tender_authority': authority, # Dynamic tender authority
                })
               # Extract stats from the map_result dictionary
                current_success = map_result.get("inserted_entries", 0)
                current_failed = map_result.get("failed_entries", 0)
                
                # If map_data hit a total API error, ensure we account for the missing records
                if map_result.get("status") == "api_error" and current_success == 0:
                    current_failed = num_records

                total_success += current_success
                total_failed += current_failed
                
                if current_failed == 0:
                    regions_processed.append(f"✅ **{authority}**: {current_success} sent")
                else:
                    regions_processed.append(f"⚠️ **{authority}**: {current_success} success, {current_failed} failed")
            except Exception as e:
                print(f"❌ Failed to process data for {authority}: {e}")
                total_failed += num_records
                regions_failed.append(f"❌ **{authority}**: Failed ({num_records} records lost)")
                
        else:
            regions_empty.append(authority)
            print(f"No recent tenders found in {csv_file}. No data sent to map_data for {city_name.capitalize()}.")
    # --- SEND DISCORD NOTIFICATION ---
    if total_found > 0 or regions_failed:
        color_code = 3066993 if total_failed == 0 else 15158332 # Green if all good, Red if any failures
        
        embed_fields = {
            "📊 Run Summary": f"**Total Found:** {total_found}\n**Total Success:** {total_success}\n**Total Failed:** {total_failed}",
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
            description="Run completed successfully, but no new tenders were found in any CSVs.",
            fields={"💤 Status": "All regions empty"},
            color=9807270 # Grey
        )
if __name__ == "__main__":
    main()
