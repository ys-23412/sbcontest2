import asyncio
import os
import pandas as pd
from pydoll.browser.chromium import Chrome
from pydoll.browser.options import ChromiumOptions
from random_user_agent.user_agent import UserAgent
import time
from io import StringIO
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from validate_tenders import send_discord_message


from mappers import _filter_bid_tenders_by_recent_date, process_and_send_bid_tenders # A more robust way to join URL parts

def parse_document_date(html_string):
    """
    Parses the 'dgDocuments' grid to find the first date associated with a file.
    """
    import re
    soup = BeautifulSoup(html_string, 'html.parser')
    print("--- Parsing Document Date ---")
    # 1. Target the specific container for Documents
    # We look for the ID 'dgDocuments' or the panel containing the text "Documents"
    doc_panel = soup.find(id='dgDocuments')
    print(f"Found panel: {doc_panel}")
    if not doc_panel:
        # Fallback: Find header with "Documents" and get parent panel
        header = soup.find('span', string=re.compile(r"Documents"))
        if header:
            doc_panel = header.find_parent(class_="x-panel")

    if not doc_panel:
        return {"published_date_parsing_error": "Documents panel not found"}

    cell_text = doc_panel.get_text(strip=True)
    # remove Document from the text
    cell_text = cell_text.replace("Document", "").replace('document', '').strip()
    date_pattern = r"([A-Za-z]+ [A-Za-z]+ \d{1,2}, \d{4} \d{1,2}:\d{2} (?:AM|PM))"
    
    match = re.search(date_pattern, cell_text)
    if match:
        return {"Published Date": match.group(1)}
            
    return {"published_date_parsing_error": "Date not found in Documents panel"}

def parse_bid_details_from_html(html_string):
    """
    Parses a bid details table from an HTML string and extracts key-value pairs.

    Args:
        html_string: A string containing the HTML of the bid details table.

    Returns:
        A dictionary where keys are the bid detail headers (th) and values are
        the corresponding data (td).
    """
    soup = BeautifulSoup(html_string, 'html.parser')
    bid_details = {}
    
    # Find the first table in the HTML
    table = soup.find('table')
    if not table:
        return {"error": "No table found in the HTML."}
    
    # Iterate through all table rows (tr)
    for row in table.find_all('tr'):
        # Find the header (th) and data (td) in each row
        header_tag = row.find('th')
        value_tag = row.find('td')
        
        if header_tag and value_tag:
            # Clean up header text by stripping whitespace and the colon
            header = header_tag.get_text(strip=True).replace(':', '')
            
            # Clean up the value text
            # This handles nested divs and spans by getting all text content
            value = value_tag.get_text(separator=' ', strip=True)
            
            # Add the key-value pair to the dictionary
            bid_details[header] = value
    if not bid_details.get('Published Date'):
        print("No published date found in bid details.")
        try:
            bid_details.update(parse_document_date(html_string))
            print(bid_details)
        except Exception as e:
            print(f"Error parsing document date: {e}")
            bid_details["published_date_parsing_error"] = f"Error parsing document date: {e}"

    return bid_details

async def scrap_bids_and_tenders_site(config: dict):
    base_url = config['url']
    region_name = config['region_name']
    tender_authority = config['tender_authority']
    file_prefix = config['file_prefix']
    base_dir = os.getenv('BASE_DIR', "data")

    options = ChromiumOptions()
    if not os.environ.get("NODRIVER_HEADLESS") == "True" and os.environ.get("DISPLAY", ":99"):
        display_var = os.environ.get("DISPLAY")
        print("display", display_var)
        options.add_argument(f'--display=:99')

    options.add_argument("--enable-webgl")

    # stealth automation
    fake_timestamp = int(time.time()) - (90 * 24 * 60 * 60)  # 90 days ago

    # options.browser_preferences = {
    #     # Override new tab page
    #     'newtab_page_location_override': 'https://www.google.com',
    #     # Disable telemetry
    #     'user_experience_metrics': {
    #         'reporting_enabled': False
    #     }
    # }

    async with Chrome(options=options) as browser:
        try:
            tab = await browser.start()
        except Exception as e:
            print(f"Error starting browser: {e}")
            await asyncio.sleep(5)
            tab = await browser.start()

        await tab.go_to(base_url)
        print(f'Page loaded for {region_name}, waiting for captcha to be handled...')
        await asyncio.sleep(5)

        page_source = await tab.page_source
        os.makedirs(base_dir, exist_ok=True)
        with open(f'{base_dir}/page_source.html', 'w', errors='ignore') as f:
            f.write(page_source)
        tables = pd.read_html(StringIO(page_source))

        soup = BeautifulSoup(page_source, 'html.parser')

        # 2. Find the first table on the page
        table = soup.find('table')

        final_data = []

        if table:
            # 3. Get all 'tr' (table row) elements from the table's body
            # Searching within 'tbody' is a good practice to avoid header rows
            rows = table.find_all('tr')
            header_row = table.find('thead').find('tr')
            headers = []
            # Loop through each header cell (th)
            for th in header_row.find_all('th'):
                # 1. Find the first 'div' tag inside the current 'th'
                div = th.find('div')
                
                # 2. Check if a 'div' was actually found
                if div:
                    # If found, get the text from the 'div'
                    headers.append(div.get_text(strip=True))
                else:
                    # Fallback: if no 'div', get the text from the 'th' itself
                    headers.append(th.get_text(strip=True))
                    # cut the duplicate words in the header

            # 4. Iterate over the list of rows, taking two at a time (a "double row")
            # We use a for loop with a step of 2
            for i in range(1, len(rows), 2):
                # The first row in the current pair
                row1 = rows[i]

                if i + 1 < len(rows):
                    row2 = rows[i+1]
                    
                    cells1 = row1.find_all('td')
                    data_row_text = []
                    for cell in cells1:
                        data_row_text.append(cell.get_text(strip=True))
                    # print(f"Found Data: {data_row_text}")

                    # 2. Check if the number of cells matches the number of headers
                    if len(data_row_text) == len(headers):
                        # 3. Create a dictionary by zipping the headers and the cell text together
                        row_dict = dict(zip(headers, data_row_text))

                        links = row2.find_all('a')
                        
                        # We can be more specific to get only the links on the right
                        # links_container = row2.find('div', style='float:right;')
                        # if links_container:
                        #    links = links_container.find_all('a')

                        # 3. Process the found links and add them to the dictionary
                        for link in links:
                            link_text = link.get_text(strip=True)
                            relative_url = link.get('href')

                            if relative_url:
                                # Construct the absolute URL
                                absolute_url = urljoin(base_url, relative_url)
                                
                                # Add to dictionary with a clean key
                                if 'Bid Details' in link_text:
                                    row_dict['Details URL'] = absolute_url
                                elif 'Download Documents' in link_text:
                                    row_dict['Documents URL'] = absolute_url
                                elif 'Plan Takers' in link_text:
                                    row_dict['Plan Takers URL'] = absolute_url
                        
                        final_data.append(row_dict)
                    else:
                        print(f"Warning: Skipping a row because its cell count ({len(data_row_text)}) doesn't match the header count ({len(headers)}).")
                        print(data_row_text)

        await asyncio.sleep(4)
        print(final_data)
        # This code runs only after the captcha is successfully bypassed
        output_dir = "screenshots"
        os.makedirs(output_dir, exist_ok=True) # Ensure the directory exists
        screenshot_path = os.path.join(output_dir, f"{file_prefix}_cloudflare_bypass_screenshot.png")
        
        print(f"Taking screenshot and saving to {screenshot_path}")
        await tab.take_screenshot(path=screenshot_path, quality=90) # Save as PNG, full page

        print(f"Screenshot saved: {screenshot_path}")
        
        # await tab.disable_auto_solve_cloudflare_captcha()
        # convert to final_data
        df = pd.DataFrame(final_data)
        df.to_csv(f'{base_dir}/output.csv', index=False)
        await asyncio.sleep(3)
        full_results = []
        # go through each row and download the files
        for index, row in df.iterrows():
            details_url = row['Details URL']
            print("visiting", details_url)
            # full results, start with the row
            # Convert the pandas Series 'row' to a dictionary
            row_dict = row.to_dict()
            
            # Initialize an empty dictionary for the details
            values = {}
            
            if details_url:
                await tab.go_to(details_url)
                page_source = await tab.page_source
                values = parse_bid_details_from_html(page_source)
            
            merged_dict = {**row_dict, **values}
            
            # Append the new, merged dictionary to the results list
            full_results.append(merged_dict)
            await asyncio.sleep(3)

        df = pd.DataFrame(full_results)
        df.to_csv(f'{base_dir}/{file_prefix}_tenders.csv', index=False)
        await asyncio.sleep(3)
        # await tab.close()
        # loop through each entry
        clean_entries = _filter_bid_tenders_by_recent_date(full_results)

        print("clean entries", clean_entries)

        process_and_send_bid_tenders({
            "data": clean_entries,
            "region_name": region_name,
            'hide_tiny_url': os.getenv('HIDE_TINY_URL', False),
            'file_prefix': file_prefix,
            'tender_authority': tender_authority,
        })

async def main():
    """
    Main function to define and run scrapers for multiple municipalities.
    """
    # Define an array of dictionaries, each representing a target site.
    # You can easily add more municipalities to this list.
    municipalities_to_scrape = [
        {
            "region_name": "Campbell River",
            "tender_authority": "Campbell River - Bids and Tenders",
            "file_prefix": "campbell_river_bid_tenders",
            "url": 'https://campbellriver.bidsandtenders.ca/Module/Tenders/en'
        },
        # --- EXAMPLE: Add another city below ---
        {
            "region_name": "Nanaimo",
            "tender_authority": "Nanaimo - Bids and Tenders",
            "file_prefix": "nanaimo_tenders",
            "url": "https://nanaimo.bidsandtenders.ca/Module/Tenders/en"
        },
        {
            "region_name": "Sidney",
            "tender_authority": "Sidney - Bids and Tenders",
            "file_prefix": "sidney_tenders",
            "url": "https://sidney.bidsandtenders.ca/Module/Tenders/en"
        },
        {
            "region_name": "Comox Valley RD",
            "tender_authority": "Comox Valley - Bids and Tenders",
            "file_prefix": "comox_tenders",
            "url": "https://comoxvalleyrd.bidsandtenders.ca/Module/Tenders/en"
        },
        {
            "region_name": "Campbell River",
            "tender_authority": "School District 72 (Campbell River) - Bids and Tenders",
            "file_prefix": "campbell_river_bid_tenders",
            "url": 'https://sd72.bidsandtenders.ca/Module/Tenders/en'
        }
        {
            "region_name": "Victoria",
            "tender_authority": "Island Health - Bids and Tenders",
            "file_prefix": "island_health",
            "url": "https://islandhealthfdc.bidsandtenders.ca/Module/Tenders/en"
        }
    ]
    discord_webhook_url = os.getenv('DISCORD_WEBHOOK_URL')
    for municipality in municipalities_to_scrape:
        print(f"--- Starting scrape for {municipality['tender_authority']} ---")
        try:
            await scrap_bids_and_tenders_site(municipality)
            print(f"--- Successfully finished scrape for {municipality['region_name']} ---")
        except Exception as e:
            print(f"!!! An error occurred while scraping {municipality['region_name']}: {e} !!!")
            # Optionally, send an error notification
            send_discord_message(f"Scraper failed for {municipality['region_name']} with error: {e}", discord_webhook_url)
            try:
                time.sleep(10)
                await scrap_bids_and_tenders_site(municipality)
                print(f"--- Successfully finished scrape for {municipality['region_name']} ---")
            except Exception as e:
                print(f"!!! An error occurred while scraping {municipality['region_name']}: {e} !!!")
                send_discord_message(f"Scraper failed for {municipality['region_name']} with error: {e}", discord_webhook_url)

        print("-" * 50)


if __name__ == "__main__":
    asyncio.run(main())
