import pandas as pd
import json
import requests
from bs4 import BeautifulSoup

base_url = "https://bid.crd.ca"

try:
    response = requests.get(f"{base_url}/contracts-rfps/current")
    response.raise_for_status()
    soup = BeautifulSoup(response.text, 'html.parser')

    all_merged_dfs = []

    tables = soup.find_all('table')

    if not tables:
        print("No tables found on the page.")
    else:
        for i, table in enumerate(tables):
            print(f"Processing Table {i+1} for merging links...")
            for list_card_element in soup.find_all(class_='listCard'):
              list_card_element.decompose()
            headers = []
            # Extract headers from thead if available, otherwise from first tr
            if table.find('thead'):
                header_row = table.find('thead').find('tr')
            else:
                header_row = table.find('tr')

            if header_row:
                for th in header_row.find_all(['th', 'td']):
                    headers.append(th.get_text(strip=True))
            else:
                print(f"Could not find headers for Table {i+1}. Skipping.")
                continue

            table_rows_data = []
            body_rows = table.find('tbody').find_all('tr') if table.find('tbody') else table.find_all('tr')

            # Adjust body_rows if header was extracted from the first <tr> of the table itself
            if not table.find('thead') and header_row == table.find('tr'):
                body_rows = body_rows[1:]

            for row in body_rows:
                cols = row.find_all(['td', 'th'])
                row_data = {}
                row_links = {} # To store links found in this row

                for col_idx, col in enumerate(cols):
                    col_name = headers[col_idx] if col_idx < len(headers) else f"Column_{col_idx+1}"
                    text_content = col.get_text(strip=True)
                    link_href = None

                    a_tag = col.find('a', href=True)
                    if a_tag:
                        # If a link is found, prioritize its text content for the column value
                        # and store the href in a separate 'Links' entry.
                        row_data[col_name] = a_tag.get_text(strip=True)
                        row_links[col_name] = a_tag['href']
                    else:
                        row_data[col_name] = text_content

                # After processing all columns in a row, add a consolidated 'Links' column
                # This will store a dictionary of original_column_name: link for that column
                # Or you could choose to store just the first link, or a list of all links in the row.
                # For simplicity, let's just add a 'Link' column for the first link found in the row.
                # If multiple links are possible in one row, you might need a more complex structure (e.g., list of links per row).
                # For this specific website, links typically appear in a single column per row.
                
                # Let's try to find a logical column for the link, e.g., 'Title' or 'Description'
                # If no specific mapping, we'll just add a general 'Link' column for the first link found.
                
                # Check if 'Links' column is already in headers based on a known pattern
                if 'Links' not in headers and 'Link' not in headers:
                    # Find the first link in the row_links dictionary and add it to a generic 'Link' column
                    first_link_key = next(iter(row_links), None)
                    if first_link_key:
                        row_data['Link'] = row_links[first_link_key]
                    else:
                        row_data['Link'] = None # No link found in this row

                table_rows_data.append(row_data)

            if table_rows_data:
                merged_df = pd.DataFrame(table_rows_data)

                # Drop rows where the 'Link' column is NaN
                # This assumes we want to drop rows that *don't* have an associated link.
                # If 'Link' column might not exist, ensure to handle it.
                if 'Link' in merged_df.columns:
                    merged_df.dropna(subset=['Link'], inplace=True)
                else:
                    print(f"Warning: 'Link' column not found in Table {i+1}. Skipping NaN drop based on 'Link'.")

                if not merged_df.empty:
                    all_merged_dfs.append(merged_df)
                    print(f"\nMerged DataFrame for Table {i+1} (after dropping NaNs in Link column):")
                    print("\n" + "="*80 + "\n")
                else:
                    print(f"Table {i+1} became empty after dropping rows with no links.")
            else:
                print(f"No data rows found for Table {i+1}.")

except requests.exceptions.RequestException as e:
    print(f"Network or HTTP error occurred: {e}")
    print("Please check your internet connection or the URL.")
except Exception as e:
    print(f"An unexpected error occurred: {e}")
    print("Please ensure the URL is correct and the page contains tables.")

# 'all_merged_dfs' now contains a list of DataFrames, each representing a table
# with an integrated 'Link' column and rows without links dropped.

if all_merged_dfs:
    print("\n--- All Merged DataFrames ---")
    for j, df in enumerate(all_merged_dfs):
        print(f"\nDataFrame {j+1}:")
        print(df.to_string()) # Using to_string() to ensure full DataFrame is printed if large
else:
    print("\nNo merged DataFrames were successfully created.")



def parse_table_info(table):
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

def parse_table_by_headers(table):
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
  
def parse_container(container_bid):
    # Find all tables
    tables = container_bid.find_all("table")
    tables_data = {}
    for idx, table in enumerate(tables):
        table_id = table.get('id') or f"table_{idx}"
        print("table is", table)
        if idx == 0:
            tables_data[table_id] = parse_table_info(table)
        else:
          tables_data[table_id] = parse_table_by_headers(table)
    # Extract rest of the text content not in tables (for context)
    for table in tables:
        table.extract()

    # feed in content_text to grab description follow up
    project_description = get_project_description_follow_up(str(container_bid))
    content_text = container.get_text(separator="\n", strip=True)
    content_text = ''
    return {
        "tables": tables_data,
        "content_text": content_text,
        "project_description": project_description
    }

def get_project_description_follow_up(html_content):
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
                    combined_text_parts.append(current_element.get_text(strip=True))
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

print("Now we are going to iterate across column in pandas")
df = all_merged_dfs[0]
for relative_url in df['Link']:
  bid_url = f"{base_url}{relative_url}"
  print("bid_url", bid_url)
  html_bid = requests.get(bid_url).text

  soup_bid = BeautifulSoup(html_bid, "html.parser")

  # Try to find the main content area based on your order of preference
  container = soup_bid.find("div", class_="main-content")
  if not container:
      container = soup_bid.find("div", id="contentWrapper")
  if not container:
      container = soup_bid.find("div", class_="sf_cols")

  if container:
      result = parse_container(container)
      print("Found container:")
      # print(json.dumps(result, indent=2))
      print(result)
  else:
      print("No container found!")
  break