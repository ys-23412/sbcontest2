import requests
import re
import random
from enum import Enum
from datetime import datetime, timedelta
import base64
import json
import dateparser
from random_user_agent.user_agent import UserAgent
from bs4 import BeautifulSoup

class NewProjectSiteTypes(Enum):
    SAANICH = "saanich"
    VICTORIA = "victoria"
    CENTRAL_SAANICH = "central saanich"
    COLWOOD="colwood"
    COURTENAY="courtenay"
    OAKBAY="oak bay"
    NORTH_COWICHAN="north cowichan"

def get_site_params(site_type_enum: NewProjectSiteTypes) -> dict:
    """
    Returns a JSON string containing the base_url, starting_url, and siteType
    for a given NewProjectSiteTypes enum member.

    Args:
        site_type_enum (NewProjectSiteTypes): An enum member representing the type of site.

    Returns:
        str: A JSON string with base_url, starting_url, and siteType,
             or an error message if the enum member's value is not found.
    """
    site_data = {
        NewProjectSiteTypes.COLWOOD.value: {
            "base_url": "https://services.colwood.ca",
            "starting_url": "TLive/OurCity/Prospero/Search.aspx",
            "types_to_keep": [
                "BOARD OF VARIANCE",
                "DEVELOPMENT PERMIT",
                "DEVELOPMENT PERMIT AMENDMENT",
                "DEVELOPMENT VARIANCE PERMIT",
                "OCP AMENDMENT",
                "REZONING",
                "SUBDIVISION"
            ]
        },
        NewProjectSiteTypes.COURTENAY.value: {
            "base_url": "https://prospero.courtenay.ca",
            "starting_url": "TempestLive/ourcity/prospero/Search.aspx",
            "types_to_keep": [
                "DEVELOPMENT PERMIT",
                "DEVELOPMENT PERMIT AMENDMENT",
                "DEVELOPMENT VARIANCE PERMIT",
                "REZONING",
                "STRATA",
                "SUBDIVISION"
            ]
        },
        NewProjectSiteTypes.OAKBAY.value: {
            "base_url": "https://onlineservice.oakbay.ca",
            "starting_url": "WebApps/OurCity/Prospero/Search.aspx",
            "types_to_skip": [
                "ADVISORY DESIGN PANEL",
                "DEVELOPMENT VARIANCE PERMIT",
                "HERITAGE ALTERATION PERMIT",
                "MULTI-RESIDENTIAL",
                "OFFICIAL COMMUNITY PLAN AMENDMENT",
                "PART 3 BUILDING (COMPLEX)",
                "PART 9 BUILDING (STANDARD)",
                "ZONING BYLAW AMENDMENT"
            ]
        },
        NewProjectSiteTypes.VICTORIA.value: {
            "base_url": "https://tender.victoria.ca",
            "starting_url": "webapps/ourcity/prospero/Search.aspx",
            "types_to_skip": [
                "TEMPORARY USE PERMIT",
            ]
        },
        NewProjectSiteTypes.CENTRAL_SAANICH.value: {
            "base_url": "https://www.mycentralsaanich.ca",
            "starting_url": "TempestLive/OURCITY/Prospero/Search.aspx",
             "types_to_skip": [
                "TEMPORARY USE PERMIT",
            ]
        },
        NewProjectSiteTypes.SAANICH.value: {
            "base_url": "https://online.saanich.ca",
            "starting_url": "Tempest/OurCity/Prospero/Search.aspx",
            "types_to_keep": [
                "DEVELOPMENT PERMIT",
                "DEVELOPMENT PERMIT AMENDMENT",
                "DEVELOPMENT VARIANCE PERMIT",
                "REZONING",
                "STRATA",
                "SUBDIVISION"
            ]
        },
        NewProjectSiteTypes.NORTH_COWICHAN.value: {
            "base_url": "https://egov.northcowichan.ca",
            "starting_url": "apps/OurCity/Prospero/Search.aspx",
            "types_to_skip": [
                "TEMPORARY USE PERMIT",
            ],
            "iteration_limit": 1
        }
    }

    site_type_str = site_type_enum.value

    if site_type_str in site_data:
        params = {
            "base_url": site_data[site_type_str]["base_url"],
            "starting_url": site_data[site_type_str]["starting_url"],
            "siteType": site_type_str
        }
         # Add the filtering lists to the params dictionary
        if "types_to_keep" in site_data[site_type_str]:
            params["types_to_keep"] = site_data[site_type_str]["types_to_keep"]
        elif "types_to_skip" in site_data[site_type_str]:
            params["types_to_skip"] = site_data[site_type_str]["types_to_skip"]
        if "iteration_limit" in site_data[site_type_str]:
            params["iteration_limit"] = site_data[site_type_str]["iteration_limit"]
        return params
    else:
        # This case should ideally not be reached if the enum is exhaustive
        # but included for robustness.
        raise Exception("Error: Site type not found in site_data.")
        return {}

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
def get_proxies_proxifly(url="https://cdn.jsdelivr.net/gh/proxifly/free-proxy-list@main/proxies/countries/CA/data.txt"):
    """
    Fetches proxies from the Proxifly GitHub CDN text file.
    Assumes proxies are one per line in 'protocol://IP:PORT' format.
    """
    proxies = []
    session = requests.Session()
    session.headers.update({
        'User-Agent': mk_user_agent(),
        'Accept': 'text/plain, */*;q=0.8',
    })

    try:
        print(f"Fetching proxies from Proxifly CDN: {url}")
        response = session.get(url, timeout=10)
        response.raise_for_status() # Raise an HTTPError for bad responses (4xx or 5xx)
        
        # Split by lines and strip whitespace
        lines = response.text.splitlines()
        for line in lines:
            stripped_line = line.strip()
            if stripped_line:
                # Basic validation: check if it starts with http://, https://, socks5://, etc.
                if re.match(r'^(http|https|socks4|socks5):\/\/\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}:\d{1,5}$', stripped_line):
                    proxies.append(stripped_line)
                else:
                    print(f"Skipping malformed proxy entry from Proxifly: {stripped_line}")

    except requests.exceptions.RequestException as e:
        print(f"Network error fetching from Proxifly CDN: {e}")
    except Exception as e:
        print(f"An unexpected error occurred while parsing Proxifly CDN data: {e}")
    
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
        get_proxies_proxifly,
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

def to_initial_caps_advanced(field):
    if type(field) != str:
        return field
    # List of words to exclude from capitalization
    exceptions = ['a', 'an', 'bc' 'available', 'the', 'and', 'but', 'or', 'for', 'nor', 'on', 'at', 'to', 'from', 'by']
    
    # Split the text into words
    words = field.split()
    final_words = []
    
    # Only capitalize the first letter of each word, except for exceptions
    for i, word in enumerate(words):
        if i == 0 or i == len(words)-1 or word.lower() not in exceptions:
            # Always capitalize the first and last word
            final_words.append(word.capitalize())
        else:
            # Lowercase for exceptions, unless it's the first word
            final_words.append(word.lower())
    
    # Rejoin the capitalized words
    return ' '.join(final_words)

def decode_js_email(js_script):
    """
    Decodes an email address hidden in a JavaScript snippet that uses
    an array and concatenation within a document.write mailto link.

    Args:
        js_script (str): The full JavaScript string containing the email obfuscation.

    Returns:
        str: The decoded email address, or None if it cannot be found/decoded.
    """
    # 1. Extract the array definition
    array_match = re.search(r"var a = new Array\((.*?)\);", js_script)
    if not array_match:
        print("Could not find 'var a = new Array(...)' in the script.")
        return None

    array_content_str = array_match.group(1)
    
    # Safely parse the array elements.
    # This pattern captures quoted strings, allowing for single or double quotes.
    # It handles cases where there might be spaces or extra commas.
    elements_raw = re.findall(r"'(.*?)'|\"(.*?)\"", array_content_str)
    
    # Flatten the list of tuples and remove empty strings
    a_array = [item.strip() for tpl in elements_raw for item in tpl if item.strip()]

    if not a_array:
        print("Could not extract array elements.")
        return None

    # 2. Extract the concatenation sequence from the mailto link
    # This regex specifically looks for `a[number]` patterns inside the mailto link.
    mailto_match = re.search(r"mailto:\"?\+(" + r"(a\[\d+\]\+?)+" + r")\"?", js_script)

    if not mailto_match:
        print("Could not find the 'mailto:' link with array concatenation in the script.")
        return None

    concatenation_str = mailto_match.group(1)
    
    # Extract the indices (numbers inside a[])
    indices = [int(i) for i in re.findall(r"a\[(\d+)\]", concatenation_str)]

    if not indices:
        print("Could not extract array indices from the concatenation string.")
        return None

    # 3. Assemble the email address
    decoded_email = ""
    for index in indices:
        if 0 <= index < len(a_array):
            decoded_email += a_array[index]
        else:
            print(f"Warning: Index {index} out of bounds for array of size {len(a_array)}. Email might be incomplete.")
            return None # Or handle more gracefully if partial email is acceptable

    return decoded_email

def extract_application_detail_field(html, field="Application Contact:"):
    """
    Extracts the application contact information from the given HTML snippet.

    Args:
        html (str): The HTML string containing the contact information.

    Returns:
        str: The cleaned extracted contact information, or None if not found.
    """
    soup = BeautifulSoup(html, 'html.parser')

    # Find the div containing the "Application Contact:" label
    contact_label_div = soup.find('div', string=field)
    text = None
    if contact_label_div:
        # Get the next sibling div, which should contain the contact details
        contact_details_div = contact_label_div.find_next_sibling('div')

        if contact_details_div:
            # Extract text, remove script tags and extra whitespace
            # We explicitly get the text content of the <span> and then clean it.
            # We also get the mailto link's text as it's the actual email.
            span_tag = contact_details_div.find('span')
            if span_tag:
                # 1. Get all visible text content from the span and its descendants
                # This handles text directly in the span, and text in nested tags (like <a> for mailto)
                text_content = span_tag.get_text(separator=" ", strip=True)
                
                # 2. Extract text from any script tags within the span, if they exist
                script_texts = []
                for script in span_tag.find_all('script'):
                    script_text = script.string
                    if script_text:
                        script_texts.append(script_text.strip())


                clean_script_output = []
                # 3. Evaluate any JavaScript code within the script tags
                for script_text in script_texts:
                    try:
                        result = decode_js_email(script_text)
                        if isinstance(result, str):
                            clean_script_output.append(result.strip())
                        elif isinstance(result, list):
                            clean_script_output.extend(result)
                    except Exception as e:
                        print(f"Error evaluating JavaScript: {e}")
                    
                    print("clean_script_text", clean_script_output)
                # Combine the text content. You might want to format this based on your needs.
                # For example, adding a newline or a specific separator if script content is important.
                if script_texts:
                    combined_content = f"{text_content} {' '.join(clean_script_output)}"
                    text =combined_content.strip()
                
                elif text_content:
                    text = text_content

    if text:
        # we want to format the text, if LTD exists
        return text
    return None


def permit_development_tracker(params):
    # destructure, make sure we have base_url, starting path (relative url)
    # https://tender.victoria.ca/
    base_url = params.get('base_url', 'https://online.saanich.ca/')
    # webapps/ourcity/Prospero/Search.aspx
    starting_url = params.get('starting_url', 'Tempest/OurCity/Prospero/Search.aspx')
    # values should be issued or applied

    siteType = params.get('siteType', 'saanich')


    url = f"{base_url}/{starting_url}"
    session = params.get('session', requests.Session())
    proxies = params.get('proxies', {})
    print("url in use is", url)
    print("proxies is", proxies)
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
    iteration_limit = params.get('iteration_limit', 10)
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
        else:
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
                # adjust to replace search.aspx no matter what the case is
                ref_url = url.replace('/Search.aspx', '')
                # remove the last
                # we want to replace ../ with https://online.saanich.ca/Tempest/OurCity/Prospero
                data['details_link'] = ref_url + data['details_link'].replace('../Prospero', '')

            
            processed_data = {}
            for key, value in data.items():
                if key == 'details_link':
                    processed_data[key] = value
                else:
                    processed_data[key] = to_initial_caps_advanced(value)
            if siteType:
                processed_data['city_name'] = siteType


            entries.append(processed_data)
            
        current_page += 1
    # remove duplicate entries

    # attempt to grab details link and extract

    # output to data folder with sitename
    with open(f'data/{siteType}_all_entries.json', 'w') as f:
        json.dump(entries, f, indent=4)
    return entries
    # data = {
    #     "permits_raw": result_response.text,
    #     "page_load_raw": page_load_resp.text,
    #     "selection_raw": selection_resp.text,
    #     "permits": permits
    # }
    # return data
# Optionally, you can parse the result to confirm the submission or to continue with further processing

def calculate_target_date_ref(ref_datetime=datetime.now()):
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

def calculate_target_date(ref_datetime=datetime.now()):
    """
    Calculates the target cutoff date based on the current day of the week.
    - If today is Monday: target is last week's Friday.
    - Otherwise: target is yesterday's date.
    The returned date is the actual day to be used as a boundary; applications
    must be *after* this day.
    """
    today_date = ref_datetime.date()  # Work with date objects for calculation
    weekday = today_date.weekday()  # Monday is 0, ..., Sunday is 6

    # Rule: If today is Monday (0), grab last week's Friday.
    if weekday == 0:
        # To get to last week's Friday from Monday: subtract 3 days
        target_date_val = today_date - timedelta(days=3)
    # Rule: For any other day, grab yesterday's date.
    else:
        target_date_val = today_date - timedelta(days=1)
    
    return target_date_val


def get_filtered_permits_with_contacts(params, target_date=None):
    """
    Fetches development permits, filters them, and then extracts application contact
    information for each filtered entry by visiting their details link.

    Args:
        params (dict): Parameters to pass to permit_development_tracker.
        target_date (str or datetime, optional): The target date for filtering permits.
                                                If None, it defaults to 30 days ago.

    Returns:
        list: A list of dictionaries, where each dictionary represents a filtered
              permit entry with an added 'application_contact' field.
    """

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

        proxies={
            'http': proxy,
            # 'https': https_proxy

        }
    else:
        proxies = {}

    session.headers.update({
        'User-Agent': mk_user_agent(),
    })
    params['session'] = session
    params['proxies'] = proxies
    # Step 1: Get all permit entries
    all_entries = permit_development_tracker(params)

    clean_entries = []
    siteType = params.get('siteType')
    types_to_keep = params.get('types_to_keep')
    types_to_skip = params.get('types_to_skip')
    if types_to_keep:
        print(f"Filtering {siteType} entries: Keeping types {types_to_keep}")
        types_to_keep_lower = {t.lower() for t in types_to_keep}
        for entry in all_entries:
            if entry['type'].lower() in types_to_keep_lower:
                clean_entries.append(entry)
    elif types_to_skip:
        print(f"Filtering {siteType} entries: Skipping types {types_to_skip}")
        types_to_skip_lower = {t.lower() for t in types_to_skip}
        for entry in all_entries:
            if entry['type'].lower() not in types_to_skip_lower:
                clean_entries.append(entry)
    else:
        error_message = f"No specific 'types_to_keep' or 'types_to_skip' defined for {siteType}. Error."

        raise Exception(error_message)



    filtered_entries = filter_permits_by_date(clean_entries, target_date=target_date)

    proxies = None
    # proxies_list = get_proxy_list()
    # if len(proxies_list) > 0:
    #     proxy = random.choice(proxies_list)
    #     if proxy:
    #         proxies = {'http': proxy, 'https': proxy}
    # Step 3: For each filtered entry, visit the details_link and extract application contact
    for entry in filtered_entries:
        details_link = entry.get('details_link')
        if details_link:
            try:
                details_resp = session.get(details_link)
                details_resp.raise_for_status()  # Raise an exception for HTTP errors
                contact_info = extract_application_detail_field(details_resp.text)
                entry['application_contact'] = to_initial_caps_advanced(contact_info)

            except requests.exceptions.RequestException as e:
                print(f"Error fetching details link {details_link}: {e}")
                entry['application_contact'] = "Error retrieving contact info"
        else:
            entry['application_contact'] = "No details link available"
    
    return filtered_entries

def filter_permits_by_date(entries, target_date=None):

    filtered_entries = []
    if target_date is None:
        target_filter_date = calculate_target_date()
    else:
        target_filter_date = calculate_target_date(ref_datetime=target_date)
    print("looking for entries with target date", target_filter_date)
    # filter out entries before today
    for entry in entries:
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

    # paramscentral = {
    #     "base_url": "https://www.mycentralsaanich.ca",
    #     "starting_url": "TempestLive/OURCITY/Prospero/Search.aspx",
    #     "siteType": "centralSaanich"
    # }
    # entries = permit_development_tracker(params)
    # print(entries)
    import json
    # with open("data/saanich.json", "w") as f:
    #     json.dump(entries, f)
    # print("entries", entries)
    # filtered_entries = filter_permits(entries, target_date=datetime.now())
    # filtered_entries = get_filtered_permits_with_contacts(params, target_date=datetime.now())

    # print("filtered_entries", filtered_entries)
    # use requests to get html for https://online.saanich.ca/Tempest/OurCity/Prospero/Details.aspx?folderNumber=ALR00045
    resp = requests.get("https://online.saanich.ca/Tempest/OurCity/Prospero/Details.aspx?folderNumber=ALR00045")
    # get text response
    html = resp.text
    application_contact = extract_application_detail_field(html)

    # print(html)

    print("extracted data", application_contact)


    # print(data.get("permits"))
