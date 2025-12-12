import json
from src.fetchers import Fetcher
from src.storage import JobStorage

# We do NOT import JobBrain because we aren't using AI yet.

def load_targets():
    with open('config/targets.json', 'r') as f:
        return json.load(f)

def main():
    targets = load_targets()
    fetcher = Fetcher()
    storage = JobStorage()
    
    print("--- STARTING COLLECTOR MODE (NO AI, SAVING ALL) ---")

    new_jobs_count = 0

    for target in targets:
        print(f"\n[*] Checking {target['name']}...")
        found_jobs = fetcher.fetch(target)
        
        for job in found_jobs:
            if not job['id']: 
                continue 

            # MEMORY CHECK: Do we already have this job?
            if storage.job_exists(job['id']):
                # We stay silent for duplicates
                continue
            
            # NO AI CHECK - We just save everything for now to test the DB
            print(f"    [SAVING] {job['title']}")
            print(f"             Location: {job['location']}")
            
            # Save to database
            storage.save_job(job)
            new_jobs_count += 1

    print("\n" + "="*40)
    print(f"DONE. Saved {new_jobs_count} NEW jobs to database.")
    print("="*40)

if __name__ == "__main__":
    main()