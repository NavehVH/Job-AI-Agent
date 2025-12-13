import pandas as pd
from jobspy import scrape_jobs
from .base import BaseFetcher

class JobSpyFetcher(BaseFetcher):
    def fetch(self, target_config):
        print(f"[*] Running JobSpy: '{target_config['search_term']}' on {target_config.get('sites', ['linkedin'])}...")
        
        # Map our config types to JobSpy's expected types
        # job_type options: "fulltime", "parttime", "internship", "contract"
        j_type = target_config.get('job_type', None) 
        
        try:
            jobs_df = scrape_jobs(
                site_name=target_config.get('sites', ["linkedin"]), # Support multiple sites!
                search_term=target_config['search_term'],
                location=target_config.get('location', 'Israel'),
                results_wanted=target_config.get('limit', 20),
                hours_old=24,
                job_type=j_type,            # <--- THE MAGIC FILTER
                description_format="markdown", # <--- SAVES AI TOKENS
                country_macosx=False
            )
            
            if jobs_df.empty:
                print("    -> No jobs found.")
                return []

            print(f"    -> Scanned {len(jobs_df)} listings")
            
            all_jobs = []
            for index, row in jobs_df.iterrows():
                # Filter: Ensure strictly Israel
                loc = str(row.get('location', '')).lower()
                if "israel" not in loc and "tel aviv" not in loc and "haifa" not in loc:
                    continue

                # Clean up the ID
                job_id = row.get('id')
                if not job_id or pd.isna(job_id):
                    job_id = row.get('job_url')

                job_obj = {
                    "company": row.get('company'),
                    "title": row.get('title'),
                    "location": row.get('location'),
                    "posted_on": str(row.get('date_posted')),
                    "url": row.get('job_url'),
                    "id": str(job_id),
                    # Markdown is much cleaner for the AI to read!
                    "description": row.get('description', "Check Link for details")
                }
                
                all_jobs.append(job_obj)
            
            print(f"    -> Kept {len(all_jobs)} valid Israeli jobs")
            return all_jobs

        except Exception as e:
            print(f"[!] JobSpy Error: {e}")
            return []