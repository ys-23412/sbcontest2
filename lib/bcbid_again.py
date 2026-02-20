import asyncio
from playwright.async_api import async_playwright
from playwright_captcha import CaptchaType, ClickSolver, FrameworkType
import time

async def solve_captcha():
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch()
        page = await browser.new_page()
        
        framework = FrameworkType.PLAYWRIGHT
        
        # Create solver before navigating to the page
        async with ClickSolver(framework=framework, page=page) as solver:
            # Navigate to your target page
            await page.goto('https://bcbid.gov.bc.ca/page.aspx/en/bas/browser_check')
            
            # Solve the captcha
            await solver.solve_captcha(
                captcha_container=page,
                captcha_type=CaptchaType.RECAPTCHA_V2
            )

        print("Captcha solved!")
        page_content = await page.content()
        with open("page_source.html", "w", errors="ignore") as f:
            f.write(page_content)
        # close browser
        time.sleep(5)
        with open("page_source2.html", "w", errors="ignore") as f:
            f.write(page_content)
        await browser.close()
        
        # Continue with your automation...

asyncio.run(solve_captcha())