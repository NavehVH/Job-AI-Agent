import json
import time 
import threading
import queue
import requests
import os
import sys, io
import re
from src.fetchers import Fetcher
from src.storage import JobStorage

# Force standard output to use UTF-8
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# --- UPDATED: LISTEN TO FILTER TOGGLE ---
def should_keep_job(title):
    """Checks if filtering is enabled and applies regex blacklist."""
    # Logic: Check the environment variable set by engine.py
    enable_filters = os.environ.get("ENABLE_FILTERS") == "True"
    
    if not enable_filters:
        return True # Trigger is OFF: let everything through
        
    if not os.path.exists("filters.txt"):
        return True
    
    try:
        with open("filters.txt", "r", encoding='utf-8') as f:
            excluded_keywords = []
            for line in f:
                clean_line = line.strip().lower()
                if clean_line and not clean_line.startswith("#"):
                    keyword = clean_line.split("#")[0].strip()
                    if keyword:
                        excluded_keywords.append(keyword)
        
        title_lower = title.lower()
        for keyword in excluded_keywords:
            pattern = r'\b' + re.escape(keyword) + r'\b'
            if re.search(pattern, title_lower):
                return False
        return True
    except Exception as e:
        print(f"    [!] Error reading filters.txt: {e}")
        return True

job_queue = queue.Queue()

def database_worker():
    storage = JobStorage()
    session = requests.Session() 
    print("[DATABASE] Consumer active.", flush=True)

    while True:
        item = job_queue.get()
        if item is None: break
        job, source = item
        
        # Respect the toggle logic defined above
        if not should_keep_job(job['title']):
            job_queue.task_done()
            continue

        if not storage.job_exists(job['id']):
            try:
                headers = {"Accept": "application/json", "X-Workday-Subdomain": job.get('tenant_id', '')}
                desc_url = job.get('description_url')
                if desc_url:
                    resp = session.get(desc_url, headers=headers, timeout=10)
                    if resp.status_code == 200:
                        job['description'] = resp.json().get('jobPostingInfo', {}).get('jobDescription', '')
                
                storage.save_job(job)
                print(f"    [SAVED] {job['title'][:40]:<40} | {source} ", flush=True)
            except Exception as e:
                print(f"    [!] Error saving {job['title'].encode('ascii', 'ignore').decode()}: {e}")
        
        job_queue.task_done()

# ... (fast_scraper_worker and round_robin_scraper remain the same) ...
def fast_scraper_worker(targets, fetcher):
    for target in targets:
        try:
            print(f"[*] Fetching jobs for {target['name']}...", flush=True)
            jobs = fetcher.fetch(target) 
            if jobs:
                for job in jobs:
                    job_queue.put((job, target['name']))
        except Exception as e:
            print(f"    [!] Fast Scraper Error for {target['name']}: {e}")

def round_robin_scraper(targets, fetcher):
    if not targets: return
    offset, limit = 0, 20
    active_targets = list(targets)
    target_totals = {t['name']: 0 for t in targets}
    last_seen_ids = {t['name']: [] for t in targets}

    while active_targets and offset < 2000:
        print(f"\n[WORKDAY WAVE] Offset {offset} | Active Sites: {len(active_targets)}", flush=True)
        finished_this_wave = []
        for target in active_targets:
            found_jobs, has_more, total_count = fetcher.workday.fetch_single_batch(target, offset)
            if offset == 0: target_totals[target['name']] = total_count
            current_ids = [j['id'] for j in found_jobs]
            if current_ids and current_ids == last_seen_ids.get(target['name']):
                finished_this_wave.append(target)
                continue
            last_seen_ids[target['name']] = current_ids
            if found_jobs:
                print(f"    [+] {target['name']}: Found {len(found_jobs)} jobs.", flush=True)
                for job in found_jobs:
                    job_queue.put((job, target['name']))
            if (offset + limit) >= target_totals[target['name']]:
                finished_this_wave.append(target)
            time.sleep(0.5) 
        for t in finished_this_wave:
            if t in active_targets: active_targets.remove(t)
        offset += limit

def main():
    # Only show warning, don't stop execution.
    # AppEngine now handles the key validation before triggering the Brain.
    if not os.path.exists("authorization.txt"):
        print("[!] Warning: authorization.txt missing.")

    print("[*] Scraper started. Checking filters...", flush=True)
    
    with open('config/targets.json', 'r') as f:
        targets = json.load(f)

    fetcher = Fetcher()
    workday_targets = [t for t in targets if t.get('type') == 'workday']
    fast_targets = [t for t in targets if t.get('type') not in ['workday', 'jobspy']]

    consumer = threading.Thread(target=database_worker, daemon=True)
    consumer.start()

    threads = [
        threading.Thread(target=round_robin_scraper, args=(workday_targets, fetcher)),
        threading.Thread(target=fast_scraper_worker, args=(fast_targets, fetcher))
    ]

    for t in threads: t.start()
    for t in threads: t.join()

    job_queue.join()
    job_queue.put(None)
    consumer.join()

if __name__ == "__main__":
    main()