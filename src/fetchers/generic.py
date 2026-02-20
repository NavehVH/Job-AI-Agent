import time
from typing import Dict, List
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse, urljoin
import requests
from bs4 import BeautifulSoup
from src.fetchers.base import BaseFetcher

class GenericHTMLFetcher(BaseFetcher):
    def fetch(self, target_config: Dict) -> List[Dict]:
        name = target_config.get("name", "Unknown")
        render = target_config.get("render", False)
        print(f"[*] Fetching jobs for {name} (Ultimate Hybrid Engine)...")

        if not render:
            return self._fetch_requests(target_config)
        else:
            return self._fetch_selenium(target_config)

    def _fetch_requests(self, target_config: Dict) -> List[Dict]:
        name = target_config.get("name", "Unknown")
        url = target_config["url"]
        pagination = target_config.get("pagination", {})
        
        session = requests.Session()
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }
        
        param = pagination.get("param", "start")
        start_val = pagination.get("start", 0)
        step = pagination.get("step", 10)
        max_pages = pagination.get("max_pages", 5)
        
        jobs = []
        seen_ids = set()

        # 
        for page_idx in range(max_pages):
            offset = start_val + (page_idx * step)
            page_url = self._set_query_param(url, param, offset)
            
            try:
                resp = session.get(page_url, headers=headers, timeout=20)
                if resp.status_code != 200: break
                
                soup = BeautifulSoup(resp.text, "html.parser")
                page_jobs = self._parse_jobs(soup, target_config, name, resp.url)
                
                new_jobs = [j for j in page_jobs if j["id"] not in seen_ids]
                if not new_jobs: break
                
                for j in new_jobs: seen_ids.add(j["id"])
                jobs.extend(new_jobs)
                
                print(f"    -> {name} Index {offset}: Found {len(new_jobs)} NEW jobs.")
                time.sleep(1)
            except Exception as e:
                print(f"    [!] Error: {e}")
                break
                
        return jobs

    def _fetch_selenium(self, target_config: Dict) -> List[Dict]:
        name = target_config.get("name", "Unknown")
        url = target_config["url"]
        
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.chrome.service import Service
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from webdriver_manager.chrome import ChromeDriverManager
        
        options = Options()
        options.add_argument("--headless=new")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")

        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
        driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
            "source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        })

        jobs = []
        seen_ids = set()
        
        try:
            driver.get(url)
            page_count = 1
            max_pages = target_config.get("pagination", {}).get("max_pages", 4)
            
            # 
            while page_count <= max_pages:
                try:
                    WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.CSS_SELECTOR, target_config['row_selector'])))
                except: break
                
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight/2);")
                time.sleep(3)
                
                soup = BeautifulSoup(driver.page_source, "html.parser")
                page_jobs = self._parse_jobs(soup, target_config, name, driver.current_url)
                
                new_jobs = [j for j in page_jobs if j["id"] not in seen_ids]
                if not new_jobs: break
                
                for j in new_jobs: seen_ids.add(j["id"])
                jobs.extend(new_jobs)
                
                print(f"    -> {name} Page {page_count}: Found {len(new_jobs)} NEW jobs.")
                
                next_sel = target_config.get("next_button_selector")
                if next_sel:
                    try:
                        btn = driver.find_element(By.CSS_SELECTOR, next_sel)
                        driver.execute_script("arguments[0].scrollIntoView();", btn)
                        time.sleep(1)
                        driver.execute_script("arguments[0].click();", btn)
                        page_count += 1
                        time.sleep(4)
                    except: break
                else: break
        finally:
            driver.quit()
            
        return jobs

    def _parse_jobs(self, soup: BeautifulSoup, config: Dict, company: str, base_url: str) -> List[Dict]:
        jobs = []
        rows = soup.select(config.get("row_selector", ""))
        
        # If row selector fails, fallback to all links (Check Point needs this)
        items = rows if rows else soup.select("a[href]")

        includes = config.get("href_include", [])
        # Hardcode social excludes so they never show up again
        excludes = config.get("href_exclude", []) + ["mailto:", "twitter.com", "linkedin.com", "facebook.com", "share"]
        
        for item in items:
            title_sel = config.get("title_selector")
            t_el = item.select_one(title_sel) if title_sel and item.name != 'a' else item
            
            if item.name == 'a':
                link = item.get("href", "")
            else:
                l_el = item.select_one("a[href]")
                link = l_el.get("href", "") if l_el else ""

            if not link: continue
            
            link_lower = link.lower()
            if any(x in link_lower for x in excludes): continue
            if includes and not any(x in link_lower for x in includes): continue

            title = t_el.get_text(" ", strip=True) if t_el else ""
            if not title or len(title) < 4: continue

            if not link.startswith("http"):
                link = urljoin(base_url, link)
                
            jobs.append({
                "company": company, "title": title, "location": config.get("location", "Israel"),
                "url": link, "id": link, "posted_on": "Recent"
            })
            
        return jobs

    def _set_query_param(self, url: str, param: str, value: int) -> str:
        parsed = urlparse(url)
        qs = parse_qs(parsed.query, keep_blank_values=True)
        qs[param] = [str(value)]
        new_query = urlencode(qs, doseq=True)
        return urlunparse(parsed._replace(query=new_query))