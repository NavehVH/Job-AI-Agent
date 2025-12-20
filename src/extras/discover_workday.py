import requests
import re

def get_workday_api_url(user_url):
    # This specific User-Agent and Accept header is the key to stopping 406/500 errors
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
    }
    
    try:
        # Strip trailing slashes and 'jobs' path
        clean_base = user_url.split('/jobs')[0].split('/en-US')[0].rstrip('/')
        
        # Extract tenant from the subdomain (e.g., 'redhat' from redhat.wd5...)
        tenant = clean_base.split('//')[1].split('.')[0]
        
        # The Universal Search API Pattern
        api_url = f"{clean_base}/wday/cxs/{tenant}/jobs/search"
        
        # Validate the link by actually trying to reach the site
        session = requests.Session()
        resp = session.get(clean_base, headers=headers, timeout=10)
        
        if resp.status_code == 200:
            return api_url
        else:
            return f"Failed with status {resp.status_code}. Response: {resp.text[:100]}"
            
    except Exception as e:
        return f"Discovery Error: {e}"

# Test with the known Red Hat link
url = "https://redhat.wd5.myworkdayjobs.com/redhat"
print(f"\n✅ CORRECT URL FOR TARGETS.JSON:\n{get_workday_api_url(url)}\n")