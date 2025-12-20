import requests
import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from .base import BaseFetcher

GLOBAL_SESSIONS = {} 

class WorkdayFetcher(BaseFetcher):
    def __init__(self):
        self.common_headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "X-Workday-Client-Application-ID": "wday-cxs"
        }

    def fetch(self, target_config):
        jobs, _ = self.fetch_single_batch(target_config, 0)
        return jobs

    def _get_selenium_handshake(self, url):
        options = Options()
        options.add_argument("--headless")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
        try:
            driver.get(url)
            # Wait for search results container to ensure the session is fully 'warmed up'
            WebDriverWait(driver, 25).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
            time.sleep(7) 
            session = requests.Session()
            for c in driver.get_cookies():
                session.cookies.set(c['name'], c['value'])
            return session
        except Exception as e:
            print(f"    [!] Handshake failed: {e}")
            return None
        finally:
            driver.quit()

    def fetch_single_batch(self, target_config, offset):
        limit = 20
        all_batch_jobs = []
        try:
            hostname = target_config['url'].split('//')[1].split('/')[0]
            tenant_id = hostname.split('.')[0]
            portal_id = target_config['url'].split('/cxs/')[1].split('/')[0]
            base_url = f"https://{hostname}"
            session_key = f"{tenant_id}_{portal_id}"

            if session_key not in GLOBAL_SESSIONS:
                print(f"    [*] Handshaking {target_config['name']} ({tenant_id}/{portal_id})...")
                GLOBAL_SESSIONS[session_key] = self._get_selenium_handshake(f"{base_url}/en-US/{portal_id}/jobs")

            session = GLOBAL_SESSIONS[session_key]
            if not session: return [], False

            headers = self.common_headers.copy()
            headers.update({
                "X-Workday-Subdomain": tenant_id,
                "Origin": base_url,
                "Referer": f"{base_url}/en-US/{portal_id}/jobs"
            })

            # STRATEGY: Try "Israel" first, then fallback to "ISR" if 0 found
            search_terms = ["Israel", "ISR"]
            data = {"total": 0, "jobPostings": []}

            for term in search_terms:
                payload = {
                    "appliedFacets": {}, 
                    "limit": limit, 
                    "offset": offset, 
                    "searchText": term,
                    "subdomain": tenant_id
                }
                
                response = session.post(target_config['url'], json=payload, headers=headers, timeout=15)
                if response.status_code == 200:
                    data = response.json()
                    if data.get("total", 0) > 0:
                        break # Found results with this term!
                else:
                    if session_key in GLOBAL_SESSIONS: del GLOBAL_SESSIONS[session_key]
                    return [], False

            batch = data.get("jobPostings", [])
            if offset == 0:
                print(f"    [*] {target_config['name']} connected. Total results: {data.get('total', 0)}")

            # Universal Location Filter
            for job in batch:
                loc = job.get('locationsText', '').lower()
                if any(k in loc for k in ["israel", "isr", "herzliya", "raanana", "haifa", "tel aviv"]):
                    slug = job.get('externalPath')
                    all_batch_jobs.append({
                        "company": target_config["name"],
                        "title": job.get("title"),
                        "location": job.get("locationsText"),
                        "posted_on": job.get("postedOn"),
                        "id": job.get("bulletFields", [None])[0] or slug,
                        "tenant_id": tenant_id,
                        "url": f"{base_url}{slug}",
                        "description_url": f"{base_url}/wday/cxs/{portal_id}/job{slug}"
                    })
            
            return all_batch_jobs, (len(batch) == limit and len(batch) > 0)
        except Exception as e:
            print(f"    [!] Batch Error for {target_config['name']}: {e}")
            return [], False