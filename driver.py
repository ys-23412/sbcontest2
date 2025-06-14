from web_requests import get_filtered_permits_with_contacts, NewProjectSiteTypes, get_site_params
from process_project_data import map_data, get_latest_issue, find_correct_issue_date
import time
import requests
import dateparser
import os 
import json
def main():
    api_url = os.getenv('YS_APIURL', 'http://localhost')


    for site_type in NewProjectSiteTypes:
        # Convert enum name (e.g., SAANICH) to a more readable format (e.g., Saanich)
        region_name = site_type.value.replace("_", " ").title()
        file_name_prefix = site_type.value.replace(" ", "_") # For file names like "saanich_filtered.json"

        params = get_site_params(site_type)

        print(f"DOING {region_name.upper()}")
        filtered_entries = get_filtered_permits_with_contacts(params)

        output_filename = f"data/{file_name_prefix}_filtered.json"
        with open(output_filename, "w") as f:
            json.dump(filtered_entries, f, indent=4)
        
        print(f"UPLOAD {region_name.upper()} ENTRIES {filtered_entries}")
        map_data({
            "data": filtered_entries,
            "region_name": region_name
        })
        print("-" * 30) # Separator for better readability between iterations
    # params_saanich = get_site_params(NewProjectSiteTypes.SAANICH)
    # if not os.path.exists("data"):
    #     os.makedirs("data")


    # print("DOING SAANICH")
    # filtered_entries = get_filtered_permits_with_contacts(params_saanich)


    # with open("data/saanich_filtered.json", "w") as f:
    #     json.dump(filtered_entries, f)
    # print("UPLOAD SAANICH ENTRIES", filtered_entries)
    # map_data({
    #     "data": filtered_entries,
    #     "region_name": "Saanich"
    # })
    # params_victoria = get_site_params(NewProjectSiteTypes.VICTORIA)


    # filtered_victoria_entries = get_filtered_permits_with_contacts(params_victoria)

    # with open("data/victoria_filtered.json", "w") as f:
    #     json.dump(filtered_victoria_entries, f)
    # print("UPLOAD VICTORIA ENTRIES", filtered_victoria_entries)
    # map_data({
    #     "data": filtered_victoria_entries,
    #     "region_name": "Victoria"
    # })

    # params_central = get_site_params(NewProjectSiteTypes.CENTRAL_SAANICH)

    # centralsaanich_entries = get_filtered_permits_with_contacts(params_central)

    # with open("data/centralsaanich_filtered.json", "w") as f:
    #     json.dump(centralsaanich_entries, f)
    # print("UPLOAD CENTRAL SAANICH ENTRIES", centralsaanich_entries)
    # map_data({
    #     "data": centralsaanich_entries,
    #     "region_name": "Central Saanich"
    # })

if __name__ == "__main__":
    main()