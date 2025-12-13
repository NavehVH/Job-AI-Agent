import requests
import time
from .base import BaseFetcher

class GreenhouseFetcher(BaseFetcher):
    def fetch(self, target_config):
        print(f"[*] Fetching jobs for {target_config['name']} (Greenhouse)...")
        
        api_url = f"https://boards-api.greenhouse.io/v1/boards/{target_config['board_token']}/jobs?content=true"
        all_jobs = []
        
        try:
            response = requests.get(api_url)
            
            if response.status_code != 200:
                print(f"    [!] Error: {response.status_code}")
                return []
                
            data = response.json()
            batch = data.get('jobs', [])
            
            # --- STRICT FILTERING ---
            relevant_batch = []
            # Only accept these if "Israel" is missing from the location string
            israel_cities = [
                "tel aviv", "tlv", "herzliya", "haifa", "yokneam", 
                "jerusalem", "raanana", "petah tikva", "ramat gan", 
                "rehovot", "hod hasharon", "kfar saba", "netanya"
            ]
            
            for job in batch:
                loc_name = job.get("location", {}).get("name", "").lower()
                
                # 1. Strict 'Israel' check (Safe)
                if "israel" in loc_name:
                    relevant_batch.append(job)
                    continue
                
                # 2. City Check (Safe)
                # We check if the location string CONTAINS a city name
                if any(city in loc_name for city in israel_cities):
                    relevant_batch.append(job)
                    continue
                
                # REMOVED the "il" check because it matches "Brazil", "Illinois", etc.
            # -----------------------

            print(f"    -> Scanned {len(batch)} | Kept {len(relevant_batch)} (Israel)")

            for job in relevant_batch:
                description_html = job.get("content", "No description")
                
                job_obj = {
                    "company": target_config["name"],
                    "title": job.get("title"),
                    "location": job.get("location", {}).get("name"),
                    "posted_on": job.get("updated_at"),
                    "url": job.get("absolute_url"),
                    "id": str(job.get("id")),
                    "description": description_html
                }
                
                all_jobs.append(job_obj)
                
        except Exception as e:
            print(f"[!] Crash fetching {target_config['name']}: {e}")
            
        return all_jobs