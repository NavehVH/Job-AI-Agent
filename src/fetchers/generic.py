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
        pagination = target_config.get("pagination", {})
        pagination_type = pagination.get("type", "next_button")

        from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

        jobs = []
        seen_ids = set()

        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-blink-features=AutomationControlled"]
            )
            context = browser.new_context(
                user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            )
            page = context.new_page()
            page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

            try:
                page.goto(url, wait_until="domcontentloaded", timeout=30000)

                if pagination_type == "scroll":
                    max_scrolls = pagination.get("max_scrolls", 15)
                    stable_rounds = pagination.get("stable_rounds", 3)
                    sleep_after_scroll = pagination.get("sleep_after_scroll", 1.5)
                    stable_count = 0

                    for scroll_idx in range(max_scrolls):
                        try:
                            page.wait_for_selector(target_config['row_selector'], timeout=10000)
                        except PlaywrightTimeoutError:
                            break

                        page.evaluate("window.scrollTo(0, document.body.scrollHeight / 2)")
                        time.sleep(0.5)

                        soup = BeautifulSoup(page.content(), "html.parser")
                        page_jobs = self._parse_jobs(soup, target_config, name, page.url)
                        new_jobs = [j for j in page_jobs if j["id"] not in seen_ids]

                        if not new_jobs:
                            stable_count += 1
                            if stable_count >= stable_rounds:
                                print(f"    -> {name}: No new jobs for {stable_rounds} rounds. Done.")
                                break
                        else:
                            stable_count = 0
                            for j in new_jobs:
                                seen_ids.add(j["id"])
                            jobs.extend(new_jobs)
                            print(f"    -> {name} Scroll {scroll_idx + 1}: Found {len(new_jobs)} NEW jobs.")

                        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                        time.sleep(sleep_after_scroll)

                else:
                    max_pages = pagination.get("max_pages", 4)
                    next_sel = target_config.get("next_button_selector")
                    page_count = 1

                    while page_count <= max_pages:
                        try:
                            page.wait_for_selector(target_config['row_selector'], timeout=15000)
                        except PlaywrightTimeoutError:
                            break

                        page.evaluate("window.scrollTo(0, document.body.scrollHeight / 2)")
                        time.sleep(3)

                        soup = BeautifulSoup(page.content(), "html.parser")
                        page_jobs = self._parse_jobs(soup, target_config, name, page.url)
                        new_jobs = [j for j in page_jobs if j["id"] not in seen_ids]
                        if not new_jobs:
                            break

                        for j in new_jobs:
                            seen_ids.add(j["id"])
                        jobs.extend(new_jobs)
                        print(f"    -> {name} Page {page_count}: Found {len(new_jobs)} NEW jobs.")

                        if not next_sel:
                            break
                        try:
                            btn = page.query_selector(next_sel)
                            if btn is None:
                                break
                            btn.scroll_into_view_if_needed()
                            time.sleep(1)
                            btn.click()
                            page_count += 1
                            time.sleep(4)
                        except Exception:
                            break

            except Exception as e:
                print(f"    [!] Browser error for {name}: {e}")
            finally:
                browser.close()

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