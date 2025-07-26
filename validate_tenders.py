import pandas as pd
from datetime import datetime, timedelta
import dateparser
import os
import pytz
import re
import requests # Added for Discord webhook
from dotenv import load_dotenv

def clean_column_names(df):
    """
    Cleans DataFrame column names by converting to lowercase and replacing spaces with underscores.
    """
    cols = df.columns
    new_cols = [col.lower().replace(' ', '_') for col in cols]
    df.columns = new_cols
    return df

def send_discord_message(message, webhook_url):
    """
    Sends a message to a Discord channel via webhook.
    """
    if not webhook_url:
        print("Discord webhook URL not configured. Skipping Discord notification.")
        return

    data = {"content": message}
    try:
        response = requests.post(webhook_url, json=data)
        response.raise_for_status() # Raise an exception for HTTP errors
        print("Discord message sent successfully.")
    except requests.exceptions.RequestException as e:
        print(f"Failed to send Discord message: {e}")

def validate_tenders(base_dir, csv_file, city_name, pacific_tz):
    """
    Loads tenders from a CSV file, cleans column names, and validates for entries
    with open_date or published_date from yesterday or today.
    """
    csv_path = os.path.join(base_dir, csv_file)
    if not os.path.exists(csv_path):
        print(f"File not found: {csv_path}. Skipping validation for {city_name}.")
        return pd.DataFrame(), False

    df = pd.read_csv(csv_path)
    df = clean_column_names(df)

    # Current date and yesterday's date in Pacific Time, start of day
    today = datetime.now(pacific_tz).replace(hour=0, minute=0, second=0, microsecond=0)
    yesterday = today - timedelta(days=1)

    print(f"--- Validating dates for {csv_file} ({city_name}) ---")

    date_column_found = False
    
    # Try 'open_date' first
    if 'open_date' in df.columns:
        df['parsed_date'] = df['open_date'].apply(
            lambda x: dateparser.parse(re.sub(r'(\d+)(st|nd|rd|th)', r'\1', x)) if isinstance(x, str) else None
        )
        date_column_found = True
        print(f"Using 'open_date' for date parsing.")
    else:
        # Fallback to 'publisheddate' if 'open_date' is not present
        # Find the actual column name for 'publisheddate' case-insensitively
        published_date_col = next((col for col in df.columns if col.lower() == 'publisheddate'), None)
        if published_date_col:
            df['parsed_date'] = df[published_date_col].apply(
                lambda x: dateparser.parse(str(x)) if pd.notna(x) else None
            )
            date_column_found = True
            print(f"Using '{published_date_col}' for date parsing.")
        else:
            print(f"Neither 'open_date' nor 'publisheddate' found in {csv_file}. Cannot validate dates.")
            return pd.DataFrame(), False

    # Convert parsed dates to datetime objects and ensure UTC timezone for consistency before conversion
    df['parsed_date'] = pd.to_datetime(df['parsed_date'], utc=True)
    
    # Convert parsed dates to Pacific Time for consistent comparison with `today` and `yesterday`
    df['parsed_date_pst'] = df['parsed_date'].dt.tz_convert(pacific_tz)
    
    # Filter for yesterday or today in Pacific Time
    df_filtered = df[
        (df['parsed_date_pst'].dt.date == today.date()) |
        (df['parsed_date_pst'].dt.date == yesterday.date())
    ]
    
    if not df_filtered.empty:
        print(f"\nSUCCESS: Found {len(df_filtered)} entries in {csv_file} ({city_name}) with open date from yesterday or today:")
        for index, row in df_filtered.iterrows():
            # Get original open_date or publisheddate value if available, otherwise fallback to parsed_date_pst
            original_date_str = row.get('open_date') or row.get('publisheddate') or row['parsed_date_pst'].strftime('%Y-%m-%d %H:%M:%S %Z%z')
            print(f"  - Title: {row.get('title', 'N/A')}, Original Date: {original_date_str}, Parsed Date (PST): {row['parsed_date_pst'].strftime('%Y-%m-%d %H:%M:%S %Z%z')}")
        return df_filtered, True
    else:
        print(f"No entries found in {csv_file} ({city_name}) with open date from yesterday or today.")
        return pd.DataFrame(), False

def main():
    load_dotenv()
    base_dir = os.getenv('BASE_DIR', "screenshots_output")
    discord_webhook_url = os.getenv('DISCORD_WEBHOOK_URL')

    csv_configs = [
        {"file_name": "bonfire_victoria_with_links.csv", "city": "victoria"},
        {"file_name": "bonfire_saanich_with_links.csv", "city": "saanich"},
        {"file_name": "bonfire_north_cowichan_with_links.csv", "city": "north cowichan"},
        {"file_name": "bonfire_cvrd_with_links.csv", "city": "cowichan valley rd"},
        {"file_name": "bonfire_fnha_with_links.csv", "city": "first nations health authority"},
        {"file_name": "bonfire_bc_transit_with_links.csv", "city": "bc transit"},
        {"file_name": "bonfire_uvic_with_links.csv", "city": "university of victoria"},
        {"file_name": "bonfire_courtenay_with_links.csv", "city": "courtenay"},
        {"file_name": "bonfire_central_saanich_with_links.csv", "city": "central saanich"},
        {"file_name": "bonfire_fraserhealth_with_links.csv", "city": "fraser health"},
        {"file_name": "bonfire_icbc_with_links.csv", "city": "icbc"},
        {"file_name": "bonfire_phsa_with_links.csv", "city": "provincial health services authority"},
        {"file_name": "bonfire_comox_with_links.csv", "city": "comox"},
        {"file_name": "bonfire_islandhealth_with_links.csv", "city": "island health"},
        {"file_name": "bonfire_viu_with_links.csv", "city": "vancouver island university"},
        {"file_name": "bids_summary.csv", "city": "crd tenderes"}
    ]

    pacific_tz = pytz.timezone('America/Los_Angeles')

    print("--- Starting Tender Validation Script ---")

    total_files_processed = 0
    any_recent_tenders_found_overall = False

    for config in csv_configs:
        csv_file = config["file_name"]
        city_name = config["city"]

        # Check if the file exists before processing to count only existing files
        if os.path.exists(os.path.join(base_dir, csv_file)):
            total_files_processed += 1
            _, found_recent_in_file = validate_tenders(base_dir, csv_file, city_name, pacific_tz)
            if found_recent_in_file:
                any_recent_tenders_found_overall = True
            else:
                print(f"Validation complete for {csv_file}. No recent entries found for {city_name}.")
        else:
            print(f"File not found: {os.path.join(base_dir, csv_file)}. Skipping this config.")

    print("\n--- Tender Validation Script Finished ---")

    # Send Discord message if no recent tenders were found across multiple files
    if not any_recent_tenders_found_overall and total_files_processed > 1:
        message = "Daily tender validation complete: No recent tenders (yesterday or today) found across multiple processed CSV files."
        send_discord_message(message, discord_webhook_url)
    elif any_recent_tenders_found_overall:
        print("Recent tenders were found in one or more files. No Discord notification needed for 'no matches'.")
    elif total_files_processed <= 1:
        print("Only one or no CSV files were processed; skipping 'no matches' Discord notification.")


if __name__ == "__main__":
    main()