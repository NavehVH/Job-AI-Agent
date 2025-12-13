import requests
import json
from .base import BaseFetcher

class LeverFetcher(BaseFetcher):
    def fetch(self, target_config):
        print(f"[*] Fetching jobs for {target_config['name']} (Lever)...")
        
        # Lever's hidden API: https://api.lever.co/v0/postings/[ID]?mode=json
        url = f"https://api.lever.co/v0/postings/{target_config['lever_id']}?mode=json"
        
        all_jobs = []
        try:
            response = requests.get(url)
            if response.status_code != 200:
                print(f"    [!] Error: {response.status_code}")
                return []
            
            batch = response.json()
            
            # --- FILTERING ---
            relevant_batch = []
            israel_cities = ["tel aviv", "tlv", "herzliya", "haifa", "yokneam", "jerusalem", "raanana", "petah tikva", "ramat gan", "rehovot"]

            for job in batch:
                # Lever location is in "categories" -> "location"
                loc = job.get("categories", {}).get("location", "").lower()
                
                # Check 1: Explicit Country
                if "israel" in loc or "il" in loc:
                    relevant_batch.append(job)
                    continue
                
                # Check 2: Major Cities
                if any(city in loc for city in israel_cities):
                    relevant_batch.append(job)
            # -----------------
            
            print(f"    -> Scanned {len(batch)} | Kept {len(relevant_batch)} (Israel)")

            for job in relevant_batch:
                job_obj = {
                    "company": target_config["name"],
                    "title": job.get("text"),
                    "location": job.get("categories", {}).get("location"),
                    "posted_on": job.get("createdAt"), # Lever gives precise timestamps!
                    "url": job.get("hostedUrl"),
                    "id": job.get("id"),
                    "description": job.get("descriptionPlain", "No description")
                }
                all_jobs.append(job_obj)
                
        except Exception as e:
            print(f"[!] Crash fetching {target_config['name']}: {e}")
            
        return all_jobs