import asyncio
import os
import pandas as pd
from dotenv import load_dotenv
from io import StringIO
from bs4 import BeautifulSoup, NavigableString
import time
import random
import traceback
# Pydoll Imports
from pydoll.browser.chromium import Chrome
from pydoll.browser.options import ChromiumOptions
from pydoll.browser.tab import Tab
from pydoll.constants import Key, By, ScrollPosition
# Assuming you have a captcha solving utility like the one in your example
# If not, you may need to find or create one. For this example, we will
# assume a placeholder function exists.
# from camoufox_captcha import solve_captcha

# --- Helper Function (Unchanged) ---
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
        await tab.enable_auto_solve_cloudflare_captcha()
        await tab.go_to(initial_url)
        login_flag = False
        try:
            login_element = await tab.query('//*[text()="Log In"]', raise_exc=False)
            register_element = await tab.query('//*[text()="Register"]', raise_exc=False)
            euna_supplier_network = await tab.query('//*[contains(text(), "My Euna Supplier Network")]', raise_exc=False)
        except Exception as e:
            login_element = None 
            register_element = None
        try:
            euna_supplier_network = await tab.query('//*[text()="My Euna Supplier Network]"', timeout=5000)
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
                if "login" in href or login_flag:
                    # go to login page
                    await tab.go_to(f"{initial_url}/login")
                    await asyncio.sleep(4)
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
                else:
                    # await page.screenshot(path=f"{base_dir}/{CITY_NAME}_no_login.png")
                    print(f"The current page for {CITY_NAME} is not a login page (or 'login' is not in the URL). Assuming already logged in or direct access.")
            except Exception as e:
                traceback.print_exc()
                print(f"Failed to login for {CITY_NAME}. Skipping.")
            # Log In look to element Log In, if so, set login flag to true
            await tab.disable_auto_solve_cloudflare_captcha()
            await asyncio.sleep(random.uniform(5, 10))
            # await page.wait_for_timeout(10000)
            # await page.wait_for_load_state('networkidle', timeout=10000)
            page_source = await tab.page_source
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

            # --- 3. Scrape Detail Pages ---
            project_data = []
            for index, row in content_df.iterrows():
                action_link = row["Action Link"]
                if action_link:
                    full_link = f"{BASE_URL}{action_link}"
                    print(f"({index + 1}/{len(content_df)}) Navigating to detail page for {CITY_NAME}: {full_link}")
                    
                    try:
                        await tab.enable_auto_solve_cloudflare_captcha()
                        await tab.go_to(full_link)
                        await tab.disable_auto_solve_cloudflare_captcha()
                        print(f"Failed to solve captcha challenge for detail page {full_link}. Skipping.")
                        new_page_source = await tab.page_source
                        with open(f"{base_dir}/{CITY_NAME}_tender_scrap_{index}.html", "w", encoding='utf-8', errors='ignore') as f:
                            f.write(new_page_source)

                        # Take screenshot and get page source
                        screenshot_path = f"{base_dir}/{CITY_NAME}_tender_{index}.png"
                        await tab.take_screenshot(path=screenshot_path)
                        new_page_source = await page.inner_html('html')

                        with open(f"{base_dir}/{CITY_NAME}_tender_{index}.html", "w", encoding='utf-8', errors='ignore') as f:
                            f.write(new_page_source)

                        # Parse details from the new page
                        detail_soup = BeautifulSoup(new_page_source, 'html.parser')
                        
                        type_text = get_tag_on_details_page(detail_soup, labelText = "Type:")
                        project_description = get_tag_on_details_page(detail_soup, labelText = "Project Description:")
                        open_date = get_tag_on_details_page(detail_soup, labelText = "Open Date:")
                        close_date = get_tag_on_details_page(detail_soup, labelText = "Close Date:")
                        days_left = get_tag_on_details_page(detail_soup, labelText = "Days Left:")
                        contact_information = get_tag_on_details_page(detail_soup, labelText = "Contact Information:")

                        page_data = [
                            row['Status'], row['Ref. #'], row['Project'],
                            type_text, full_link, project_description,
                            open_date, close_date, days_left, contact_information
                        ]
                        project_data.append(page_data)

                    except Exception as e:
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

async def main():
    load_dotenv() # Load environment variables from .env file

    # Define the list of tender configurations
    tender_configs = [
        {"base_url_env_key": "TENDER_BASE_VIC_URL", "csv_file_name": "bonfire_victoria_with_links.csv", "city_name": "victoria"},
        {"base_url_env_key": "TENDER_BASE_SAANICH_URL", "csv_file_name": "bonfire_saanich_with_links.csv", "city_name": "saanich"},
        {"base_url_env_key": "TENDER_BASE_NORTHCOW_URL", "csv_file_name": "bonfire_north_cowichan_with_links.csv", "city_name": "north cowichan"},
        {"base_url_env_key": "TENDER_BASE_CVRD_URL", "csv_file_name": "bonfire_cvrd_with_links.csv", "city_name": "cvrd"},
        {"base_url_env_key": "TENDER_BASE_FNHA_URL", "csv_file_name": "bonfire_fnha_with_links.csv", "city_name": "fnha"},
        {"base_url_env_key": "TENDER_BASE_UVIC_URL", "csv_file_name": "bonfire_uvic_with_links.csv", "city_name": "uvic"},
        {"base_url_env_key": "TENDER_BASE_BCTRANSIT_URL", "csv_file_name": "bonfire_bc_transit_with_links.csv", "city_name": "bctransit"},
        {"base_url_env_key": "TENDER_BASE_COURTENAY_URL", "csv_file_name": "bonfire_courtenay_with_links.csv", "city_name": "courtenay"},
        {"base_url_env_key": "TENDER_BASE_CENTRALSAANICH_URL", "csv_file_name": "bonfire_central_saanich_with_links.csv", "city_name": "central saanich"},
        {"base_url_env_key": "TENDER_BASE_FRASERHEALTH_URL", "csv_file_name": "bonfire_fraserhealth_with_links.csv", "city_name": "fraser health"},
        {"base_url_env_key": "TENDER_BASE_ICBC_URL", "csv_file_name": "bonfire_icbc_with_links.csv", "city_name": "icbc"},
        {"base_url_env_key": "TENDER_BASE_PHSA_URL", "csv_file_name": "bonfire_phsa_with_links.csv", "city_name": "phsa"},
        {"base_url_env_key": "TENDER_BASE_COMOX_URL", "csv_file_name": "bonfire_comox_with_links.csv", "city_name": "comox"},
        {"base_url_env_key": "TENDER_BASE_ISLANDHEALTH_URL", "csv_file_name": "bonfire_islandhealth_with_links.csv", "city_name": "victoria"},
        {"base_url_env_key": "TENDER_BASE_VIU_URL", "csv_file_name": "bonfire_viu_with_links.csv", "city_name": "victoria"},
    ]

    options = ChromiumOptions()
    # Pydoll humanization and stealth
    if not os.environ.get("NODRIVER_HEADLESS") == "True" and os.environ.get("DISPLAY", ":99"):
        display_var = os.environ.get("DISPLAY")
        print("display", display_var)
        options.add_argument(f'--display=:99')

    options.add_argument("--enable-webgl")

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
    # proxy_url = os.environ.get("PROXY_URL")
    # if proxy_url:
    #     options.add_argument(f'--proxy-server={proxy_url}')


    # proxy = 'geo.iproyal.com:12321'
    # proxy_username = os.getenv('IPROYAL_USERNAME')
    # proxy_password = os.getenv('IPROYAL_PASSWORD')
    # proxy_auth = f'{proxy_username}:{proxy_password}_country-ca_city-vancouver_session-EWassIZ9_lifetime-30m_streaming-1'

    # if proxy_username and proxy_password:
    #     proxy_url = f'http://{proxy_auth}@{proxy}'
    #     print("Using proxy:", proxy_url)
    #     options.add_argument(f'--proxy-server={proxy_url}')


    print("--- Initializing Pydoll Browser ---")
    has_errors = False
    try:
        # Initialize AsyncCamoufox once
        # async with AsyncCamoufox(
        #     headless=True,
        #     geoip=True,
        #     humanize=False,
        #     i_know_what_im_doing=True,
        #     config={'forceScopeAccess': True},
        #     disable_coop=True,
        # ) as browser:
        #     print("--- Browser initialized. Starting tender fetches ---")
            
        #     page = await browser.new_page() 
        #     for config_item in tender_configs:
        #         # Retrieve the actual BASE_URL from environment variables using the key
        #         base_url = os.getenv(config_item['base_url_env_key'])
        #         if not base_url:
        #             print(f"Warning: {config_item['base_url_env_key']} not found in environment variables. Skipping {config_item['city_name']}.")
        #             continue
                
        #         # Create a complete config dictionary to pass to fetch_single_tender
        #         current_tender_config = {
        #             "base_url": base_url,
        #             "csv_file_name": config_item['csv_file_name'],
        #             "city_name": config_item['city_name']
        #         }
        #         await fetch_single_tender(page, current_tender_config) # Pass the browser instance
        #     print("--- All tender fetches completed. ---")
        async with Chrome(options=options) as browser:
            tab = await browser.start()
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
                await asyncio.sleep(random.uniform(5, 10))

    except Exception as e:
        has_errors = True
        print(f"An error occurred during browser initialization or main loop: {e}")

    # if has_errors raise exception
    if has_errors:
        raise Exception("An error occurred during browser initialization or main loop.")

# Run the asynchronous main function
if __name__ == "__main__":
    asyncio.run(main())
