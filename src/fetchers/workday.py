import requests
import time
from .base import BaseFetcher

class WorkdayFetcher(BaseFetcher):
    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

    def fetch(self, target_config):
        print(f"[*] Fetching jobs for {target_config['name']} (Workday)...")
        all_jobs = []
        offset = 0
        limit = 20
        base_api_url = target_config['url'].replace("/jobs", "")
        
        while True:
            payload = {"appliedFacets": {}, "limit": limit, "offset": offset, "searchText": ""}
            if "payload" in target_config:
                payload.update(target_config["payload"])

            try:
                response = requests.post(target_config['url'], json=payload, headers=self.headers)
                if response.status_code != 200: break
                
                try:
                    data = response.json()
                except:
                    break
                    
                if "jobPostings" not in data: break
                batch = data["jobPostings"]
                
                # Filter for Israel
                relevant_batch = [j for j in batch if "Israel" in j.get('locationsText', '')]
                
                print(f"    -> Offset {offset}: Scanned {len(batch)} | Kept {len(relevant_batch)} (Israel)")

                for job in relevant_batch:
                    job_obj = {
                        "company": target_config["name"],
                        "title": job.get("title"),
                        "location": job.get("locationsText"),
                        "posted_on": job.get("postedOn"),
                        "url": f"{target_config['url'].split('/wday')[0]}{job.get('externalPath')}",
                        "id": job.get("bulletFields", [None])[0] 
                    }
                    
                    slug = job.get('externalPath')
                    if slug:
                         job_obj['description'] = self._fetch_description(base_api_url + slug)
                    all_jobs.append(job_obj)
                
                if offset > 80: break
                offset += limit
                time.sleep(0.5)
                
            except Exception as e:
                print(f"[!] Error fetching {target_config['name']}: {e}")
                break
        return all_jobs

    def _fetch_description(self, url):
        try:
            r = requests.get(url, headers=self.headers)
            return r.json().get('jobPostingInfo', {}).get('jobDescription', 'No desc')
        except:
            return "Error"