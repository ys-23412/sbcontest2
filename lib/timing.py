from typing import Dict, List, Tuple, Optional
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import dateparser
import requests
import os

def _fetch_last_successful_run_from_api(workflow_name="Scrap Sites Dev") -> Optional[datetime]:
    """
    Fetches the last successful GitHub Action run timestamp for sbcontest2.
    """
    repo = os.getenv("GITHUB_REPOSITORY", "ys-23412/sbcontest2")
    # Filter by 'status=completed' and 'status=success' to get only the wins
    # we have to filter for a least 10 to because we have prod and dev workflows.
    url = f"https://api.github.com/repos/{repo}/actions/runs?status=success&per_page=40"
    workflow_name = os.getenv("GH_WORKFLOW_NAME", workflow_name)
    token = os.getenv("GITHUB_TOKEN")
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    pacific_tz = ZoneInfo("America/Vancouver")
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
        utc_dt = datetime.fromisoformat(last_run_str.replace("Z", "+00:00"))
        # Convert ISO 8601 string to datetime object
        pst_dt = utc_dt.astimezone(pacific_tz)
        print(f"Last successful run (PST): {pst_dt}")
        # Note: .replace(tzinfo=None) if you need naive UTC, 
        # or keep as is for timezone awareness.
        return pst_dt

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
    print("[get_execution_window] - Using now_pst time", now_pst)
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

    # 3. Determine the 'start_time' based on which slot we snapped to
    # Default Logic: Start time is the *previous* slot relative to the end_time
    if closest_target.hour == 17: # If snapped to 5:00 PM
        # Window: 12:30 PM -> 5:00 PM
        start_time = closest_target.replace(hour=12, minute=30)
    elif closest_target.hour == 12: # If snapped to 12:30 PM
        # Window: 8:30 AM -> 12:30 PM
        start_time = closest_target.replace(hour=8, minute=30)
    else: # If snapped to 8:30 AM (or default fallback)
        # Window: Yesterday 5:00 PM -> Today 8:30 AM
        # We subtract 1 day and set to 17:00
        start_time = (closest_target - timedelta(days=1)).replace(hour=17, minute=0)

    end_time = now_pst
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
    print("Using start_time", start_time)
    print("Using end_time", end_time)
    return start_time, end_time

def filter_tenders_by_last_run(tender_records: List[Dict], date_field: str = 'Issue Date and Time (Pacific Time)') -> List[Dict]:
    """
    Filters BC Bid records based on the calculated execution window.
    Looks specifically at 'Issue Date and Time (Pacific Time)'.
    """
    pst_timezone = ZoneInfo("America/Vancouver")
    now_pst = datetime.now(pst_timezone)
    
    start_dt, end_dt = get_execution_window(now_pst)

    print(f"--- Run Configuration ({now_pst.strftime('%H:%M')}) for {date_field} ---")
    print(f"Target Window: {start_dt.strftime('%m-%d %H:%M')} TO {end_dt.strftime('%m-%d %H:%M')}")
    
    filtered_records = []

    for record in tender_records:
        date_str = record.get(date_field)
        if not date_str:
            continue

        try:
            parsed_datetime = dateparser.parse(
                date_str, 
                settings={'TIMEZONE': 'America/Vancouver', 'TO_TIMEZONE': 'America/Vancouver', 'RETURN_AS_TIMEZONE_AWARE': True}
            )
            
            if not parsed_datetime:
                continue
            
            if start_dt < parsed_datetime <= end_dt:
                filtered_records.append(record)
            elif (parsed_datetime.hour == 0 and parsed_datetime.minute == 0):
                is_morning_run = (end_dt.hour == 8)
                if parsed_datetime.date() == end_dt.date() and is_morning_run:
                     filtered_records.append(record)

        except Exception as e:
            print(f"Date parse error on record {record.get('Opportunity ID')}: {e}")

    print(f"BC Bid Filter complete. Kept {len(filtered_records)} records.")
    return filtered_records