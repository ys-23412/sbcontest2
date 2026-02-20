from playwright.sync_api import sync_playwright
from playwright_recaptcha import recaptchav2
from time import sleep

with sync_playwright() as playwright:
    browser = playwright.firefox.launch()
    page = browser.new_page()
    page.goto("https://bcbid.gov.bc.ca/page.aspx/en/bas/browser_check")
    sleep(10)
    # save page html
    with open("page.html", "w", errors="ignore") as f:
        f.write(page.content())
    with recaptchav2.SyncSolver(page) as solver:
        token = solver.solve_recaptcha(wait=True)
        print(token)

    