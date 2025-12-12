import requests
import json
import time

class Fetcher:
    """Base class to route to the correct fetcher"""
    def fetch(self, target_config):
        if target_config['type'] == 'workday':
            return WorkdayFetcher().fetch(target_config)
        elif target_config['type'] == 'smartrecruiters':
            return SmartRecruitersFetcher().fetch(target_config)
        else:
            print(f"[!] Unknown fetcher type: {target_config['type']}")
            return []

class SmartRecruitersFetcher:
    def fetch(self, target_config):
        print(f"[*] Fetching jobs for {target_config['name']} (SmartRecruiters)...")
        
        api_url = f"https://api.smartrecruiters.com/v1/companies/{target_config['company_id']}/postings"
        all_jobs = []
        offset = 0
        limit = 100 # Fetch 100 at a time
        
        while True:
            # We loop through pages using 'offset'
            params = {"limit": limit, "offset": offset}
            
            try:
                response = requests.get(api_url, params=params)
                if response.status_code != 200:
                    print(f"    [!] Error: {response.status_code}")
                    break
                    
                data = response.json()
                batch = data.get('content', [])
                
                # If batch is empty, we reached the end
                if not batch:
                    break
                
                # --- LOCAL FILTERING ---
                relevant_batch = []
                for job in batch:
                    loc = job.get("location", {})
                    city = loc.get("city", "").lower()
                    region = loc.get("region", "").lower()
                    country = loc.get("country", "").lower()
                    
                    # If ANY field says "israel" or "il", we keep it.
                    if "israel" in city or "israel" in region or "il" == country:
                        relevant_batch.append(job)
                # -----------------------

                print(f"    -> Offset {offset}: Scanned {len(batch)} | Kept {len(relevant_batch)} (Israel only)")

                for job in relevant_batch:
                    job_obj = {
                        "company": target_config["name"],
                        "title": job.get("name"),
                        "location": job.get("location", {}).get("city", "Israel"),
                        "posted_on": job.get("releasedDate"),
                        "url": f"https://jobs.smartrecruiters.com/{target_config['company_id']}/{job.get('id')}",
                        "id": job.get("id"),
                    }
                    
                    # Lazy Load Description
                    details_url = f"{api_url}/{job.get('id')}"
                    job_obj['description'] = self._fetch_description(details_url)
                    all_jobs.append(job_obj)

                # Safety Brake: Stop after 5000 jobs to avoid infinite loops
                if offset > 80:
                    break
                    
                offset += limit
                time.sleep(0.5) # Be polite
                
            except Exception as e:
                print(f"[!] Error processing batch: {e}")
                break
            
        return all_jobs

    def _fetch_description(self, url):
        try:
            res = requests.get(url)
            data = res.json()
            full_text = ""
            if 'jobAd' in data and 'sections' in data['jobAd']:
                for section_data in data['jobAd']['sections'].values():
                    full_text += section_data.get('text', '') + "\n"
            return full_text if full_text else "No description available"
        except:
            return "Error fetching description"

class WorkdayFetcher:
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
                
                if response.status_code != 200:
                    # Silent skip or simple log
                    break
                
                try:
                    data = response.json()
                except:
                    break
                    
                if "jobPostings" not in data or not data["jobPostings"]:
                    break
                    
                batch = data["jobPostings"]
                
                # Workday Filter for Israel
                relevant_batch = []
                for job in batch:
                    if "Israel" in job.get('locationsText', ''):
                        relevant_batch.append(job)
                
                print(f"    -> Offset {offset}: Scanned {len(batch)} | Kept {len(relevant_batch)} (Israel only)")

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
                        full_desc = self._fetch_description(base_api_url + slug)
                        job_obj['description'] = full_desc
                    
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
            response = requests.get(url, headers=self.headers)
            data = response.json()
            return data.get('jobPostingInfo', {}).get('jobDescription', 'No description found')
        except:
            return "Error fetching description"