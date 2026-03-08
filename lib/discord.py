
import requests
import os
from datetime import datetime
from zoneinfo import ZoneInfo


def send_discord_message(message, webhook_url):
    """
    Sends a message to a Discord channel via webhook.
    """
    if not webhook_url:
        print("Discord webhook URL not configured. Skipping Discord notification.")
        return

    data = {"content": message}
    if not "username" in data:
        workflow_name = os.getenv("GH_WORKFLOW_NAME", None)
        if workflow_name:
            data[workflow_name] = workflow_name
    try:
        response = requests.post(webhook_url, json=data)
        response.raise_for_status() # Raise an exception for HTTP errors
        print("Discord message sent successfully.")
    except requests.exceptions.RequestException as e:
        print(f"Failed to send Discord message: {e}")
        
def send_discord_embed(webhook_url: str, title: str, description: str, fields: dict, color: int = 3447003):
    """
    Sends a rich embed message to a Discord channel via webhook.
    """
    if not webhook_url:
        print("Discord webhook URL not configured. Skipping Discord notification.")
        return

    # Convert the dictionary of stats into Discord's expected 'fields' array
    embed_fields = [
        {"name": str(key), "value": str(value), "inline": False} # Changed to False for better list readability
        for key, value in fields.items() if value # Only add field if it has content
    ]

    embed = {
        "title": title,
        "description": description,
        "color": color,
        "fields": embed_fields,
        "timestamp": datetime.now(ZoneInfo("UTC")).isoformat()
    }
    
    data = {"embeds": [embed]}
    
    try:
        response = requests.post(webhook_url, json=data)
        response.raise_for_status()
        print("Discord embed message sent successfully.")
    except requests.exceptions.RequestException as e:
        print(f"Failed to send Discord embed message: {e}")