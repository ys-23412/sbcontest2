import asyncio
from pydoll.browser.chrome import Chrome
from pydoll.browser.options import ChromiumOptions
import time
import os

def get_browser_options(headless=False):
    """
    Returns a configured ChromiumOptions object with stealth settings,
    custom User Agent, and Proxy configurations.
    """
    options = ChromiumOptions()

    # --- 1. Stealth & Anti-Bot ---
    # crucial for bypassing detection (e.g., Cloudflare)
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_argument("--enable-webgl")
    options.add_argument("--no-sandbox") # Often needed in containerized environments


    # --- 3. Display / Headless Logic ---
    # Checks environment variables as requested
    if not os.environ.get("NODRIVER_HEADLESS") == "True" and os.environ.get("DISPLAY", ":99"):
        display_var = os.environ.get("DISPLAY")
        print("display", display_var)
        options.add_argument(f'--display=:99')
    
    # If explicitly passed headless=True or env var requires it
    if headless or env_headless:
        # Note: Some 'stealth' setups prefer avoiding standard headless flags 
        # or using 'new' headless mode to avoid detection.
        options.add_argument("--headless=new")

    # --- 4. Browser Preferences (Fingerprinting mitigation) ---
    fake_timestamp = int(time.time()) - (90 * 24 * 60 * 60)  # 90 days ago
    options.browser_preferences = {
        'profile': {
            'last_engagement_time': fake_timestamp,
            'exited_cleanly': True,
            'exit_type': 'Normal'
        },
        'newtab_page_location_override': 'https://www.google.com',
        'user_experience_metrics': {
            'reporting_enabled': False
        },
        # Disable automation bars and save password bubbles
        'credentials_enable_service': False,
        'profile.password_manager_enabled': False
    }

    # --- 5. Proxy Setup ---
    # Assuming get_and_set_selenium_proxy returns a proxy string or modifies options directly.
    # If it returns a string like "ip:port", usage would be:
    # proxy = get_and_set_selenium_proxy()
    # options.add_argument(f'--proxy-server={proxy}')
    
    # For now, we call it if it modifies global state or returns args
    try:
        # Placeholder for your specific proxy logic implementation
        # options = get_and_set_selenium_proxy(options) 
        pass 
    except Exception as e:
        print(f"Proxy setup skipped: {e}")

    return options

async def main():
    opts = get_browser_options()
    # Initialize Chrome. Pydoll handles the binary and connection automatically.
    async with Chrome() as browser:
        print("Starting browser...")
        
        # 1. Start a new tab
        tab = await browser.start()

        # 2. Visit the Login Page
        print("Navigating to login page...")
        await tab.go_to("https://www.bcferries.com/login")
        
        # 3. Handle Login
        # We find elements using the IDs visible in your HTML snippet
        print("Entering credentials...")
        
        # Find email field by ID and type email
        email_field = await tab.find(id="email")
        await email_field.type_text("YOUR_EMAIL_HERE")

        # Find password field by ID and type password
        password_field = await tab.find(id="j_password")
        await password_field.type_text("YOUR_PASSWORD_HERE")

        # Find the submit button. 
        # Your HTML shows <button type="submit"...> so we can target by the 'type' attribute.
        submit_btn = await tab.find(type="submit")
        await submit_btn.click()
        
        print("Logged in. Waiting for redirection...")
        # Wait for the navigation to complete or for a specific element on the dashboard to load.
        # A simple sleep is used here for demonstration, but you can use tab.wait_for_selector()
        await asyncio.sleep(5) 

        # 4. Go to the Business Ops page
        target_url = "https://www.bcferries.com/business-ops"
        print(f"Navigating to {target_url}...")
        await tab.go_to(target_url)

        # 5. Scrape the page content
        # We can extract the full HTML or just the visible text
        print("Scraping content...")
        
        # Option A: Get the full HTML
        page_html = await tab.execute_script("return document.documentElement.outerHTML")
        
        # Option B: Get just the visible text body
        page_text = await tab.execute_script("return document.body.innerText")

        print("--- Scraped Data Preview ---")
        print(page_text[:500]) # Print first 500 characters
        print("----------------------------")

        # You can now save 'page_html' or 'page_text' to a file if needed
        # with open("bc_ferries_data.txt", "w") as f:
        #     f.write(page_text)
        with open("bc_ferries_ops.txt", "w", encoding="utf-8") as f:
                    f.write(content)

if __name__ == "__main__":
    asyncio.run(main())
