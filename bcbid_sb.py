from seleniumbase import SB
import pandas as pd

with SB(uc=True, test=True, locale="en", ad_block=True) as sb:
    url = "https://bcbid.gov.bc.ca/page.aspx/en/bas/browser_check"
    sb.activate_cdp_mode(url)
    sb.sleep(1.5)
    # print page title to console
    sb.post_message("SeleniumBase wasn't detected", duration=4)
    # wait 10 seconds
    sb.sleep(10)
    
    # full html
    full_html = sb.get_page_source()
    print("What is going on here?")
    # 3. Use Pandas to parse the HTML string
    # pd.read_html returns a list of DataFrames; we take the first one [0]
    try:
        dfs = pd.read_html(full_html)
        df = dfs[0]
    except ValueError:
        print("No tables found in the HTML.")
        df = pd.DataFrame()
        
    # We have to add automatication to click until the last date on the page is before today
    # 4. Clean up the data
    # Tables with buttons/icons in headers often create messy column names.
    # We can strip extra whitespace or rename as needed.
    df.columns = [col.strip() for col in df.columns]
    
    # Print the result
    print("\n--- Extracted Table Data ---")
    print(df.head())
    df.to_csv("bid_recent.csv", index=False)

    # close browser
    sb.quit()