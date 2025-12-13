import requests
import re
import json
import html
from .base import BaseFetcher

class ComeetFetcher(BaseFetcher):
    def fetch(self, target_config):
        print(f"[*] Fetching jobs for {target_config['name']} (Comeet)...")
        
        base_url = f"https://www.comeet.com/jobs/{target_config['comeet_name']}/{target_config['comeet_uid']}"
        
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Referer": base_url
            }
            
            response = requests.get(base_url, headers=headers)
            if response.status_code != 200:
                print(f"    [!] Error loading page: {response.status_code}")
                return []
            
            page_source = response.text
            token = None

            # --- STRATEGY 1: Regex Search (Standard) ---
            # Looks for "token": "XYZ" 
            patterns = [
                r'"token"\s*:\s*"([A-Z0-9]+)"',
                r"'token'\s*:\s*'([A-Z0-9]+)'",
                r'token\s*=\s*"([A-Z0-9]+)"',
                r'&quot;token&quot;:&quot;([A-Z0-9]+)&quot;',
                # New pattern for Hailo/Angular apps
                r'company_token:\s*"([A-Z0-9]+)"', 
                r"company_token:\s*'([A-Z0-9]+)'"
            ]
            
            for p in patterns:
                match = re.search(p, page_source, re.IGNORECASE)
                if match:
                    token = match.group(1)
                    break
            
            # --- STRATEGY 2: Brute Force JSON Blob ---
            if not token:
                try:
                    # Look for any long hex string that looks like a token
                    potential_tokens = re.findall(r'["\']([A-F0-9]{10,40})["\']', page_source, re.IGNORECASE)
                    for t in potential_tokens:
                        # Heuristic: Tokens are usually hex, no spaces, length > 15
                        if len(t) > 15 and " " not in t:
                            # Verify if this token works by making a tiny API call
                            if self._verify_token(t, target_config['comeet_uid'], headers):
                                token = t
                                print(f"    -> Found Token via Brute Force: {token[:5]}...")
                                break
                except:
                    pass

            if not token:
                print(f"    [!] FAILED to find token for {target_config['name']}. Skipping.")
                return []

            # 2. Hit the API
            api_url = f"https://www.comeet.co/careers-api/2.0/company/{target_config['comeet_uid']}/positions?token={token}&details=true"
            
            api_response = requests.get(api_url, headers=headers)
            if api_response.status_code != 200:
                print(f"    [!] API Error: {api_response.status_code}")
                return []
                
            data = api_response.json()
            batch = data if isinstance(data, list) else data.get('positions', [])

            # --- FILTERING ---
            relevant_batch = []
            israel_cities = ["tel aviv", "tlv", "herzliya", "haifa", "yokneam", "jerusalem", "raanana", "petah tikva", "ramat gan", "rehovot", "hod hasharon"]

            for job in batch:
                # FIX FOR TEAM8 CRASH: Handle case where location is None
                loc_data = job.get("location")
                if not loc_data:
                    # If location is null, we can't check it. 
                    # Option: Skip it, or keep it if description contains Hebrew/Israel.
                    # Let's skip safely.
                    continue
                    
                loc_name = loc_data.get("name", "").lower()
                
                if "israel" in loc_name:
                    relevant_batch.append(job)
                    continue
                
                if any(city in loc_name for city in israel_cities):
                    relevant_batch.append(job)
            # -----------------

            print(f"    -> Scanned {len(batch)} | Kept {len(relevant_batch)} (Israel)")

            all_jobs = []
            for job in relevant_batch:
                # Description can be in 'details' list or separate fields
                desc = "No description"
                if job.get("details") and len(job["details"]) > 0:
                    desc = job["details"][0].get("value", "No description")

                job_obj = {
                    "company": target_config["name"],
                    "title": job.get("name"),
                    "location": job.get("location", {}).get("name", "Israel"),
                    "posted_on": job.get("time_updated"),
                    "url": job.get("url_active_page"),
                    "id": job.get("uid"),
                    "description": desc
                }
                all_jobs.append(job_obj)
                
            return all_jobs

        except Exception as e:
            print(f"[!] Crash fetching {target_config['name']}: {e}")
            return []

    def _verify_token(self, token, uid, headers):
        """Helper to test a guessed token"""
        try:
            # Request just 1 job to see if token is valid
            test_url = f"https://www.comeet.co/careers-api/2.0/company/{uid}/positions?token={token}&limit=1"
            r = requests.get(test_url, headers=headers)
            return r.status_code == 200
        except:
            return False