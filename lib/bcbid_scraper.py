import asyncio
import os
import time
import lxml
import re
import pandas as pd
import random
from io import StringIO
from pydoll.browser.chromium import Chrome
from pydoll.browser.options import ChromiumOptions
from pydoll.browser.tab import Tab
from pydoll.constants import Key
from pydoll.constants import By
from pydoll.constants import ScrollPosition
from pydoll.exceptions import FailedToStartBrowser
from lib.utils import find_bcbid_city_match, load_city_mapping, regional_districts, target_organizations, \
scan_text_for_cities, DEFAULT_CITY
from datetime import datetime, timedelta

FILE_DIR = "screenshots"

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

    # Handle Headless environment variables
    env_headless = os.environ.get("NODRIVER_HEADLESS") == "True"
    # url encode password
    proxy_url = os.environ.get("PROXY_URL")
    if proxy_url:
        options.add_argument(f'--proxy-server={proxy_url}')
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
        
        url = "https://bcbid.gov.bc.ca/page.aspx/en/rfp/request_browse_public"
        days_to_check = int(os.getenv('DAYS_TO_CHECK', 1))
        # Calculate consistent dates for both passes
        min_date = (datetime.now() - timedelta(days=days_to_check)).strftime('%Y-%m-%d')
        max_date = datetime.now().strftime('%Y-%m-%d')

        # Create our scan sequences for the dual extraction
        scans = [
            {
                "name": "Region Scan",
                "input_id": "body_x_selRfpIdAreaLevelAreaNode_search",
                "values": regional_districts
            },
            {
                "name": "Organization Scan",
                "input_id": "body_x_selBpmIdOrgaLevelOrgaNode_search", 
                "values": target_organizations
            }
        ]
        # if directory exists
        if not os.path.exists(FILE_DIR):
            # remove directory
            os.mkdir(FILE_DIR)
        global_all_table_htmls = []
        global_all_dfs = []
        print(f"Navigating to {url} to state...")
        await tab.go_to(url)
        for scan_index, scan in enumerate(scans):
            print(f"\n========== Starting {scan['name']} ==========")

            await asyncio.sleep(random.uniform(2.0, 4.0))

            # Wait for page to load via header
            selector = "//h1[contains(@class, 'maintitle') and contains(text(), 'Opportunities')]"
            success = await perform_human_loop(tab, selector)

            if not success:
                print("Target not found after actions. Forcing navigation/wait...")
                try:
                    await tab.go_to(url)
                    await tab.find_or_wait_element(By.XPATH, selector, timeout=15)
                    await tab.take_screenshot(f'{FILE_DIR}/{scan["name"]}_recovery_success.png')
                except Exception as e:
                    print(f"Final recovery failed: {e}")
                    await tab.take_screenshot(f'{FILE_DIR}/{scan["name"]}_final_timeout.png')

            # 1. Set specific scan entity filters (Region or Organizations)
            try:
                print(f"Setting text filters for {scan['name']}...")
                filter_search = await tab.find(scan['input_id'], timeout=15)
                await filter_search.click()
                # also click on the parent element
                # await filter_search.parent().click()

                for value_tag in scan['values']:
                    print(f"Typing: {value_tag}")
                    await filter_search.type_text(value_tag, humanize=False)
                    await asyncio.sleep(random.uniform(0.5, 0.7))
                    await tab.keyboard.press(Key.ENTER)
                    await asyncio.sleep(random.uniform(0.5, 1.2))

                await tab.keyboard.press(Key.ESCAPE)
            except Exception as e:
                print(f"Error during {scan['name']} filtering: {e}")
                break

            # 2. Set Dates filters (applied on top of current scan limits)
            try:
                print("Setting date filters...")
                await tab.execute_script(f"""
                    (() => {{
                        const minInput = document.getElementById('body_x_txtRfpBeginDate');
                        if (minInput) {{
                            minInput.value = '{min_date}';
                            minInput.dispatchEvent(new Event('change', {{ bubbles: true }}));
                        }}

                        const datePickerDiv = document.getElementById('ui-datepicker-div');
                        if (datePickerDiv) {{
                            datePickerDiv.style.display = 'none';
                        }}
                    }})()
                """)

                await asyncio.sleep(5)

                try:
                    search_button = await tab.find(id='body_x_prxFilterBar_x_cmdSearchBtn')
                    await search_button.click()
                except Exception as e:
                    print(f"Error clicking search button: {e}")
                
                print(f"Set Issue Date filters: Min = {min_date}, Max = {max_date}")
            except Exception as e:
                print(f"Error during date filtering: {e}")
            # ==========================================
            # FILTER VALIDATION CHECK
            # ==========================================
            print(f"Validating if {scan['name']} filters were successfully applied...")
            
            # Give the AJAX/DOM a moment to render the filter summary tags
            await asyncio.sleep(3) 

            # The summary data-id matches the input_id but without '_search'
            # e.g., 'body_x_selBpmIdOrgaLevelOrgaNode_search' -> 'body_x_selBpmIdOrgaLevelOrgaNode'
            summary_data_id = scan['input_id'].replace('_search', '')

            validation_script = f"""
                (() => {{
                    const summaryUl = document.querySelector('ul.tag-summary[data-id="{summary_data_id}"]');
                    if (!summaryUl) return false;
                    
                    // If it has the 'hidden' class, it means no filters were applied for this category
                    if (summaryUl.classList.contains('hidden')) return false;
                    
                    // Ensure there is at least one active tag value rendered
                    return summaryUl.querySelectorAll('li.tag-value').length > 0;
                }})()
            """
            
            validation_result = await tab.execute_script(validation_script, return_by_value=True, await_promise=True)
            
            try:
                filters_applied = validation_result.get('result', {}).get('result', {}).get('value')
            except Exception as e:
                print(f"Error parsing validation script result: {e}")
                filters_applied = False

            if not filters_applied:
                print(f"⚠️ ERROR: Validation failed for {scan['name']}. The filter labels did not appear.")
                # Take an error screenshot for debugging later
                await tab.take_screenshot(f'{FILE_DIR}/{scan["name"].replace(" ", "_")}_validation_error.png', quality=90)
                
                # You can choose to skip to the next scan here, or continue anyway. 
                # If you want to skip:
                # break 
                # If you want to just log it and continue as requested:
                print("Continuing despite missing filter tags...")
                from lib.discord import send_discord_message
                discord_webhook_url = os.getenv('DISCORD_WEBHOOK_URL')
                send_discord_message(f"BC Bid Scraper Failed to start the scan for {scan['name']} @grandfleet:", discord_webhook_url)
                break
            else:
                print(f"✅ Validation passed: {scan['name']} tags are visible in the summary.")
            # ==========================================
            # 3. Scrape current Tabular Data
            try:
                print(f"Starting tabular data extraction for {scan['name']}...")
                page = 1
                max_pages = 10
                
                while page <= max_pages:
                    print(f"[{scan['name']}] Extracting data from page {page}...")
                    
                    try:
                        # Wait for AJAX table to fully load
                        await asyncio.sleep(8)
                        page_source = await tab.page_source
                        
                        # Save the page source to an html page
                        with open(f'{FILE_DIR}/{scan["name"].replace(" ", "_")}_page_{page}.html', 'w', encoding='utf-8') as f:
                            f.write(page_source)
                            
                        dfs = pd.read_html(
                                StringIO(page_source), 
                                attrs={'id': 'body_x_grid_grd'}
                            )
                        df = dfs[0]

                        # Extract URLs
                        tree = lxml.html.fromstring(page_source)
                        rows = tree.xpath("//table[@id='body_x_grid_grd']//tr[td]")
                        
                        urls = []
                        for row in rows:
                            hrefs = row.xpath("./td[2]//a/@href")
                            if hrefs:
                                urls.append(f"https://bcbid.gov.bc.ca{hrefs[0]}")
                            else:
                                urls.append("")
                        
                        df['Opportunity Url'] = pd.Series(urls)
                        table_html = df.to_html(index=False)
            
                        global_all_table_htmls.append(table_html)
                        global_all_dfs.append(df)
                            
                        # Check pagination
                        scriptReturnResult = await tab.execute_script("""
                            (() => {
                                const nextBtn = document.getElementById("body_x_grid_gridPagerBtnNextPage");
                                if (!nextBtn) return true;
                                const isClassDisabled = nextBtn.className.toLowerCase().includes('disabled');
                                return isClassDisabled || nextBtn.disabled;
                            })()
                        """, return_by_value=True, await_promise=True)
                        print(f"Next button is disabled: {scriptReturnResult}")

                        try:
                            is_disabled = scriptReturnResult.get('result', {}).get('result', {}).get('value')
                        except Exception as e:
                            print(f"Error checking if next button is disabled: {e}")
                            is_disabled = True
                        
                        if is_disabled:
                            print(f"Reached the last page for {scan['name']}.")
                            break
                            
                        print(f"Clicking 'Next' button to navigate to page {page + 1}...")
                        await tab.execute_script('document.getElementById("body_x_grid_gridPagerBtnNextPage").click()')
                        
                        page += 1
                        
                    except Exception as e:
                        print(f"Error encountered during pagination on page {page}: {e}")
                        break

                await tab.take_screenshot(f'{FILE_DIR}/{scan["name"].replace(" ", "_")}_last_page.png', quality=90, beyond_viewport=True)
            except Exception as e:
                print(f"Error during tabular data extraction for {scan['name']}: {e}")
            # make FILE_DIR if it doesnt exist
            if not os.path.exists(FILE_DIR):
                os.mkdir(FILE_DIR)
            # Optional network events bundle save per scan
            await tab.save_bundle(f"{FILE_DIR}/bcbid_{scan['name'].replace(' ', '_')}.zip")

            # click the reset button to start the next scan
            # body_x_prxFilterBar_x_cmdRazBtn
            
            print(f"Clicking 'Reset' button...")

            if scan_index < len(scans) - 1:
                try:
                    await tab.execute_script('document.getElementById("body_x_prxFilterBar_x_cmdRazBtn").click()')
                    # let reset happen
                    await asyncio.sleep(10)
                except Exception as e:
                    print(f"Error clicking 'Reset' button: {e}")
            print(f"Scan {scan['name']} complete.")
            # save csv as temp with scan name combine global dfs
            if global_all_dfs:
                df_temp = pd.concat(global_all_dfs, ignore_index=True)
                df_temp.to_csv(f"{FILE_DIR}/{scan['name'].replace(' ', '_')}.csv", index=False)

        # --- END OF SCANS: Combine, Deduplicate and Save Phase ---
        print(f"\n========== Scans complete. Processing output... ==========")
        
        try:
            with open(f"{FILE_DIR}/bcbid.html", "w", encoding="utf-8") as f:
                f.write("<html><head><meta charset='utf-8'></head><body>\n")
                for idx, html_content in enumerate(global_all_table_htmls):
                    f.write(f"<h2>Table Page Extraction {idx + 1}</h2>\n")
                    f.write(html_content)
                    f.write("\n<hr>\n")
                f.write("</body></html>\n")
            print(f"Successfully compiled all tables to 'bcbid.html'")
        except Exception as e:
            print(f"Failed to write combined HTML file: {e}")

        if global_all_dfs:
            try:
                # Concatenate all DataFrames
                final_df = pd.concat(global_all_dfs, ignore_index=True)
                # final_df.dropna(how='all', inplace=True) 
                
                original_count = len(final_df)
                # Drop duplicate URLs gathered from combining scans
                final_df.drop_duplicates(subset=['Opportunity Url'], inplace=True, keep='first')
                
                print(f"Total rows extracted: {original_count}. Distinct unique rows after merge: {len(final_df)}")
                
                # Save DataFrames
                final_df.to_csv(f"{FILE_DIR}/bid_recent_raw.csv", index=False, encoding='utf-8')
                final_df.to_csv(f"{FILE_DIR}/bid_recent.csv", index=False, encoding='utf-8')
                print("Successfully combined and saved merged data to CSVs.")
            except Exception as e:
                print(f"Failed to concatenate or save CSV: {e}")
        else:
            print("No DataFrames were created across any scans. Skipping CSV generation.")


        # --- Deep Dive Link Extraction Phase ---
        csv_path = f"{FILE_DIR}/bid_recent.csv"
        
        if os.path.exists(csv_path):
            print(f"Found {csv_path}. Processing individual distinct opportunity URLs...")
            df = pd.read_csv(csv_path)
            CITY_MAPPING = load_city_mapping('data/city.csv')
            
            for col in ['Name', 'Email', 'Phone', 'City']:
                if col not in df.columns:
                    df[col] = ""

            for index, row in df.iterrows():
                try:
                    url = row.get('Opportunity Url')
                    if pd.isna(url) or not url:
                        continue

                    print(f"Navigating to {url}")
                    await tab.go_to(url)
                    
                    await asyncio.sleep(random.uniform(1.5, 3.0))

                    selector = "//h2[contains(text(), 'RFx General Information')]"
                    success = await perform_human_loop(tab, selector, max_attempts=1)

                    if not success:
                        print(f"Warning: Could not definitively find general info tab on {url}")

                    page_source = await tab.page_source
                    clean_text = re.sub(r'<[^>]+>', ' ', page_source)
                    clean_text = re.sub(r'\s+', ' ', clean_text)

                    email_match = re.search(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', clean_text)
                    email = email_match.group(0) if email_match else ""

                    name = ""
                    phone = ""
                    
                    if email:
                        email_idx = clean_text.find(email)
                        start_idx = max(0, email_idx - 200)
                        end_idx = min(len(clean_text), email_idx + 200)
                        window = clean_text[start_idx:end_idx]

                        attention_match = re.search(r'Attention:\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)', window)
                        if attention_match:
                            name = attention_match.group(1).strip()
                        else:
                            pre_email_window = clean_text[max(0, email_idx - 80):email_idx]
                            name_match = re.search(r'\b([A-Z][a-z]+\s+[A-Z][a-z]+)\b', pre_email_window)
                            if name_match:
                                name = name_match.group(1).strip()

                        phone_match = re.search(r'\(?\b\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b', window)
                        if phone_match:
                            phone = phone_match.group(0).strip()

                    row_dict = row.to_dict()
                    city = find_bcbid_city_match(row_dict, CITY_MAPPING)

                    if city.lower() == DEFAULT_CITY:
                        deep_scan_city = scan_text_for_cities(clean_text, CITY_MAPPING)
                        city = deep_scan_city

                    df.at[index, 'Email'] = email
                    df.at[index, 'Name'] = name
                    df.at[index, 'Phone'] = phone
                    df.at[index, 'City'] = city

                except Exception as e:
                    print(f"Error processing {url}: {e}")

            df.to_csv(csv_path, index=False, encoding='utf-8')
            print(f"Successfully processed URLs and updated {csv_path} with Contact fields.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except FailedToStartBrowser as e:
        from lib.discord import send_discord_message
        discord_webhook_url = os.getenv('DISCORD_WEBHOOK_URL')
        send_discord_message(f"BC Bid Scraper Failed to start the browser @grandfleet: {e}", discord_webhook_url)
        raise FailedToStartBrowser(f"Failed to start the browser: {e}")

