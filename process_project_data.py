import os
import requests
import time
import json
import re
import dateparser
from enum import Enum
from datetime import datetime, date, timedelta
from dateutil.relativedelta import relativedelta # Import this
import pytz
from google import genai
from google.genai import types



class DataTypes(Enum):
    UPDATED_TENDERS = 11
    TENDERS = 10
    NEW_PROJECT = 7

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
112,"leased space",1,Tenders,0,0
113,"mechanical, electrical & plumbing",3,Tenders,0,0
114,"land development",1,Multi-family,0,0
""".strip()

def find_correct_issue_date(issues, current_datetime_utc):
    """
    Finds the immediate next upcoming issue from a list and a flag indicating
    if the current time is within the 'New Tender' classification period.

    Args:
        issues (list): A list of dictionaries, each representing an issue with a 'date' key
                       in 'YYYY-MM-DD' format.
        current_datetime_utc (datetime.datetime): The current UTC datetime object.

    Returns:
        tuple: A tuple containing:
            - dict or None: The immediate next upcoming issue dictionary, or None if no suitable issue is found.
            - bool: True if the current time (PST) is between Wednesday Noon and Sunday 10 PM,
                    indicating a 'New Tender' classification period for the *next* issue.
                    False otherwise.
    """

    pst = pytz.timezone('America/Los_Angeles')
    # Convert current_datetime_utc to PST
    current_datetime_pst = current_datetime_utc.astimezone(pst)
    current_date_only_pst = current_datetime_pst.date()
    current_weekday_pst = current_datetime_pst.weekday() # Monday is 0, Sunday is 6

    parsed_issues = []
    for issue in issues:
        # Assuming 'date' is in 'YYYY-MM-DD' format
        issue_date_obj = datetime.strptime(issue['date'], '%Y-%m-%d').date()
        parsed_issues.append({'original_issue': issue, 'date_obj': issue_date_obj})

    # Sort the issues by their date_obj
    parsed_issues.sort(key=lambda x: x['date_obj'])

    found_issue = None

    filter_start_date = current_date_only_pst - timedelta(days=6)
    upcoming_issues = [
        issue_entry for issue_entry in parsed_issues
        if issue_entry['date_obj'] > filter_start_date
    ]


    if upcoming_issues:
        # automatically put in this issue
        found_issue = upcoming_issues[0]['original_issue']

    # --- Determine if current time falls into the 'New Tender' classification period ---
    is_new_tender_period = False

    # Get the date of the current week's Wednesday and Sunday in PST
    # Find the current week's Wednesday at Noon PST
    # If today is Wednesday or later in the week
    if current_weekday_pst >= 2: # Wednesday (2), Thursday (3), Friday (4), Saturday (5), Sunday (6)
        days_since_wednesday = (current_weekday_pst - 2)
        wednesday_noon_this_week = (current_datetime_pst - timedelta(days=days_since_wednesday)).replace(
            hour=12, minute=0, second=0, microsecond=0, tzinfo=pst
        )
    else: # Monday (0), Tuesday (1) - Wednesday is in the future of this week
        days_until_wednesday = (2 - current_weekday_pst)
        wednesday_noon_this_week = (current_datetime_pst + timedelta(days=days_until_wednesday)).replace(
            hour=12, minute=0, second=0, microsecond=0, tzinfo=pst
        )
    
    # Find the current week's Sunday at 10 PM PST
    # If today is Sunday or earlier in the week
    if current_weekday_pst <= 6: # Monday (0) to Sunday (6)
        days_until_sunday = (6 - current_weekday_pst)
        sunday_10pm_this_week = (current_datetime_pst + timedelta(days=days_until_sunday)).replace(
            hour=22, minute=0, second=0, microsecond=0, tzinfo=pst
        )
    else: # Should not happen with weekday 0-6, but for completeness or if logic shifts
        sunday_10pm_this_week = current_datetime_pst.replace(
            hour=22, minute=0, second=0, microsecond=0, tzinfo=pst
        )


    # Check if current_datetime_pst is between Wednesday Noon and Sunday 10 PM PST
    # "between Wednesday Noon and Sunday 22:00" (inclusive of Wednesday Noon, exclusive of Sunday 10 PM)
    if wednesday_noon_this_week <= current_datetime_pst < sunday_10pm_this_week:
        is_new_tender_period = True
        # grab this week's tender for this sunday
        found_issue = upcoming_issues[0]['original_issue']

    return found_issue, is_new_tender_period

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


    current_datetime_utc_aware = datetime.now(pytz.utc) 
    found_issue, is_new_tender_period = find_correct_issue_date(latest_issue, current_datetime_utc_aware)

    return {
       "issues": latest_issue,
       "found_issue": found_issue,
       "is_new_tender_period": is_new_tender_period
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
    
def detect_and_split_addresses(address_string):
    """
    Detects and splits multiple addresses concatenated in a single string.

    This function assumes addresses are joined without delimiters and
    each new address starts with digits immediately following a letter
    from the previous address's street name/type.

    Args:
        address_string (str): A string containing one or more concatenated addresses.
                              Example: "2612 Richmond Rd2616 Richmond Rd2620 Richmond Rd"

    Returns:
        list: A list of individual address strings. Returns an empty list
              if the input string is empty.
    """
    if not address_string:
        return []

    # The regular expression to split by:
    # (?<=[a-zA-Z])   - Positive lookbehind: asserts that the position is preceded by any letter (a-z, A-Z)
    # (?=\d)          - Positive lookahead: asserts that the position is followed by any digit (0-9)
    # This combination means: split exactly at the point where a letter ends and a digit begins.
    try:
        split_addresses = re.split(r'(?<=[a-zA-Z])(?=\d)', address_string)

        # Basic cleanup: remove any empty strings that might result from splitting
        # or leading/trailing whitespace if the original string had it.
        cleaned_addresses = [addr.strip() for addr in split_addresses if addr.strip()]

        return cleaned_addresses
    except Exception as e:
        print(f"Error splitting addresses: {e}")
        return []

def get_project_type_id(project_data_entry):
    """
    Determines the project type ID for a given project entry using a generative AI model.

    Args:
        project_data_entry (dict): A dictionary containing the project's data.
        project_types_csv_data (str): A string containing project types in CSV format.
        client_model (object): An initialized generative AI client model (e.g., from google.generativeai).
                               If None, a default 'gemini-2.0-flash' model will be used.

    Returns:
        int: The determined project type ID, or 0 if none could be found.
    """

    GEMINI_API_KEY = os.getenv("GOOGLE_API_KEY")
    client = genai.Client(api_key=GEMINI_API_KEY)
    prompt = f"""
        Given the following new project data, we want to determine the project type:

        Use the following csv data and return the best matching id 

        {project_types_csv}

        Below is the project data:

        {json.dumps(project_data_entry, indent=2)}

        Please respond in the following format:

        ```json
        {{
            "project_type_id": <project_type_id>
        }}
        ```
    """

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents = [
                prompt
            ]
        )

        project_type_id = 0 # Default value if nothing is found
        project_data = parse_json_string(response.text)
        
        if project_data and 'project_type_id' in project_data:
            # If JSON is valid and contains 'project_type_id', use its value
            project_type_id: int = project_data['project_type_id']
            print(f"Using project_type_id from JSON: {project_type_id}")
        else:
            # If JSON parsing failed or 'project_type_id' key is missing,
            # fallback to regex to find the first number in the raw response text.
            # Using \d+ to match any number of digits, not just two.
            match = re.search(r'\b(\d+)\b', response.text) 
            if match:
                # If a number is found, convert it to an integer
                project_type_id = int(match.group(1))
                print(f"Using project_type_id from regex: {project_type_id}")
            else:
                # If no number is found via regex, keep default 0
                print("No project_type_id found in JSON or via regex. Defaulting to 0.")
        
        return project_type_id

    except Exception as e:
        print(f"An error occurred during content generation: {e}")
        return 0 # Return 0 or handle error as appropriate


def map_data(params):

    data = params.get('data', [])
    if len(data) == 0:
        print("No data to map")
        return
    region_name = params.get('region_name', 'Saanich')
    agent_id = os.getenv('YS_AGENTID', 'AutoHarvest')
    file_prefix = params.get('file_prefix', 'np')
    ys_component_id = os.getenv('YS_COMPONENTID', 7)
    print("ys_component_id: " + str(ys_component_id))
    hide_tiny_url_str = params.get('hide_tiny_url', False)
    # Check if the retrieved value is a string and then convert it
    if isinstance(hide_tiny_url_str, str):
        if hide_tiny_url_str.lower() == 'true':
            hide_tiny_url = True
        elif hide_tiny_url_str.lower() == 'false':
            hide_tiny_url = False
        # You might want to add an else here for unexpected string values
        # For now, if it's a string but not 'true' or 'false', it will remain False
    else:
        # If it's not a string (e.g., already a boolean False from the default),
        # just assign its value directly.
        # This covers the case where params.get already returned a boolean False.
        hide_tiny_url = bool(hide_tiny_url_str)


    api_url = os.getenv('YS_APIURL', 'http://localhost')

    default_city_name = "Saanich"
    file_type = agent_id
    file_name = "AutoHarvest"

    issue_results = get_latest_issue()
    found_issue = issue_results['found_issue']
    latest_issue = issue_results['issues']
    is_new_tender = issue_results['is_new_tender_period']

    print("Using found issue", found_issue)
    ys_volume_id = found_issue['id']

    mapped_data = []
    entries_with_project_types = []
    # classified entries
    print(len(data))
    print("Mapping Google Project Data?")
    for unclassified_entry in data:
        # copy unclassified_entry and remove details_link
        entry_copy = unclassified_entry.copy()
        # entry_copy['details_link'] = None
        try:
            entry_copy['ys_project_type'] = get_project_type_id(entry_copy)
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
    with open(f"data/{file_prefix}_with_project_type_{filename}.json", "w") as f:
        json.dump(entries_with_project_types, f)

    fill_entries_url = f"{api_url}/api_fill_entries.php"
    for unmapped_entry in entries_with_project_types:
        entry = {}
        ys_body = {}
        entry['issue_id'] = ys_volume_id
        entry['city_name'] = unmapped_entry.get('city_name', default_city_name)
        addresses = detect_and_split_addresses(unmapped_entry['address'])
        if len(addresses) <= 1:
            entry['ys_address'] = unmapped_entry['address']
        else:
            entry['ys_address'] = addresses[-1]
            # and we have to set the body the location details
            ys_body['ys_location_detail'] = ", ".join(addresses)

        if entry['ys_address'] is None or entry['ys_address'] == "":
            # TODO scan the rest of the addresses
            entry['ys_address'] = "Various Locations"
        # take first 255 characters
        current_ys_component_id = int(ys_component_id)
        if current_ys_component_id == DataTypes.TENDERS.value:
            entry['ys_description'] = unmapped_entry['project'][:95]
            # remove bad characters like ' and replace with sql safe characters
            entry['ys_description'] = entry['ys_description'].replace("'", "''")
            entry['ys_description'] = entry['ys_description'].replace(" - ", " &ndash; ", 1) # Replace only the first instance of " - "

        elif current_ys_component_id == DataTypes.NEW_PROJECT.value:
            entry['ys_description'] = unmapped_entry['purpose'][:95]
            # remove bad characters like ' and replace with sql safe characters
            entry['ys_description'] = entry['ys_description'].replace("'", "''")
        # strip everything past #, assume that means unit number
        # if '#' in entry['ys_description']:
        #     entry['ys_description'] = entry['ys_description'].split('#')[0]
       #  entry['ys_description'] = unmapped_entry['address'].split('#')[0]
        entry['ys_component'] = current_ys_component_id
        # all status is ACTIVE We can ignore, we only want to process active anyway
        entry['ys_type'] = unmapped_entry.get('ys_project_type', 0)
        entry['project_type'] = unmapped_entry.get('ys_project_type', 0)
        entry['region'] = unmapped_entry.get('city_name', default_city_name)

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
        # TODO add LA - June 23/25
        fmt_date = date.today().strftime("%B %d/%y")
        ys_body['ys_internal_note'] = f"LA - {fmt_date} AUTOBOT"

        if unmapped_entry.get('type'):
            # we use the "Type" field from here to populate "ys_stage"
            ys_body['ys_stage'] = unmapped_entry['type']

        if current_ys_component_id == DataTypes.TENDERS.value:
            entry['ys_date'] = unmapped_entry['open_date']
            parsed_date_close = dateparser.parse(unmapped_entry['close_date'])
            if parsed_date_close:
                try:
                    ys_body['ys_closing'] = parsed_date_close.strftime("%#m/%#d/%Y - %-I %p")
                except Exception as e:
                    print(e)
                    ys_body['ys_closing'] = parsed_date_close.strftime("%#m/%#d/%Y - %I %p")
            else:
                ys_body['ys_closing'] = unmapped_entry['close_date']
            ys_body['ys_project'] = unmapped_entry['project_description'] or unmapped_entry['project']
            ys_body['ys_project'] = ys_body['ys_project'].replace(" - ", " &ndash; ", 1) # Replace only the first instance of " - "

            entry['ys_permit'] = unmapped_entry['ref']
            ys_body['ys_documents_drawings_link'] = unmapped_entry['link']
            ys_body['ys_sector'] = 'Public'

            if unmapped_entry.get('ref'):
                ys_body['ys_reference'] = unmapped_entry['ref']
            if params.get('tender_authority'):
                ys_body['ys_tender_authority'] = params['tender_authority']

            # grab Contact Information
            if unmapped_entry.get('contact_information'):
                ys_body['ys_enquiries'] = unmapped_entry.get('contact_information', '')
            # we want to set stage based on a mapping here
            if unmapped_entry.get('type'):
                # we use the "Type" field from here to populate "ys_stage"
                if unmapped_entry['type'] == 'ITT':
                    ys_body['ys_stage'] = 'Tender Call'
                elif unmapped_entry['type'] == 'RFP':
                    ys_body['ys_stage'] = 'Request for proposals'
                elif unmapped_entry['type'] == 'RFQ':
                    ys_body['ys_stage'] = 'Request for Quotations'
                elif unmapped_entry['type'] == 'NRFP':
                    ys_body['ys_stage'] = 'Request for Proposals'
                elif unmapped_entry['type'] == 'RFT':
                    ys_body['ys_stage'] = 'Tender Call'
                elif unmapped_entry['type'] == 'NOI':
                    ys_body['ys_stage'] = 'NOI - Notice of Intent'

            # determine if we should update the item to updated_tenders
            found_issue_date_obj = datetime.strptime(found_issue['date'], '%Y-%m-%d').date()
            if parsed_date_close:
                if parsed_date_close.date() > found_issue_date_obj:
                
                    # make sure that its within the target 
                    if not is_new_tender:
                        # think this is handled by the cron job on ys website
                        print(f"Tender closing date ({parsed_date_close.date()}) is after issue date ({found_issue_date_obj}). Classifying as Updated Tender.")
                        # current_ys_component_id = DataTypes.UPDATED_TENDERS.value # Change component_id to 11 for Updated Tenders
                    else:
                        print("this is in the new tender period")
                else:
                    print(f"Tender closing date ({parsed_date_close.date()}) is on or before issue date ({found_issue_date_obj}). Classifying as New Tender.")
            

            try:
                if parsed_date_close:
                    review_date_obj = parsed_date_close.date() + relativedelta(months=+1)
                else:
                    review_date_obj = date.today() + relativedelta(months=+1)
            except Exception as e:
                # Fallback for non-Windows systems
                review_date_obj = date.today() + relativedelta(months=+1)
            formatted_review_date = review_date_obj.strftime("%Y-%m-%d")
            entry['review_date'] = formatted_review_date # Add to ys_body
            entry['project_step_id'] = 1001

        elif int(ys_component_id) == DataTypes.NEW_PROJECT.value:
            # ys project is set to purpose
            ys_body['ys_project'] = unmapped_entry['purpose']
            entry['ys_date'] = unmapped_entry['application_date']
            entry['ys_permit'] = unmapped_entry['folder_no']
            ys_body['ys_documents_drawings_link'] = unmapped_entry['details_link']
            ys_body['ys_sector'] = 'Private'
            entry['project_step_id'] = 1001
        else:
            raise Exception(f"Unknown ys_component_id: {ys_component_id}")
        

        ys_body['ys_no_tiny_urls'] = hide_tiny_url

        entry['ys_body'] = ys_body
        entry['isBuildingPermit'] = False
        entry['user_id'] = '2025060339'
        entry['ys_project_details'] = ''
        mapped_data.append(entry)

    if len(mapped_data) == 0:
        print("no mapped data returning")
        return

    curr_date = datetime.now().strftime("%Y-%m-%d %H_%M_%S")

    first_city = mapped_data[0].get('city_name', default_city_name)
    with open(f"data/{file_prefix}_with_mapping_{file_name}_{curr_date}_{region_name}.json", "w") as f:
        json.dump(mapped_data, f)
    filled_entries_data = [{
        'filename': f'{file_prefix}_{file_name}_{curr_date}_{region_name}.json',
        "pdf_type": "api",
        "region": first_city,
        "file_type": "json",
        "data": mapped_data,
        'user_id': '2025060339'
    }]

    with open(f"data/{file_prefix}_with_mapping_all{file_name}_{curr_date}_{region_name}.json", "w") as f:
        json.dump(filled_entries_data, f)

    filled_entries_resp = requests.post(fill_entries_url, json=filled_entries_data)
    # print response text to index.html
    # send api request to api_insert_into_data.php

    filled_entries = filled_entries_resp.json()

    with open(f"data/{file_prefix}_with_fill_{filename}_{region_name}.json", "w") as f:
        json.dump(filled_entries, f)

    insert_into_data_url = f"{api_url}/api_insert_into_data.php"
    insert_into_data_resp = requests.post(insert_into_data_url, json=filled_entries)
    try:
        # check for 500 then if so raise errro
        insert_into_data_resp.raise_for_status()
        insert_response = insert_into_data_resp.json()

        print(insert_response)
        # we could add in logic to 
        if good_json_string['failed_entries'] > 0:
            # send to discord webhook
            from validate_tenders import send_discord_message
            discord_webhook_url = os.getenv('DISCORD_WEBHOOK_URL')
            send_discord_message(f"Error inserting into data: {good_json_string}", discord_webhook_url)
        elif good_json_string['inserted_entries'] > 0:
            # send to discord webhook
            from validate_tenders import send_discord_message
            discord_webhook_url = os.getenv('DISCORD_WEBHOOK_URL')
            send_discord_message(f"Successfully inserted into data: {good_json_string}", discord_webhook_url)
        else:
            print("nothing wrong with the json string")
    except requests.HTTPError as http_err:
        print(f'HTTP error occurred: {http_err}')
    except:
        # see if we can parse json from the response, ignore text that is not json
        print(insert_into_data_resp.text)
        with open("insert_into_data_resp.txt", "w", errors='ignore') as f:
            f.write(insert_into_data_resp.text)

        try:
            import json_repair
            good_json_string = json_repair.loads(insert_into_data_resp.text)
            # make sure that inserted_entries and failed_entries is 
            print("good json string", good_json_string)

            # check failed_entries is not > 0 and 
            # inserted_entries > 0 else send message to discord

            if good_json_string['failed_entries'] > 0:
                # send to discord webhook
                from validate_tenders import send_discord_message
                discord_webhook_url = os.getenv('DISCORD_WEBHOOK_URL')
                send_discord_message(f"Error inserting into data: {good_json_string}", discord_webhook_url)
            elif good_json_string['inserted_entries'] > 0:
                # send to discord webhook
                from validate_tenders import send_discord_message
                discord_webhook_url = os.getenv('DISCORD_WEBHOOK_URL')
                send_discord_message(f"Successfully inserted into data: {good_json_string}", discord_webhook_url)
            else:
                print("nothing wrong with the json string")
        except Exception as e:
            print(f"Error repairing json: {e}")
            good_json_string = insert_into_data_resp.text



    return

if __name__ == "__main__":

    issue_results = get_latest_issue()

    print(issue_results.get('found_issue'))

    sample_data =  [
        # {'address': '', 'folder_no': 'BVD00560', 'type': 'BOULEVARD PERMIT', 'application_date': 'May 29, 2025', 'status': 'ACTIVE', 'purpose': 'ALTERING THE BOULEVARD', 'details_link': 'https://online.saanich.ca/Tempest/OurCity/Prospero/Details.aspx?folderNumber=BVD00560'}, 
        # {'address': '200-3561       SHELBOURNE ST', 'folder_no': 'BLC07059', 'type': 'COMMERCIAL PERMIT', 'application_date': 'Jun 02, 2025', 'status': 'ACTIVE', 'purpose': 'TENANT IMPROVEMENT FOR BURKETT & CO - UNIT 200', 'details_link': 'https://online.saanich.ca/Tempest/OurCity/Prospero/Details.aspx?folderNumber=BLC07059'},
        # {'address': '4444       WEST SAANICH RD', 'folder_no': 'BLC07058', 'type': 'COMMERCIAL PERMIT', 'application_date': 'May 29, 2025', 'status': 'ACTIVE', 'purpose': 'REPLACE FIRE ALARM PANEL - ROYAL OAK SHOPPING CENTRE', 'details_link': 'https://online.saanich.ca/Tempest/OurCity/Prospero/Details.aspx?folderNumber=BLC07058'},
         {
            "address": "2612 Richmond Rd2616 Richmond Rd2620 Richmond Rd2628 Richmond Rd",
            "folder_no": "Rez00900",
            "type": "Rezoning Application",
            "application_date": "Jun 20, 2025",
            "status": "Active",
            "purpose": "The City Is Considering a Rezoning Application for a 101 Unit Purpose Built Rental Building. Concurrent W/dp000653",
            "details_link": "https://tender.victoria.ca/webapps/ourcity/prospero/Details.aspx?folderNumber=REZ00900",
            "city_name": "victoria",
            "application_contact": "N/a"
        },
    ]
    map_data({
        "data": sample_data,
        "region_name": "testing"
    })
