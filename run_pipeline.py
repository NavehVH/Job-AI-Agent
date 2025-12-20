import json
import time 
import threading
import queue
import requests
import argparse
import random
from src.fetchers import Fetcher
from src.storage import JobStorage

job_queue = queue.Queue()

# --- THE GATEKEEPER: SENIOR FILTER (COMMENTED PER REQUEST) ---
def pre_filter_senior(job):
    """
    Returns True if the job is Senior/Lead, False if it's potentially Junior.
    Checks the title and (if available) the description.
    """
    title = job.get('title', '').lower()
    desc = job.get('description', '').lower()
    full_text = f"{title} {desc}"
    
    senior_keywords = [
        'senior', 'sr.', 'lead', 'principal', 'vp', 'director', 'staff',
        'architect', 'manager', 'head of', 'expert', 'specialist', 'team lead',
        'בכיר', 'מנהל', 'ראש צוות', 'מוביל', 'ארכיטקט'
    ]
    
    return any(word in full_text for word in senior_keywords)

# --- THREAD: DATABASE & DESCRIPTION CONSUMER ---
def database_worker():
    storage = JobStorage()
    session = requests.Session() 
    print("[DATABASE] Consumer active. Processing queue...", flush=True)

    while True:
        item = job_queue.get()
        if item is None: break
        
        job, source = item
        
        # Phase 1: Found it in the search
        print(f"    [FOUND] {job['title'][:50]:<50} | {source}", flush=True)
        
        # Phase 2: Filter check (Commented per request)
        # if pre_filter_senior(job):
        #     job_queue.task_done()
        #     continue

        # Phase 3: Check for duplicates
        if not storage.job_exists(job['id']):
            try:
                # Fetch full description if URL exists (mostly for Workday)
                headers = {"Accept": "application/json"}
                if job.get('tenant_id'):
                    headers["X-Workday-Subdomain"] = job['tenant_id']
                
                desc_url = job.get('description_url')
                if desc_url and not job.get('description'):
                    resp = session.get(desc_url, headers=headers, timeout=10)
                    if resp.status_code == 200:
                        # Workday specific parsing
                        try:
                            job['description'] = resp.json().get('jobPostingInfo', {}).get('jobDescription', '')
                        except:
                            job['description'] = resp.text[:1000]

                # Phase 4: Save
                storage.save_job(job)
                print(f"    [SAVED] {job['title'][:50]:<50} | {source} ✅", flush=True)
            except Exception as e:
                print(f"    [!] Error saving {job['title']}: {e}")
        
        job_queue.task_done()

# --- THREAD 1: ROUND-ROBIN WORKDAY SCRAPER ---
def round_robin_scraper(targets, fetcher):
    if not targets: return
    offset = 0
    limit = 20
    max_offset = 3000
    active_targets = list(targets)
    last_seen_ids = {t['name']: [] for t in targets}

    print(f"🚀 [WORKDAY] Round-Robin active: {len(active_targets)} sites.", flush=True)

    while offset < max_offset and active_targets:
        finished_this_wave = []
        for target in active_targets:
            found_jobs, has_more = fetcher.fetch_single_batch(target, offset)
            
            # Loop detection
            current_ids = [j['id'] for j in found_jobs]
            if current_ids and current_ids == last_seen_ids.get(target['name']):
                finished_this_wave.append(target)
                continue
            last_seen_ids[target['name']] = current_ids

            if found_jobs:
                for job in found_jobs:
                    job_queue.put((job, target['name']))
            
            if not has_more:
                finished_this_wave.append(target)
            time.sleep(0.1) 

        for t in finished_this_wave:
            if t in active_targets: active_targets.remove(t)
        offset += limit

# --- THREAD 2: FAST-ATS SCRAPER (Lever, Greenhouse, etc.) ---
def fast_ats_worker(targets, fetcher):
    if not targets: return
    print(f"🚀 [FAST-ATS] Processing {len(targets)} direct sites...", flush=True)
    for target in targets:
        try:
            jobs = fetcher.fetch(target)
            for job in jobs:
                job_queue.put((job, target['name']))
        except Exception as e:
            print(f"    [!] Fast-ATS Error {target['name']}: {e}")

# --- THREAD 3: JOBSPY AGGREGATOR (LinkedIn/Glassdoor) ---
def jobspy_worker(targets, fetcher):
    if not targets: return
    print(f"🚀 [JOBSPY] Aggregator started...", flush=True)
    for target in targets:
        try:
            jobs = fetcher.fetch(target)
            for job in jobs:
                job_queue.put((job, target['name']))
            # Delay to prevent IP blocks
            time.sleep(random.randint(10, 20))
        except Exception as e:
            print(f"    [!] JobSpy Error: {e}")

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run-jobspy', action='store_true')
    return parser.parse_args()

def main():
    args = parse_args()
    with open('config/targets.json', 'r') as f:
        targets = json.load(f)

    fetcher = Fetcher()
    
    # Categorize targets
    workday_targets = [t for t in targets if t.get('type') == 'workday']
    jobspy_targets = [t for t in targets if t.get('type') == 'jobspy' and args.run_jobspy]
    fast_targets = [t for t in targets if t.get('type') not in ['workday', 'jobspy']]

    # Start Consumer
    consumer = threading.Thread(target=database_worker, daemon=True)
    consumer.start()

    # Define Threads
    threads = [
        threading.Thread(target=round_robin_scraper, args=(workday_targets, fetcher)),
        threading.Thread(target=fast_ats_worker, args=(fast_targets, fetcher)),
        threading.Thread(target=jobspy_worker, args=(jobspy_targets, fetcher))
    ]

    # Start All
    for t in threads: t.start()
    
    # Wait for All to finish
    for t in threads: t.join()

    # Final Wait for Consumer
    job_queue.join()
    job_queue.put(None)
    consumer.join()
    print("\n🏁 ALL THREADS COMPLETE. Pipeline Finished.")

if __name__ == "__main__":
    main()