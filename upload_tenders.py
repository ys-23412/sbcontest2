import pandas as pd
from web_requests import get_filtered_permits_with_contacts, NewProjectSiteTypes, get_site_params
from process_project_data import map_data
from datetime import datetime, timedelta
import dateparser
import os 

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

def load_and_filter_tenders(base_dir):
    """
    Loads tenders from a CSV file, cleans column names, and filters for recent entries.
    """
    csv_path = os.path.join(base_dir, "bonfire_victoria_with_links.csv")
    if not os.path.exists(csv_path):
        print(f"Error: The file {csv_path} was not found.")
        return pd.DataFrame()

    df = pd.read_csv(csv_path)
    df = clean_column_names(df)

    # Date filtering logic
    # Assuming the script runs at 5:00 AM, so 'today' is based on the start of the day
    today = datetime.now().date()
    yesterday = today - timedelta(days=1)
    
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
    
    # Filter rows where the open_date is today or yesterday
    df_filtered = df[df['open_date_parsed'].dt.date.isin([today, yesterday])]
    # add address column fill with ''
    df_filtered['address'] = ''
    return df_filtered



def main():
    load_dotenv()
    base_dir = os.getenv('BASE_DIR', "screenshots_output")

    print("--- Starting Tender Processing Script ---")
    if not os.path.exists("data"):
        os.makedirs("data")
    # 1. Load and filter tenders from the CSV file
    filtered_tenders_df = load_and_filter_tenders(base_dir)
    # delete open_date_parsed we dont need this TimeStamp Non json parsable field anymore
    if 'open_date_parsed' in filtered_tenders_df.columns:
        del filtered_tenders_df['open_date_parsed']
        print("Removed 'open_date_parsed' column from the DataFrame.")
    else:
        print("'open_date_parsed' column not found in the DataFrame (perhaps already removed or not generated).")

    # apply city_name
    filtered_tenders_df['city_name'] = 'victoria'
    filtered_entries = filtered_tenders_df.to_dict('records')
    map_data({
        "data": filtered_entries,
        "region_name": 'victoria',
        'hide_tiny_url': os.getenv('HIDE_TINY_URL', False),
        'file_prefix': 'tenders',
        'tender_authority': 'City of Victoria Purchasing',
    })

if __name__ == "__main__":
    main()
