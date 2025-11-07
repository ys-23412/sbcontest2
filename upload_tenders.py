import pandas as pd
from web_requests import get_filtered_permits_with_contacts, NewProjectSiteTypes, get_site_params
from process_project_data import map_data
from datetime import datetime, timedelta, timezone
import dateparser
import os 
import pytz

from dotenv import load_dotenv
import re
import json

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
    today = datetime.now(pacific_tz) # Using pytz.utc for consistency with pytz
    # Date filtering logic
    # set today to the start of the day
    today = today.replace(hour=0, minute=0, second=0, microsecond=0)

    
    # The date format in the CSV is tricky, so we'll use dateparser
    # We need to remove the ordinal indicators (st, nd, rd, th) for robust parsing
    print(df['open_date'])
    df['open_date_parsed'] = df['open_date'].apply(
        lambda x: dateparser.parse(re.sub(r'(\d+)(st|nd|rd|th)', r'\1', x)) if isinstance(x, str) else None
    )

    df['open_date_parsed'] = pd.to_datetime(df['open_date_parsed'], utc=True)

    # --- PRINTING THE TYPE INFORMATION ---
    print("--- Type Information for 'open_date_parsed' column ---")
    print(f"The object type of the column is: {type(df['open_date_parsed'])}")
    print(f"The data type (dtype) of the values within the column is: {df['open_date_parsed'].dtype}")
    print("----------------------------------------------------")
    print(df['open_date_parsed'])
    # from datetime import date, timedelta
    # start_date = date(2025, 7, 16)
    # end_date = date(2025, 7, 25)

    # # Filter the DataFrame
    # df_filtered = df[(df['open_date_parsed'].dt.date >= start_date) & 
    #                 (df['open_date_parsed'].dt.date <= end_date)]
    # add address column fill with ''
   

    df_date_only = df['open_date_parsed'].dt.date

    # Convert today's date to Pacific Time (just the date part for comparison)
    today_pst_date = today.astimezone(pacific_tz).date()

    # Calculate tomorrow's date in Pacific Time
    tmmr_pst_date = (today + timedelta(days=1)).astimezone(pacific_tz).date()

    print("today_pst_date", today_pst_date)
    # --- Filtering for the date range ---
    # Use boolean indexing with comparison operators
    # The '&' operator performs a logical AND between the two conditions.
    # make sure the types are the same

    try:
        df_filtered_range = df[
            (df_date_only >= today_pst_date) &
            (df_date_only <= tmmr_pst_date)
        ]

    except Exception as e:
        today_pst_ts = pd.to_datetime(today_pst_date)
        tmmr_pst_ts = pd.to_datetime(tmmr_pst_date)

        print(f"Filtering between {today_pst_ts} and {tmmr_pst_ts}")

        # --- Filtering for the date range ---
        # Now the comparison will work correctly.
        df_filtered_range = df[
            (df_date_only >= today_pst_ts) &
            (df_date_only <= tmmr_pst_ts)
        ]

    print("--- Filtered DataFrame ---")
    print(df_filtered_range)

    df_filtered_range['address'] = ''
    # if any field is NaN set to ''
    df_filtered_range = df_filtered_range.fillna('')
    return df_filtered_range


# def load_and_filter_tenders_fix(base_dir, csv_file):
#     """
#     Loads tenders from a CSV file, cleans column names, and filters for recent entries.
#     """
#     csv_path = os.path.join(base_dir, csv_file)
#     if not os.path.exists(csv_path):
#         print(f"Error: The file {csv_path} was not found.")
#         return pd.DataFrame()

#     df = pd.read_csv(csv_path)
#     df = clean_column_names(df)

#     # Date filtering logic
#     # Assuming the script runs at 5:00 AM, so 'today' is based on the start of the day
#     # today = datetime.now(datetime.timezone.utc)
#     # tmmr = today + timedelta(days=1)
#     # utc_now = datetime.utcnow().replace(tzinfo=pytz.utc)

    
#     # The date format in the CSV is tricky, so we'll use dateparser
#     # We need to remove the ordinal indicators (st, nd, rd, th) for robust parsing
#     print(df['open_date'])
#     df['open_date_parsed'] = df['open_date'].apply(
#         lambda x: dateparser.parse(re.sub(r'(\d+)(st|nd|rd|th)', r'\1', x)) if isinstance(x, str) else None
#     )

#     df['open_date_parsed'] = pd.to_datetime(df['open_date_parsed'], utc=True)

#     # --- PRINTING THE TYPE INFORMATION ---
#     print("--- Type Information for 'open_date_parsed' column ---")
#     print(f"The object type of the column is: {type(df['open_date_parsed'])}")
#     print(f"The data type (dtype) of the values within the column is: {df['open_date_parsed'].dtype}")
#     print("----------------------------------------------------")
#     print(df['open_date_parsed'])
    
#     # Filter rows where the open_date is today or yesterday
#     # df_filtered = df[df['open_date_parsed'].dt.date.isin([today, yesterday])]
#     # df_filtered = df[df['open_date_parsed'].dt.date.isin([today, tmmr])]
#     from datetime import date, timedelta
#     start_date = date(2025, 7, 16)
#     end_date = date(2025, 7, 25)

#     # Filter the DataFrame
#     df_filtered = df[(df['open_date_parsed'].dt.date >= start_date) & 
#                     (df['open_date_parsed'].dt.date <= end_date)]
#     # add address column fill with ''
#     df_filtered['address'] = ''
#     # if any field is NaN set to ''
#     df_filtered = df_filtered.fillna('')

#     return df_filtered

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

    for config in csv_configs:
        csv_file = config["file_name"]
        city_name = config["city"]

        print(f"\n--- Processing {csv_file} for {city_name.capitalize()} ---")
        
        # 1. Load and filter tenders from the current CSV file
        filtered_tenders_df = load_and_filter_tenders(base_dir, csv_file)
        
        if not filtered_tenders_df.empty:
            # delete open_date_parsed we dont need this TimeStamp Non json parsable field anymore
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
            map_data({
                "data": filtered_entries,
                "region_name": city_name, # Use the hardcoded city name as the region
                'hide_tiny_url': os.getenv('HIDE_TINY_URL', False),
                'file_prefix': 'tenders',
                'tender_authority': config.get("tender_authority"), # Dynamic tender authority
            })
        else:
            print(f"No recent tenders found in {csv_file}. No data sent to map_data for {city_name.capitalize()}.")

if __name__ == "__main__":
    main()
