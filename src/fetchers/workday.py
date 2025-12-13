import requests
import time
from .base import BaseFetcher

class WorkdayFetcher(BaseFetcher):
    def __init__(self):
        # Base headers - will be merged with dynamic ones in fetch()
        self.base_headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

    def fetch(self, target_config):
        print(f"[*] Fetching jobs for {target_config['name']} (Workday)...")
        all_jobs = []
        offset = 0
        limit = 20
        
        try:
            # 1. Extract Tenant ID (e.g., 'NVIDIAExternalCareerSite') from the URL
            tenant_id = target_config['url'].split('/cxs/')[1].split('/')[0]
            base_api_url = target_config['url'].replace("/jobs", "")
        except IndexError:
            print(f"[!] Error: Could not extract Workday Tenant ID from URL for {target_config['name']}.")
            return []

        # 2. Define dynamic headers using the Tenant ID
        dynamic_headers = self.base_headers.copy()
        # --- CRITICAL FIX: Add the Workday X-Workday-Subdomain header ---
        dynamic_headers["X-Workday-Subdomain"] = tenant_id 
        
        while True:
            # 3. Define payload with mandatory Workday service keys
            payload = {
                "appliedFacets": {}, 
                "limit": limit, 
                "offset": offset, 
                "searchText": "",
                "subdomain": tenant_id,
                "serviceName": "Public_Search_Service" 
            }
            
            if "payload" in target_config:
                payload.update(target_config["payload"])

            try:
                # 4. Make the POST request
                response = requests.post(target_config['url'], json=payload, headers=dynamic_headers)
                
                if response.status_code != 200: 
                    print(f"    [!] Workday HTTP Error {response.status_code}. Status text: {response.text[:50]}...")
                    break
                
                try:
                    data = response.json()
                except:
                    # JSON Decode Error usually means Workday returned an HTML/Text error page
                    print(f"    [!] Workday JSON Decode Error for {target_config['name']}. Likely a blocked request.")
                    break
                    
                if "jobPostings" not in data or not data["jobPostings"]: break
                batch = data["jobPostings"]
                
                # Filter for Israel
                relevant_batch = [j for j in batch if "Israel" in j.get('locationsText', '')]
                
                print(f"    -> Offset {offset}: Scanned {len(batch)} | Kept {len(relevant_batch)} (Israel)")

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
                         job_obj['description'] = self._fetch_description(base_api_url + slug, dynamic_headers)
                    all_jobs.append(job_obj)
                
                if offset > 80: break
                offset += limit
                time.sleep(0.5) # Polite delay
                
            except Exception as e:
                print(f"[!] Critical Error fetching {target_config['name']}: {e}")
                break
        return all_jobs

    # NOTE: Updated to accept dynamic_headers for consistency
    def _fetch_description(self, url, headers): 
        try:
            r = requests.get(url, headers=headers)
            # The description endpoint is often more relaxed, but we use the same headers for safety
            return r.json().get('jobPostingInfo', {}).get('jobDescription', 'No desc')
        except:
            return "Error"