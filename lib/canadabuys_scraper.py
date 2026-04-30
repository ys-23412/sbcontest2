import io
import os
import urllib.parse
import asyncio
import pandas as pd
from pydoll.browser import Chrome

FILE_DIR = os.environ.get("FILE_DIR") or "screenshots_canadabuys"
# 1. Editable Filters
# These are the decoded parameters from your CanadaBuys URL.
# You can modify the values (e.g., change "record_per_page" to "100") 
# or remove keys entirely to change your search scope.
filters = {
    "search_filter": "",
    "pub[2]": "2",                 # Publication type filter
    "status[87]": "87",            # Status filter
    "location[1925]": "1925",      # Location filters...
    "location[1556]": "1556",
    "location[1563]": "1563",
    "location[1594]": "1594",
    "location[1618]": "1618",
    "location[1580]": "1580",
    "Apply_filters": "Apply filters",
    "record_per_page": "50",       # Number of records to display
    "current_tab": "t",            # Target active tab format
    "words": ""
}

# Base URL for the Tender Opportunities page
base_url = "https://canadabuys.canada.ca/en/tender-opportunities"

# Reconstruct the query string using the editable dictionary
query_string = urllib.parse.urlencode(filters)
target_url = f"{base_url}?{query_string}"

print(f"Target URL constructed:\n{target_url}\n")

# 2. Pydoll Automation Script
async def extract_tables():
    print("Launching Chrome via Pydoll...")
    
    # Initialize the Chrome browser natively with Pydoll (no external webdrivers required)
    async with Chrome() as browser:
        # Start the browser session
        tab = await browser.start()
        
        print("Navigating to the target URL...")
        await tab.go_to(target_url)
        
        # Give the page's dynamic content (tables, dynamic lists) some time to load
        print("Waiting for dynamic content to render...")
        await asyncio.sleep(5) 
        
        # Give the page's dynamic content (tables, dynamic lists) some time to load
        print("Waiting for dynamic content to render...")
        await asyncio.sleep(5) 
        
        print("Extracting page source...")
        # Get the full page source of the rendered DOM
        page_source = await tab.page_source
        
        print("Parsing tables with pandas...")
        try:
            # Wrap in StringIO to avoid pandas FutureWarnings for raw string inputs
            html_buffer = io.StringIO(page_source)
            
            # Read all tables from the page source into a list of DataFrames
            dfs = pd.read_html(html_buffer, extract_links="all")
            
            print(f"\n✅ Successfully extracted {len(dfs)} table(s) as pandas DataFrames.")
            for i, df in enumerate(dfs, 1):
                
                # 1. CLEAN HEADERS: Extract just the text part of the header (ignore ?search_filter URLs)
                df.columns = [col[0] if isinstance(col, tuple) else col for col in df.columns]
                
                # 2. CREATE 'link' COLUMN: Extract the URL from the first column (usually 'Title')
                title_col = df.columns[0]
                df['link'] = df[title_col].apply(lambda x: x[1] if isinstance(x, tuple) else None)
                
                # 3. CLEAN BODY CELLS: Convert all tuple cells back to normal strings (keep text only)
                for col in df.columns:
                    if col != 'link':
                        df[col] = df[col].apply(lambda x: x[0] if isinstance(x, tuple) else x)
                
                # 4. FILTER: Keep only rows where 'link' contains '/en/tender-opportunities'
                # First drop rows where link is None, then filter by the string
                df = df[df['link'].notna()]
                df = df[df['link'].str.contains('/en/tender-opportunities', regex=False)]
                
                # 5. MERGE URL: Prepend the base domain to create clickable links
                base_domain = "https://canadabuys.canada.ca"
                df['link'] = base_domain + df['link']
                
                print(f"\n--- Cleaned Table {i} ---")
                
                # Print a clean preview of specific columns to verify
                # Adjust column names if they differ
                print(df[['Title', 'Category', 'link']].head()) 
                
                # Optional: Export to a CSV spreadsheet
                # df.to_csv(f"tender_results_{i}.csv", index=False)
                # print(f"Saved to tender_results_{i}.csv")
                
        except ValueError as e:
            print(f"\n❌ No tables were found on the page. Error details: {e}")
        # save to csv
        # we expect two tables on that page
        df[1].to_csv(f"{FILE_DIR}/canadabuys_enriched_bids.csv", index=False)

        # https://canadabuys.canada.ca/en/tender-opportunities/tender-notice/cb-935-68737969
        # get more details from the bids
if __name__ == "__main__":
    # Execute the asynchronous main function
    asyncio.run(extract_tables())