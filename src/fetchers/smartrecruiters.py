import requests
import time
from .base import BaseFetcher

class SmartRecruitersFetcher(BaseFetcher):
    def fetch(self, target_config):
        print(f"[*] Fetching jobs for {target_config['name']} (SmartRecruiters)...")
        
        api_url = f"https://api.smartrecruiters.com/v1/companies/{target_config['company_id']}/postings"
        all_jobs = []
        offset = 0
        limit = 100 
        
        while True:
            params = {"limit": limit, "offset": offset}
            try:
                response = requests.get(api_url, params=params)
                
                if response.status_code == 429:
                    print(f"    [!] Rate Limit Hit. Sleeping 10s...")
                    time.sleep(10)
                    continue
                
                if response.status_code != 200: break
                
                data = response.json()
                batch = data.get('content', [])
                if not batch: break
                
                # Local Filter for Israel
                relevant_batch = []
                for job in batch:
                    loc = str(job.get("location", {})).lower()
                    if "israel" in loc or "'il'" in loc:
                        relevant_batch.append(job)

                print(f"    -> Offset {offset}: Scanned {len(batch)} | Kept {len(relevant_batch)} (Israel)")

                for job in relevant_batch:
                    job_obj = {
                        "company": target_config["name"],
                        "title": job.get("name"),
                        "location": job.get("location", {}).get("city", "Israel"),
                        "posted_on": job.get("releasedDate"),
                        "url": f"https://jobs.smartrecruiters.com/{target_config['company_id']}/{job.get('id')}",
                        "id": job.get("id"),
                    }
                    details_url = f"{api_url}/{job.get('id')}"
                    job_obj['description'] = self._fetch_description(details_url)
                    all_jobs.append(job_obj)

                if offset > 80: break
                offset += limit
                time.sleep(2) 
                
            except Exception as e:
                print(f"[!] Crash: {e}")
                break
            
        return all_jobs

    def _fetch_description(self, url):
        try:
            res = requests.get(url)
            data = res.json()
            full_text = ""
            if 'jobAd' in data and 'sections' in data['jobAd']:
                for section in data['jobAd']['sections'].values():
                    full_text += section.get('text', '') + "\n"
            return full_text if full_text else "No description"
        except:
            return "Error"