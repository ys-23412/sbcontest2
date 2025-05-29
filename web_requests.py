import requests
import re
import random
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

            if proxy_type == 'socks5':
                ip = cols[0].text.strip()
                port = cols[1].text.strip()
                proxies.append(f'socks5://{ip}:{port}')

            if proxy_type == 'socks4':
                ip = cols[0].text.strip()
                port = cols[1].text.strip()
                proxies.append(f'socks4://{ip}:{port}')

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

            if proxy_type.lower() == 'socks5':
                port = cols[1].text.strip()
                proxies.append(f'socks5://{ip}:{port}')

            if proxy_type.lower() == 'socks4':
                port = cols[1].text.strip()
                proxies.append(f'socks4://{ip}:{port}')
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
    if siteType == 'sidney':
        proxies_list = get_proxies_world()
    else:
        proxies_list = get_proxies_cz()
    # proxies_list = get_proxies_cz()
    proxy = random.choice(proxies_list)
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

    session.headers.update({
        'User-Agent': mk_user_agent(),
    })

    print("parsing url", url)
    print("proxies", proxies)

    # Make an initial GET request
    page_load_resp = session.get(url,proxies=proxies)

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


def permit_development_tracker(params):
    # destructure, make sure we have base_url, starting path (relative url)
    base_url = params.get('base_url', 'https://online.saanich.ca/')
    starting_url = params.get('starting_url', 'Tempest/OurCity/Prospero/Search.aspx')
    # values should be issued or applied

    siteType = params.get('siteType', 'saanich')


    # get start_date and end_date variables from the params
    # assume this will not be called if this is not set
    # start_date = params.get('start_date')
    # end_date = params.get('end_date')

    # # format these dates into "05/01/2024",
    # if type(start_date) == str:
    #     start_date = dateparser.parse(start_date)
    #     start_date_fmt = start_date.strftime("%m/%d/%Y")
    # else:
    #     start_date_fmt = start_date.strftime("%m/%d/%Y")
    # if type(end_date) == str:
    #     end_date = dateparser.parse(end_date)
    #     end_date_fmt = end_date.strftime("%m/%d/%Y")
    # else:
    #     end_date_fmt = end_date.strftime("%m/%d/%Y")

    url = f"{base_url}/{starting_url}"

    session = requests.Session()

    # sidney doesnt seem to care about https
    if siteType == 'sidney':
        proxies_list = get_proxies_world()
    else:
        proxies_list = get_proxies_cz()
    # proxies_list = get_proxies_cz()
    proxy = random.choice(proxies_list)
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

    session.headers.update({
        'User-Agent': mk_user_agent(),
    })

    # Make an initial GET request
    page_load_resp = session.get(url,proxies=proxies)

    # with open('selection_alberni.html', 'w', errors='ignore') as file:
    #     file.write(page_load_resp.text)

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
        new_payload = {
            "__EVENTTARGET": "",
            "__EVENTARGUMENT": "",
            "__VIEWSTATE": viewstate,
            "__VIEWSTATEGENERATOR": soup.find(id="__VIEWSTATEGENERATOR")['value'],
            "__VIEWSTATEENCRYPTED": "",
            "__EVENTVALIDATION": eventvalidation,
            "ctl00$FeaturedContent$folderStatusRepeater$ctl00$folderStatusCheckBox": "ACTIVE",
            "ctl00$FeaturedContent$folderTypeRepeater$ctl19$folderTypeCheckBox": "REZONING",
            "ctl00$FeaturedContent$folderTypeRepeater$ctl22$folderTypeCheckBox": "SUBDIVISION",
            "ctl00$FeaturedContent$folderStatusMobileRepeater$ctl00$folderStatusMobileCheckBox": "ACTIVE",
            "ctl00$FeaturedContent$folderTypeMobileRepeater$ctl19$folderTypeMobileCheckBox": "REZONING",
            "ctl00$FeaturedContent$folderTypeMobileRepeater$ctl22$folderTypeMobileCheckBox": "SUBDIVISION",
            "ctl00$FeaturedContent$hdn_filterFolderTypeSelected": "REZONING,SUBDIVISION",
            "ctl00$FeaturedContent$hdn_filterFolderStatusSelected": "ACTIVE",
            "ctl00$FeaturedContent$SearchButton": "Search",
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

            # Extract Details Link
            details_button = content_container.find("button", class_="details-btn")
            if details_button and details_button.has_attr('onclick'):
                onclick_attr = details_button['onclick']
                # Example: "window.location = '../Prospero/Details.aspx?folderNumber=REZ00796'"
                # We want to extract the URL part
                if "../Prospero/Details.aspx?folderNumber=" in onclick_attr:
                    link_start_index = onclick_attr.find("'") + 1
                    link_end_index = onclick_attr.rfind("'")
                    if link_start_index > 0 and link_end_index > link_start_index:
                            data['details_link'] = onclick_attr[link_start_index:link_end_index]

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
    entries = permit_development_tracker({})
    print(entries)

    # print(data.get("permits"))