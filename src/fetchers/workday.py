import requests
import time
from .base import BaseFetcher

class WorkdayFetcher(BaseFetcher):
    def __init__(self):
        self.base_headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

    # --- ADD THIS METHOD BACK ---
    def fetch(self, target_config):
        """
        Satisfies the BaseFetcher requirement. 
        You can leave this empty or call your batch logic for a single crawl.
        """
        # For now, we'll just return the first page if called normally
        jobs, _ = self.fetch_single_batch(target_config, 0)
        return jobs

    def fetch_single_batch(self, target_config, offset):
        """Your new Round-Robin logic"""
        limit = 20
        all_batch_jobs = []
        
        try:
            tenant_id = target_config['url'].split('/cxs/')[1].split('/')[0]
            base_api_url = target_config['url'].replace("/jobs", "")
            
            dynamic_headers = self.base_headers.copy()
            dynamic_headers["X-Workday-Subdomain"] = tenant_id 

            payload = {
                "appliedFacets": {}, 
                "limit": limit, 
                "offset": offset, 
                "searchText": "",
                "subdomain": tenant_id,
                "serviceName": "Public_Search_Service" 
            }

            response = requests.post(target_config['url'], json=payload, headers=dynamic_headers, timeout=15)
            
            if response.status_code != 200:
                return [], False 
            
            data = response.json()
            if "jobPostings" not in data or not data["jobPostings"]:
                return [], False 
                
            batch = data["jobPostings"]
            relevant_batch = [j for j in batch if "Israel" in j.get('locationsText', '')]

            for job in relevant_batch:
                job_obj = {
                    "company": target_config["name"],
                    "title": job.get("title"),
                    "location": job.get("locationsText"),
                    "posted_on": job.get("postedOn"),
                    "url": f"{target_config['url'].split('/wday')[0]}{job.get('externalPath')}",
                    "id": job.get("bulletFields", [None])[0] or job.get('externalPath'),
                    "tenant_id": tenant_id # Added for the consumer to use
                }
                
                slug = job.get('externalPath')
                if slug:
                    job_obj['description_url'] = base_api_url + slug
                    # Note: We are NO LONGER fetching description here 
                    # so the Round-Robin stays lightning fast.
                
                all_batch_jobs.append(job_obj)
            
            return all_batch_jobs, len(batch) == limit

        except Exception:
            return [], False