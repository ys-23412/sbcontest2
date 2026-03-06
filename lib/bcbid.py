import asyncio
import os
import time
import pandas as pd
from io import StringIO
from pydoll.browser.chromium import Chrome
from pydoll.browser.options import ChromiumOptions
from pydoll.browser.tab import Tab

def get_browser_options(headless=False):
    """
    Returns a configured ChromiumOptions object with stealth settings.
    """
    options = ChromiumOptions()
    current_time = int(time.time())
    options.browser_preferences = {
        'profile': {
            'last_engagement_time': str(current_time - (3 * 60 * 60)),  # 3 hours ago
            'exited_cleanly': True,
            'exit_type': 'Normal',
        },
        'safebrowsing': {'enabled': True},
    }

    # Handle Headless environment variables
    env_headless = os.environ.get("NODRIVER_HEADLESS") == "True"
    
    if headless or env_headless:
        options.add_argument("--headless=new")

    options.browser_preferences = {
        'profile': {'exit_type': 'Normal'},
        'credentials_enable_service': False,
        'profile.password_manager_enabled': False
    }
    return options

async def dummy_login(tab, username, password):
    """
    Placeholder login logic for BC Bid portal.
    Targeting IDs found in the provided HTML: body_x_txtLogin and body_x_txtPass
    """
    print("Attempting login...")
    # Find username field
    # username_field = await tab.find(id="body_x_txtLogin")
    # await username_field.type_text(username)

    # Find password field
    # password_field = await tab.find(id="body_x_txtPass")
    # await password_field.type_text(password)

    # Click login button
    # login_btn = await tab.find(id="body_x_btnLogin")
    # await login_btn.click()
    
    # Wait for session to establish
    # await asyncio.sleep(5)
    pass

async def navigate_to_opportunities(tab: Tab):
    """
    Attempts to find the Opportunities link using XPath via the FindElementsMixin.
    Logic: 1. Search by Text -> 2. Search by relative href fallback.
    """
    print("Searching for 'Opportunities' link...")
    
    # 1. Attempt to find by Text using XPath
    # Using normalize-space() to handle potential whitespace in the link text
    xpath_by_text = "//a[normalize-space()='Opportunities']"
    
    # We use raise_exc=False so the script doesn't crash if the first attempt fails
    opps_link = await tab.query(xpath_by_text, raise_exc=False)

    # 2. Fallback: Search by relative href using XPath
    if not opps_link:
        print("Text-based search failed. Attempting fallback via href XPath...")
        xpath_fallback = "//a[@href='/page.aspx/en/rfp/request_browse_public']"
        opps_link = await tab.query(xpath_fallback, raise_exc=False)

    if opps_link:
        print("Link found. Clicking...")
        os.mkdir("screenshots")
        await opps_link.click()
        await asyncio.sleep(3)
        await tab.take_screenshot('screenshots/page.png', quality=90, beyond_viewport=True,)
        await asyncio.sleep(25)  # Wait for portal redirection
        # take a screenshot
        await tab.take_screenshot('screenshots/page2.png', quality=90, beyond_viewport=True)
        # try:
        #     submit_button = await tab.find(id='submit-btn')
        #     await submit_button.click()
        # except Exception as e:
        #     print(f"Error clicking submit button: {e}")
    else:
        print("Error: Could not locate Opportunities link using text or href XPaths.")

async def scrape_tabular_data(tab: Tab):
    """
    Scrapes the table with id 'body_x_grid_grd' across all paginated pages.
    Uses JS evaluation to avoid Stale Element Reference errors common in ASP.NET AJAX sites.
    """
    print("Starting tabular data extraction...")
    all_table_htmls = []
    all_dfs = [] # List to hold DataFrames for each page
    page = 1
    max_pages = 100 # Safety limit to prevent infinite loops
    
    while page <= max_pages:
        print(f"Extracting data from page {page}...")
        
        try:
            # Wait for AJAX table to fully load
            await asyncio.sleep(4)
            
            # 1. Grab the table HTML directly using JavaScript
            table_html = await tab.evaluate("""
                document.getElementById('body_x_grid_grd') 
                ? document.getElementById('body_x_grid_grd').outerHTML 
                : null
            """)
            
            if table_html:
                all_table_htmls.append(table_html)
                print(f"Successfully captured table HTML for page {page}.")
                try:
                    # pd.read_html returns a list of dataframes found in the HTML string.
                    # We wrap the string in StringIO to avoid Pandas FutureWarnings.
                    dfs = pd.read_html(StringIO(table_html))
                    if dfs:
                        df = dfs[0] # Grab the first (and only) table
                        all_dfs.append(df)
                        print(f"Successfully parsed {len(df)} rows from page {page} into DataFrame.")
                except Exception as e:
                    print(f"Pandas failed to parse the HTML table on page {page}: {e}")
            else:
                print(f"Warning: Table 'body_x_grid_grd' not found on page {page}.")
                break
                
            # 2. Check if the 'Next' button is disabled or missing
            is_disabled = await tab.evaluate("""
                (() => {
                    const nextBtn = document.getElementById("body_x_grid_gridPagerBtnNextPage");
                    if (!nextBtn) return true; // Treat as disabled if element doesn't exist
                    
                    // Check if the class contains 'disabled' (standard for BC Bid pagination)
                    const isClassDisabled = nextBtn.className.toLowerCase().includes('disabled');
                    return isClassDisabled || nextBtn.disabled;
                })()
            """)
            
            if is_disabled:
                print("Next button is disabled. Reached the last page.")
                break
                
            # 3. Click the 'Next' button via JS to trigger the site's AJAX pagination
            print(f"Clicking 'Next' button to navigate to page {page + 1}...")
            await tab.evaluate('document.getElementById("body_x_grid_gridPagerBtnNextPage").click()')
            
            page += 1
            
        except Exception as e:
            print(f"Error encountered during pagination on page {page}: {e}")
            break
            
    # Save all gathered HTML to a file so the Github Action can upload it
    print(f"Finished scraping. Saving {len(all_table_htmls)} pages of tables to bcbid.html...")
    try:
        with open("bcbid.html", "w", encoding="utf-8") as f:
            f.write("<html><head><meta charset='utf-8'></head><body>\n")
            for idx, html_content in enumerate(all_table_htmls):
                f.write(f"<h2>Page {idx + 1}</h2>\n")
                f.write(html_content)
                f.write("\n<hr>\n")
            f.write("</body></html>\n")
        print("Successfully saved 'bcbid.html'")
    except Exception as e:
        print(f"Failed to write HTML file: {e}")

    if all_dfs:
        try:
            # Concatenate all individual page DataFrames into one massive DataFrame
            final_df = pd.concat(all_dfs, ignore_index=True)
            
            # Optional: Clean up empty columns or rows that Pandas might have picked up
            final_df.dropna(how='all', inplace=True) 
            
            print(f"Total rows extracted across all pages: {len(final_df)}")
            
            # Save the DataFrame to CSV
            final_df.to_csv("bid_recent.csv", index=False, encoding='utf-8')
            print("Successfully saved data to 'bid_recent.csv'")
        except Exception as e:
            print(f"Failed to concatenate or save CSV: {e}")
    else:
        print("No DataFrames were created. Skipping CSV generation.")

async def main():
    opts = get_browser_options(headless=False)
    
    async with Chrome(options=opts) as browser:
        print("Starting browser...")
        tab = await browser.start()
        # 1. Navigate to BC Bid
        url = "https://bcbid.gov.bc.ca"
        print(f"Navigating to {url}...")
        await tab.go_to(url)
        
        # 2. Dummy Login (Commented out as requested)
        # await dummy_login(tab, "YOUR_USERNAME", "YOUR_PASSWORD")
        await asyncio.sleep(10)
        
        # 3. Click on "Browse Opportunities"
        # Based on the uploaded HTML, the ID is 'body_x_btnPublicOpportunities'
        print("Clicking on 'Browse Opportunities'...")
        try:
            await navigate_to_opportunities(tab)
        except Exception as e:
            print(f"Error during navigation: {e}")

        try:
            await scrape_tabular_data(tab)
        except Exception as e:
            print(f"Error during tabular data extraction: {e}")

        # logs = await tab.get_network_logs()

        # print(f"Total requests captured: {len(logs)}")

        # for log in logs:
        #     print(log)
            # print(f"→ {request['method']} {request['url']}")
        # except Exception as e:
        #     print(f"Error clicking opportunities button: {e}")
        # await tab.disable_network_events()
        print("Scraping task complete.")
        # await asyncio.sleep(155)

if __name__ == "__main__":
    asyncio.run(main())