from seleniumbase import SB
import pandas as pd
import os
proxy_username = os.getenv('IPROYAL_USERNAME')
proxy_password = os.getenv('IPROYAL_PASSWORD')
proxy_settings = "_country-ca_city-vancouver_session-nnoMTsdN_lifetime-30m"
# proxy_address = f"{proxy_username}:{proxy_password}{proxy_settings}@socks5://geo.iproyal.com:12321" 
with SB(uc=True, test=True, incognito=True) as sb:
    url = "https://bcbid.gov.bc.ca/page.aspx/en/bas/browser_check"
    # sb.activate_cdp_mode(url)
    sb.uc_open_with_reconnect(url, 4)
    sb.sleep(1)
    sb.uc_gui_handle_captcha()
    # sb.solve_captcha()
    # print page title to console
    sb.set_messenger_theme(location="top_left")
    sb.post_message("SeleniumBase wasn't detected", duration=3)
    # wait 10 seconds
    # go directly
    sb.sleep(10)
    print("Trying to save as html...")
    sb.save_as_html("bcbid.html")
    # full html
    full_html = sb.get_html()
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