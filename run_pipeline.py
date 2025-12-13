import json
import time 
import random 
import argparse # <--- NEW IMPORT
from src.fetchers import Fetcher
from src.storage import JobStorage

# We do NOT import JobBrain because we aren't using AI yet.

def load_targets():
    with open('config/targets.json', 'r') as f:
        return json.load(f)

def parse_args(): # <--- NEW FUNCTION
    parser = argparse.ArgumentParser(description="AI Agent Job Hunter Pipeline.")
    
    # The action='store_true' means the flag defaults to False, 
    # but if the user provides --run-jobspy, it is set to True.
    parser.add_argument(
        '--run-jobspy', 
        action='store_true', 
        default=False, # Explicitly set default to False
        help="Set this flag to run high-risk JobSpy/LinkedIn searches."
    )
    return parser.parse_args()

def main():
    args = parse_args() # <--- CALL ARGS PARSER
    targets = load_targets()
    fetcher = Fetcher()
    storage = JobStorage()
    
    # ... (rest of main function)
    
    print("--- STARTING COLLECTOR MODE (NO AI, SAVING ALL) ---")
    if not args.run_jobspy:
        print("[* INFO] JobSpy searches are currently DISABLED. Use --run-jobspy flag to enable.")
    # ... (rest of setup)

    new_jobs_count = 0

    for target in targets:
        target_type = target.get('type')
        target_name = target.get('name')
        
        # --- NEW CONDITIONAL CHECK ---
        if target_type == 'jobspy' and not args.run_jobspy:
            print(f"\n[SKIP] Skipping {target_name} (JobSpy is disabled).")
            continue
        # ----------------------------

        print(f"\n[*] Checking {target_name} ({target_type})...")
        
        # 1. FETCH JOB
        try:
            found_jobs = fetcher.fetch(target)
        except Exception as e:
            print(f"    [!] Error fetching {target_name}: {e}")
            continue # Move to the next target if fetching fails

        # 2. IMPLEMENT DELAYS BASED ON RISK LEVEL
        
        # ... (Workday delay remains the same)
        if target_type == 'workday':
            time.sleep(0.5)
            
        # --- JOBSPY (LinkedIn/Google) DELAY (IP Ban Defense) ---
        # The logic below only runs if the loop *wasn't* skipped
        if target_type == 'jobspy':
            delay = random.randint(30, 90)
            print(f"    [SLEEP] Pausing {delay}s after JobSpy to avoid IP ban...")
            time.sleep(delay)
            
        # 3. SAVE JOBS
        for job in found_jobs:
            if not job.get('id'): 
                continue 

            if storage.job_exists(job['id']):
                continue
            
            # ... (saving logic)
            storage.save_job(job)
            new_jobs_count += 1

    print("\n" + "="*40)
    print(f"DONE. Saved {new_jobs_count} NEW jobs to database.")
    print("="*40)

if __name__ == "__main__":
    main()