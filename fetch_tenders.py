import asyncio
from camoufox.async_api import AsyncCamoufox # Import AsyncCamoufox
from camoufox_captcha import solve_captcha


import asyncio
import os
import pandas as pd
from dotenv import load_dotenv
from io import StringIO
from bs4 import BeautifulSoup, NavigableString
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
        
        return project_text
    else:
        # print(f"Could not find the '{labelText}' tag.") # Optional for debugging
        return "" # Return empty if the label itself is not found

async def main():
    """
    Asynchronously navigates to a URL using Camoufox and retrieves the inner HTML.
    """
    load_dotenv()
    BASE_URL = os.getenv('BASE_URL')
    EMAIL = os.getenv('EMAIL')
    PASSWORD = os.getenv('PASSWORD')
    base_dir = os.getenv('BASE_DIR', "/app/screenshots")
    try:
        # Use async with for asynchronous context management
        async with AsyncCamoufox(
            headless=True,
            geoip=True,
            humanize=False,
            i_know_what_im_doing=True,
            config={'forceScopeAccess': True},  # add this when creating Camoufox instance
            disable_coop=True,  # add this when creating Camoufox instance
            # }
        ) as browser:
            # Await the new_page method as it's asynchronous, page is a Playwright Page
            page = await browser.new_page()
            print(f"Navigating to {BASE_URL}...")
            initial_url = f'{BASE_URL}/login'
            await page.goto(initial_url)

            try:
                print("Navigating to the page...")
                # Await inner_html() and pass 'html' as the selector to get the entire page's HTML
                # print(inner_html_content)
                # turnstile_container = await page.wait_for_selector('.turnstile_container')

                # specify challenge type for Turnstile
                success = await solve_captcha(page, captcha_type='cloudflare', challenge_type='interstitial')
                if not success:
                    return print("Failed to solve captcha challenge")

                if not success:
                    return print("Failed to solve captcha challenge")
                
                # print("Attempting to log in...")
                # await page.locator('.login-button').click()

                # # Wait for the login form to be ready
                # await page.wait_for_timeout(3000) 
                
                print("Entering email...")
                await page.locator("input[type='email']").fill(EMAIL)
                await page.locator('button[type="submit"]').click()
 
                inner_html_content = await page.inner_html('html') # Fix: Added 'html' selector
                print("inner_html_content", inner_html_content)

                
                # Wait for the password field to appear
                await page.wait_for_timeout(6000)

                print("Entering password...")
                await page.locator("input[type='password']").fill(PASSWORD)
                await page.screenshot(path=f"{base_dir}/input_password.png")
                await page.locator('button[type="submit"]').click()

                # Wait for the page to load after login
                print("Login submitted. Waiting for opportunities page...")
                # wait for login to happen
                await page.wait_for_timeout(10000)
                await page.wait_for_load_state('networkidle', timeout=10000)
                page_source = await page.content()
                with open(f"{base_dir}/bonfire_victoria.html", "w", errors='ignore') as f:
                    f.write(page_source)

                # --- 2. Scrape the Main Table ---
                print("Parsing opportunities table...")
                soup = BeautifulSoup(page_source, 'html.parser')
                dataTables_scroll_soup = soup.find('div', {'class': 'dataTables_scroll'})
                
                if not dataTables_scroll_soup:
                    print("Could not find the main data table. Exiting.")
                    return

                # Extract Headers
                header_list = []
                header_table_soup = dataTables_scroll_soup.find('div', class_='dataTables_scrollHead')
                if header_table_soup:
                    headers_th = header_table_soup.find_all('th')
                    header_list = [th.get_text(strip=True) for th in headers_th]
                    if header_list and header_list[-1].lower() == "action":
                        header_list[-1] = "Action Link"
                else:
                    print("Warning: Could not find headers. Using default headers.")
                    header_list = ['Status', 'Ref. #', 'Project', 'Close Date', 'Days Left', 'Action Link']

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
                    print("No data rows found in the table.")
                    content_df = pd.DataFrame(columns=header_list)
                else:
                    content_df = pd.DataFrame(all_rows_data, columns=header_list)
                    print(f"Successfully scraped {len(content_df)} opportunities from the main table.")

                # --- 3. Scrape Detail Pages ---
                project_data = []
                for index, row in content_df.iterrows():
                    action_link = row["Action Link"]
                    if action_link:
                        full_link = f"{BASE_URL}{action_link}"
                        print(f"({index + 1}/{len(content_df)}) Navigating to detail page: {full_link}")
                        
                        try:
                            await page.goto(full_link)
                            success = await solve_captcha(page, captcha_type='cloudflare', challenge_type='interstitial')
                            if not success:
                                print("Failed to solve captcha challenge")
                                new_page_source = await page.inner_html('html')
                                with open(f"{base_dir}/tender_fail_{index}.html", "w", errors='ignore') as f:
                                    f.write(new_page_source)
                                    continue
                            await page.wait_for_load_state('domcontentloaded')

                            # Take screenshot and get page source
                            screenshot_path = f"{base_dir}/tender_{index}.png"
                            await page.screenshot(path=screenshot_path)
                            new_page_source = await page.inner_html('html')

                            with open(f"{base_dir}/tender_{index}.html", "w", errors='ignore') as f:
                                f.write(new_page_source)

                            # Parse details from the new page
                            detail_soup = BeautifulSoup(new_page_source, 'html.parser')
                            
                            type_text = get_tag_on_details_page(detail_soup, labelText = "Type:")
                            project_description = get_tag_on_details_page(detail_soup, labelText = "Project Description:")
                            open_date = get_tag_on_details_page(detail_soup, labelText = "Open Date:")
                            close_date = get_tag_on_details_page(detail_soup, labelText = "Close Date:")
                            days_left = get_tag_on_details_page(detail_soup, labelText = "Days Left:")

                            page_data = [
                                row['Status'], row['Ref. #'], row['Project'],
                                type_text, full_link, project_description,
                                open_date, close_date, days_left
                            ]
                            project_data.append(page_data)

                        except Exception as e:
                            print(f"Error processing link {full_link}: {e}")
                    else:
                        print(f"No Action Link found for row {index}.")

                # --- 4. Save Final Data ---
                if project_data:
                    final_header_list = ['Status', 'Ref', 'Project', 'Type', "Link", 'Project Description', 'Open Date', 'Close Date', 'Days Left']
                    final_df = pd.DataFrame(project_data, columns=final_header_list)
                    
                    output_path = f"{base_dir}/bonfire_victoria_with_links.csv"
                    final_df.to_csv(output_path, index=False)
                    print(f"Scraping complete. Data saved to {output_path}")
                    print(final_df)
                else:
                    print("No project detail data was collected.")
                # Extract Rows
                print("Successfully solved captcha challenge!")
                with open(f"{base_dir}/index.html", "w") as f:
                    f.write(inner_html_content)
            except Exception as e:
                # If there's an error getting inner_html, print the exception
                print(f"Error retrieving inner HTML: {e}")
                # You can still try to print the error page's content if available
                # print(await page.inner_html()) # This might also fail if page is broken

    except Exception as e:
        print(f"An error occurred during browser operation: {e}")

# Run the asynchronous main function
if __name__ == "__main__":
    asyncio.run(main())
