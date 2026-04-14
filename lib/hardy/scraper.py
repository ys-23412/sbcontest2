import asyncio
import os
import time
import re
from bs4 import BeautifulSoup
import pandas as pd
import random
from datetime import datetime, timedelta

from pydoll.browser.chromium import Chrome
from pydoll.browser.options import ChromiumOptions

# Updated directory for the new website
FILE_DIR = os.environ.get("FILE_DIR") or "screenshots_porthardy"

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

        url = "https://porthardy.ca/municipal-hall/staff/tender-and-bid-opportunities/"
        print(f"Navigating to {url}...")
        await tab.go_to(url)
        
        # Wait for the page to load fully
        await asyncio.sleep(random.uniform(3.0, 5.0))
   
        page_source = await tab.page_source
        
        print("Extracting bids...")
        soup = BeautifulSoup(page_source, 'html.parser')
        
        # The list is enclosed in a div with class "secondary-content post-list"
        # Each item has a class "post"
        posts = soup.find_all('div', class_='post')
        
        bids_data =[]
        for post in posts:
            heading = post.find('a', class_='secondary-heading')
            title = heading.get_text(strip=True) if heading else "Unknown Title"
            link = heading['href'] if heading and heading.has_attr('href') else ""
            
            date_div = post.find('div', class_='small-heading')
            date_str = date_div.get_text(strip=True) if date_div else ""
            
            desc_p = post.find('p')
            brief_desc = desc_p.get_text(strip=True) if desc_p else ""
            
            bids_data.append({
                'Bid Opportunity': title,
                'Opportunity Url': link,
                'Posted': date_str,
                'Brief Description': brief_desc
            })
            
        target_df = pd.DataFrame(bids_data)

        if target_df.empty:
            print("No bids found on the page.")
            return

        # Parse the 'Posted' dates (Port Hardy format: "Posted: Apr 09, 2026")
        def parse_date(date_str):
            try:
                clean_str = str(date_str).replace('Posted:', '').strip()
                return pd.to_datetime(clean_str)
            except Exception as e:
                return pd.NaT

        target_df['Parsed Date'] = target_df['Posted'].apply(parse_date)

        print(f"Found {len(target_df)} total bids.")
        
        # Define "newly" posted as within the last 5 days
        days_threshold = os.getenv('NEW_BID_DAYS_THRESHOLD', 5)
        cutoff_date = pd.to_datetime(datetime.now() - timedelta(days=days_threshold))
        
        # Filter dataframe for recent dates
        new_bids = target_df[target_df['Parsed Date'] >= cutoff_date].copy()
        print(f"Found {len(new_bids)} new bids posted in the last {days_threshold} days.")
        
        # Save the filtered results
        new_bids.to_csv(f"{FILE_DIR}/porthardy_new_bids_raw.csv", index=False)
        
        # List to hold enriched data
        enriched_results =[]

        # Iterate through the filtered links
        for index, row in new_bids.iterrows():
            link = row.get('Opportunity Url')
            title = row.get('Bid Opportunity') 
            
            # Create a base record from the existing row data
            record = row.to_dict()
            
            if pd.notna(link) and str(link).startswith('http'):
                print(f"Navigating to new bid: {str(title)[:35]}... -> {link}")
                await tab.go_to(link)
                
                await asyncio.sleep(random.uniform(2.0, 4.0))
                
                # Cleanup and Screenshot
                safe_title = "".join([c for c in str(title) if c.isalnum() or c==' ']).rstrip()[:25]
                await tab.take_screenshot(f'{FILE_DIR}/bid_{index}_{safe_title.replace(" ", "_")}.png', quality=90, beyond_viewport=True)
                
                # --- Scrape logic for detail page ---
                html_content = await tab.page_source
                page_soup = BeautifulSoup(html_content, 'html.parser')
                
                # Cleanup potentially distracting elements
                for aside in page_soup.find_all(['aside', 'footer', 'header']):
                    aside.decompose()
                    
                description = ""
                email = ""
                contact_name = ""
                closing_date = ""
                
                # Based on the theme, the main content is likely in a 'blog-content' wrapper
                main_content = page_soup.find('div', class_='blog-content')
                if not main_content:
                    main_content = page_soup.find('div', class_='content-inner') or page_soup # fallbacks
                
                paragraphs = main_content.find_all('p')
                if paragraphs:
                    # Grab the first few paragraphs as the extended description
                    description = "\n".join([p.get_text(strip=True) for p in paragraphs[:4]])
                    
                    # Extract Closing Date and Contact Name
                    for p in paragraphs:
                        text = p.get_text(strip=True)
                        text_lower = text.lower()
                        
                        # Find closing date
                        if 'until:' in text_lower or 'closing:' in text_lower:
                            strong_tag = p.find('strong')
                            if strong_tag:
                                closing_date = strong_tag.get_text(strip=True)
                            else:
                                split_text = re.split(r'until:|closing:', text, flags=re.IGNORECASE)
                                if len(split_text) > 1:
                                    closing_date = split_text[-1].strip()
                        
                        # Find bold contact name (Attention)
                        if 'attention:' in text_lower:
                            strong_tag = p.find('strong')
                            if strong_tag:
                                contact_name = strong_tag.get_text(strip=True)
                            else:
                                split_text = re.split(r'attention:', text, flags=re.IGNORECASE)
                                if len(split_text) > 1:
                                    contact_name = split_text[-1].strip()
                
                # Search for mailto anchor tags
                mailto_link = main_content.find('a', href=lambda href: href and href.startswith('mailto:'))
                if mailto_link:
                    email = mailto_link.get_text(strip=True)
                else:
                    # Fallback Regex to find email if no mailto link is formatted
                    text_content = main_content.get_text()
                    email_match = re.search(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', text_content)
                    if email_match:
                        email = email_match.group(0)
                
                # Update the record with newly scraped fields
                record.update({
                    'contact_name': contact_name,
                    'email': email,
                    'closing_date': closing_date,
                    'full_description': description
                })
                
                print(f"Extracted -> Name: {contact_name} | Closing Date: {closing_date} | Email: {email}")
                enriched_results.append(record)
            else:
                # If no link, still append the original record to maintain index alignment
                enriched_results.append(record)

        # Convert enriched results to a new DataFrame and save
        enriched_df = pd.DataFrame(enriched_results)
        enriched_df.to_csv(f"{FILE_DIR}/porthardy_enriched_bids.csv", index=False)

        print(f"Scraping task complete. Saved {len(enriched_df)} enriched records.")

if __name__ == "__main__":
    asyncio.run(main())