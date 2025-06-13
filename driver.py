from web_requests import get_filtered_permits_with_contacts, permit_development_tracker
from process_project_data import map_data, get_latest_issue, find_correct_issue_date
import time
import requests
import dateparser
import os 
import json
def main():
    api_url = os.getenv('YS_APIURL', 'http://localhost')

    params = {
        "siteType": "saanich"
    }
    if not os.path.exists("data"):
        os.makedirs("data")


    print("DOING SAANICH")
    filtered_entries = get_filtered_permits_with_contacts(params)


    with open("data/saanich_filtered.json", "w") as f:
        json.dump(filtered_entries, f)
    print("UPLOAD SAANICH ENTRIES", filtered_entries)
    map_data({
        "data": filtered_entries,
        "region_name": "Saanich"
    })
    params_victoria = {
        "base_url": "https://tender.victoria.ca",
        "starting_url": "webapps/ourcity/Prospero/Search.aspx",
        "siteType": "victoria"
    }
    print("GRAB VICTORIA ENTRIES")

    filtered_victoria_entries = get_filtered_permits_with_contacts(params_victoria)

    with open("data/victoria_filtered.json", "w") as f:
        json.dump(filtered_victoria_entries, f)
    print("UPLOAD VICTORIA ENTRIES", filtered_victoria_entries)
    map_data({
        "data": filtered_victoria_entries,
        "region_name": "Victoria"
    })


    params_central = {
        "base_url": "https://www.mycentralsaanich.ca",
        "starting_url": "TempestLive/OURCITY/Prospero/Search.aspx",
        "siteType": "central saanich"
    }

    centralsaanich_entries = get_filtered_permits_with_contacts(params_central)

    with open("data/centralsaanich_filtered.json", "w") as f:
        json.dump(centralsaanich_entries, f)
    print("UPLOAD CENTRAL SAANICH ENTRIES", centralsaanich_entries)
    map_data({
        "data": centralsaanich_entries,
        "region_name": "Central Saanich"
    })
if __name__ == "__main__":
    main()