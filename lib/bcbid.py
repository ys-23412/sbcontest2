import asyncio
import os
import time
import csv
import re
from pydoll.browser.chromium import Chrome
from pydoll.utils import SOCKS5Forwarder
from pydoll.browser.options import ChromiumOptions
from pydoll.browser.tab import Tab

def get_browser_options(headless=False):
    """
    Returns a configured ChromiumOptions object with stealth settings.
    """
    options = ChromiumOptions()
    # options.add_argument('--disable-blink-features=AutomationControlled')
    current_time = int(time.time())
    options.browser_preferences = {
        'profile': {
            'last_engagement_time': str(current_time - (3 * 60 * 60)),  # 3 hours ago
            'exited_cleanly': True,
            'exit_type': 'Normal',
        },
        'safebrowsing': {'enabled': True},
    }
    
    options.add_argument('--proxy-server=socks5://127.0.0.1:1081')
    # options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36')
    # Handle Headless environment variables
    env_headless = os.environ.get("NODRIVER_HEADLESS") == "True"
    if not env_headless and os.environ.get("DISPLAY"):
        options.add_argument(f'--display={os.environ.get("DISPLAY")}')
    
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
        await opps_link.click()
        await asyncio.sleep(3)  # Wait for portal redirection
        try:
            submit_button = await tab.find(id='submit-btn')
            await submit_button.click()
        except Exception as e:
            print(f"Error clicking submit button: {e}")
    else:
        print("Error: Could not locate Opportunities link using text or href XPaths.")

# import asyncio
# import os
# from camoufox.async_api import AsyncCamoufox

# async def navigate_to_opportunitiesv2(page):
#     """
#     Attempts to find the Opportunities link using Playwright locators.
#     """
#     print("Searching for 'Opportunities' link...")
    
#     # 1. Attempt to find by Text
#     # normalize-space() is handled by Playwright's 'has_text' or regex
#     opps_link = page.get_by_role("link", name="Opportunities", exact=False)

#     try:
#         # Check if the text-based link is visible
#         if await opps_link.is_visible():
#             print("Link found via text. Clicking...")
#             await opps_link.click()
#         else:
#             # 2. Fallback: Search by relative href
#             print("Text-based search failed. Attempting fallback via href...")
#             opps_link = page.locator('a[href*="/page.aspx/en/rfp/request_browse_public"]')
#             await opps_link.click()
            
#         # Wait for network to settle after click
#         await page.wait_for_load_state("networkidle")
#     except Exception as e:
#         print(f"Error: Could not locate or click Opportunities link: {e}")

# async def mainv2():
#     # Handle Headless environment variables
#     env_headless = os.environ.get("NODRIVER_HEADLESS") == "True"
    
#     # Camoufox context manager handles browser launch and stealth automatically
#     async with AsyncCamoufox(
#         headless=env_headless,
#         # You can add specific geo/language spoofing here if needed
#         # humanize=True adds random mouse movements/delays
#         humanize=True 
#     ) as browser:
        
#         print("Starting Camoufox...")
#         # Create a new page (context is handled internally by the library)
#         page = await browser.new_page()

#         # 1. Navigate to BC Bid
#         url = "https://bcbid.gov.bc.ca/"
#         print(f"Navigating to {url}...")
#         await page.goto(url, wait_until="domcontentloaded")
        
#         # 2. Dummy Login Placeholder
#         # await page.fill("#body_x_txtLogin", "YOUR_USERNAME")
#         # await page.fill("#body_x_txtPass", "YOUR_PASSWORD")
#         # await page.click("#body_x_btnLogin")

#         # 3. Click on "Browse Opportunities"
#         try:
#             await navigate_to_opportunities(page)
#         except Exception as e:
#             print(f"Error during navigation: {e}")

#         print("Scraping task complete.")
#         time.sleep(155)

async def main():
    proxy_username = os.getenv('IPROYAL_USERNAME')
    proxy_password = os.getenv('IPROYAL_PASSWORD')
    full_password = f"{proxy_password}_country-ca_city-vancouver_session-N33zLThd_lifetime-30m"
    proxy_port = '11200'
    proxy_host = 'geo.iproyal.com'
    forwarder = SOCKS5Forwarder(
        remote_host=proxy_host,
        remote_port=proxy_port,
        username=proxy_username,
        password=full_password,
        local_port=1081,
    )
    async with forwarder:
        opts = get_browser_options(headless=False)
        
        async with Chrome(options=opts) as browser:
            print("Starting browser...")
            tab = await browser.start()

            # 1. Navigate to BC Bid
            url = "https://bcbid.com"
            print(f"Navigating to {url}...")
            await tab.go_to(url)
            
            # 2. Dummy Login (Commented out as requested)
            # await dummy_login(tab, "YOUR_USERNAME", "YOUR_PASSWORD")
            await asyncio.sleep(5)
            # 3. Click on "Browse Opportunities"
            # Based on the uploaded HTML, the ID is 'body_x_btnPublicOpportunities'
            print("Clicking on 'Browse Opportunities'...")
            # try:
            #     await navigate_to_opportunities(tab)

            # except Exception as e:
            #     print(f"Error clicking opportunities button: {e}")

            print("Scraping task complete.")

if __name__ == "__main__":
    asyncio.run(main())