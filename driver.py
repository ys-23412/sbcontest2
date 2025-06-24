from web_requests import get_filtered_permits_with_contacts, NewProjectSiteTypes, get_site_params
from process_project_data import map_data, get_latest_issue, find_correct_issue_date
import time
import requests
import dateparser
import os 
import json

def main():
    api_url = os.getenv('YS_APIURL', 'http://localhost')

    if not os.path.exists("data"):
        os.makedirs("data")

    all_regions = list(NewProjectSiteTypes)
    regions_to_process = list(NewProjectSiteTypes) # Start with all regions
    
    retry_attempts = 0
    max_retries = 3

    while regions_to_process and retry_attempts < max_retries:
        print(f"--- Starting pass {retry_attempts + 1}/{max_retries} ---")
        failed_regions_current_pass = []

        for site_type in regions_to_process:
            region_name = site_type.value.replace("_", " ").title()
            file_name_prefix = site_type.value.replace(" ", "_")

            params = get_site_params(site_type)

            print(f"DOING {region_name.upper()}")
            try:
                filtered_entries = get_filtered_permits_with_contacts(params)

                output_filename = f"data/{file_name_prefix}_filtered.json"
                with open(output_filename, "w") as f:
                    json.dump(filtered_entries, f, indent=4)
                
                print(f"UPLOAD {region_name.upper()} ENTRIES {len(filtered_entries)} items")
                map_data({
                    "data": filtered_entries,
                    "region_name": region_name,
                    'hide_tiny_url': os.getenv('HIDE_TINY_URL', False)
                })
            except Exception as e:
                print(f"ERROR processing {region_name.upper()}: {e}")
                failed_regions_current_pass.append(site_type)
            print("-" * 30) # Separator for better readability between iterations
        
        regions_to_process = failed_regions_current_pass
        if regions_to_process:
            print(f"Retrying failed regions: {[region.value for region in regions_to_process]}")
        retry_attempts += 1

    if regions_to_process:
        print(f"\n--- ATTENTION: The following regions failed after {max_retries} attempts: ---")
        for site_type in regions_to_process:
            print(f"- {site_type.value.replace('_', ' ').title()}")
    else:
        print("\n--- All regions processed successfully! ---")

if __name__ == "__main__":
    main()
