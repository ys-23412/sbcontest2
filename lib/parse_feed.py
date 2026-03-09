import pandas as pd
from bs4 import BeautifulSoup
import requests

def parse_rss_to_dataframe(xml_content):
    """Parses XML RSS content and returns a Pandas DataFrame."""
    soup = BeautifulSoup(xml_content, 'xml')
    items = soup.find_all('item')
    
    data = []
    for item in items:
        # Extract title and link
        title = item.find('title').text.strip() if item.find('title') else None
        link = item.find('link').text.strip() if item.find('link') else None
        
        # The description contains escaped HTML. Parse it via html.parser to get clean text.
        desc_raw = item.find('description').text if item.find('description') else ""
        description = BeautifulSoup(desc_raw, 'html.parser').text.strip()
        
        # Extract remaining fields
        pub_date = item.find('pubDate').text.strip() if item.find('pubDate') else None
        creator = item.find('creator').text.strip() if item.find('creator') else None
        guid = item.find('guid').text.strip() if item.find('guid') else None
        
        # Append as a dictionary
        data.append({
            'Title': title,
            'Link': link,
            'Description': description,
            'Publish Date': pub_date,
            'Creator': creator,
            'GUID': guid
        })
        
    # Convert list of dictionaries to a Pandas DataFrame
    df = pd.DataFrame(data)
    
    # Check if DataFrame is empty before trying to convert dates
    if not df.empty:
        # Convert the 'Publish Date' column to actual datetime objects for filtering
        df['Publish Date'] = pd.to_datetime(df['Publish Date'])
    
    return df

def main(url, start_date, end_date):
    """Fetches an RSS feed from a URL, parses it, and filters by date."""
    print(f"Fetching RSS feed from: {url}")
    
    try:
        # Fetch the XML data from the URL
        response = requests.get(url, timeout=10)
        response.raise_for_status()  # This will raise an exception for bad HTTP status codes (like 404 or 500)
    except requests.exceptions.RequestException as e:
        print(f"Error fetching the URL: {e}")
        return

    # 1. Parse Data
    xml_data = response.content
    df = parse_rss_to_dataframe(xml_data)

    if df.empty:
        print("No items found in the RSS feed.")
        return

    # 2. Filter DataFrame using Pandas
    # We use pd.to_datetime on the start/end strings to match the column type
    mask = (df['Publish Date'] >= pd.to_datetime(start_date)) & (df['Publish Date'] <= pd.to_datetime(end_date))
    filtered_df = df.loc[mask]

    # 3. Display the result
    print("\n--- Filtered Data ---")
    if filtered_df.empty:
         print(f"No results found between {start_date} and {end_date}.")
    else:
         print(filtered_df[['Publish Date', 'Title']])

if __name__ == "__main__":
    # Define your inputs
    target_url = 'https://rdn.bc.ca/rss'
    filter_start = '2026-03-04'
    filter_end = '2026-03-06'
    
    # Run the main function
    main(target_url, filter_start, filter_end)