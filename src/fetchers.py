import requests
import json
import time

class WorkdayFetcher:
    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

    def fetch(self, target_config):
        print(f"[*] Fetching jobs for {target_config['name']}...")
        
        all_jobs = []
        offset = 0
        limit = 20
        
        # Base URL for the hidden API (remove /jobs at the end)
        # e.g. https://nvidia.../wday/cxs/nvidia/NVIDIAExternalCareerSite
        base_api_url = target_config['url'].replace("/jobs", "")
        
        while True:
            payload = {
                "appliedFacets": {},
                "limit": limit,
                "offset": offset,
                "searchText": "" 
            }
            
            if "payload" in target_config:
                payload.update(target_config["payload"])

            try:
                response = requests.post(target_config['url'], json=payload, headers=self.headers)
                data = response.json()
                
                if "jobPostings" not in data or not data["jobPostings"]:
                    break
                    
                batch = data["jobPostings"]
                
                # Filter for Israel
                relevant_batch = []
                for job in batch:
                    if "Israel" in job.get('locationsText', ''):
                        relevant_batch.append(job)
                
                print(f"    -> Offset {offset}: Scanned {len(batch)} | Kept {len(relevant_batch)} (Israel only)")

                for job in relevant_batch:
                    # 1. Get basic info
                    job_obj = {
                        "company": target_config["name"],
                        "title": job.get("title"),
                        "location": job.get("locationsText"),
                        "posted_on": job.get("postedOn"),
                        "url": f"{target_config['url'].split('/wday')[0]}{job.get('externalPath')}",
                        "id": job.get("bulletFields", [None])[0] 
                    }
                    
                    # 2. LAZY LOAD: Fetch the full description now
                    # The API for details is usually base_api_url + job_slug
                    slug = job.get('externalPath') # e.g. "/job/NVIDIA/Senior-Eng_R-12345"
                    full_desc = self._fetch_description(base_api_url + slug)
                    job_obj['description'] = full_desc
                    
                    all_jobs.append(job_obj)
                
                # Safety brake
                if offset > 1000: break
                offset += limit
                time.sleep(0.5)
                
            except Exception as e:
                print(f"[!] Error fetching {target_config['name']}: {e}")
                break

        return all_jobs

    def _fetch_description(self, distinct_job_url):
        """
        Hits the specific job endpoint to get the full text.
        """
        try:
            # We don't need a payload for GET requests to the detail view
            response = requests.get(distinct_job_url, headers=self.headers)
            data = response.json()
            # The description is usually in 'jobPostingInfo' -> 'jobDescription'
            return data.get('jobPostingInfo', {}).get('jobDescription', 'No description found')
        except Exception:
            return "Error fetching description"