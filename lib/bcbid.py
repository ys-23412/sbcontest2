import asyncio
import os
import time
import csv
import re
from pydoll.browser.chromium import Chrome
from pydoll.browser.options import ChromiumOptions
from pydoll.browser.tab import Tab

def get_browser_options(headless=False):
    """
    Returns a configured ChromiumOptions object with stealth settings.
    """
    options = ChromiumOptions()
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_argument("--enable-webgl")

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
        await asyncio.sleep(5)  # Wait for portal redirection
    else:
        print("Error: Could not locate Opportunities link using text or href XPaths.")

async def main():
    opts = get_browser_options(headless=False)
    
    async with Chrome(options=opts) as browser:
        print("Starting browser...")
        tab = await browser.start()

        # 1. Navigate to BC Bid
        url = "https://bcbid.gov.bc.ca/"
        print(f"Navigating to {url}...")
        await tab.go_to(url)
        
        # 2. Dummy Login (Commented out as requested)
        # await dummy_login(tab, "YOUR_USERNAME", "YOUR_PASSWORD")

        # 3. Click on "Browse Opportunities"
        # Based on the uploaded HTML, the ID is 'body_x_btnPublicOpportunities'
        print("Clicking on 'Browse Opportunities'...")
        try:
            await navigate_to_opportunities(tab)

        except Exception as e:
            print(f"Error clicking opportunities button: {e}")

        print("Scraping task complete.")

if __name__ == "__main__":
    asyncio.run(main())