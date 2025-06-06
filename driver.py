from web_requests import permit_development_tracker, filter_saanich_permits
from process_project_data import map_data, get_latest_issue, find_correct_issue_date
import time
import requests
import dateparser
import os 
import json
def main():
    api_url = os.getenv('YS_APIURL', 'http://localhost')
    latest_issue_url = f"{api_url}/api_get_latest_issue.php"
    # make request to api
    agent_id = os.getenv('YS_AGENTID', 'AutoHarvest')

    params = {
        "siteType": "saanich"
    }
    # if not os.path.exists("data"):
    #     os.makedirs("data")


    # print("DOING SAANICH")
    # entries = permit_development_tracker(params)

    # print(entries)

    # with open("data/saanich.json", "w") as f:
    #     json.dump(entries, f)
    # # print("entries", entries)
    # filtered_entries = filter_saanich_permits(entries)


    # with open("data/saanich_filtered.json", "w") as f:
    #     json.dump(filtered_entries, f)
    # print("UPLOAD SAANICH ENTRIES", filtered_entries)
    # map_data(filtered_entries)
    # params_victoria = {
    #     "base_url": "https://tender.victoria.ca",
    #     "starting_url": "webapps/ourcity/Prospero/Search.aspx",
    #     "siteType": "victoria"
    # }
    # print("GRAB VICTORIA ENTRIES")
    # # wait 1 minute and do the same for victoria
    # # check if data folder exists
    # victoria_entries = permit_development_tracker(params_victoria)
    # with open("data/victoria.json", "w") as f:
    #     json.dump(victoria_entries, f)

    # filtered_victoria_entries = filter_saanich_permits(victoria_entries, "Victoria")

    # with open("data/victoria_filtered.json", "w") as f:
    #     json.dump(filtered_victoria_entries, f)
    # print("UPLOAD VICTORIA ENTRIES", filtered_victoria_entries)
    # map_data(filtered_victoria_entries)


    params_central = {
        "base_url": "https://www.mycentralsaanich.ca",
        "starting_url": "TempestLive/OURCITY/Prospero/Search.aspx",
        "siteType": "central saanich"
    }
    centralsaanich_entries = permit_development_tracker(params_central)
    with open("data/centralsaanich.json", "w") as f:
        json.dump(centralsaanich_entries, f)

    centralsaanich_entries = filter_saanich_permits(centralsaanich_entries)

    with open("data/centralsaanich_filtered.json", "w") as f:
        json.dump(centralsaanich_entries, f)
    print("UPLOAD CENTRAL SAANICH ENTRIES", centralsaanich_entries)
    map_data(centralsaanich_entries)
if __name__ == "__main__":
    main()