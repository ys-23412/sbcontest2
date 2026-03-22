import asyncio
import os
import time
import lxml
import pandas as pd
import random
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
    number_last = random.randint(1, 3)
    options.browser_preferences = {
        'profile': {
            'last_engagement_time': str(current_time - (number_last * 60 * 60)),  # 3 hours ago
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

async def action_scroll_and_hover(tab: Tab):
    """Simulates a user scrolling and moving the mouse naturally."""
    print("Executing: Scroll and Hover")
    for _ in range(random.randint(2, 4)):
        scroll_amount = random.randint(200, 500)
        await tab.scroll.by(ScrollPosition.DOWN, scroll_amount, smooth=True)
        await asyncio.sleep(random.uniform(0.8, 1.5))
    await tab.mouse.move(random.randint(100, 700), random.randint(100, 500), humanize=True)

async def action_random_drag(tab: Tab):
    """Simulates accidental or incidental mouse drags/selection."""
    print("Executing: Random Drag")
    await tab.mouse.drag(100, 200, 400, 300, humanize=True)
    await asyncio.sleep(random.uniform(1.0, 2.0))

async def action_reading_pause(tab: Tab):
    """Simulates a user stopping to read content."""
    print("Executing: Reading Pause")
    await tab.mouse.move(500, 300, humanize=True)
    await asyncio.sleep(random.uniform(3.0, 5.0))

async def action_hesitant_scroll(tab: Tab):
    """Simulates scrolling down then back up slightly."""
    print("Executing: Hesitant Scroll")
    await tab.scroll.by(ScrollPosition.DOWN, 600, smooth=True)
    await asyncio.sleep(1)
    await tab.scroll.by(ScrollPosition.UP, 200, smooth=True)

async def action_wide_mouse_sweep(tab):
    """Simulates a user moving the mouse across the screen arbitrarily."""
    print("Executing: Wide Mouse Sweep")
    # Determine sweeping from left-to-right or right-to-left
    if random.choice([True, False]):
        start_x, end_x = random.randint(10, 200), random.randint(700, 1100)
    else:
        start_x, end_x = random.randint(700, 1100), random.randint(10, 200)
        
    start_y = random.randint(50, 800)
    end_y = random.randint(50, 800)

    await tab.mouse.move(start_x, start_y, humanize=True)
    await asyncio.sleep(random.uniform(0.1, 0.5))
    await tab.mouse.move(end_x, end_y, humanize=True)
    await asyncio.sleep(random.uniform(0.5, 1.5))

async def action_micro_clicks(tab):
    """Simulates distracted clicking in neutral 'dead' areas with heavy cursor jitter."""
    print("Executing: Micro Clicks")
    
    # Target "dead" margin areas (far left/right or extreme top/bottom)
    x = random.choice([random.randint(10, 150), random.randint(850, 1100)])
    y = random.choice([random.randint(10, 150), random.randint(600, 900)])
    
    await tab.mouse.move(x, y, humanize=True)
    await asyncio.sleep(random.uniform(0.3, 1.0))

    # Perform 1 to 4 random, jittery clicks
    for _ in range(random.randint(1, 4)):
        # Apply a tiny bit of jitter between clicks (like a shaky hand)
        x += random.randint(-4, 4)
        y += random.randint(-4, 4)
        await tab.mouse.move(x, y, humanize=False) # Skip humanize for micro pixel shifts
        
        # await tab.mouse.click() # Actually execute the click!
        
        # Sometime double click fast, sometimes pause
        await asyncio.sleep(random.uniform(0.05, 0.4))

async def action_read_and_highlight(tab: Tab):
    """Simulates a user highlighting a line of text while reading it."""
    print("Executing: Read and Highlight")
    
    # Pick a starting point vaguely in the central content area
    start_x = random.randint(200, 500)
    start_y = random.randint(300, 600)
    
    # Move to the start of the "sentence"
    await tab.mouse.move(start_x, start_y, humanize=True)
    await asyncio.sleep(random.uniform(0.5, 1.0))
    
    # Drag horizontally to the right, simulating highlighting text
    drag_length = random.randint(150, 450)
    # Add a slight vertical drift to mimic an imperfect human hand dragging across a line
    end_y = start_y + random.randint(-10, 10) 
    
    await tab.mouse.drag(start_x, start_y, start_x + drag_length, end_y, humanize=True)
    
    # Pause as if finishing reading the highlighted block
    await asyncio.sleep(random.uniform(2.0, 4.0))
    
    # "Clear" the highlight by clicking nearby in a neutral space
    clear_x = start_x + drag_length + random.randint(20, 80)
    clear_y = end_y + random.randint(20, 80)
    await tab.mouse.move(clear_x, clear_y, humanize=True)
    
    # Assuming your tab object has a click method to clear the selection
    # await tab.mouse.click()

async def action_tab_switch_hesitation(tab: Tab):
    """Simulates moving toward the browser tabs/URL bar, then changing mind."""
    print("Executing: Tab Switch Hesitation")
    
    # Start somewhere in the middle of the screen
    await tab.mouse.move(random.randint(300, 800), random.randint(300, 600), humanize=True)
    await asyncio.sleep(random.uniform(0.2, 0.5))
    
    # Move rapidly to the very top edge of the screen (tab/menu bar area)
    target_x = random.randint(100, 900)
    target_y = random.randint(5, 40) 
    
    await tab.mouse.move(target_x, target_y, humanize=True)
    
    # Hesitate at the top as if reading a notification or thinking
    await asyncio.sleep(random.uniform(0.8, 2.0))
    
    # "Nevermind" - move back down into the main content area
    return_x = target_x + random.randint(-150, 150)
    return_y = random.randint(250, 600)
    await tab.mouse.move(return_x, return_y, humanize=True)

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

async def perform_human_loop(tab: Tab, selector: str, max_attempts=2):
    """Loops through human actions until the selector is found."""
    actions = [
        action_scroll_and_hover, action_random_drag, action_reading_pause,
        action_hesitant_scroll, action_wide_mouse_sweep, action_micro_clicks,
        action_read_and_highlight, action_tab_switch_hesitation
    ]
    random.shuffle(actions)
    
    for i in range(min(max_attempts, len(actions))):
        try:
            # Execute a random unique action
            await actions[i](tab)
            
            # Check if element exists
            print(f"Check {i+1}: Looking for selector...")
            found = await tab.query(selector, timeout=3, raise_exc=False)
            if found:
                print("Element found during human-like actions!")
                return True
        except Exception as e:
            print(f"Action {i} failed: {e}")
            await tab.take_screenshot(f'{FILE_DIR}/action_error_{i}.png')
            
    return False

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
        await asyncio.sleep(random.uniform(2.0, 4.0))
        # for _ in range(random.randint(2, 4)):
        #     scroll_amount = random.randint(200, 500)
        #     await tab.scroll.by(ScrollPosition.DOWN, scroll_amount, smooth=True)
        #     await asyncio.sleep(random.uniform(0.8, 2.0))
        # await tab.mouse.drag(100, 200, 500, 400, humanize=True)
        # await tab.take_screenshot(f'{FILE_DIR}/trying_to_login.png', quality=90, beyond_viewport=True)
        # await tab.mouse.move(500, 300, humanize=True)
        # wait for page to load
        selector = "//h1[contains(@class, 'maintitle') and contains(text(), 'Opportunities')]"

        success = await perform_human_loop(tab, selector)

        if not success:
            print("Target not found after actions. Forcing navigation/wait...")
            try:
                await tab.go_to(url)
                await tab.find_or_wait_element(By.XPATH, selector, timeout=15)
                await tab.take_screenshot(f'{FILE_DIR}/recovery_success.png')
            except Exception as e:
                print(f"Final recovery failed: {e}")
                await tab.take_screenshot(f'{FILE_DIR}/final_timeout.png')
        
        # try:
        #     await tab.find_or_wait_element(By.XPATH, selector, timeout=5)
        #     print("Found the Opportunities header!")
        # except Exception as e:
        #     print(f"Timed out waiting for text: {e}")
        #     url = "https://bcbid.gov.bc.ca/page.aspx/en/rfp/request_browse_public"
        #     print(f"Navigating to {url}...")
        #     await tab.go_to(url)
        #     await tab.find_or_wait_element(By.XPATH, selector, timeout=15)
        #     await tab.take_screenshot(f'{FILE_DIR}/trying_to_login2.png', quality=90, beyond_viewport=True)
        # take a screenshot
        # await tab.take_screenshot(f'{FILE_DIR}/after_login.png', quality=90, beyond_viewport=True)
        # 3. Click on "Browse Opportunities"
        # Based on the uploaded HTML, the ID is 'body_x_btnPublicOpportunities'
        # print("Clicking on 'Browse Opportunities'...")
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
            # max_date = datetime.now().strftime('%Y-%m-%d')
            
            # OR if you literally meant "2 days in the future" for min_date, use:
            # min_date = (datetime.now() + timedelta(days=2)).strftime('%Y-%m-%d')

            # Inject the values directly into the input fields and trigger the 'change' event
                                
            # // 2. Set Max Date
            # const maxInput = document.getElementById('body_x_txtRfpBeginDatemax');
            # if (maxInput) {{
            #     maxInput.value = '{max_date}';
            #     maxInput.dispatchEvent(new Event('change', {{ bubbles: true }}));
            # }}
            
            await tab.execute_script(f"""
                (() => {{
                    // 1. Set Min Date
                    const minInput = document.getElementById('body_x_txtRfpBeginDate');
                    if (minInput) {{
                        minInput.value = '{min_date}';
                        minInput.dispatchEvent(new Event('change', {{ bubbles: true }}));
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
                    # save the page source to a html page
                    with open(f'{FILE_DIR}/page_{page}.html', 'w', encoding='utf-8') as f:
                        f.write(page_source)
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
