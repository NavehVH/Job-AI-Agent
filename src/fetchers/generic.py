import requests
import time
import re
from bs4 import BeautifulSoup
from .base import BaseFetcher

class GenericHTMLFetcher(BaseFetcher):
    def fetch(self, target_config):
        name = target_config.get('name', 'Unknown')
        print(f"[*] Fetching jobs for {name} (Hybrid Generic)...")
        
        url = target_config['url']
        all_jobs = []
        page_source = ""

        try:
            # --- PHASE 1: GET SOURCE ---
            if target_config.get('render', False):
                from selenium import webdriver
                from selenium.webdriver.chrome.options import Options
                from selenium.webdriver.chrome.service import Service
                from webdriver_manager.chrome import ChromeDriverManager
                
                options = Options()
                options.add_argument("--headless=new")
                ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
                options.add_argument(f"user-agent={ua}")
                options.add_experimental_option('excludeSwitches', ['enable-logging'])
                
                driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
                driver.get(url)
                time.sleep(target_config.get('render_sleep', 8))
                page_source = driver.page_source
                driver.quit()
            else:
                session = requests.Session()
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,webp,*/*;q=0.8",
                    "Referer": "https://www.google.com/",
                    "Connection": "keep-alive"
                }
                response = session.get(url, headers=headers, timeout=20)
                page_source = response.text

            # --- PHASE 2: PARSE ---
            soup = BeautifulSoup(page_source, 'html.parser')
            row_selector = target_config.get('row_selector')
            items = soup.select(row_selector) if row_selector else []
            
            if not items:
                items = soup.find_all('a', href=re.compile(r'joborderid=|job_id=|posting/|/position/', re.I))
                link_mode = True
            else:
                link_mode = False

            print(f"    -> Identified {len(items)} items")

            for item in items:
                try:
                    if link_mode:
                        title = item.get_text(strip=True)
                        link = item['href']
                    else:
                        # 1. Try specific title selector first
                        title_sel = target_config.get('title_selector')
                        title_elem = item.select_one(title_sel) if title_sel else None
                        
                        # 2. Try specific link selector
                        link_sel = target_config.get('link_selector')
                        link_elem = item.select_one(link_sel) if link_sel else item.find('a', href=True)

                        if not link_elem: continue
                        link = link_elem['href']
                        
                        # 3. Smart Title logic: If title_elem is junk or missing, find better text in the row
                        title = title_elem.get_text(strip=True) if title_elem else ""
                        blacklist = ["whatsapp", "share", "copy link", "save job", "facebook", "linkedin", "browse positions"]
                        
                        if not title or any(word in title.lower() for word in blacklist):
                            # Fallback: Look for any child element with decent text that isn't blacklisted
                            potential_titles = [t.get_text(strip=True) for t in item.find_all(['p', 'span', 'h3', 'a']) 
                                               if len(t.get_text(strip=True)) > 5 
                                               and not any(word in t.get_text(strip=True).lower() for word in blacklist)]
                            if potential_titles:
                                title = potential_titles[0]
                            else:
                                continue

                    # Construct Absolute URL
                    base = target_config.get('base_url', '').rstrip('/')
                    if link and not link.startswith('http'):
                        link = f"{base}/{link.lstrip('/')}"

                    all_jobs.append({
                        "company": name, 
                        "title": title, 
                        "location": "Israel",
                        "url": link, 
                        "id": link, 
                        "posted_on": "Recent"
                    })
                except: continue
                    
        except Exception as e:
            print(f"    [!] Error for {name}: {e}")
            
        return all_jobs