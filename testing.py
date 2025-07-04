import os
import json
from google import genai
from process_project_data import map_data
import dateparser
def main():
    agent_id = os.getenv('YS_AGENTID', 'AutoHarvest')
    ys_component_id = os.getenv('YS_COMPONENTID', 7)

    GEMINI_API_KEY = os.getenv("GOOGLE_API_KEY")
    client = genai.Client(api_key=GEMINI_API_KEY)
    api_url = os.getenv('YS_APIURL', 'http://localhost')
    saanich_entries = json.load(open("data/saanich_filtered.json"))
    map_data(saanich_entries)

if __name__ == '__main__':
    test_date = dateparser.parse('Aug 1st 2025, 4:00 PM PDT')
    print(test_date)
    # main()