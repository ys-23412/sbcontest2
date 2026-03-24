import asyncio
import os
import time
from bs4 import BeautifulSoup
import lxml.html
import pandas as pd
import random
from io import StringIO
from pydoll.browser.chromium import Chrome
from pydoll.browser.options import ChromiumOptions
from pydoll.browser.tab import Tab
from pydoll.constants import By
from pydoll.constants import ScrollPosition
from datetime import datetime, timedelta

FILE_DIR = os.environ.get("FILE_DIR") or "screenshots_rdn"

def get_browser_options(headless=False):
    """
    Returns a configured ChromiumOptions object with stealth settings.
    """
    options = ChromiumOptions()
    current_time = int(time.time())
    number_last = random.randint(3, 10)
    options.browser_preferences = {
        'profile': {
            'last_engagement_time': str(current_time - (number_last * 60 * 60)),  # 3 hours ago
            'exited_cleanly': True,
            'exit_type': 'Normal',
        },
        'safebrowsing': {'enabled': True},
    }

    env_headless = os.environ.get("NODRIVER_HEADLESS") == "True"
    proxy_url = os.environ.get("PROXY_URL")
    if proxy_url:
        options.add_argument(f'--proxy-server={proxy_url}')

    options.browser_preferences.update({
        'credentials_enable_service': False,
        'profile.password_manager_enabled': False
    })
    return options

# --- Main Scraper Logic ---
async def main():
    opts = get_browser_options()
    
    async with Chrome(options=opts) as browser:
        print("Starting browser...")
        tab = await browser.start()
        
        if not os.path.exists(FILE_DIR):
            os.mkdir(FILE_DIR)

        url = "https://rdn.bc.ca/current-bid-opportunities"
        print(f"Navigating to {url}...")
        await tab.go_to(url)
        
        # Wait for the table to populate
        await asyncio.sleep(random.uniform(3.0, 5.0))
   
        page_source = await tab.page_source
        
        print("Extracting table...")
        dfs = pd.read_html(StringIO(page_source))
        
        # RDN's table headers typically include 'Bid Opportunity', 'Posted', 'Updated', 'Closing'
        target_df = None
        for df in dfs:
            if any('Bid Opportunity' in str(c) for c in df.columns):
                target_df = df
                break
                
        if target_df is None:
            # Fallback to the first table if exact header matching fails
            target_df = dfs[0] if len(dfs) > 0 else None
            
        if target_df is None:
            print("No tables found on the page.")
            return

        # Extract underlying URLs using lxml
        tree = lxml.html.fromstring(page_source)
        # Find the table containing our headers
        tables = tree.xpath("//table[.//th[contains(., 'Bid Opportunity')]]")
        if not tables:
             tables = tree.xpath("//table")
             
        urls = []
        if tables:
            # Skip the header row, target rows with <td>
            rows = tables[0].xpath(".//tr[td]")
            for row in rows:
                # The bid link is located in the first column for RDN
                hrefs = row.xpath("./td[1]//a/@href")
                if hrefs:
                    href = hrefs[0]
                    # Ensure relative URLs are resolved
                    if href.startswith('/'):
                        href = f"https://rdn.bc.ca{href}"
                    urls.append(href)
                else:
                    urls.append("")
        
        # Align URLs with the Pandas DataFrame
        if len(urls) == len(target_df):
            target_df['Opportunity Url'] = urls
        else:
            print(f"Warning: Row mismatch. Table has {len(target_df)} rows, found {len(urls)} URLs.")
            target_df['Opportunity Url'] = pd.Series(urls)

        # Parse the 'Posted' dates
        # RDN text often looks like "March 5, 2026" or "Posted: March 5, 2026"
        def parse_date(date_str):
            try:
                clean_str = str(date_str).replace('Posted:', '').strip()
                return pd.to_datetime(clean_str)
            except:
                return pd.NaT

        posted_col = next((col for col in target_df.columns if 'Posted' in str(col)), None)
        
        if posted_col is not None:
            target_df['Parsed Date'] = target_df[posted_col].apply(parse_date)
        else:
            print("Could not locate 'Posted' column. Skipping date filtering.")
            target_df['Parsed Date'] = pd.NaT 

        print(f"Found {len(target_df)} total bids.")
        
        # Define "newly" posted as within the last 7 days
        days_threshold = 5
        cutoff_date = pd.to_datetime(datetime.now() - timedelta(days=days_threshold))
        
        # Filter dataframe for recent dates
        new_bids = target_df[target_df['Parsed Date'] >= cutoff_date].copy()
        print(f"Found {len(new_bids)} new bids posted in the last {days_threshold} days.")
        
        # Save the filtered results
        new_bids.to_csv(f"{FILE_DIR}/rdn_new_bids_raw.csv", index=False)
        
        # List to hold enriched data
        enriched_results = []

        # Iterate through the filtered links
        for index, row in new_bids.iterrows():
            link = row.get('Opportunity Url')
            title = row.iloc[0] 
            
            # Create a base record from the existing row data
            record = row.to_dict()
            
            if pd.notna(link) and str(link).startswith('http'):
                print(f"Navigating to new bid: {str(title)[:35]}... -> {link}")
                await tab.go_to(link)
                
                await asyncio.sleep(random.uniform(2.0, 4.0))
                
                # Cleanup and Screenshot
                safe_title = "".join([c for c in str(title) if c.isalnum() or c==' ']).rstrip()[:25]
                await tab.take_screenshot(f'{FILE_DIR}/bid_{index}_{safe_title.replace(" ", "_")}.png', quality=90, beyond_viewport=True)
                
                # --- Scrape logic ---
                html_content = await tab.page_source
                soup = BeautifulSoup(html_content, 'html.parser')
                
                for aside in soup.find_all('aside'):
                    aside.decompose()
                    
                description = ""
                email = ""
                contact_name = ""
                job_title = ""
                
                body_div = soup.find('div', class_='field--name-body')
                if body_div:
                    paragraphs = body_div.find_all('p')
                    if paragraphs:
                        description = paragraphs[0].get_text(strip=True)
                        
                    mailto_link = body_div.find('a', href=lambda href: href and href.startswith('mailto:'))
                    if mailto_link:
                        email = mailto_link.get_text(strip=True)
                        
                        parent_p = mailto_link.find_parent('p')
                        if parent_p:
                            for br in parent_p.find_all('br'):
                                br.replace_with('\n')
                            
                            contact_text = parent_p.get_text()
                            lines = [line.strip() for line in contact_text.split('\n') if line.strip()]
                            
                            for i, line in enumerate(lines):
                                if 'Email:' in line or email in line:
                                    if i > 0:
                                        full_contact_line = lines[i-1]
                                        parts = full_contact_line.split(',')
                                        if len(parts) > 1:
                                            # e.g. "Keona Wiley, Parks Planner"
                                            contact_name = parts[0].strip()
                                            job_title = parts[1].strip()
                                        else:
                                            contact_name = full_contact_line
                                            job_title = "N/A"
                                    break
                
                # Update the record with newly scraped fields
                record.update({
                    'contact_name': contact_name,
                    'job_title': job_title,
                    'email': email,
                    'description': description
                })
                
                print(f"Extracted -> Name: {contact_name} | Title: {job_title} | Email: {email}")
                enriched_results.append(record)
            else:
                # If no link, still append the original record to maintain index alignment
                enriched_results.append(record)

        # Convert enriched results to a new DataFrame and save
        enriched_df = pd.DataFrame(enriched_results)
        enriched_df.to_csv(f"{FILE_DIR}/rdn_enriched_bids.csv", index=False)

        print(f"Scraping task complete. Saved {len(enriched_df)} enriched records.")

if __name__ == "__main__":
    asyncio.run(main())