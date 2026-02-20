from seleniumbase import SB

with SB(uc=True, test=True, locale="en", ad_block=True) as sb:
    url = "https://bcbid.gov.bc.ca/page.aspx/en/bas/browser_check"
    sb.activate_cdp_mode(url)
    sb.sleep(1.5)
    # print page source to console
    print(sb.get_page_source())

    # print page title to console
    print(sb.get_title())
    sb.post_message("SeleniumBase wasn't detected", duration=4)
    # wait 10 seconds
    sb.sleep(10)

    # print again
    print(sb.get_page_source())
    # close browser
    sb.quit()