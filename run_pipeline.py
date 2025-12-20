import json
import time 
import threading
import queue
import requests
from src.fetchers import Fetcher
from src.storage import JobStorage

job_queue = queue.Queue()

def database_worker():
    storage = JobStorage()
    session = requests.Session() 
    print("[DATABASE] Consumer active.", flush=True)

    while True:
        item = job_queue.get()
        if item is None: break
        job, source = item
        
        if not storage.job_exists(job['id']):
            try:
                headers = {"Accept": "application/json", "X-Workday-Subdomain": job.get('tenant_id', '')}
                desc_url = job.get('description_url')
                if desc_url:
                    resp = session.get(desc_url, headers=headers, timeout=10)
                    if resp.status_code == 200:
                        job['description'] = resp.json().get('jobPostingInfo', {}).get('jobDescription', '')
                storage.save_job(job)
                print(f"    [SAVED] {job['title'][:40]:<40} | {source} ✅", flush=True)
            except Exception as e:
                print(f"    [!] Error saving {job['title']}: {e}")
        else:
            # We skip duplicates to keep the DB clean
            job_queue.task_done()
            continue
        job_queue.task_done()

def round_robin_scraper(targets, fetcher):
    if not targets: return
    offset = 0
    limit = 20
    active_targets = list(targets)
    target_totals = {t['name']: 0 for t in targets}
    last_seen_ids = {t['name']: [] for t in targets}

    while active_targets and offset < 2000:
        print(f"\n[WORKDAY WAVE] Offset {offset} | Active Sites: {len(active_targets)}", flush=True)
        
        finished_this_wave = []
        for target in active_targets:
            found_jobs, has_more, total_count = fetcher.workday.fetch_single_batch(target, offset)
            
            if offset == 0:
                target_totals[target['name']] = total_count

            # LOOP PROTECTION
            current_ids = [j['id'] for j in found_jobs]
            if current_ids and current_ids == last_seen_ids.get(target['name']):
                print(f"    [!] {target['name']} repeating data. Ending site scan.", flush=True)
                finished_this_wave.append(target)
                continue
            last_seen_ids[target['name']] = current_ids

            if found_jobs:
                print(f"    [+] {target['name']}: Found {len(found_jobs)} jobs.", flush=True)
                for job in found_jobs:
                    job_queue.put((job, target['name']))

            # MATH PAGINATION: Keep going as long as the offset hasn't reached the Total matches
            if (offset + limit) >= target_totals[target['name']]:
                print(f"    [-] {target['name']} reached end of {target_totals[target['name']]} matches.", flush=True)
                finished_this_wave.append(target)
            
            time.sleep(0.5) 

        for t in finished_this_wave:
            if t in active_targets: active_targets.remove(t)
        offset += limit

def main():
    with open('config/targets.json', 'r') as f:
        targets = json.load(f)

    fetcher = Fetcher()
    workday_targets = [t for t in targets if t.get('type') == 'workday']
    fast_targets = [t for t in targets if t.get('type') not in ['workday', 'jobspy']]

    consumer = threading.Thread(target=database_worker, daemon=True)
    consumer.start()

    threads = [
        threading.Thread(target=round_robin_scraper, args=(workday_targets, fetcher)),
        threading.Thread(target=threading.Thread(target=lambda: [fetcher.fetch(t) for t in fast_targets]).start())
    ]

    for t in threads: 
        if t: t.start()
    for t in threads: 
        if t: t.join()

    job_queue.join()
    job_queue.put(None)
    consumer.join()
    print("\n🏁 PIPELINE COMPLETE.")

if __name__ == "__main__":
    main()