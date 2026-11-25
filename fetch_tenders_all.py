import asyncio
import os
import pandas as pd
from dotenv import load_dotenv
from io import StringIO
from bs4 import BeautifulSoup, NavigableString
import time
import random
import traceback
import re
import json
from pathlib import Path
# Pydoll Imports
from pydoll.browser.chromium import Chrome
from pydoll.browser.options import ChromiumOptions
from pydoll.browser.tab import Tab
from pydoll.constants import Key, By, ScrollPosition
from pydoll.protocol.network.types import ErrorReason
from pydoll.protocol.fetch.events import FetchEvent, RequestPausedEvent
from pydoll.protocol.fetch.types import AuthChallengeResponseType
from pydoll.commands import FetchCommands
import random
import string
# Assuming you have a captcha solving utility like the one in your example
# If not, you may need to find or create one. For this example, we will
# assume a placeholder function exists.
# copied from bc bid logic

BUNDLE_DIR = Path("./downloaded_bundles")

# 1. Locate the expected Profile directory paths
default_profile_dir = BUNDLE_DIR / "Default"

# 2. Force create the folder tree if it doesn't exist
default_profile_dir.mkdir(parents=True, exist_ok=True)

# 3. Create empty placeholder files so nodriver doesn't throw a FileNotFoundError
pref_file = default_profile_dir / "Preferences"
pref_backup = default_profile_dir / "Preferences.backup"

if not pref_file.exists():
    pref_file.write_text(json.dumps({}))
if not pref_backup.exists():
    pref_backup.write_text(json.dumps({}))
    
# Global variable to track login status across different portal attempts
LOGIN_DISABLED = True

def generate_session_id(length=8):
    characters = string.ascii_letters + string.digits
    return ''.join(random.choices(characters, k=length))

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
# --- Helper Function (Unchanged) ---
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
            base_dir = os.getenv('BASE_DIR', "screenshots")
            print(f"Action {i} failed: {e}")
            await tab.take_screenshot(f'{base_dir}/action_error_{i}.png')
            
    return False

# This function works on the parsed HTML (soup) and does not need modification.
def get_tag_on_details_page(soup, labelText="Project Description:"):
    """
    Finds a label tag (<b>) and extracts the text that follows it.
    This function is robust enough to handle different HTML structures where the value
    might be in a sibling <div>, a following text node, or just within the parent element.
    """
    stripped_labelText = labelText.strip()
    found_b_tag = soup.find(lambda tag: tag.name == 'b' and tag.get_text(strip=True).startswith(stripped_labelText))
    project_text = ""
    if found_b_tag:
        project_text = ""

        # Case 1: The value is in a sibling <div> (e.g., "Project Description:")
        description_div = found_b_tag.find_next_sibling('div')
        if description_div:
            project_text = description_div.get_text(strip=True)
            return project_text

        # Case 2: The value is in the parent element's text, immediately following the label.
        parent_element = found_b_tag.parent
        if parent_element:
            parent_full_text = parent_element.get_text(strip=True)
            b_tag_actual_text = found_b_tag.get_text(strip=True)
            
            if parent_full_text.startswith(b_tag_actual_text):
                project_text = parent_full_text[len(b_tag_actual_text):].strip()

            # Fallback if stripping/spacing causes mismatches
            elif parent_full_text.startswith(stripped_labelText):
                project_text = parent_full_text[len(stripped_labelText):].strip()

        # Case 3: Fallback - the value is in the immediate next sibling (could be a string or another tag)
        if not project_text:
            next_sibling = found_b_tag.next_sibling
            if next_sibling:
                if isinstance(next_sibling, NavigableString):
                    candidate_text = next_sibling.string
                    if candidate_text:
                        project_text = candidate_text.strip()
                elif hasattr(next_sibling, 'get_text'): # It's a tag
                    project_text = next_sibling.get_text(strip=True)
        if not project_text:
            return ""
        return project_text
    else:
        # print(f"Could not find the '{labelText}' tag.") # Optional for debugging
        return "" # Return empty if the label itself is not found


async def fetch_single_tender(tab: Tab, config: dict):
    """
    Asynchronously navigates to a URL using a given Camoufox browser instance, 
    retrieves the inner HTML, and scrapes tender data.
    
    Args:
        browser (AsyncCamoufox): The persistent AsyncCamoufox browser instance.
        config (dict): A dictionary containing 'base_url', 'csv_file_name', and 'city_name'.
    """

    global LOGIN_DISABLED
    failed_to_parse_open_date_num = 0
    BASE_URL = config['base_url']
    CSV_FILE_NAME = config['csv_file_name']
    CITY_NAME = config['city_name']

    EMAIL = os.getenv('EMAIL')
    PASSWORD = os.getenv('PASSWORD')
    base_dir = os.getenv('BASE_DIR', "screenshots")

    # Create directory if it doesn't exist
    os.makedirs(base_dir, exist_ok=True)

    print(f"\n--- Starting fetch for {CITY_NAME.capitalize()} tenders ---")

    try:
        # Create a new page for each tender within the existing browser instance
        print(f"Navigating to {BASE_URL} page...")
        initial_url = f'{BASE_URL}'
        async with tab.expect_cloudflare_turnstile():
            await tab.go_to(initial_url)
        login_flag = False
        try:
            login_element = await tab.query('//*[text()="Log In"]', raise_exc=False, timeout=5)
            register_element = await tab.query('//*[text()="Register"]', raise_exc=False, timeout=5)
        except Exception as e:
            login_element = None 
            register_element = None
        try:
            euna_supplier_network = await tab.query('//*[text()="My Euna Supplier Network]"', timeout=5, raise_exc=False)
        except Exception as e:
            euna_supplier_network = None

        if login_element and register_element:
            print("user is not logged in, logging in...")
            login_flag = True
        elif euna_supplier_network:
            print("user is already logged in...")
            login_flag = False
        try:
            url_result = await tab.execute_script('window.location.href', return_by_value=True)
            href = url_result.get('result', {}).get('value', '')
            try:
                pass
                if "login" in href or login_flag:
                    if not LOGIN_DISABLED:
                        # go to login page
                        await tab.go_to(f"{initial_url}/login")
                        print(f"Current page is login for {CITY_NAME}, proceeding with login...")
                        print("Entering email...")
                        email_input = await tab.find(tag_name="input", type="email", timeout=10)
                        await email_input.type_text(EMAIL, humanize=True)
                        submit_btn = await tab.find(tag_name="button", type="submit", timeout=5)
                        await submit_btn.click()
            
                        await asyncio.sleep(6) # Wait for password field to appear
    
                        print("Entering password...")
                        pass_input = await tab.find(tag_name="input", type="password", timeout=10)
                        await pass_input.type_text(PASSWORD, humanize=True)
                        submit_btn_pass = await tab.find(tag_name="button", type="submit", timeout=5)
                        await submit_btn_pass.click()
    
                        print("Login submitted. Waiting for opportunities page...")
                        LOGIN_DISABLED = True # Global flag: Don't try again for other portals
                else:
                    # await page.screenshot(path=f"{base_dir}/{CITY_NAME}_no_login.png")
                    print(f"The current page for {CITY_NAME} is not a login page (or 'login' is not in the URL). Assuming already logged in or direct access.")
            except Exception as e:
                traceback.print_exc()
                LOGIN_DISABLED = True # Global flag: Don't try again for other portals
                await tab.go_to(initial_url)
                print(f"Failed to login for {CITY_NAME}. Skipping.")
            # Log In look to element Log In, if so, set login flag to true
            await asyncio.sleep(random.uniform(4, 5))
            page_source = await tab.page_source()
            with open(f"{base_dir}/{CITY_NAME}_bonfire.html", "w", encoding='utf-8', errors='ignore') as f:
                f.write(page_source)

            # --- 2. Scrape the Main Table ---
            print(f"Parsing opportunities table for {CITY_NAME}...")
            dataTables_scroll_soup = BeautifulSoup(page_source, 'html.parser')
            table_wrapper = dataTables_scroll_soup.find('div', class_='dataTables_scroll')
            if not table_wrapper:
                # Fallback: Sometimes if scrolling isn't triggered, DataTables just uses a wrapper ID
                table_wrapper = dataTables_scroll_soup.find('div', id=lambda x: x and x.endswith('_wrapper'))

            if not table_wrapper:
                print("this doesnt matter if it fails it fails")
            # Extract Headers
            header_list = []
            header_table_soup = dataTables_scroll_soup.find('div', class_='dataTables_scrollHead')
            if header_table_soup:
                headers_th = header_table_soup.find_all('th')
                header_list = [th.get_text(strip=True) for th in headers_th]
                if header_list and header_list[-1].lower() == "action":
                    header_list[-1] = "Action Link"
            else:
                print(f"Warning: Could not find headers for {CITY_NAME}. Using default headers.")
                header_list = ['Status', 'Ref. #', 'Project', 'Close Date', 'Days Left', 'Action Link', 'Contact Information']

            # Extract Data Rows
            all_rows_data = []
            body_table_soup = dataTables_scroll_soup.find('div', class_='dataTables_scrollBody')
            if body_table_soup:
                tbody = body_table_soup.find('tbody')
                if tbody:
                    for row_tr in tbody.find_all('tr'):
                        cells_td = row_tr.find_all('td')
                        row_data = [cell.get_text(separator=' ', strip=True) for cell in cells_td]
                        
                        # Special handling for the last cell to get the href
                        if cells_td:
                            link_tag = cells_td[-1].find('a')
                            row_data[-1] = link_tag['href'] if link_tag and link_tag.has_attr('href') else None
                        
                        if len(row_data) == len(header_list):
                            all_rows_data.append(row_data)

            if not all_rows_data:
                print(f"No data rows found in the table for {CITY_NAME}.")
                content_df = pd.DataFrame(columns=header_list)
            else:
                content_df = pd.DataFrame(all_rows_data, columns=header_list)
                print(f"Successfully scraped {len(content_df)} opportunities from the main table for {CITY_NAME}.")
                # filter out all entries that have closed, cancelled and awarded in the status under the status column
                # --- FILTERING LOGIC START ---
                # Combine statuses into a regex pattern separated by '|' (OR)
                exclude_pattern = 'closed|cancelled|awarded'
                
                # Filter out rows where 'Status' matches the pattern (case-insensitive)
                # The ~ operator inverts the boolean mask (keeps what DOES NOT match)
                # we have past opportunities table, completely pointless to parse it
                content_df = content_df[~content_df['Status'].str.contains(exclude_pattern, case=False, na=False)]
                
                print(f"Filtered DataFrame: {len(content_df)} active opportunities remaining.")


            # --- 3. Scrape Detail Pages ---
            project_data = []
            for index, row in content_df.iterrows():
                action_link = row["Action Link"]
                if action_link:
                    full_link = f"{BASE_URL}{action_link}"
                    print(f"({index + 1}/{len(content_df)}) Navigating to detail page for {CITY_NAME}: {full_link}")
                    
                    try:
                        if index < 2:
                            time_to_wait_captcha = 15 if 'fraserhealth' in full_link else 15
                            
                            async with tab.expect_cloudflare_turnstile(time_to_wait_captcha=time_to_wait_captcha):
                                await tab.go_to(full_link)
                        else:
                            # Direct navigation for everything else
                            await tab.go_to(full_link)
                            await asyncio.sleep(random.uniform(3, 4))
                        # dont need the human loop
                        # selector = "//body"
                        # await perform_human_loop(tab, selector, 1)
                        # print(f"Failed to solve captcha challenge for detail page {full_link}. Skipping.")
                        new_page_source = await tab.page_source()
                        with open(f"{base_dir}/{CITY_NAME}_tender_scrap_{index}.html", "w", encoding='utf-8', errors='ignore') as f:
                            f.write(new_page_source)

                        # Take screenshot and get page source
                        screenshot_path = f"{base_dir}/{CITY_NAME}_tender_{index}.png"
                        await tab.take_screenshot(path=screenshot_path)

                        # Parse details from the new page
                        detail_soup = BeautifulSoup(new_page_source, 'html.parser')
                        
                        type_text = get_tag_on_details_page(detail_soup, labelText = "Type:")
                        project_description = get_tag_on_details_page(detail_soup, labelText = "Project Description:")
                        open_date = get_tag_on_details_page(detail_soup, labelText = "Open Date:")
                        close_date = get_tag_on_details_page(detail_soup, labelText = "Close Date:")
                        days_left = get_tag_on_details_page(detail_soup, labelText = "Days Left:")
                        contact_information = get_tag_on_details_page(detail_soup, labelText = "Contact Information:")

                        status_val = row.get('Status')
                        ref_val = row.get('Ref. #')
                        project_val = row.get('Project')
                        new_page_source = await tab.page_source()
                        detail_soup = BeautifulSoup(new_page_source, 'html.parser')

                        # Mechanism 2: Fallback to checking the new div-based layout inside the details page
                        project_container = detail_soup.find('div', class_='projectDetailContainer')
                        if project_container:
                            # Build a dictionary of all available fields from the container
                            div_data = {}
                            sections = project_container.find_all('div', class_='modalSection projectDetailSection')
                            
                            for section in sections:
                                b_tag = section.find('b')
                                if b_tag:
                                    # Extract Key (e.g., "Open Date") and remove trailing colon
                                    key = b_tag.get_text(strip=True).rstrip(':')
                                    
                                    # Extract Value by stripping the <b> tag's text out of the full section text
                                    full_text = section.get_text(separator=' ', strip=True)
                                    b_text = b_tag.get_text(separator=' ', strip=True)
                                    value = full_text.replace(b_text, '', 1).strip()
                                    
                                    div_data[key] = value

                            # Fill in any missing details from Mechanism 1 using the extracted div_data
                            if not type_text: type_text = div_data.get('Type')
                            if not project_description: project_description = div_data.get('Project Description')
                            if not open_date: open_date = div_data.get('Open Date')
                            if not close_date: close_date = div_data.get('Close Date')
                            if not days_left: days_left = div_data.get('Days Left')
                            if not contact_information: contact_information = div_data.get('Contact Information')
                            
                            # Fill in row values if they were missing from the initial main table scrape
                            if not status_val: status_val = div_data.get('Status')
                            if not ref_val: ref_val = div_data.get('Ref. #')
                            if not project_val: project_val = div_data.get('Project')
                        # Mechanism 3: Final emergency fallback for open_date
                        new_page_source = await tab.page_source()
                        detail_soup = BeautifulSoup(new_page_source, 'html.parser')
                        if not open_date:
                            # Search the entire soup for an element containing "Open Date:"
                            open_date_element = detail_soup.find(string=lambda text: text and "Open Date" in text)
                            print("scanned for open_date_element", open_date_element)
                            if open_date_element:
                                # Get the parent container's full text
                                parent_text = open_date_element.parent.get_text(strip=True)
                                # Strip out the "Open Date:" label to isolate just the date value
                                open_date = parent_text.replace("Open Date:", "").strip()

                        if not open_date:
                            date_pattern = r"(\b\d{1,4}[-/.]\d{1,2}[-/.]\d{1,4}\b|\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* \d{1,2}(?:st|nd|rd|th)?,? \d{4}(?:,?\s+\d{1,2}:\d{2}(?::\d{2})?\s*[AP]M\s*[A-Z]{1,5})?\b)"
                            all_matches = re.findall(date_pattern, new_page_source, re.IGNORECASE)

                            if all_matches:
                                first_raw_date = all_matches[0]
                                print(f"Found raw text date match: {first_raw_date}")
                    
                                try:
                                    # Use dateutil parser to cleanly format the date string
                                    # make sure length is greater than 5 characters
                                    if len(first_raw_date) > 5:
                                        open_date = first_raw_date
                                        print(f"Successfully parsed fallback date: {open_date}")
                                    else:
                                        print("failed to parse date")
                                        failed_to_parse_open_date_num = failed_to_parse_open_date_num + 1
                                        if failed_to_parse_open_date_num >= 5:
                                            break
                    
                                except (ValueError, TypeError) as e:
                                    print(f"Could not parse the found date string: {e}")
                        page_data = [
                            status_val, ref_val, project_val,
                            type_text, full_link, project_description,
                            open_date, close_date, days_left, contact_information
                        ]
                        project_data.append(page_data)
                        if "fraserhealth" in full_link or "icbc" in full_link:
                            await asyncio.sleep(random.uniform(5, 8))
                            

                    except Exception as e:
                        traceback.print_exc()
                        print(f"Error processing link {full_link} for {CITY_NAME}: {e}")
                else:
                    print(f"No Action Link found for row {index} in {CITY_NAME}.")

            # --- 4. Save Final Data ---
            if project_data:
                final_header_list = ['Status', 'Ref', 'Project', 'Type', "Link", 'Project Description', 'Open Date', 'Close Date', 'Days Left', 'Contact Information']
                final_df = pd.DataFrame(project_data, columns=final_header_list)
                
                output_path = os.path.join(base_dir, f"{CSV_FILE_NAME}")
                final_df.to_csv(output_path, index=False)
                print(f"Scraping complete for {CITY_NAME}. Data saved to {output_path}")
                print(final_df)
            else:
                print(f"No project detail data was collected for {CITY_NAME}.")
            
        except Exception as e:
            print(f"Error during main scraping process for {CITY_NAME}: {e}")

    except Exception as e:
        print(f"An error occurred during browser operation for {CITY_NAME}: {e}")
    finally:
        print("page should be safe here")
        pass
        # if page:
        #     await page.close() # Close the page after use

# --- Browser / proxy bandwidth settings ---
# Measured locally (2 portals, 18 tenders) through a byte-counting proxy:
#   fresh profile, old settings ........ 71.6 MB, ~92% of it Chrome's own background
#                                        downloads (optimization-guide models, component
#                                        updates, Safe Browsing lists), not Bonfire
#   reused profile, old settings ........ 9.6 MB
# Everything Chrome fetches goes through the paid proxy, so: keep the profile between
# runs (workflow cache), switch off Chrome's background downloads, and send hosts that
# don't need a Canadian residential IP around the proxy.
PROXY_HOST = 'geo.iproyal.com:12321'

# Only Bonfire (*.bonfirehub.ca) and the Cloudflare challenge need to come from the proxy IP.
PROXY_BYPASS_HOSTS = [
    "*.google.com", "*.googleapis.com", "*.googleusercontent.com", "*.gstatic.com",
    "*.gvt1.com", "*.gvt2.com", "*.google-analytics.com", "*.googletagmanager.com",
    "*.doubleclick.net", "*.pendo.io", "*.vidyard.com", "*.trackjs.com",
    "*.amazonaws.com", "assets.bonfirehub.com",
]

# Chrome features that download data in the background (not needed for scraping)
BANDWIDTH_FLAGS = [
    "--disable-component-update",
    "--disable-background-networking",
    "--safebrowsing-disable-auto-update",
    "--disable-features=OptimizationGuideModelDownloading,OptimizationHintsFetching,"
    "OptimizationTargetPrediction,OptimizationHints,Translate,MediaRouter,AutofillServerCommunication",
    "--disk-cache-size=104857600",  # cap the HTTP cache at 100 MB so the saved profile stays small
    "--password-store=basic",       # cookies stay readable when the profile moves between runners
]


def build_browser_options(user_data_dir, proxy_server=None):
    """Chrome options for the Bonfire scrape. proxy_server may embed user:pass (pydoll handles auth)."""
    options = ChromiumOptions()
    if not os.environ.get("NODRIVER_HEADLESS") == "True" and os.environ.get("DISPLAY", ":99"):
        options.add_argument('--display=:99')

    # Reuse the persisted profile: cookies (Cloudflare clearance) and cached Bonfire assets
    options.add_argument(f"--user-data-dir={user_data_dir}")

    current_time = int(time.time())
    number_last = random.randint(3, 10)
    options.browser_preferences = {
        'profile': {
            'last_engagement_time': str(current_time - (number_last * 60 * 60)),  # 3 hours ago
            'exited_cleanly': True,
            'exit_type': 'Normal',
            'password_manager_enabled': False
        },
        # Safe Browsing list updates were ~9 MB per run through the proxy
        'safebrowsing': {'enabled': False},
    }

    for flag in BANDWIDTH_FLAGS:
        options.add_argument(flag)

    if proxy_server:
        options.add_argument(f'--proxy-server={proxy_server}')
        options.add_argument(f'--proxy-bypass-list={";".join(PROXY_BYPASS_HOSTS)}')
    return options


async def enable_proxy_auth(browser, username, password):
    """
    Answer the proxy's login prompt for the whole session.

    pydoll's built-in handling (credentials embedded in --proxy-server) pauses every
    request until the first login prompt but only releases the *first* paused request.
    That used to work because Chrome's own background traffic hit the proxy first; with
    that traffic now switched off/bypassed, page loads stayed paused and every Page.navigate
    timed out on CI. These handlers stay registered, so nothing is left paused.
    """
    await browser.enable_fetch_events(handle_auth_requests=True)

    async def release(event):
        try:
            await browser.continue_request(event['params']['requestId'])
        except Exception as e:
            print(f"⚠️ Could not release paused request: {e}")

    async def answer_login(event):
        params = event['params']
        from_proxy = params.get('authChallenge', {}).get('source') == 'Proxy'
        try:
            await browser._execute_command(FetchCommands.continue_request_with_auth(
                params['requestId'],
                auth_challenge_response=(AuthChallengeResponseType.PROVIDE_CREDENTIALS if from_proxy
                                         else AuthChallengeResponseType.DEFAULT),
                proxy_username=username if from_proxy else None,
                proxy_password=password if from_proxy else None,
            ))
        except Exception as e:
            print(f"⚠️ Could not answer auth challenge: {e}")

    await browser.on(FetchEvent.REQUEST_PAUSED, release)
    await browser.on(FetchEvent.AUTH_REQUIRED, answer_login)


# Bonfire portals to scrape, in order
TENDER_CONFIGS = [
    {"base_url_env_key": "TENDER_BASE_PRYCE_URL", "csv_file_name": "bonfire_pyrce_with_links.csv", "city_name": "powell river"},
    {"base_url_env_key": "TENDER_BASE_UVIC_URL", "csv_file_name": "bonfire_uvic_with_links.csv", "city_name": "uvic"},
    {"base_url_env_key": "TENDER_BASE_BCTRANSIT_URL", "csv_file_name": "bonfire_bc_transit_with_links.csv", "city_name": "bctransit"},
    {"base_url_env_key": "TENDER_BASE_VIC_URL", "csv_file_name": "bonfire_victoria_with_links.csv", "city_name": "victoria"},
    {"base_url_env_key": "TENDER_BASE_SAANICH_URL", "csv_file_name": "bonfire_saanich_with_links.csv", "city_name": "saanich"},
    {"base_url_env_key": "TENDER_BASE_NORTHCOW_URL", "csv_file_name": "bonfire_north_cowichan_with_links.csv", "city_name": "north cowichan"},
    {"base_url_env_key": "TENDER_BASE_CVRD_URL", "csv_file_name": "bonfire_cvrd_with_links.csv", "city_name": "cvrd"},
    {"base_url_env_key": "TENDER_BASE_FNHA_URL", "csv_file_name": "bonfire_fnha_with_links.csv", "city_name": "fnha"},
    {"base_url_env_key": "TENDER_BASE_COURTENAY_URL", "csv_file_name": "bonfire_courtenay_with_links.csv", "city_name": "courtenay"},
    {"base_url_env_key": "TENDER_BASE_CENTRALSAANICH_URL", "csv_file_name": "bonfire_central_saanich_with_links.csv", "city_name": "central saanich"},
    {"base_url_env_key": "TENDER_BASE_FRASERHEALTH_URL", "csv_file_name": "bonfire_fraserhealth_with_links.csv", "city_name": "fraser health"},
    {"base_url_env_key": "TENDER_BASE_ICBC_URL", "csv_file_name": "bonfire_icbc_with_links.csv", "city_name": "icbc"},
    {"base_url_env_key": "TENDER_BASE_PHSA_URL", "csv_file_name": "bonfire_phsa_with_links.csv", "city_name": "phsa"},
    {"base_url_env_key": "TENDER_BASE_COMOX_URL", "csv_file_name": "bonfire_comox_with_links.csv", "city_name": "comox"},
    {"base_url_env_key": "TENDER_BASE_ISLANDHEALTH_URL", "csv_file_name": "bonfire_islandhealth_with_links.csv", "city_name": "victoria"},
    {"base_url_env_key": "TENDER_BASE_VIU_URL", "csv_file_name": "bonfire_viu_with_links.csv", "city_name": "victoria"},
]


async def main():
    load_dotenv() # Load environment variables from .env file

    tender_configs = TENDER_CONFIGS

    proxy_server = None
    proxy_username = os.getenv('IPROYAL_USERNAME')
    proxy_password = os.getenv('IPROYAL_PASSWORD')
    if proxy_username and proxy_password:
        # IPRoyal reads the targeting options from the password
        proxy_password = (
            f"{proxy_password}"
            f"_country-ca"
            f"_session-{generate_session_id()}"
            f"_lifetime-30m_streaming-1"
        )
        # No credentials in the URL: enable_proxy_auth() answers the login prompt instead
        proxy_server = f'http://{PROXY_HOST}'
        print(f"Using proxy {PROXY_HOST} for Bonfire/Cloudflare only; bypassing: {', '.join(PROXY_BYPASS_HOSTS)}")
    else:
        print("No proxy used")

    options = build_browser_options(BUNDLE_DIR.resolve().as_posix(), proxy_server)

    print("--- Initializing Pydoll Browser ---")
    has_errors = False
    try:
        async with Chrome(options=options) as browser:
            tab = await browser.start()
            if proxy_server:
                await enable_proxy_auth(browser, proxy_username, proxy_password)
            # --- START HIGH PERFORMANCE IMAGE BLOCKING ---
            # blocked_count = 0
            
            # async def block_resource(event: RequestPausedEvent):
            #     nonlocal blocked_count
            #     request_id = event['params']['requestId']
            #     url = event['params']['request']['url']
            #     blocked_count += 1
            #     print(f"🚫 Blocked Image ({blocked_count}): {url[:60]}")
            #     # Instantly drop image requests at client side
            #     await tab.fail_request(request_id, ErrorReason.BLOCKED_BY_CLIENT)

            # # Only intercept 'Image' resource types to maximize network speed
            # await tab.enable_fetch_events(resource_type='Image')
            # await tab.on(FetchEvent.REQUEST_PAUSED, block_resource)
            # --- END HIGH PERFORMANCE IMAGE BLOCKING ---
            await asyncio.sleep(5)
            # visit google.com and then youtube.com after 10 seconds
            for config_item in tender_configs:
                base_url = os.getenv(config_item['base_url_env_key'])
                if not base_url:
                    print(f"Skipping {config_item['city_name']} - No URL found.")
                    continue
                
                current_config = {
                    "base_url": base_url,
                    "csv_file_name": config_item['csv_file_name'],
                    "city_name": config_item['city_name']
                }
                
                await fetch_single_tender(tab, current_config)
                # Short rest between different portals
                await asyncio.sleep(random.uniform(2, 5))

    except Exception as e:
        has_errors = True
        print(f"An error occurred during browser initialization or main loop: {e}")

    # if has_errors raise exception
    if has_errors:
        raise Exception("An error occurred during browser initialization or main loop.")

# Run the asynchronous main function
if __name__ == "__main__":
    asyncio.run(main())
