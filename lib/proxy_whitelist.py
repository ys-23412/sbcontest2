import requests
import sys
import time
import os

# Configuration from Environment Variables
API_TOKEN = os.getenv("IPROYAL_API_TOKEN")
USER_HASH = os.getenv("IPROYAL_USER_HASH")
# Your specific proxy port assigned by IPRoyal
PROXY_PORT = os.getenv("IPROYAL_PROXY_PORT", "12321") 

BASE_URL = f"https://resi-api.iproyal.com/v1/residential-users/{USER_HASH}/whitelist-entries"
HEADERS = {
    "Authorization": f"Bearer {API_TOKEN}",
    "Content-Type": "application/json"
}

def get_current_ip():
    return requests.get("https://ifconfig.me").text.strip()

def add_to_whitelist(ip):
    print(f"Adding {ip} to IPRoyal whitelist...")
    data = {
        "ip": ip,
        "port": int(PROXY_PORT),
        "note": f"GitHub-Runner-{os.getenv('GITHUB_RUN_ID')}"
    }
    response = requests.post(BASE_URL, json=data, headers=HEADERS)
    if response.status_code in [200, 201]:
        print("Successfully whitelisted. Waiting 30s for propagation...")
        time.sleep(30) # Crucial wait time
    else:
        print(f"Failed to whitelist: {response.text}")
        sys.exit(1)

def remove_from_whitelist(ip):
    print(f"Cleaning up {ip} from whitelist...")
    # First, we must find the entry ID for this IP
    entries = requests.get(BASE_URL, headers=HEADERS).json()
    
    # Logic to find the specific entry by IP or Note
    entry_id = None
    for entry in entries.get('data', []):
        if entry['ip'] == ip:
            entry_id = entry['id']
            break
            
    if entry_id:
        del_url = f"{BASE_URL}/{entry_id}"
        resp = requests.delete(del_url, headers=HEADERS)
        print(f"Delete status: {resp.status_code}")
    else:
        print("No matching whitelist entry found to delete.")

if __name__ == "__main__":
    command = sys.argv[1]
    current_ip = get_current_ip()
    
    if command == "setup":
        add_to_whitelist(current_ip)
    elif command == "cleanup":
        remove_from_whitelist(current_ip)
