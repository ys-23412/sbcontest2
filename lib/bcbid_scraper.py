import asyncio
import os
import time
import lxml
import pandas as pd
from io import StringIO
from pydoll.browser.chromium import Chrome
from pydoll.browser.options import ChromiumOptions
from pydoll.browser.tab import Tab
from pydoll.constants import By
from pydoll.constants import ScrollPosition
from datetime import datetime, timedelta

FILE_DIR = "screenshots"

def get_browser_options(headless=False):
    """
    Returns a configured ChromiumOptions object with stealth settings.
    """
    options = ChromiumOptions()
    current_time = int(time.time())
    options.browser_preferences = {
        'profile': {
            'last_engagement_time': str(current_time - (10 * 60 * 60)),  # 3 hours ago
            'exited_cleanly': True,
            'exit_type': 'Normal',
        },
        'safebrowsing': {'enabled': True},
    }

    # Handle Headless environment variables
    env_headless = os.environ.get("NODRIVER_HEADLESS") == "True"
    
    # if headless or env_headless:
    #     options.add_argument("--headless=new")

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
        # if directory exists
        if not os.path.exists(FILE_DIR):
            # remove directory
            os.mkdir(FILE_DIR)
        await opps_link.click()
        await asyncio.sleep(3)
        await tab.take_screenshot(f'{FILE_DIR}/trying_to_login.png', quality=90, beyond_viewport=True)
        await asyncio.sleep(4)  # Wait for portal redirection
        # wait for page to load
        selector = "//h1[contains(@class, 'maintitle') and contains(text(), 'Opportunities')]"
        
        try:
            await tab.scroll.by(ScrollPosition.DOWN, 500, humanize=True)
            await tab.find_or_wait_element(By.XPATH, selector, timeout=40000)
            print("Found the Opportunities header!")
        except Exception as e:
            print(f"Timed out waiting for text: {e}")
        # take a screenshot
        await tab.take_screenshot(f'{FILE_DIR}/after_login.png', quality=90, beyond_viewport=True)
        # try:
        #     submit_button = await tab.find(id='submit-btn')
        #     await submit_button.click()
        # except Exception as e:
        #     print(f"Error clicking submit button: {e}")
    else:
        print("Error: Could not locate Opportunities link using text or href XPaths.")

async def main():
    opts = get_browser_options()
    
    async with Chrome(options=opts) as browser:
        print("Starting browser...")
        tab = await browser.start()
        # 1. Navigate to BC Bid
        url = "https://bcbid.gov.bc.ca/page.aspx/en/rfp/request_browse_public"
        print(f"Navigating to {url}...")
        await tab.go_to(url)
        if not os.path.exists(FILE_DIR):
            # remove directory
            os.mkdir(FILE_DIR)
        # 2. Dummy Login (Commented out as requested)
        # await dummy_login(tab, "YOUR_USERNAME", "YOUR_PASSWORD")
        await asyncio.sleep(10)
        await tab.mouse.drag(100, 200, 500, 400, humanize=True)
        await tab.take_screenshot(f'{FILE_DIR}/trying_to_login.png', quality=90, beyond_viewport=True)
        await tab.mouse.move(500, 300, humanize=True)
        # wait for page to load
        selector = "//h1[contains(@class, 'maintitle') and contains(text(), 'Opportunities')]"
        
        try:
            await tab.find_or_wait_element(By.XPATH, selector, timeout=40)
            print("Found the Opportunities header!")
        except Exception as e:
            print(f"Timed out waiting for text: {e}")
            url = "https://bcbid.gov.bc.ca/page.aspx/en/rfp/request_browse_public"
            print(f"Navigating to {url}...")
            await tab.go_to(url)
            await tab.find_or_wait_element(By.XPATH, selector, timeout=15)
            await tab.take_screenshot(f'{FILE_DIR}/trying_to_login2.png', quality=90, beyond_viewport=True)
        # take a screenshot
        await tab.take_screenshot(f'{FILE_DIR}/after_login.png', quality=90, beyond_viewport=True)
        # 3. Click on "Browse Opportunities"
        # Based on the uploaded HTML, the ID is 'body_x_btnPublicOpportunities'
        print("Clicking on 'Browse Opportunities'...")
        try:
            pass
            # await navigate_to_opportunities(tab)
        except Exception as e:
            print(f"Error during navigation: {e}")
        try:
            print("Setting date filters...")
            
            # Calculate dates. Adjust format based on what BC Bid expects (usually YYYY-MM-DD)
            # If you meant "past 2 days":
            min_date = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
            max_date = datetime.now().strftime('%Y-%m-%d')
            
            # OR if you literally meant "2 days in the future" for min_date, use:
            # min_date = (datetime.now() + timedelta(days=2)).strftime('%Y-%m-%d')

            # Inject the values directly into the input fields and trigger the 'change' event
            await tab.execute_script(f"""
                (() => {{
                    // 1. Set Min Date
                    const minInput = document.getElementById('body_x_txtRfpBeginDate');
                    if (minInput) {{
                        minInput.value = '{min_date}';
                        minInput.dispatchEvent(new Event('change', {{ bubbles: true }}));
                    }}
                    
                    // 2. Set Max Date
                    const maxInput = document.getElementById('body_x_txtRfpBeginDatemax');
                    if (maxInput) {{
                        maxInput.value = '{max_date}';
                        maxInput.dispatchEvent(new Event('change', {{ bubbles: true }}));
                    }}
                    
                    // 3. Hide the calendar popup if it accidentally opened
                    const datePickerDiv = document.getElementById('ui-datepicker-div');
                    if (datePickerDiv) {{
                        datePickerDiv.style.display = 'none';
                    }}
                }})()
            """)

            await asyncio.sleep(10)

            # click on search button
            try:
                search_button = await tab.find(id='body_x_prxFilterBar_x_cmdSearchBtn')
                await search_button.click()
            except Exception as e:
                print(f"Error clicking search button: {e}")
            
            print(f"Set Issue Date filters: Min = {min_date}, Max = {max_date}")
        except Exception as e:
            print(f"Error during date filtering: {e}")
        try:
            print("Starting tabular data extraction...")
            all_table_htmls = []
            all_dfs =[] # List to hold DataFrames for each page
            page = 1
            # we apply filtering to grab recent entries so the number of pages should be quite low, 20
            # is probably overkill
            max_pages = 20 # Safety limit to prevent infinite loops
            
            while page <= max_pages:
                print(f"Extracting data from page {page}...")
                
                try:
                    # Wait for AJAX table to fully load
                    await asyncio.sleep(8)
                    page_source = await tab.page_source
                    # 1. Grab the table HTML directly using JavaScript

                    dfs = pd.read_html(
                            StringIO(page_source), 
                            attrs={'id': 'body_x_grid_grd'}
                        )
                    df = dfs[0]

                    # --- NEW URL EXTRACTION LOGIC ---
                    # Parse the HTML with lxml to extract the hidden hrefs
                    tree = lxml.html.fromstring(page_source)
                    
                    # Find all table rows inside the grid that contain data cells (<td>)
                    # This perfectly matches the rows that Pandas extracted.
                    rows = tree.xpath("//table[@id='body_x_grid_grd']//tr[td]")
                    
                    urls =[]
                    for row in rows:
                        # Grab the 'href' from the <a> tag inside the 2nd <td>
                        # Note: XPath indexing is 1-based, so td[2] is the second column
                        hrefs = row.xpath("./td[2]//a/@href")
                        if hrefs:
                            urls.append(f"https://bcbid.gov.bc.ca{hrefs[0]}")
                        else:
                            urls.append("")
                    
                    # Attach the URLs as a new column to the DataFrame
                    df['Opportunity Url'] = pd.Series(urls)
                    table_html = df.to_html(index=False)
        
                    all_table_htmls.append(table_html)
                    all_dfs.append(df)
                        
                    # 2. Check if the 'Next' button is disabled or missing
                    scriptReturnResult = await tab.execute_script("""
                        (() => {
                            const nextBtn = document.getElementById("body_x_grid_gridPagerBtnNextPage");
                            if (!nextBtn) return true; // Treat as disabled if element doesn't exist
                            
                            // Check if the class contains 'disabled' (standard for BC Bid pagination)
                            const isClassDisabled = nextBtn.className.toLowerCase().includes('disabled');
                            return isClassDisabled || nextBtn.disabled;
                        })()
                    """, return_by_value=True, await_promise=True)
                    print(f"Next button is disabled: {scriptReturnResult}")
                    # check if element exists

                    try:
                        is_disabled = scriptReturnResult.get('result', {}).get('result', {}).get('value')
                    except Exception as e:
                        print(f"Error checking if next button is disabled: {e}")
                        is_disabled = True
                    
                    if is_disabled:
                        print("Next button is disabled. Reached the last page.")
                        break
                        
                    # 3. Click the 'Next' button via JS to trigger the site's AJAX pagination
                    print(f"Clicking 'Next' button to navigate to page {page + 1}...")
                    await tab.execute_script('document.getElementById("body_x_grid_gridPagerBtnNextPage").click()')
                    
                    page += 1
                    
                except Exception as e:
                    print(f"Error encountered during pagination on page {page}: {e}")
                    break
                    
            # Save all gathered HTML to a file so the Github Action can upload it
            print(f"Finished scraping. Saving {len(all_table_htmls)} pages of tables to bcbid.html...")
            try:
                with open(f"{FILE_DIR}/bcbid.html", "w", encoding="utf-8") as f:
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
                    final_df.to_csv(f"{FILE_DIR}/bid_recent.csv", index=False, encoding='utf-8')
                    print("Successfully saved data to 'bid_recent.csv'")
                except Exception as e:
                    print(f"Failed to concatenate or save CSV: {e}")
            else:
                print("No DataFrames were created. Skipping CSV generation.")

            await tab.take_screenshot(f'{FILE_DIR}/last_page.png', quality=90, beyond_viewport=True)
        except Exception as e:
            print(f"Error during tabular data extraction: {e}")
        # save page source
        await tab.save_bundle(f"{FILE_DIR}/bcbid.zip")

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
