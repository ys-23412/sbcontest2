import io
import os
import urllib.parse
import asyncio
import traceback
from bs4 import BeautifulSoup
import pandas as pd
from pydoll.browser import Chrome

FILE_DIR = os.environ.get("FILE_DIR") or "screenshots_canadabuys"
RAW_CSV = os.path.join(FILE_DIR, "canadabuys_enriched_bids.csv")
OUTPUT_CSV = os.path.join(FILE_DIR, "canadabuys_final_details.csv")
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

# Define new columns
tender_detail_columns =[
    "Publication date", "Closing date and time", "Notice type", 
    "Contract duration", "Procurement method", "Description",
    "Organization", "Address", "Contracting authority name", 
    "Contracting authority email", "Buying organization(s)"
]
# Base URL for the Tender Opportunities page
base_url = "https://canadabuys.canada.ca/en/tender-opportunities"

# Reconstruct the query string using the editable dictionary
query_string = urllib.parse.urlencode(filters)
target_url = f"{base_url}?{query_string}"

print(f"Target URL constructed:\n{target_url}\n")

# Helper function to safely extract text from BeautifulSoup elements
def safe_extract(soup, selector, is_list=False, join_str=", "):
    if is_list:
        elements = soup.select(selector)
        if elements:
            return join_str.join([e.get_text(separator=" ", strip=True) for e in elements])
        return None
    else:
        element = soup.select_one(selector)
        if element:
            # Replace multiple spaces/newlines with a single space
            return " ".join(element.get_text(separator=" ", strip=True).split())
        return None
        
# 2. Pydoll Automation Script
async def extract_tables():
    print("Launching Chrome via Pydoll...")
    
    # Initialize the Chrome browser natively with Pydoll (no external webdrivers required)
    async with Chrome() as browser:
        # Start the browser session
        tab = await browser.start()

        # timezone = await tab.evaluate("Intl.DateTimeFormat().resolvedOptions().timeZone")
        # print(f"Browser Timezone: {timezone}")
        # return
        validation_result = await tab.execute_script("Intl.DateTimeFormat().resolvedOptions().timeZone", return_by_value=True, await_promise=True)
        validated_timezone = validation_result.get('result', {}).get('result', {}).get('value')
        
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

                df['browser_timezone'] = validated_timezone
                
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
        df.to_csv(RAW_CSV, index=False)

        if not os.path.exists(RAW_CSV):
            print(f"❌ Input file not found: {RAW_CSV}")
            return

        # Read the dataset
        df = pd.read_csv(RAW_CSV)

        for col in tender_detail_columns:
            if col not in df.columns:
                df[col] = None
        for index, row in df.iterrows():
            url = row['link']
            if pd.isna(url):
                continue
            
            print(f"\n[{index + 1}/{len(df)}] Navigating to: {url}")
            try:
                await tab.go_to(url)
                await asyncio.sleep(3) # Wait for page to render

                # 1. Parse the page for general info (Summary, Description, Dates)
                page_source = await tab.page_source
                soup = BeautifulSoup(page_source, 'html.parser')

                df.at[index, 'Publication date'] = safe_extract(soup, '.field--name-field-tender-publication-date time')
                df.at[index, 'Closing date and time'] = safe_extract(soup, '.closing-date-field .field--item')
                df.at[index, 'Notice type'] = safe_extract(soup, '.views-field-field-tender-notice-type .field-content')
                df.at[index, 'Contract duration'] = safe_extract(soup, '.views-field-field-tender-contract-duration .field-content')
                df.at[index, 'Procurement method'] = safe_extract(soup, '.views-field-field-tender-procurement-method .field-content')
                df.at[index, 'Description'] = safe_extract(soup, '.tender-detail-description')

                # 2. Click the "Contact Information" tab
                # The ID of the <a> tag based on the provided HTML is 'edit-group-contact-information-id'
                print("Clicking 'Contact information' tab...")
                try:
                    # 1. Locate the tab element
                    contact_tab = await tab.find(id='edit-group-contact-information-id', timeout=5)
                    
                    # 2. Check its state via the 'aria-selected' attribute
                    is_selected = contact_tab.get_attribute('aria-selected')
                    
                    # 3. Only click if it is NOT already selected
                    if is_selected == 'true':
                        print("✅ Contact tab is already open. Skipping click.")
                    else:
                        print("🖱️ Contact tab is closed. Clicking to open...")
                        await contact_tab.click()
                    await asyncio.sleep(2)
                    # 4. Wait for the target content to be ready
                    # (Even if the tab was already open, this safely ensures the content exists)
                    content_element = await tab.find(id='edit-group-contact-information-id', timeout=5)
                    # check for aria-selected="true" to ensure content is ready
                    is_selected = content_element.get_attribute('aria-selected')
                    if is_selected != 'true':
                        print("❌ Content is not ready. Skipping click.")
                        continue
                    # 5. Grab your data!
                    # text_data = await content_element.get_text()
                except Exception as e:
                    traceback.print_exc()
                    print(f"⚠️ Could not click Contact tab (it may already be open or missing): {e}")

                # 3. Get updated page source after click and parse Contact Information
                page_source = await tab.page_source
                soup = BeautifulSoup(page_source, 'html.parser')

                # Organization
                df.at[index, 'Organization'] = safe_extract(soup, '#edit-group-contact-information .field--name-field-tender-contracting-entity .field--name-field-tender-contact-orgname')
                
                # Address (Combine Line, City, Country)
                address_parts =[
                    safe_extract(soup, '#edit-group-contact-information .field--name-field-tender-contact-a-line'),
                    safe_extract(soup, '#edit-group-contact-information .field--name-field-tender-contact-a-city'),
                    safe_extract(soup, '#edit-group-contact-information .field--name-field-tender-contact-a-country')
                ]
                # Filter out empty parts and join
                valid_address = [part for part in address_parts if part]
                df.at[index, 'Address'] = ", ".join(valid_address) if valid_address else None

                # Contracting authority and Email
                df.at[index, 'Contracting authority name'] = safe_extract(soup, '.field--name-field-tender-contact-contactname .field--item')
                df.at[index, 'Contracting authority email'] = safe_extract(soup, '.field--name-field-tender-contact-email .field--item')

                # Buying organization(s) - Could be multiple, so we extract as a list
                df.at[index, 'Buying organization(s)'] = safe_extract(
                    soup, 
                    '.field--name-field-tender-end-user-entities .field--name-field-tender-contact-orgname', 
                    is_list=True
                )

                print(f"✅ Extracted info for {url.split('/')[-1]}")

            except Exception as e:
                traceback.print_exc()
                print(f"❌ Failed to process {url}. Error: {e}")

    # Save the updated DataFrame
    if not os.path.exists(FILE_DIR):
        os.makedirs(FILE_DIR)
        
    df.to_csv(OUTPUT_CSV, index=False)
    print(f"\n🎉 Done! All detailed data has been saved to: {OUTPUT_CSV}")
        # https://canadabuys.canada.ca/en/tender-opportunities/tender-notice/cb-935-68737969
        # get more details from the bids
if __name__ == "__main__":
    # Execute the asynchronous main function
    asyncio.run(extract_tables())
