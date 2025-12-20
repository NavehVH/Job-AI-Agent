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

def database_worker():
    """Background thread for saving and fetching descriptions."""
    storage = JobStorage()
    session = requests.Session() 
    print("[DATABASE] Consumer active.", flush=True)

    while True:
        item = job_queue.get()
        if item is None: break
        job, source = item
        
        if not storage.job_exists(job['id']):
            try:
                headers = {"Accept": "application/json"}
                if job.get('tenant_id'):
                    headers["X-Workday-Subdomain"] = job['tenant_id']
                
                desc_url = job.get('description_url')
                if desc_url:
                    resp = session.get(desc_url, headers=headers, timeout=10)
                    if resp.status_code == 200:
                        job['description'] = resp.json().get('jobPostingInfo', {}).get('jobDescription', '')

                storage.save_job(job)
                print(f"    [SAVED] {job['title'][:40]:<40} | {source} ✅", flush=True)
            except Exception as e:
                print(f"    [!] Error saving {job['title']}: {e}")
        
        job_queue.task_done()

def round_robin_scraper(targets, fetcher):
    """The Workday Scraper Thread."""
    if not targets: return
    offset = 0
    limit = 20
    max_offset = 1200 
    active_targets = list(targets)
    last_seen_ids = {t['name']: [] for t in targets}

    while offset < max_offset and active_targets:
        # --- RESTORED WAVE LOG ---
        print(f"\n[WORKDAY WAVE] Offset {offset} | Active Sites: {len(active_targets)}", flush=True)
        
        finished_this_wave = []
        for target in active_targets:
            found_jobs, has_more = fetcher.workday.fetch_single_batch(target, offset)
            
            if found_jobs:
                # Notify when jobs are sent to the queue
                print(f"    [+] {target['name']}: Found {len(found_jobs)} jobs.", flush=True)
                for job in found_jobs:
                    job_queue.put((job, target['name']))
            
            if not has_more:
                finished_this_wave.append(target)
            
            # Small delay between sites in the same wave to keep it stable
            time.sleep(0.3) 

        for t in finished_this_wave:
            if t in active_targets: active_targets.remove(t)
        
        offset += limit

def fast_ats_worker(targets, fetcher):
    """Thread for Lever, Greenhouse, etc."""
    if not targets: return
    print(f"🚀 [FAST-ATS] Processing {len(targets)} sites...", flush=True)
    for target in targets:
        try:
            jobs = fetcher.fetch(target)
            if jobs:
                print(f"    [+] {target['name']}: Found {len(jobs)} jobs.", flush=True)
                for job in jobs:
                    job_queue.put((job, target['name']))
        except Exception as e:
            print(f"    [!] Fast-ATS Error {target['name']}: {e}")

def main():
    with open('config/targets.json', 'r') as f:
        targets = json.load(f)

    fetcher = Fetcher()
    workday_targets = [t for t in targets if t.get('type') == 'workday']
    fast_targets = [t for t in targets if t.get('type') not in ['workday', 'jobspy']]

    # Start Consumer
    consumer = threading.Thread(target=database_worker, daemon=True)
    consumer.start()

    # Define parallel scraper threads
    threads = [
        threading.Thread(target=round_robin_scraper, args=(workday_targets, fetcher)),
        threading.Thread(target=fast_ats_worker, args=(fast_targets, fetcher))
    ]

    for t in threads: t.start()
    for t in threads: t.join()

    job_queue.join()
    job_queue.put(None)
    consumer.join()
    print("\n🏁 PIPELINE COMPLETE.")

if __name__ == "__main__":
    main()