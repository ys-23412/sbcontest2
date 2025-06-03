import requests
import re
import random
from datetime import datetime, timedelta
import base64
import dateparser
from random_user_agent.user_agent import UserAgent

from bs4 import BeautifulSoup
# original url uses script tags to output proxies
# https://hidemy.io/en/proxy-list/countries/canada/?start=384#list
# https://spys.one/free-proxy-list/CA/
def get_proxies_world(url="https://www.freeproxy.world/?type=http&anonymity=&country=CA&speed=&page=1"):
    session = requests.Session()
    session.headers.update({
        'User-Agent': mk_user_agent(),
    })
    response = requests.get(url)
    soup = BeautifulSoup(response.text, 'html.parser')
    # print(response.text)
    # with open('proxies.html', 'w', errors='ignore') as file:
    #     file.write(soup.prettify())
    table = soup.find('table', attrs={'class': 'layui-table'})
    proxies = []

    for row in table.find_all('tr')[1:]:  # skip header row
        cols = row.find_all('td')
        if len(cols) >= 2:
            # print(cols[0])
            proxy_type = cols[5].text.strip()
            # http
            if proxy_type == 'http':
                ip = cols[0].text.strip()
                port = cols[1].text.strip()
                proxies.append(f'http://{ip}:{port}')

            # if proxy_type == 'socks5':
            #     ip = cols[0].text.strip()
            #     port = cols[1].text.strip()
            #     proxies.append(f'socks5://{ip}:{port}')

            # if proxy_type == 'socks4':
            #     ip = cols[0].text.strip()
            #     port = cols[1].text.strip()
            #     proxies.append(f'socks4://{ip}:{port}')

    return proxies

def get_proxies_cz(url="http://free-proxy.cz/en/proxylist/country/CA/all/date/all/"):
    session = requests.Session()
    session.headers.update({
        'User-Agent': mk_user_agent(),
    })
    response = requests.get(url)
    soup = BeautifulSoup(response.text, 'html.parser')
    pattern = re.compile(r'Base64\.decode\("([^"]+)"\)')

    proxies = []
    table = soup.find('table', attrs={'id': 'proxy_list'})
    # print(response.text)
    for row in table.find_all('tr')[1:]:  # skip header row
        cols = row.find_all('td')
        if len(cols) >= 2:
            # print(cols[0])
            script_tag = cols[0].find('script')
            if script_tag:
                # Extract the JavaScript code
                js_code = script_tag.string
                if js_code:
                    match = pattern.search(js_code)
                    if match:
                        encoded_string = match.group(1)
                        # print("Base64 Encoded String:", encoded_string)
            ip = base64.b64decode(encoded_string).decode('utf-8')
            proxy_type = cols[2].text.strip()
            if proxy_type.lower() == 'https':
                port = cols[1].text.strip()
                proxies.append(f'http://{ip}:{port}')

            # if proxy_type.lower() == 'socks5':
            #     port = cols[1].text.strip()
            #     proxies.append(f'socks5://{ip}:{port}')

            # if proxy_type.lower() == 'socks4':
            #     port = cols[1].text.strip()
            #     proxies.append(f'socks4://{ip}:{port}')
    return proxies

def mk_user_agent():
    user_agent_rotator = UserAgent()
    user_agent = user_agent_rotator.get_random_user_agent()
    return user_agent

def _parse_rows(params):
    ele = params.get('ele')
    is_header = params.get('is_header')
    if ele is None:
        return
    rowEles = ele.find_all('div', attrs={'class': 'row'})
    data = {}
    for rowEle in rowEles:
        reportLabel = rowEle.find('div', attrs={'class': 'report-label'})
        reportValue = rowEle.find('div', attrs={'class': 'report-value'})

        # Extract and clean the text
        if reportLabel:
            label = reportLabel.get_text(separator=' ', strip=True)
            # Replace multiple spaces with a single space
            label = re.sub(r'\s+', ' ', label)
        else:
            label = ''

        if reportValue:
            value = reportValue.get_text(separator=' ', strip=True)
            # Replace multiple spaces with a single space
            value = re.sub(r'\s+', ' ', value)
        else:
            value = ''

        if is_header:
            label_parts = label.split(':', 1)
            value_parts = value.split(':', 1)
            if len(label_parts) == 2:
                data[label_parts[0].strip()] = label_parts[1].strip()
            if len(value_parts) == 2:
                data[value_parts[0].strip()] = value_parts[1].strip()
        else:
            label_parts = label.split(':', 1)
            key = label_parts[0].strip()
            data[key] = value.strip()
    return data



    
def _parse_table_details(params):
    # get row
    ele = params.get('ele')
    # for ele get div with class row
    rowEle = ele.find('div', attrs={'class': 'row'})
    # get div with report-label
    # and div with report-value
    reportLabel = rowEle.find('div', attrs={'class': 'report-label'})
    reportValue = rowEle.find('div', attrs={'class': 'report-value'})
    # get text for reportLabel and reportValue
    label = reportLabel.text
    value = reportValue.text
    
    # parse these values split value by :
    label_parts = label.split(':')
    value_parts = value.split(':')
    data = {}

    data[label_parts[0].strip()] = label_parts[1].strip()
    data[value_parts[0].strip()] = value_parts[1].strip()
    return data

def _parse_permits(params):
    text = params.get('text')
    # print(text)
    # assume its just for now
    soup = BeautifulSoup(text, 'html.parser')
    # get PermitsIssuedSection

    permitsSection = soup.select_one('#PermitsIssuedSection, #PermitsAppliedSection')
    # print(permitsSection)
    # split items into groups of 2
    permit_details = permitsSection.find_all('div', recursive=False)
    # print(permit_details)
    parsed_permits = []
    # Iterate through the children two at a time
    for i in range(0, len(permit_details), 2):
        # Check if there is a pair to process, otherwise break the loop
        if i + 1 >= len(permit_details):
            break
        header = _parse_rows({
            'ele': permit_details[i],
            'is_header': True
        })
        data_elements = _parse_rows({
            'ele': permit_details[i+1],
            'is_header': False
        })
        # combine two dicts then append to parsed_permits
        parsed_permits.append({**header, **data_elements})

    return parsed_permits


def web_portal_issues(params):
    # destructure, make sure we have base_url, starting path (relative url)
    base_url = params.get('base_url', 'https://mysidney.sidney.ca')
    starting_url = params.get('starting_url', 'TempestApps/PIP/Pages/Search.aspx?templateName=LIVE_DATE')
    # values should be issued or applied
    permitType = params.get('permitType', 'issued')
    permitType = permitType.lower()
    siteType = params.get('siteType', 'sidney')
    saveFiles = params.get('saveFiles', False)

    # get start_date and end_date variables from the params
    # assume this will not be called if this is not set
    start_date = params.get('start_date')
    end_date = params.get('end_date')

    # format these dates into "05/01/2024",
    if type(start_date) == str:
        start_date = dateparser.parse(start_date)
        start_date_fmt = start_date.strftime("%m/%d/%Y")
    else:
        start_date_fmt = start_date.strftime("%m/%d/%Y")
    if type(end_date) == str:
        end_date = dateparser.parse(end_date)
        end_date_fmt = end_date.strftime("%m/%d/%Y")
    else:
        end_date_fmt = end_date.strftime("%m/%d/%Y")

    url = f"{base_url}/{starting_url}"

    session = requests.Session()

    # sidney doesnt seem to care about https
    proxy_list = get_proxy_list()

    if len(proxy_list) > 0:
        # proxies_list = get_proxies_cz()
        proxy = random.choice(proxy_list)
        # proxy="23.227.38.198:80"
        https_proxy = proxy.replace('http://', 'https://')
        # do we just buy a proxy server for this scrapping
        if siteType == 'sidney':
            proxies={
                'http': proxy,
                # 'https': https_proxy

            }
        else:
            proxies={
                'http': proxy,
                # 'https': https_proxy
            }
    else:
        proxies = {}
    session.headers.update({
        'User-Agent': mk_user_agent(),
    })

    print("parsing url", url)
    print("proxies", proxies)

    # Make an initial GET request
    try:
        print(f"Attempting to get {url} with proxies: {proxies}")
        page_load_resp = session.get(url, proxies=proxies, timeout=10) # Added a timeout
        page_load_resp.raise_for_status() # Raise an exception for bad status codes (4xx or 5xx)
        print("Successfully fetched with proxies.")
    except (requests.exceptions.ProxyError, requests.exceptions.ConnectTimeout, requests.exceptions.ConnectionError, requests.exceptions.HTTPError) as e:
        print(f"Request with proxies failed: {e}")
        print(f"Retrying {url} without proxies...")
        try:
            page_load_resp = session.get(url, timeout=10) # Retry without proxies
            page_load_resp.raise_for_status()
            print("Successfully fetched without proxies.")
        except requests.exceptions.RequestException as e_no_proxy:
            print(f"Request without proxies also failed: {e_no_proxy}")
            # Handle the failure of both attempts, e.g., return None or raise the exception
            page_load_resp = None
            raise e

    # with open('selection_alberni.html', 'w', errors='ignore') as file:
    #     file.write(page_load_resp.text)

    soup = BeautifulSoup(page_load_resp.text, 'html.parser')
    v1_site = False
    if siteType == "sidney":
        # Extract dynamic fields from the HTML
        viewstate = soup.find(id="__VIEWSTATE")['value']
        eventvalidation = soup.find(id="__EVENTVALIDATION")['value']

        # Prepare the payload for the POST request

        # set FromDate and ToDate
        payload = {
            "__EVENTTARGET": "",
            "__EVENTARGUMENT": "",
            "__VIEWSTATE": viewstate,
            "__VIEWSTATEGENERATOR": soup.find(id="__VIEWSTATEGENERATOR")['value'],
            "__VIEWSTATEENCRYPTED": "",
            "__EVENTVALIDATION": eventvalidation,
            "ctl00$FeaturedContent$txt_FromDate": start_date_fmt,
            "ctl00$FeaturedContent$txt_ToDate": end_date_fmt,
            "ctl00$FeaturedContent$btn_ViewReport": "View Report"
        }
        v1_site = True
    elif siteType == "alberni":
        # Extract dynamic fields from the HTML
        viewstate = soup.find(id="__VIEWSTATE")['value']
        eventvalidation = soup.find(id="__EVENTVALIDATION")['value']

        # Prepare the payload for the POST request

        # set FromDate and ToDate
        payload = {
            "l00$FeaturedContent$ScriptManager": "ctl00$FeaturedContent$updpnl_search|ctl00$FeaturedContent$btn_ViewReport",
            "__EVENTTARGET": "",
            "__EVENTARGUMENT": "",
            "__VIEWSTATE": viewstate,
            "__VIEWSTATEGENERATOR": soup.find(id="__VIEWSTATEGENERATOR")['value'],
            "__VIEWSTATEENCRYPTED": "",
            "__EVENTVALIDATION": eventvalidation,
            "ctl00$FeaturedContent$txt_FromDate": start_date_fmt,
            "ctl00$FeaturedContent$txt_ToDate": end_date_fmt,
            "_ASYNCPOST": True,
            "ctl00$FeaturedContent$btn_ViewReport": "Search"
        }
        v1_site = True
    elif siteType == "northcowichan":
        # Extract dynamic fields from the HTML
        viewstate = soup.find(id="__VIEWSTATE")['value']
        eventvalidation = soup.find(id="__EVENTVALIDATION")['value']

        # Prepare the payload for the POST request

        form_data = {}
        for input_tag in soup.find_all("input"):
            name = input_tag.get("name")
            value = input_tag.get("value", "")
            if name:
                form_data[name] = value
        # format 
        form_data["ctl00$FeaturedContent$txt_FromDate"] = start_date_fmt
        form_data["ctl00$FeaturedContent$txt_ToDate"] = end_date_fmt

        # Set the name and value for the button you want to "click"
        form_data['ctl00$FeaturedContent$btn_ViewReport'] = 'Search'

        # Submit the form with a POST request
        submit_url = url
        selection_resp = session.post(submit_url, data=form_data, proxies=proxies)

        soup = BeautifulSoup(selection_resp.text, 'html.parser')
        form = soup.find('form', {'name': 'form'})  # Select the form by name

        # Get the action URL
        action_url = form['action']

        # Gather hidden input fields into a dictionary for the form data
        form_data = {input_tag['name']: input_tag['value'] for input_tag in form.find_all('input', {'type': 'hidden'})}
        full_action_url = base_url + action_url

        # Submit the form with a POST request
        result_response = session.post(full_action_url, data=form_data, proxies=proxies)

        # Parse the HTML content
        soup = BeautifulSoup(result_response.text, 'html.parser')
        # how to submit a form
        # print(soup.prettify())

        pass

    if v1_site:

        # Send a POST request to submit the form
        selection_resp = session.post(url, data=payload, proxies=proxies)
        # this displays the property information portal - date range search
        # lets user select from two reports, just click on the forms

        # Parse the HTML content
        soup = BeautifulSoup(selection_resp.text, 'html.parser')

        # Find the form with id 'form0'
        form0 = soup.find('form', {'id': 'form0'})
        form1 = soup.find('form', {'id': 'form1'})
        # assert form0 and form 1 exist
        assert form0
        assert form1
        
        if siteType == 'sidney':
            if permitType == 'issued':
                form = form1
            else:
                form = form0
        else:
            if permitType == 'issued':
                form = form0
            else:
                form = form0
        
        # if isApplied:
        #     form = form1
        # else:
        #     form = form0
        # assert form or form2

        # Extract the action (the URL to send the data)
        action = form['action'] if form.get('action') else ""

        if action == "":
            raise ValueError("No action found in the form")

        # Extract the form fields
        data = {}
        for input_tag in form.find_all('input'):
            if input_tag.get('name'):
                # Handle different types of inputs like 'hidden', 'text', etc.
                value = input_tag.get('value', '')
                # check if it is input type submit, 
                if input_tag.get('type') == 'submit':
                    # overwrite value for submit button
                    data[input_tag['name']] = "Submit"
                else:
                    data[input_tag['name']] = value

        # data['ctl00$FeaturedContent$rpt_report$ctl00$submitReport'] = "Submit"
        # ctl00$FeaturedContent$rpt_report$ctl01$submitReport


        permit_response = f"{base_url}{action}"

        # Send a POST request with the extracted form data
        result_response = session.post(permit_response, data=data, proxies=proxies)
        result_response.raise_for_status()  # Optional: Raise an exception for HTTP errors
        # parse the response

        # with open('permits_alberni.html', 'w', errors='ignore') as file:
        #    file.write(result_response.text)

    permits = _parse_permits({
        'text': result_response.text
    })

    data = {
        "permits_raw": result_response.text,
        "page_load_raw": page_load_resp.text,
        "selection_raw": selection_resp.text,
        "permits": permits
    }
    return data

def get_proxy_list():
    """
    Tries a list of proxy fetching functions in order and returns
    the first successfully retrieved list of proxies.

    Args:
        params (dict, optional): Parameters for fetching proxies.
                                 Currently not used in this refactored version
                                 but kept for compatibility with the original signature.
                                 Defaults to None.

    Returns:
        list: A list of proxies if successful, otherwise an empty list.
    """
    # List of proxy fetching functions to try, in order of preference
    proxy_fetchers = [
        get_proxies_cz,
        get_proxies_world,
        # Add more proxy fetching functions here if needed
        # e.g., get_proxies_another_source
    ]

    for fetcher_function in proxy_fetchers:
        try:
            print(f"Trying {fetcher_function.__name__}...")
            proxies_list = fetcher_function()
            # Check if the list is not None and not empty
            if proxies_list:
                print(f"Successfully fetched proxies using {fetcher_function.__name__}.")
                return proxies_list
            else:
                print(f"{fetcher_function.__name__} returned an empty list or None.")
        except Exception as e:
            print(f"Error calling {fetcher_function.__name__}: {e}")
            # Continue to the next fetcher function if an error occurs
    return []

def permit_development_tracker(params):
    # destructure, make sure we have base_url, starting path (relative url)
    # https://tender.victoria.ca/
    base_url = params.get('base_url', 'https://online.saanich.ca/')
    # webapps/ourcity/Prospero/Search.aspx
    starting_url = params.get('starting_url', 'Tempest/OurCity/Prospero/Search.aspx')
    # values should be issued or applied

    siteType = params.get('siteType', 'saanich')


    url = f"{base_url}/{starting_url}"

    session = requests.Session()
    proxies_list = []
    proxies = None
    # sidney doesnt seem to care about https
    proxies_list = get_proxy_list()
    # proxies_list = get_proxies_cz()
    if len(proxies_list) > 0:
        proxy = random.choice(proxies_list)
    else:
        proxy = None
    # proxy="23.227.38.198:80"
    if proxy:
        # do we just buy a proxy server for this scrapping
        if siteType == 'sidney':
            proxies={
                'http': proxy,
                # 'https': https_proxy

            }
        else:
            proxies={
                'http': proxy,
                # 'https': https_proxy
            }
    else:
        proxies = {}

    session.headers.update({
        'User-Agent': mk_user_agent(),
    })

    page_load_resp = session.get(url,proxies=proxies)

    # with open('testing.html', 'w', errors='ignore') as file:
    #     file.write(page_load_resp.text)


    # print("trying to get data for ", url)
    soup = BeautifulSoup(page_load_resp.text, 'html.parser')

    # Extract dynamic fields from the HTML
    viewstate = soup.find(id="__VIEWSTATE")['value']
    eventvalidation = soup.find(id="__EVENTVALIDATION")['value']

    # Prepare the payload for the POST request

    # set FromDate and ToDate
    base_playload = {
        "__EVENTTARGET": "",
        "__EVENTARGUMENT": "",
        "__VIEWSTATE": viewstate,
        "__VIEWSTATEGENERATOR": soup.find(id="__VIEWSTATEGENERATOR")['value'],
        "__VIEWSTATEENCRYPTED": "",
        "__EVENTVALIDATION": eventvalidation,
        "ctl00$FeaturedContent$btn_ViewReport": "View Report"
    }
       

    initial_page_load = session.post(url, data=base_playload, proxies=proxies)
    # this displays the property information portal - date range search
    # lets user select from two reports, just click on the forms
    # click on the filters and then get the new content

    viewstate = soup.find(id="__VIEWSTATE")['value']
    eventvalidation = soup.find(id="__EVENTVALIDATION")['value']
    # Parse the HTML content
    soup = BeautifulSoup(initial_page_load.text, 'html.parser')


    no_new_pages = False
    iteration_limit = 6
    current_iteration = 0
    current_page = None
    entries = []
    
    while no_new_pages == False and current_iteration < iteration_limit:
        current_iteration += 1
        viewstate = soup.find(id="__VIEWSTATE")['value']
        eventvalidation = soup.find(id="__EVENTVALIDATION")['value']
        if siteType == 'saanich':
            new_payload = {
                "__EVENTTARGET": "",
                "__EVENTARGUMENT": "",
                "__VIEWSTATE": viewstate,
                "__VIEWSTATEGENERATOR": soup.find(id="__VIEWSTATEGENERATOR")['value'],
                "__VIEWSTATEENCRYPTED": "",
                "__EVENTVALIDATION": eventvalidation,
                "ctl00$FeaturedContent$folderStatusRepeater$ctl00$folderStatusCheckBox": "ACTIVE",
                "ctl00$FeaturedContent$folderStatusMobileRepeater$ctl00$folderStatusMobileCheckBox": "ACTIVE",
                "ctl00$FeaturedContent$hdn_filterFolderStatusSelected": "ACTIVE",
                "ctl00$FeaturedContent$SearchButton": "Search",
                "__ASYNCPOST": True
            }
        elif siteType == 'victoria':
              new_payload = {
                "__EVENTTARGET": "",
                "__EVENTARGUMENT": "",
                "__VIEWSTATE": viewstate,
                "__VIEWSTATEGENERATOR": soup.find(id="__VIEWSTATEGENERATOR")['value'],
                "__VIEWSTATEENCRYPTED": "",
                "__EVENTVALIDATION": eventvalidation,
                "ctl00$FeaturedContent$folderStatusRepeater$ctl00$folderStatusCheckBox": "ACTIVE",
                "ctl00$FeaturedContent$folderStatusMobileRepeater$ctl00$folderStatusMobileCheckBox": "ACTIVE",
                "ctl00$FeaturedContent$hdn_filterFolderStatusSelected": "ACTIVE",
                "ctl00$FeaturedContent$SearchButton": "Search",
                "ctl00$FeaturedContent$dropdown_list": "Filter Search",
                "__ASYNCPOST": True
            } 
        if current_page:
            new_payload["ctl00$FeaturedContent$PageNumberHidden"] = current_page
            new_payload["ctl00$FeaturedContent$PageNumber"] = "ctl00$FeaturedContent$PageNumber"
        else:
            current_page = 1
                
        page_data = session.post(url, data=new_payload, proxies=proxies)

        soup = BeautifulSoup(page_data.text, 'html.parser')
        # with open(f"basic_{current_iteration}.html", 'w', errors='ignore') as file:
        #     file.write(page_data.text)

        # for soup we want to grab searchResultsDiv
        searchResultsDiv = soup.find(id="searchResultsDiv")
        if not searchResultsDiv:
            no_new_pages = True
            continue
        # for the search divs we want to grab all the elements of content-container from searchResultsDiv
        content_containers = searchResultsDiv.find_all(class_="content-container")
        if not content_containers:
            no_new_pages = True
            continue
        # for each content-container we want to grab the content
        for content_container in content_containers:
            data = {}
            address_div = content_container.find(class_="search_address")
            if address_div:
                data['address'] = address_div.get_text(strip=True)

            # Extract Folder Number
            folder_no_div = content_container.find(class_="search_folderNo")
            if folder_no_div:
                data['folder_no'] = folder_no_div.get_text(strip=True)

            # Extract Type
            type_div = content_container.find(class_="search_type")
            if type_div:
                data['type'] = type_div.get_text(strip=True)

            # Extract Application Date
            # Find the div that contains "Application Date:"
            content_body = content_container.find(class_="content-container-body")
            app_date_div = content_body.find(lambda tag: tag.name == 'div' and "Application Date:" in tag.get_text())
            if app_date_div:
                data['application_date'] = app_date_div.get_text(strip=True).replace("Application Date:", "").strip()

            # Extract Status
            status_span = content_container.find("span", class_="heavy-font")
            if status_span:
                # The actual status text is the first child text node of the span,
                # or the text of the span if it has no further children tags.
                # We also want to handle the empty <span></span> inside it.
                status_text = ''.join(node for node in status_span if isinstance(node, str)).strip()
                if not status_text and status_span.contents: # If direct text is empty, check children
                        status_text = status_span.contents[0].strip() if status_span.contents and isinstance(status_span.contents[0], str) else ""
                data['status'] = status_text if status_text else status_span.get_text(strip=True)


            # Extract Purpose
            purpose_div = content_container.find(class_="search_purpose")
            if purpose_div:
                data['purpose'] = purpose_div.get_text(strip=True)

            for button_wrapper_div in content_container.find_all("div", onclick=True): # More direct: find divs with onclick
                details_button = button_wrapper_div.find("button", class_="details-btn")
                
                if not details_button: # Ensure the div actually contains our specific button
                    print("no details button found")
                    continue
                
                # The relevant onclick is on button_wrapper_div (the parent div)
                onclick_attr = button_wrapper_div.get('onclick') # Use .get() for safety

                if onclick_attr:
                    # Your original logic to extract the URL from the onclick string:
                    # "window.location = '../Prospero/Details.aspx?folderNumber=REZ00796'"
                    # This part looks for content between the first and last single quote.
                    
                    # We can make the check for "window.location = " more explicit if needed,
                    # or keep your more general "../Prospero/Details.aspx?folderNumber=" check.
                    # For extracting "content after =''", it means content within the single quotes.
                    
                    # Let's refine the extraction to be robust for "window.location = 'URL'"
                    if "window.location = '" in onclick_attr and onclick_attr.strip().endswith("'"):
                        try:
                            # Extract the content between "window.location = '" and the trailing "'"
                            start_pattern = "window.location = '"
                            url_start_index = onclick_attr.find(start_pattern)
                            
                            if url_start_index != -1:
                                actual_url_start = url_start_index + len(start_pattern)
                                # Ensure we find the last single quote of this specific assignment
                                # For simplicity, if the structure is consistently "window.location = '...'",
                                # rfind("'") works.
                                url_end_index = onclick_attr.rfind("'")
                                
                                if url_end_index > actual_url_start:
                                    data['details_link'] = onclick_attr[actual_url_start:url_end_index]
                                else:
                                    data['details_link'] = None # Extraction failed
                            else:
                                data['details_link'] = None # Pattern not found
                        except Exception:
                            data['details_link'] = None # Error during parsing
                    elif "../Prospero/Details.aspx?folderNumber=" in onclick_attr:
                        # Fallback to your original specific string check and extraction logic
                        # if the "window.location = " pattern isn't matched but the Prospero path is there.
                        # This part assumes the URL is still wrapped in single quotes.
                        link_start_index = onclick_attr.find("'") 
                        if link_start_index != -1:
                            link_start_index += 1 # Move past the first quote
                            link_end_index = onclick_attr.rfind("'")
                            if link_end_index > link_start_index:
                                data['details_link'] = onclick_attr[link_start_index:link_end_index]
                            else:
                                data['details_link'] = None # Quotes not found as expected for URL
                        else:
                            data['details_link'] = None # Starting quote not found
                    else:
                        data['details_link'] = None # Onclick attribute present but not in a recognized URL format
                else:
                    data['details_link'] = None # Parent div does not have an onclick attribute
            # adjust details_link if not None 

            if data['details_link']:
                # adjustment starting url
                base_url = "https://online.saanich.ca/Tempest/OurCity/Prospero"
                # we want to replace ../ with https://online.saanich.ca/Tempest/OurCity/Prospero
                data['details_link'] = base_url + data['details_link'].replace('../Prospero', '')
            # # Extract Details Link
            # details_button = content_container.find("button", class_="details-btn")
            # # grab the parent div

            # if details_button and details_button.has_attr('onclick'):
            #     onclick_attr = details_button['onclick']
            #     # Example: "window.location = '../Prospero/Details.aspx?folderNumber=REZ00796'"
            #     # We want to extract the URL part
            #     if "../Prospero/Details.aspx?folderNumber=" in onclick_attr:
            #         link_start_index = onclick_attr.find("'") + 1
            #         link_end_index = onclick_attr.rfind("'")
            #         if link_start_index > 0 and link_end_index > link_start_index:
            #                 data['details_link'] = onclick_attr[link_start_index:link_end_index]
            #     else:
            #         data['details_link'] = onclick_attr
            # else:
            #     data['details_link'] = None

            # Now you have a dictionary 'data' for each content_container
            # You can append it to a list, print it, or process it further

            entries.append(data)
            
        current_page += 1
    # remove duplicate entries
    return entries
    # data = {
    #     "permits_raw": result_response.text,
    #     "page_load_raw": page_load_resp.text,
    #     "selection_raw": selection_resp.text,
    #     "permits": permits
    # }
    # return data
# Optionally, you can parse the result to confirm the submission or to continue with further processing

def calculate_target_date(ref_datetime=datetime.now()):
    """
    Calculates the target cutoff date based on the current day of the week.
    - If today is Sunday, Monday, Tuesday, or Wednesday: target is last week's Thursday.
    - If today is Thursday, Friday, or Saturday: target is the current week's Monday.
    The returned date is the actual day to be used as a boundary; applications
    must be *after* this day.
    """
    today_date = ref_datetime.date()  # Work with date objects for calculation
    weekday = today_date.weekday()  # Monday is 0, ..., Sunday is 6

    target_date_val = None

    # Rule: If Sunday (6), Monday (0), Tuesday (1), or Wednesday (2), grab last week's Thursday.
    # Thursday is weekday 3.
    if weekday == 6 or weekday <= 2:  # Covers Sunday, Monday, Tuesday, Wednesday
        # To get to the previous week's Thursday:
        # If Mon (0): target is Mon - 4 days = last Thursday (e.g., Mon 20th -> Thu 16th)
        # If Tue (1): target is Tue - 5 days = last Thursday (e.g., Tue 21st -> Thu 16th)
        # If Wed (2): target is Wed - 6 days = last Thursday (e.g., Wed 22nd -> Thu 16th)
        # If Sun (6): target is Sun - 10 days = last Thursday (e.g., Sun 26th -> Thu 16th)
        # This can be calculated as today_date - timedelta(days=weekday + 4)
        target_date_val = today_date - timedelta(days=weekday + 4)
    # Rule: If past Thursday (3) and up to Saturday (5), grab Monday.
    # Monday is weekday 0.
    elif weekday >= 3 and weekday <= 5:  # Covers Thursday, Friday, Saturday
        # To get to the current week's Monday:
        # If Thu (3): target is Thu - 3 days = Monday (e.g., Thu 23rd -> Mon 20th)
        # If Fri (4): target is Fri - 4 days = Monday (e.g., Fri 24th -> Mon 20th)
        # If Sat (5): target is Sat - 5 days = Monday (e.g., Sat 25th -> Mon 20th)
        # This can be calculated as today_date - timedelta(days=weekday - 0)
        target_date_val = today_date - timedelta(days=weekday)
    
    # Fallback in case weekday logic is ever incomplete (should not happen for 0-6)
    if target_date_val is None:
        # This case should ideally not be reached if weekday is always 0-6.
        # As a very basic fallback, could use yesterday, but specific handling might be needed.
        print("Warning: Could not determine target_date_val based on weekday. Defaulting might occur or an error.")
        # For safety, let's ensure it's a date, e.g., yesterday, or raise an error.
        # For now, let's assume it's always set by the logic above.
        # If this function MUST return a date, a more robust fallback is needed.
        # However, the conditions for weekday 0-6 are exhaustive.
        pass

    return target_date_val # This is a date object


def filter_saanich_permits(entries):
    clean_entries = []
    # filter out type Temporary Use Permit
    for entry in entries:
        if entry['type'] != 'Temporary Use Permit':
            clean_entries.append(entry)

    filtered_entries = []

    target_filter_date = calculate_target_date()
    print("looking for entries with target date", target_filter_date)
    # filter out entries before today
    for entry in clean_entries:
        application_date = dateparser.parse(entry['application_date'])
        if application_date is None:

            print(f"Could not parse application_date '{application_date}' for entry ID {entry.get('id', 'N/A')}. Skipping.")
            continue
        
        # We need to compare dates. Convert the parsed datetime to a date object.
        application_actual_date = application_date.date()

        # Keep the entry if its application_date is strictly after the target_filter_date
        if application_actual_date >= target_filter_date:
            # print(f"KEEPING entry ID {entry.get('id', 'N/A')}: app_date {application_actual_date} > target_date {target_filter_date}")
            filtered_entries.append(entry)

    return filtered_entries

if __name__ == "__main__":
    # params = {
    #     "base_url": "https://mysidney.sidney.ca",
    #     "starting_url": "TempestApps/PIP/Pages/Search.aspx?templateName=LIVE_DATE"
    # }
    # params = {
    #     "base_url": "https://egov.northcowichan.ca",
    #     "starting_url": "apps/PIP/Pages/Search.aspx?templateName=PERMITSISSU",
    #     'siteType': "northcowichan"
    # }
    # params = {
    #     "base_url": "https://egov.northcowichan.ca",
    #     "starting_url": "apps/PIP/Pages/Search.aspx?templatename=PERMITSAPPL",
    #     'siteType': "northcowichan"
    # }
    # params = {
    #     "base_url": "https://online.portalberni.ca",
    #     "starting_url": "WebApps/PIP/Pages/Search.aspx?templateName=permit reporting",
    #     "siteType": "alberni",
    #     "start_date": "11/01/2024",
    #     "end_date": "11/16/2024"
    # }
    # data = web_portal_issues(params)

    # print(data.get("permits"))
    params = {
        # "base_url": "https://tender.victoria.ca",
        # "starting_url": "webapps/ourcity/Prospero/Search.aspx",
        # "siteType": "victoria"
    }
    entries = permit_development_tracker(params)
    print(entries)
    import json
    # with open("data/saanich.json", "w") as f:
    #     json.dump(entries, f)
    # print("entries", entries)
    filtered_entries = filter_saanich_permits(entries)

    print("filtered_entries", filtered_entries)


    # print(data.get("permits"))