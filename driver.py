from web_requests import permit_development_tracker, filter_saanich_permits
from process_project_data import map_data
import time
import os 

def main():
    params = {

    }
    if not os.path.exists("data"):
        os.makedirs("data")

    params_victoria = {
        "base_url": "https://tender.victoria.ca",
        "starting_url": "webapps/ourcity/Prospero/Search.aspx",
        "siteType": "victoria"
    }
    print("DOING SAANICH")
    entries = permit_development_tracker(params)

    print(entries)
    import json
    with open("data/saanich.json", "w") as f:
        json.dump(entries, f)
    # print("entries", entries)
    filtered_entries = filter_saanich_permits(entries)


    with open("data/saanich_filtered.json", "w") as f:
        json.dump(filtered_entries, f)
    print("UPLOAD SAANICH ENTRIES", filtered_entries)
    map_data(filtered_entries)

    print("GRAB VICTORIA ENTRIES")
    time.sleep(60)
    # wait 1 minute and do the same for victoria
    # check if data folder exists
    victoria_entries = permit_development_tracker(params_victoria)
    with open("data/victoria.json", "w") as f:
        json.dump(victoria_entries, f)

    filtered_victoria_entries = filter_saanich_permits(victoria_entries)

    with open("data/victoria_filtered.json", "w") as f:
        json.dump(filtered_victoria_entries, f)
    print("UPLOAD VICTORIA ENTRIES", filtered_victoria_entries)
    map_data(filtered_victoria_entries)
if __name__ == "__main__":
    main()