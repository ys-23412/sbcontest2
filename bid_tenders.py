import pandas as pd
import requests
import time
import json
import os
from bs4 import BeautifulSoup
from typing import List, Dict, Any, Iterator
from mappers import process_and_send_tenders
# --- Constants ---
BASE_URL = "https://bid.crd.ca"
BIDS_URL = f"{BASE_URL}/contracts-rfps/current"
REQUEST_DELAY_SECONDS = 0.01  # Delay between fetching detail pages

# --- Main Scraping Functions ---

def fetch_bids_summary(url: str) -> pd.DataFrame:
    """
    Fetches the main bids page and manually parses the primary table into a DataFrame,
    removing interfering elements first.

    Args:
        url: The URL of the main bids listing page.

    Returns:
        A pandas DataFrame containing the summary of bids, including a link to the detail page.
        Returns an empty DataFrame if no table is found or an error occurs.
    """
    print(f"Fetching bid summary from {url}...")
    try:
        response = requests.get(url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        # Decompose 'listCard' elements as they can interfere with table parsing.
        for list_card in soup.find_all(class_='listCard'):
            list_card.decompose()

        table = soup.find('table')
        if not table:
            print("No table found on the page after pre-processing.")
            return pd.DataFrame()

        # Extract headers from the <thead>
        headers = [th.get_text(strip=True) for th in table.select('thead th')]
        if not headers:
            print("Could not find table headers.")
            return pd.DataFrame()

        # Extract data from table rows
        all_rows_data = []
        for row in table.select('tbody tr'):
            cols = row.find_all('td')
            if not cols:
                continue

            row_data = {}
            # Use zip to map header names to column data
            for header, col in zip(headers, cols):
                row_data[header] = col.get_text(strip=True)

            # Find the link specifically within the row
            a_tag = row.find('a', href=True)
            if a_tag:
                row_data['Link'] = f"{BASE_URL}{a_tag['href']}"
            else:
                row_data['Link'] = None
            
            all_rows_data.append(row_data)

        if not all_rows_data:
            print("No data rows found in the table.")
            return pd.DataFrame()

        # Create DataFrame and clean up
        df = pd.DataFrame(all_rows_data)
        df.dropna(subset=['Link'], inplace=True)  # Drop rows without a valid link

        print(f"✅ Successfully found {len(df)} bids with links.")
        return df

    except requests.exceptions.RequestException as e:
        print(f"❌ Error: Network or HTTP error occurred: {e}")
    except Exception as e:
        print(f"❌ An unexpected error occurred while fetching the summary: {e}")

    return pd.DataFrame()


def scrape_bid_details(bids_df: pd.DataFrame) -> Iterator[Dict[str, Any]]:
    """
    Generator function that iterates through bid links, fetches detail pages,
    parses them, and yields the combined data.

    Args:
        bids_df: DataFrame containing bid summaries and links.

    Yields:
        A dictionary containing the combined summary and detailed information for each bid.
    """
    if 'Link' not in bids_df.columns:
        print("Error: DataFrame is missing the 'Link' column.")
        return

    for index, row in bids_df.iterrows():
        bid_url = row['Link']
        print(f"\nProcessing: {row.get('Title', bid_url)}")

        try:
            response = requests.get(bid_url)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")
            
            # The main content area on the detail pages
            container = soup.find("div", class_="main-content")
            if not container:
                container = soup.find("div", id="contentWrapper")
            if not container:
                container = soup.find("div", class_="sf_cols")
            if container:
                # Combine original summary data with newly scraped details
                details = _parse_detail_container(container)
                combined_data = {**row.to_dict(), "Details": details}
                print("combined_data", combined_data)
                yield combined_data
            else:
                print(f"  -> No content container found for {bid_url}")

        except requests.exceptions.RequestException as e:
            print(f"  -> Failed to fetch {bid_url}: {e}")
        
        # Respectful delay between requests
        time.sleep(REQUEST_DELAY_SECONDS)


# --- Helper Parsing Functions for Detail Pages ---

def _parse_table_info(table):
    result = {}

    for row in table.find_all("tr"):
        cells = row.find_all("td")
        for idx, cell in enumerate(cells):
            cell_text = cell.get_text(strip=True)
            # Split by first semicolon
            if ":" in cell_text:
                key, value = cell_text.split(":", 1)
                key = key.strip()
                value = value.strip()
            else:
                key = cell_text.strip()
                value = ""
            if key:  # Only add non-empty keys
                result[key] = value

    return result

def _parse_table_by_headers(table):
    result = []

    # Get headers from thead
    headers = []
    thead = table.find("thead")
    if thead:
        headers = [th.get_text(strip=True) for th in thead.find_all("th")]

    # Iterate over tbody rows
    tbody = table.find("tbody")
    if tbody and headers:
        for row in tbody.find_all("tr"):
            cells = row.find_all(["td", "th"])
            row_dict = {}
            for i, cell in enumerate(cells):
                # Use header if exists, else fallback to index
                key = headers[i] if i < len(headers) else f"col_{i}"
                row_dict[key] = cell.get_text(strip=True)
            result.append(row_dict)

    return result

def _parse_detail_container(container: BeautifulSoup) -> Dict[str, Any]:
    """Parses the main content container of a bid detail page."""
    
    # Extract tables first
    tables = container.find_all("table")
    tables_data = {}
    for idx, table in enumerate(tables):
        # The first table is key-value, subsequent ones have headers
        if idx == 0:
            tables_data[f"info_table"] = _parse_table_info(table)
        else:
            table = _parse_table_by_headers(table)
            if table:
                tables_data[f"table_{idx}"] = table

    # Remove tables from the soup to extract remaining text easily
    for table in tables:
        table.extract()

    description = _get_project_description_follow_up(str(container))

    return {
        "description": description,
        **tables_data
    }


def _get_project_description_follow_up(html_content):
    """
    Finds the "Project Description:" label in the HTML, regardless of case or
    leading/trailing whitespace, and extracts and combines the text content
    of the next two or three siblings or HTML elements, limited to 30 words.

    Args:
        html_content (str): The HTML content as a string.

    Returns:
        str: A single string containing the combined and truncated text from
             the elements following the "Project Description:" label.
             Returns an empty string if the label is not found or no text
             can be extracted.
    """
    soup = BeautifulSoup(html_content, 'html.parser')

    project_description_label = soup.find('div', class_='sfitemFieldLbl',
                                          string=lambda text: text and "project description:" == text.strip().lower())

    if project_description_label:
        combined_text_parts = []
        current_element = project_description_label.next_sibling
        elements_found_count = 0
        
        # Iterate to grab up to 3 relevant elements
        while current_element and elements_found_count < 3:
            if current_element.name:  # Check if it's an actual HTML tag
                if current_element.name == 'br':
                    pass  # Skip <br> tags
                else:
                    combined_text_parts.append(current_element.get_text(strip=True) + " ")
                    elements_found_count += 1
            current_element = current_element.next_sibling

        # Join the extracted parts and then truncate to 30 words
        full_text = " ".join(combined_text_parts)
        words = full_text.split()
        
        if len(words) > 30:
            truncated_text = " ".join(words[:30]) + "..." # Add ellipsis for truncation
        else:
            truncated_text = " ".join(words)
            
        return truncated_text
    return "" # Return empty string if label not found


# --- Main Execution ---

def main():
    """Main function to run the scraper."""
    # 1. Fetch the list of all current bids
    bids_summary_df = fetch_bids_summary(BIDS_URL)

    if bids_summary_df.empty:
        print("No bids found or an error occurred. Exiting.")
        return
    try:
        print("Saving bids_summary.csv...")
        BASE_DIR = os.getenv('BASE_DIR', "screenshots")
        # make data folder if it doesn't exist
        os.makedirs(BASE_DIR, exist_ok=True)
        # make data folder
        os.makedirs('data', exist_ok=True)
        bids_summary_df.to_csv('data/bids_summary.csv')
    except Exception as e:
        print(f"Error saving bids_summary.csv: {e}")
    # 2. Use the generator to process each bid's detail page
    all_bid_data = []
    for bid_details in scrape_bid_details(bids_summary_df):
        all_bid_data.append(bid_details)
        # Pretty-print the result for each bid as it's processed
        print(json.dumps(bid_details, indent=2))

    print(f"\n--- Scraping complete. Processed {len(all_bid_data)} bids. ---")
    
    # Optional: Save all data to a single JSON file
    with open(f"{BASE_DIR}/crd_bids.json", "w") as f:
        json.dump(all_bid_data, f, indent=4)
    # print("All bid data saved to crd_bids.json")
    process_and_send_tenders({
        "data": all_bid_data,
        "region_name": "Capital Regional District", # Use the hardcoded city name as the region
        'hide_tiny_url': os.getenv('HIDE_TINY_URL', False),
        'file_prefix': 'tenders',
        'tender_authority': "Capital Regional District - Purchasing", # Dynamic tender authority
    })

if __name__ == "__main__":
    main()