

# ==============================================================================
# Handles the pipeline flow
# Scrape > Filter > DB Save > AI Brain > Email Notifications
# ==============================================================================

import json
import time 
import threading
import queue
import requests
import os
import sys, io
import re
import datetime
from src.brain import JobBrain
from src.fetchers import Fetcher
from src.fetchers import Fetcher
from src.storage import JobStorage
from src.notifications import send_job_email


if sys.stdout and sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def safe_print(msg):
    print(msg)
    if sys.stdout:
        sys.stdout.flush()

# Use filter on the jobs it finds
def should_keep_job(title):
    enable_filters = os.environ.get("ENABLE_FILTERS") == "True"
    
    if not enable_filters:
        return True
        
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
        safe_print(f"    [!] Error reading filters.txt: {e}")
        return True

job_queue = queue.Queue()

# Database Worker (Add the job if it should when a new one pop)
def database_worker():
    storage = JobStorage()
    session = requests.Session() 
    ai_is_disabled = os.environ.get("AI_DISABLED_MODE") == "True"
    
    safe_print(f"[DATABASE] Consumer active. AI-Skip: {ai_is_disabled}")

    while True:
        item = job_queue.get()
        if item is None: break
        job, source = item
        
        if not should_keep_job(job['title']):
            job_queue.task_done()
            continue

        if not storage.job_exists(job['id']):
            try:
                relevance_status = 1 if ai_is_disabled else 0
                storage.save_job(job, relevance=relevance_status)
                
                safe_print(f"[SAVED] {job['title'][:40]:<40} | {source}")
            except Exception as e:
                safe_print(f"[!] Save Error: {e}")
        
        job_queue.task_done()

# Scarper Wroker for fast scarping, which deliver all the data instant
def fast_scraper_worker(targets, fetcher):
    for target in targets:
        try:
            safe_print(f"[*] Fetching jobs for {target['name']}...") 
            jobs = fetcher.fetch(target) 
            if jobs:
                for job in jobs:
                    job_queue.put((job, target['name']))
        except Exception as e:
            safe_print(f"[!] Fast Scraper Error for {target['name']}: {e}")

# Scraper Worker for slow scraping, like workday
def round_robin_scraper_worker(targets, fetcher):
    if not targets: return #
    offset, limit = 0, 20
    active_targets = list(targets)
    target_totals = {t['name']: 0 for t in targets}
    last_seen_ids = {t['name']: [] for t in targets}

    while active_targets and offset < 2000:
        safe_print(f"\n[WORKDAY WAVE] Offset {offset} | Active Sites: {len(active_targets)}") #
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
                safe_print(f"    [+] {target['name']}: Found {len(found_jobs)} jobs.") #
                for job in found_jobs:
                    job_queue.put((job, target['name'])) #
            if (offset + limit) >= target_totals[target['name']]:
                finished_this_wave.append(target)
            time.sleep(0.5) 
        for t in finished_this_wave:
            if t in active_targets: active_targets.remove(t)
        offset += limit
        
# Handles AI run if enabled and email notifications 
def run_AI_processing():
    storage = JobStorage()
    ai_enabled = os.environ.get("AI_DISABLED_MODE") != "True"
    email_enabled = os.environ.get("EMAIL_ENABLED") == "True"
    
    # AI BRAIN ANALYSIS
    if ai_enabled:
        safe_print("[*] Starting AI Brain Analysis...")
        brain = JobBrain()
        
        # Look for jobs added in this session (e.g., last 15 minutes)
        time_threshold = (datetime.datetime.now(datetime.timezone.utc) - 
                          datetime.timedelta(minutes=15)).strftime('%Y-%m-%d %H:%M:%S')
        
        # Get all jobs with relevant = 0
        cursor = storage.conn.cursor()
        cursor.execute("""
            SELECT id, title, description FROM jobs 
            WHERE is_relevant = 0 AND found_at > ?
        """, (time_threshold,))
        
        pending_jobs = cursor.fetchall()
        for j_id, title, desc in pending_jobs:
            analysis = brain.analyze(title, desc or "") #AI brain
            if analysis:
                status = 1 if analysis.is_relevant else -1
                cursor.execute("""
                    UPDATE jobs SET is_relevant = ?, ai_reason = ?, 
                    tech_stack = ?, years_required = ? WHERE id = ?
                """, (status, analysis.reason, ", ".join(analysis.tech_stack), 
                      analysis.years_required, j_id))
                storage.conn.commit()
                safe_print(f"  [{'RELEVANT' if status == 1 else 'SKIPPED'}] {title[:30]}")
  
# EMAIL NOTIFICATIONS              
def send_notifications():
    storage = JobStorage()
    ai_enabled = os.environ.get("AI_DISABLED_MODE") != "True"
    email_enabled = os.environ.get("EMAIL_ENABLED") == "True"
    
    if email_enabled:
        safe_print("[*] Checking for notifications...")
        cursor = storage.conn.cursor()
        cursor.execute("""
            SELECT company, title, location, url, found_at 
            FROM jobs WHERE sent_email = 0 AND is_relevant = 1
        """)
        newly_found = [
            {"company": r[0], "title": r[1], "location": r[2], "url": r[3], "found_at": r[4]} 
            for r in cursor.fetchall()
        ]
        
        if newly_found:
            recipient = os.environ.get("RECIPIENT_EMAIL", "navehhadas@gmail.com")
            send_job_email(newly_found, recipient)
            cursor.execute("UPDATE jobs SET sent_email = 1 WHERE sent_email = 0 AND is_relevant = 1")
            storage.conn.commit()

def main():
    if not os.path.exists("authorization.txt"):
        safe_print("[!] Warning: authorization.txt missing.")

    safe_print("[*] Scraper started. Checking filters...") 
    
    config_path = os.path.join('config', 'targets.json')
    with open(config_path, 'r') as f:
        targets = json.load(f)

    # define which scarper to which worker
    fetcher = Fetcher()
    workday_targets = [t for t in targets if t.get('type') == 'workday']
    fast_targets = [t for t in targets if t.get('type') not in ['workday', 'jobspy']]

    consumer = threading.Thread(target=database_worker, daemon=True)
    consumer.start()

    threads = [
        threading.Thread(target=round_robin_scraper_worker, args=(workday_targets, fetcher)),
        threading.Thread(target=fast_scraper_worker, args=(fast_targets, fetcher))
    ]

    for t in threads: t.start()
    for t in threads: t.join()

    job_queue.join()
    job_queue.put(None)
    consumer.join()

    safe_print("\n[*] Scraper finished. Starting post-processing...")
    # Handles AI brain and email notifications
    run_AI_processing()
    send_notifications()
    safe_print("[*] Pipeline Complete.")

if __name__ == "__main__":
    main()