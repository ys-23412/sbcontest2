import asyncio
from pydoll.browser.chromium import Chrome
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

async def scrape_competition_details(tab):
    """
    Scrapes the detail sub-page for a specific competition.
    Extracts merged headers, key dates, primary email, and introductory text.
    """
    # 1. Extract raw text and specific elements using JavaScript
    page_data = await tab.execute_script("""
        const container = document.querySelector('.business-ops-details') || document.body;
        
        // Select all h2 headings on the page
        const h2Headings = Array.from(document.querySelectorAll('h2'));
        
        // Extract text from the first two h2 headings
        let firstH2 = h2Headings[0]?.innerText.trim() || "";
        let secondH2 = h2Headings[1]?.innerText.trim() || "";
        
        // Logic to merge and remove duplicates
        let mergedHeader;
        if (secondH2.toLowerCase().includes(firstH2.toLowerCase())) {
            // If the 2nd contains the 1st, just use the 2nd (since it has the full text)
            mergedHeader = secondH2;
        } else {
            // Otherwise merge them with a space
            mergedHeader = `${firstH2} ${secondH2}`.trim();
        }
    
        // Extract the first sentence after the FIRST h2 heading
        let firstSentence = "";
        const titleEl = h2Headings[0];
        if (titleEl) {
            let nextEl = titleEl.nextElementSibling;
            // Skip over empty elements to find the first paragraph of text
            while (nextEl && !nextEl.innerText.trim()) {
                nextEl = nextEl.nextElementSibling;
            }
            if (nextEl) {
                const text = nextEl.innerText.trim();
                // Split by punctuation and keep the first part as a sentence
                firstSentence = text.split(/[.!?]/)[0] + ".";
            }
        }
    
        return {
            mergedHeader,
            fullText: container.innerText,
            firstSentence
        };
    """)

    text = page_data['fullText']
    
    # 2. Extract Key Dates using Regex (Published, Closing Date, Closing Time)
    # Pattern: Look for labels followed by date/time formats
    published = re.search(r"Published:\s*(\w+\s+\d{1,2},\s+\d{4})", text)
    closing_date = re.search(r"Closing Date:\s*(\w+\s+\d{1,2},\s+\d{4})", text)
    closing_time = re.search(r"Closing Time:\s*(\d{1,2}:\d{2}\s*[apAP][mM])", text)

    # 3. Extract first email under Primary Contact
    # Finds the block after "Primary Contact" and captures the first email pattern
    email_match = re.search(r"Primary Contact[\s\S]*?([\w\.-]+@[\w\.-]+\.\w+)", text)

    return {
        "competition": page_data['mergedHeader'],
        "published": published.group(1) if published else "N/A",
        "closing_date": closing_date.group(1) if closing_date else "N/A",
        "closing_time": closing_time.group(1) if closing_time else "N/A",
        "primary_email": email_match.group(1) if email_match else "N/A",
        "intro_sentence": page_data['firstSentence']
    }

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

        # 3. Scrape Active Competitions
        # Based on the HTML, competitions are in divs with class 'business-ops'
        print("Scraping active competitions...")
        competitions = []
        
        # We execute JS to pull all rows under the 'Active competitions' header
        rows_data = await tab.execute_script("""
            const rows = Array.from(document.querySelectorAll('.business-ops'));
            return rows.map(row => {
                const linkEl = row.querySelector('a');
                const cols = Array.from(row.querySelectorAll('p')).map(p => p.innerText.trim());
                return {
                    title: cols[0] || '',
                    description: cols[1] || '',
                    published: cols[2] || '',
                    closing: cols[3] || '',
                    url: linkEl ? linkEl.href : ''
                };
            });
        """)

        # 4. Save to CSV
        csv_file = "active_competitions.csv"
        keys = ["title", "description", "published", "closing", "url"]
        with open(csv_file, 'w', newline='', encoding='utf-8') as f:
            dict_writer = csv.DictWriter(f, fieldnames=keys)
            dict_writer.writeheader()
            dict_writer.writerows(rows_data)
        print(f"Saved {len(rows_data)} items to {csv_file}")

        # 5. Iterate and Click through each link
        for item in rows_data:
            if item['url']:
                print(f"Visiting: {item['title']} - {item['url']}")
                await tab.go_to(item['url'])
                await tab.wait_for_selector('h2') # Ensure page load
                details = await scrape_competition_details(tab)
                print(f"Extracted: {details['competition']}")
                
                # Add details to your data structure for CSV saving
                item.update(details)
                # Perform sub-page scraping here if needed
                # example_text = await tab.execute_script("return document.body.innerText")
                
                await asyncio.sleep(2) # Throttle to be polite
                await tab.go_back() # Return to main list
                await asyncio.sleep(1)

if __name__ == "__main__":
    asyncio.run(main())
