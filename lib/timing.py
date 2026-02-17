from typing import Tuple, Optional
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import requests
import os

def _fetch_last_successful_run_from_api(workflow_name="Scrap Sites Dev") -> Optional[datetime]:
    """
    Fetches the last successful GitHub Action run timestamp for sbcontest2.
    """
    repo = "ys-23412/sbcontest2"
    # Filter by 'status=completed' and 'status=success' to get only the wins
    url = f"https://api.github.com/repos/{repo}/actions/runs?status=success&per_page=1"
    workflow_name = os.getenv("GH_WORKFLOW_NAME", workflow_name)
    token = os.getenv("GITHUB_TOKEN")
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()
        
        runs = data.get("workflow_runs", [])
        # filter for first run with name
        if not runs:
            return None
        matching_run = next((run for run in runs if run.get("name") == workflow_name), None)
        
        if not matching_run:
            print(f"No successful runs found for workflow: {workflow_name}")
            return None
        # Extract the creation time of the most recent successful run
        last_run_str = matching_run.get("created_at") # e.g., "2026-02-17T01:24:19Z"
        
        # Convert ISO 8601 string to datetime object
        # Note: .replace(tzinfo=None) if you need naive UTC, 
        # or keep as is for timezone awareness.
        return datetime.fromisoformat(last_run_str.replace("Z", "+00:00"))

    except (requests.RequestException, ValueError, IndexError) as e:
        print(f"Error fetching run data: {e}")
        return None

def get_execution_window(now_pst: datetime) -> Tuple[datetime, datetime]:
    """
    Calculates the 'start' and 'end' time for the current run by 'snapping'
    the current time to the nearest scheduled slot (8:30, 12:30, 17:00).
    
    This handles early/late cron executions (e.g., 4:00 PM counts as the 5:00 PM run)
    and DST offsets naturally.
    """
    # 1. Define today's target slots
    # We use .replace() to keep the date but set the specific target times
    today_targets = [
        now_pst.replace(hour=8, minute=30, second=0, microsecond=0),  # Morning
        now_pst.replace(hour=12, minute=30, second=0, microsecond=0), # Noon
        now_pst.replace(hour=17, minute=0, second=0, microsecond=0)   # Evening
    ]

    # 2. 'Snap-to-Grid': Find the target slot closest to 'now_pst'
    # This handles the "3:50 PM or 4:00 PM rounds to 5:00 PM" requirement.
    # It calculates the absolute time difference between NOW and each Target.
    closest_target = min(today_targets, key=lambda t: abs((now_pst - t).total_seconds()))

    end_time = closest_target

    # 3. Determine the 'start_time' based on which slot we snapped to
    # Default Logic: Start time is the *previous* slot relative to the end_time
    if end_time.hour == 17: # If snapped to 5:00 PM
        # Window: 12:30 PM -> 5:00 PM
        start_time = end_time.replace(hour=12, minute=30)
    elif end_time.hour == 12: # If snapped to 12:30 PM
        # Window: 8:30 AM -> 12:30 PM
        start_time = end_time.replace(hour=8, minute=30)
    else: # If snapped to 8:30 AM (or default fallback)
        # Window: Yesterday 5:00 PM -> Today 8:30 AM
        # We subtract 1 day and set to 17:00
        start_time = (end_time - timedelta(days=1)).replace(hour=17, minute=0)

    # 4. API Override (Crucial for Data Integrity)
    # If the previous run failed or the cron was skipped, the default 'start_time' above 
    # might leave a gap. We fetch the ACTUAL last run time to ensure we pick up exactly where we left off.
    last_run_actual = _fetch_last_successful_run_from_api()
    
    if last_run_actual:
        # Ensure the API timestamp is timezone-aware (PST) before using
        if last_run_actual.tzinfo is None:
             last_run_actual = last_run_actual.replace(tzinfo=ZoneInfo("America/Vancouver"))
        
        print(f"API Update: Overriding calculated start time ({start_time}) with last successful run ({last_run_actual})")
        start_time = last_run_actual

    return start_time, end_time