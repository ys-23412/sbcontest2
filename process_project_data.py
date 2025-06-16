import os
import requests
import time
import json
import re

from datetime import datetime
from google import genai
from google.genai import types


# Sample CSV data as a string, replace this with actual file reading if needed
project_types_csv = """
id,name,sort_order,category,rank,analytics_include
68,"accessory buildings",20,,1,1
89,"agricultural building",110,,1,1
33,"civil work",53,Civil,1,0
20,"commercial add/alter",70,Commercial,5,1
18,"commercial new",60,Commercial,5,1
34,demolition/deconstruction,140,,1,1
84,foundations,160,,1,1
32,"industrial add/alter",100,Industrial,3,1
30,"industrial new",90,Industrial,3,1
23,"institutional add/alter",130,Institution,6,1
21,"institutional new",120,Institution,6,1
69,"tenant improvements",80,Commercial,5,1
71,"mixed-use dev",50,Multi-family,7,1
26,"multi-family add/alter",40,Multi-family,7,1
24,"multi-family new",30,Multi-family,7,1
64,"residential add/alter",10,,1,1
15,"residential new",1,,1,1
91,"roads & bridges",55,Civil,1,0
35,"sign permit",180,,1,0
67,"site mobile/pre-fab",170,,1,1
80,subdivision,147,Civil,1,0
92,"consulting services",1,Consulting,2,0
93,"supply & services",3,Tenders,1,0
108,landscaping,3,Tenders,0,0
99,"comprehensive development",1,Multi-family,7,0
110,"master plan",1,Consulting,0,0
111,services,1,Tenders,0,0
112,"leased space",1,Tenders,0,0
113,"mechanical, electrical & plumbing",3,Tenders,0,0
114,"land development",1,Multi-family,0,0
""".strip()

def find_correct_issue_date(issues, current_date):
    """
    Finds the correct issue from a list based on the current day's logic.

    Args:
        issues (list): A list of dictionaries, each representing an issue with a 'date' key.
        current_date (datetime.date): The current date (e.g., today's date).

    Returns:
        dict or None: The selected issue dictionary, or None if no suitable issue is found.
    """
    # Parse and sort issues by date (ascending) for easy selection of the "next" issue
    parsed_issues = []
    for issue in issues:
        # Assuming 'date' is in 'YYYY-MM-DD' format
        issue_date = datetime.strptime(issue['date'], '%Y-%m-%d').date()
        parsed_issues.append({'original_issue': issue, 'date_obj': issue_date})

    # Sort the issues by their date_obj
    # Get the weekday (Monday is 0, Sunday is 6)
    current_weekday = current_date.weekday()

    found_issue = None
    # issues start on sunday, so for 5:00 am, its equal to or less than
    if current_weekday >= 0 and current_weekday <= 2:  # Monday
        for issue_entry in parsed_issues:
            # we want to go the issue above
            if issue_entry['date_obj'] > current_date:
                found_issue = issue_entry['original_issue']
    elif current_weekday >= 3:  # Thursday
        # On Thursday, find the closest issue date that is strictly after the current date
        for issue_entry in parsed_issues:
            if issue_entry['date_obj'] > current_date:
                found_issue = issue_entry['original_issue']
                break # Found the first one strictly after, which is the closest upcoming
    # For other days (Tuesday, Wednesday, Friday, Saturday, Sunday), no issue is selected
    # as the cron job only runs on Monday and Thursday.

    return found_issue

def parse_json_string(json_string):
  """
  Finds content enclosed by ```json or ```, extracts it, and loads the JSON data.

  Args:
    json_string: A string potentially containing JSON data enclosed by ```json or ```.

  Returns:
    A Python list of dictionaries representing the parsed JSON data, or None if parsing fails
    or no valid JSON block is found.
  """
  start_json_tag = "```json"
  end_json_tag = "```"
  start_general_tag = "```"

  # Try to find ```json ... ``` block first
  start_index = json_string.find(start_json_tag)
  if start_index != -1:
    end_index = json_string.find(end_json_tag, start_index + len(start_json_tag))
    if end_index != -1:
      json_content = json_string[start_index + len(start_json_tag):end_index].strip()
      try:
        data = json.loads(json_content)
        return data
      except json.JSONDecodeError as e:
        print(f"Error decoding JSON from ```json block: {e}")
        return None

  # If no ```json block, try to find a general ``` ... ``` block
  start_index = json_string.find(start_general_tag)
  if start_index != -1:
    end_index = json_string.find(end_json_tag, start_index + len(start_general_tag))
    if end_index != -1:
      json_content = json_string[start_index + len(start_general_tag):end_index].strip()
      try:
        data = json.loads(json_content)
        return data
      except json.JSONDecodeError as e:
        print(f"Error decoding JSON from general ``` block: {e}")
        return None

  print("No valid JSON block enclosed by ```json or ``` found.")
  return None

def get_latest_issue():
    api_url = os.getenv('YS_APIURL', 'http://localhost')
    agent_id = os.getenv('YS_AGENTID', 'AutoHarvest')
    latest_issue_url = f"{api_url}/api_get_latest_issue.php"
    # make request to api
    query_params = {
        "agent": agent_id
    }
    latest_issue = requests.get(latest_issue_url, params=query_params)
    # check status code
    if latest_issue.status_code != 200:
        raise Exception("Failed to get latest issue")
    # parse response
    latest_issue = latest_issue.json()

    found_issue = find_correct_issue_date(latest_issue, datetime.now().date())

    return {
       "issues": latest_issue,
       "found_issue": found_issue
    }

def detect_company(text):
    """
    Detects if a given text likely contains a company name by searching for common
    company suffixes (e.g., LTD, INC, LLC). If found, it returns the portion
    of the text up to and including the company identifier.

    Args:
        text (str): The input string to check.

    Returns:
        str or None: The extracted company name portion of the text (e.g., "STRONGITHARM CONSULTING LTD")
                     if a company suffix is found, otherwise None.
    """
    # Define a regex pattern to find common company suffixes
    # \b ensures word boundaries so 'ltd' doesn't match 'limited'
    # ?: creates a non-capturing group for the OR conditions
    # re.IGNORECASE makes the matching case-insensitive
    pattern = re.compile(r'\b(?:LTD|INC|LLC|CORPORATION|CORP|PLC|GMBH|CO)\b', re.IGNORECASE)

    # Search the text for any matches
    match = pattern.search(text)

    if match:
        # If a match is found, return the part of the string up to the end of the match.
        # This will include the company identifier itself.
        return text[:match.end()]
    else:
        # If no match is found, return None
        return None
    
def map_data(params):

    data = params.get('data', [])
    if len(data) == 0:
        print("No data to map")
        return
    region_name = params.get('region_name', 'Saanich')
    agent_id = os.getenv('YS_AGENTID', 'AutoHarvest')
    ys_component_id = os.getenv('YS_COMPONENTID', 7)

    GEMINI_API_KEY = os.getenv("GOOGLE_API_KEY")
    client = genai.Client(api_key=GEMINI_API_KEY)
    api_url = os.getenv('YS_APIURL', 'http://localhost')

    city_id = [64, 74, 75]
    default_city_name = "Saanich"
    file_type = agent_id
    file_name = "AutoHarvest"

    issue_results = get_latest_issue()
    found_issue = issue_results['found_issue']
    latest_issue = issue_results['issues']

    print("Using found issue", found_issue)
    ys_volume_id = found_issue['id']

    mapped_data = []
    entries_with_project_types = []
    # classified entries
    print(len(data))
    print("are you getting here?")
    for unclassified_entry in data:
        # copy unclassified_entry and remove details_link
        entry_copy = unclassified_entry.copy()
        # entry_copy['details_link'] = None
        prompt=f"""
            Given the following new project data, we want to determine the project type:

            Use the following csv data and return the best matching id 

            {project_types_csv}

            Below is the project data:

            {json.dumps(entry_copy)}

            Please respond in the following format:

            {{
                "project_type_id": <project_type_id>
            }}
        """
        try:
            response = client.models.generate_content(
                model = "gemini-2.0-flash",
                contents = [
                    prompt
                ]
            )

            project_type_id = 0
            project_data = parse_json_string(response.text)
            # grab project_type_id
            if project_data and 'project_type_id' in project_data:
                # If JSON is valid and contains 'project_type_id', use its value
                project_type_id = project_data['project_type_id']
                print(f"Using project_type_id from JSON: {project_type_id}")
            else:
                # If JSON parsing failed or 'project_type_id' key is missing,
                # fallback to regex to find the first two-digit number in the raw response text.
                match = re.search(r'\b(\d{2})\b', response.text)
                if match:
                    # If a two-digit number is found, convert it to an integer
                    project_type_id = int(match.group(1))
                    print(f"Using project_type_id from regex: {project_type_id}")
                else:
                    # If no two-digit number is found via regex, keep default 0
                    print("No project_type_id found in JSON or via regex. Defaulting to 0.")
           

            # add to entries_with_project_types
            entry_copy['ys_project_type'] = project_type_id

            # entry_copy['details_link'] = unclassified_entry['details_link']
            entries_with_project_types.append(entry_copy)
        except Exception as e:
            print("Failed to process entry", e)
            entry_copy['ys_project_type'] = 0
            entries_with_project_types.append(entry_copy)
        time.sleep(4)

    if len(entries_with_project_types) == 0:
        print("do entries have project types?", entries_with_project_types)
    

    # print all the entries and save to data
    # add datetime to the filename
    current_date = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
    filename = f"{file_name}_{current_date}_{region_name}.json"
    with open(f"data/with_project_type_{filename}.json", "w") as f:
        json.dump(entries_with_project_types, f)

    fill_entries_url = f"{api_url}/api_fill_entries.php"
    for unmapped_entry in entries_with_project_types:
        entry = {}
        ys_body = {}
        entry['issue_id'] = ys_volume_id
        entry['city_name'] = unmapped_entry.get('city_name', default_city_name)
        entry['ys_date'] = unmapped_entry['application_date']
        entry['ys_address'] = unmapped_entry['address']
        # take first 255 characters
        entry['ys_description'] = unmapped_entry['purpose'][:100]
        # remove bad characters like ' and replace with sql safe characters
        entry['ys_description'] = entry['ys_description'].replace("'", "''")
        # strip everything past #, assume that means unit number
        # if '#' in entry['ys_description']:
        #     entry['ys_description'] = entry['ys_description'].split('#')[0]
       #  entry['ys_description'] = unmapped_entry['address'].split('#')[0]
        entry['ys_permit'] = unmapped_entry['folder_no']
        entry['ys_component'] = ys_component_id
        # all status is ACTIVE We can ignore, we only want to process active anyway
        entry['ys_type'] = unmapped_entry.get('ys_project_type', 0)
        entry['project_type'] = unmapped_entry.get('ys_project_type', 0)
        entry['region'] = unmapped_entry.get('city_name', default_city_name)
        ys_body['ys_documents_drawings_link'] = unmapped_entry['details_link']

        if unmapped_entry.get('application_contact'):
            # we want to determine if this is a contractor, if so we attempt to populate "ys_contractor"
            # If not use dump all the data into "Enqueries"'
            extracted_company_name = detect_company(unmapped_entry['application_contact'])
            if extracted_company_name:
                ys_body['ys_contractor'] = extracted_company_name
                print(f"Company contact extracted: {extracted_company_name}")
            else:
                # we want to still format the data, Replace Telephone with Ph: and Remove Email
                fmt_application_contact = unmapped_entry['application_contact'].replace("Telephone", "Ph").replace("Email:", "")
                ys_body['ys_enquiries'] = fmt_application_contact
            # ys_body['ys_contractor'] = unmapped_entry['application_contact']
        if unmapped_entry.get('type'):
            # we use the "Type" field from here to populate "ys_stage"
            ys_body['ys_stage'] = unmapped_entry['type']
        entry['ys_body'] = ys_body
        entry['isBuildingPermit'] = False
        entry['user_id'] = '2025060339'
        mapped_data.append(entry)

    if len(mapped_data) == 0:
        print("no mapped data returning")
        return

    curr_date = datetime.now().strftime("%Y-%m-%d %H_%M_%S")

    first_city = mapped_data[0].get('city_name', default_city_name)

    with open(f"data/with_mapping_{file_name}_{curr_date}_{region_name}.json", "w") as f:
        json.dump(mapped_data, f)
    filled_entries_data = [{
        'filename': f'{file_name}_{curr_date}_{region_name}.json',
        "pdf_type": "api",
        "region": first_city,
        "file_type": "json",
        "data": mapped_data,
        'user_id': '2025060339'
    }]

    with open(f"data/with_mapping_all{file_name}_{curr_date}_{region_name}.json", "w") as f:
        json.dump(filled_entries_data, f)

    filled_entries_resp = requests.post(fill_entries_url, json=filled_entries_data)
    # print response text to index.html
    # send api request to api_insert_into_data.php

    filled_entries = filled_entries_resp.json()

    with open(f"data/with_fill_{filename}_{region_name}.json", "w") as f:
        json.dump(filled_entries, f)

    insert_into_data_url = f"{api_url}/api_insert_into_data.php"
    insert_into_data_resp = requests.post(insert_into_data_url, json=filled_entries)
    try:
        # check for 500 then if so raise errro
        insert_into_data_resp.raise_for_status()
        insert_response = insert_into_data_resp.json()

        print(insert_response)
    except requests.HTTPError as http_err:
        print(f'HTTP error occurred: {http_err}')
    except:
        print(insert_into_data_resp.text)
        with open("insert_into_data_resp.txt", "w", errors='ignore') as f:
            f.write(insert_into_data_resp.text)

    return

if __name__ == "__main__":

    issue_results = get_latest_issue()

    print(issue_results.get('found_issue'))

    # sample_data =  [
    #     {'address': '', 'folder_no': 'BVD00560', 'type': 'BOULEVARD PERMIT', 'application_date': 'May 29, 2025', 'status': 'ACTIVE', 'purpose': 'ALTERING THE BOULEVARD', 'details_link': 'https://online.saanich.ca/Tempest/OurCity/Prospero/Details.aspx?folderNumber=BVD00560'}, 
    #     {'address': '200-3561       SHELBOURNE ST', 'folder_no': 'BLC07059', 'type': 'COMMERCIAL PERMIT', 'application_date': 'Jun 02, 2025', 'status': 'ACTIVE', 'purpose': 'TENANT IMPROVEMENT FOR BURKETT & CO - UNIT 200', 'details_link': 'https://online.saanich.ca/Tempest/OurCity/Prospero/Details.aspx?folderNumber=BLC07059'},
    #     {'address': '4444       WEST SAANICH RD', 'folder_no': 'BLC07058', 'type': 'COMMERCIAL PERMIT', 'application_date': 'May 29, 2025', 'status': 'ACTIVE', 'purpose': 'REPLACE FIRE ALARM PANEL - ROYAL OAK SHOPPING CENTRE', 'details_link': 'https://online.saanich.ca/Tempest/OurCity/Prospero/Details.aspx?folderNumber=BLC07058'}
    # ]
    # map_data(sample_data)