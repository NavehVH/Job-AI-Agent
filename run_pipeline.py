import json
import time 
import threading
import queue
import requests
import os
import sys, io
import re  # NEW: Required for word boundary matching
from src.fetchers import Fetcher
from src.storage import JobStorage

# Force standard output to use UTF-8 regardless of the terminal environment
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# --- AUTHORIZATION LOGIC ---
def get_openai_key():
    """Reads the OpenAI API key from the central authorization file."""
    try:
        if not os.path.exists("authorization.txt"):
            print("[!] Error: authorization.txt not found.")
            return None
        with open("authorization.txt", "r") as f:
            for line in f:
                if line.startswith("OPENAI_API_KEY="):
                    return line.split("=")[1].strip()
    except Exception as e:
        print(f"[!] Error reading authorization.txt: {e}")
    return None

# --- UPDATED: ROBUST FILTERING LOGIC ---
def should_keep_job(title):
    """Checks if the job title contains any blacklisted words using regex word boundaries."""
    if not os.path.exists("filters.txt"):
        return True
    
    try:
        with open("filters.txt", "r", encoding='utf-8') as f:
            # Clean lines: skip comments (#) and empty lines
            excluded_keywords = []
            for line in f:
                clean_line = line.strip().lower()
                if clean_line and not clean_line.startswith("#"):
                    # Remove inline comments like '# Common for Tier 3'
                    keyword = clean_line.split("#")[0].strip()
                    if keyword:
                        excluded_keywords.append(keyword)
        
        title_lower = title.lower()
        
        for keyword in excluded_keywords:
            # Use \b (word boundary) to ensure 'sr' matches 'Sr Backend' 
            # but doesn't match 'Israel' or 'asr'
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
        
        # Apply the new Regex Filter
        if not should_keep_job(job['title']):
            # Optional: Print filtered jobs to verify it's working
            # print(f"    [-] Filtered: {job['title'][:40]}", flush=True)
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
    openai_api_key = get_openai_key()
    if not openai_api_key:
        print("[!] Critical Error: OPENAI_API_KEY missing from authorization.txt.")
    else:
        print("[*] Authorization loaded successfully.")

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
    print("\n PIPELINE COMPLETE.")

if __name__ == "__main__":
    main()