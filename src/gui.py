import flet as ft
import datetime, sqlite3, math, threading, time
from src.storage import JobStorage
from src.engine import AppEngine
import src.config as cfg

def main(page: ft.Page):
    # --- 1. SETUP ---
    page.title = "JobAgent"
    page.theme_mode = ft.ThemeMode.DARK
    page.bgcolor = cfg.BG_COLOR
    page.window_width = cfg.WINDOW_WIDTH
    page.window_height = cfg.WINDOW_HEIGHT
    page.padding = 0

    storage = JobStorage(db_path="jobs.db")
    storage.conn = sqlite3.connect("jobs.db", check_same_thread=False)
    engine = AppEngine(storage)
    
    state = {"current_page": 0, "search": ""}

    # --- 2. UI REFS ---
    status_dot = ft.Container(width=10, height=10, bgcolor=cfg.TEXT_GREY, border_radius=5)
    status_text = ft.Text("System Idle", color=cfg.TEXT_GREY, size=12, weight="bold")
    # INITIAL LOAD FIX: Use heartbeat from text file
    last_run_label = ft.Text(f"Last Scan: {engine.get_last_scan_display()}", color="#B3B3B3", size=11)
    progress_ring = ft.ProgressRing(width=14, height=14, stroke_width=2, visible=False)
    page_number_text = ft.Text("Page 1 of 1", color="white", weight="bold")
    log_view = ft.ListView(expand=True, spacing=2, padding=10, auto_scroll=True)
    job_list = ft.ListView(expand=True, spacing=15, padding=25)

    # --- 3. HELPER FUNCTIONS ---
    def get_time_ago(ts):
        try:
            # UTC Fix: compare naive UTC objects
            now_utc = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
            db_time = datetime.datetime.strptime(ts, '%Y-%m-%d %H:%M:%S')
            diff = now_utc - db_time
            if diff.days > 0: return f"{diff.days}d ago"
            if (diff.seconds // 3600) > 0: return f"{diff.seconds // 3600}h ago"
            minutes = (diff.seconds % 3600) // 60
            return f"{minutes}m ago" if minutes > 0 else "Just now"
        except: return "Just now"

    def create_job_card(job, is_new):
        found_display = get_time_ago(job.get('found_at', ''))
        
        # --- NEW: Tech Tag Logic ---
        tech_badges = []
        raw_tech = job.get('tech_stack', '')
        if raw_tech:
            # Split the string and clean up whitespace
            tech_list = [t.strip() for t in raw_tech.split(",") if t.strip()]
            for tech in tech_list[:4]: # Limit to 4 tags to keep it clean
                tech_badges.append(
                    ft.Container(
                        content=ft.Text(tech, size=10, color=cfg.ACCENT_COLOR, weight="bold"),
                        bgcolor=f"{cfg.ACCENT_COLOR}22", # 22 is hex for ~13% opacity
                        padding=ft.padding.only(left=8, right=8, top=4, bottom=4),
                        border_radius=10,
                        border=ft.border.all(1, f"{cfg.ACCENT_COLOR}44")
                    )
                )

        return ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Column([
                        ft.Text(job['title'], weight="bold", size=18, color="white", no_wrap=True),
                        ft.Row([
                            ft.Text(job['company'], color=cfg.ACCENT_COLOR, weight="w600"), 
                            ft.Text(" • "), 
                            ft.Text(job['location'], color="#B3B3B3")
                        ]),
                    ], expand=True),
                    ft.Container(
                        content=ft.Text("NEW", size=10, weight="bold", color="black"), 
                        bgcolor=cfg.ACCENT_COLOR, 
                        padding=5, 
                        border_radius=5, 
                        visible=is_new
                    )
                ], alignment="spaceBetween"),

                ft.Row([
                    # Dynamic Tech Badges Row
                    ft.Row(tech_badges, spacing=8),
                    
                    ft.Row([
                        ft.Text(f"Found {found_display}", size=11, color="#6A6A6A"),
                        ft.IconButton(
                            icon=ft.Icons.OPEN_IN_NEW, 
                            icon_color=cfg.ACCENT_COLOR, 
                            icon_size=18, 
                            on_click=lambda _: page.launch_url(job['url'])
                        )
                    ], spacing=10)
                ], alignment="spaceBetween")
            ], spacing=12),
            padding=20, 
            bgcolor=cfg.CARD_BG, 
            border_radius=15, 
            border=ft.border.all(1, "#222222"),
            on_hover=lambda e: (
                setattr(e.control, "bgcolor", "#1A1A1A" if e.data == "true" else cfg.CARD_BG), 
                setattr(e.control, "border", ft.border.all(1, cfg.ACCENT_COLOR if e.data == "true" else "#222222")), 
                e.control.update()
            )
        )

    def load_jobs_from_db():
        job_list.controls.clear()
        cursor = storage.conn.cursor()
        
        # 1. BASE FILTER: We only want relevant jobs
        base_filter = "WHERE is_relevant = 1"
        
        # 2. GET TOTAL COUNT (for pagination)
        q_count = f"SELECT COUNT(*) FROM jobs {base_filter}"
        if state["search"]:
            cursor.execute(q_count + " AND (title LIKE ? OR company LIKE ?)", (f"%{state['search']}%", f"%{state['search']}%"))
        else: 
            cursor.execute(q_count)
            
        total_count = cursor.fetchone()[0]
        total_pages = max(1, math.ceil(total_count / cfg.RESULTS_PER_PAGE))
        
        # 3. GET MAX TIME (for "NEW" badge logic)
        # We define max_time here so it is available for the loop below
        cursor.execute(f"SELECT MAX(found_at) FROM jobs {base_filter}")
        max_ts_row = cursor.fetchone()
        max_time = None
        if max_ts_row and max_ts_row[0]:
            try:
                max_time = datetime.datetime.strptime(max_ts_row[0], '%Y-%m-%d %H:%M:%S')
            except:
                max_time = None

        # 4. FETCH THE JOBS
        offset = state["current_page"] * cfg.RESULTS_PER_PAGE
        q = f"SELECT company, title, location, url, found_at, ai_reason, tech_stack FROM jobs {base_filter} "
        
        if state["search"]:
            q += "AND (title LIKE ? OR company LIKE ?) ORDER BY found_at DESC LIMIT ? OFFSET ?"
            cursor.execute(q, (f"%{state['search']}%", f"%{state['search']}%", cfg.RESULTS_PER_PAGE, offset))
        else:
            q += "ORDER BY found_at DESC LIMIT ? OFFSET ?"
            cursor.execute(q, (cfg.RESULTS_PER_PAGE, offset))
        
        # 5. RENDER THE CARDS
        for r in cursor.fetchall():
            job_time_str = r[4]
            is_new = False
            if max_time and job_time_str:
                try:
                    job_time = datetime.datetime.strptime(job_time_str, '%Y-%m-%d %H:%M:%S')
                    # If job was found within 15 minutes of the last scan
                    is_new = (max_time - job_time).total_seconds() < 900
                except:
                    pass
            
            job_data = {
                "company": r[0], "title": r[1], "location": r[2], 
                "url": r[3], "found_at": r[4], "ai_reason": r[5], "tech_stack": r[6]
            }
            job_list.controls.append(create_job_card(job_data, is_new))
        
        # Update Pagination UI
        page_number_text.value = f"Page {state['current_page'] + 1} of {total_pages}"
        prev_btn.disabled = (state["current_page"] == 0)
        next_btn.disabled = (state["current_page"] + 1 >= total_pages)
        page.update()

    def change_page(delta):
        state["current_page"] += delta
        load_jobs_from_db()

    # --- 4. ENGINE CALLBACKS ---
    def on_pipeline_finish():
        progress_ring.visible = False
        run_button.text = "RUN JOB SEARCH"; run_button.bgcolor = cfg.ACCENT_COLOR
        status_dot.bgcolor = cfg.ACCENT_COLOR if engine.is_auto_mode else cfg.TEXT_GREY
        status_text.value = "AUTO-MODE (30m)" if engine.is_auto_mode else "System Idle"
        status_text.color = cfg.ACCENT_COLOR if engine.is_auto_mode else cfg.TEXT_GREY
        
        # UPDATE FIX: Correctly update heartbeat label
        last_run_label.value = f"Last Scan: {engine.get_last_scan_display()}"
        
        load_jobs_from_db()
        page.update()

    def on_run_click(e):
        if engine.is_running:
            engine.stop_pipeline(); status_text.value = "TERMINATING..."; status_text.color = cfg.ERROR_COLOR; page.update(); return
        engine.is_running = True; progress_ring.visible = True; run_button.text = "STOP SEARCH"; run_button.bgcolor = cfg.ERROR_COLOR
        status_dot.bgcolor = cfg.ACCENT_COLOR; status_text.value = "SEARCHING..."; status_text.color = cfg.ACCENT_COLOR
        log_view.controls.clear(); page.update()
        threading.Thread(target=engine.run_pipeline, args=(lambda m: (log_view.controls.append(ft.Text(m, size=10, color="#B3B3B3")), page.update()), on_pipeline_finish), daemon=True).start()

    # --- 5. NAVIGATION ---
    def on_nav_change(e):
        is_feed = (e.control == feed_nav)
        feed_view.visible = is_feed; settings_view.visible = not is_feed
        feed_nav.leading.color = cfg.ACCENT_COLOR if is_feed else cfg.TEXT_GREY
        feed_nav.title.color = "white" if is_feed else cfg.TEXT_GREY
        settings_nav.leading.color = cfg.ACCENT_COLOR if not is_feed else cfg.TEXT_GREY
        settings_nav.title.color = "white" if not is_feed else cfg.TEXT_GREY
        page.update()

    # --- 6. UI ASSEMBLY ---
    search_field = ft.TextField(hint_text="Search jobs...", border_radius=15, bgcolor=cfg.CARD_BG, on_change=lambda e: (state.update({"search": e.control.value, "current_page": 0}), load_jobs_from_db()))
    prev_btn = ft.IconButton(ft.Icons.ARROW_BACK_IOS_NEW, on_click=lambda _: change_page(-1))
    next_btn = ft.IconButton(ft.Icons.ARROW_FORWARD_IOS, on_click=lambda _: change_page(1))
    run_button = ft.ElevatedButton("RUN JOB SEARCH", icon=ft.Icons.PLAY_ARROW, on_click=on_run_click, style=ft.ButtonStyle(bgcolor=cfg.ACCENT_COLOR, color="white", shape=ft.RoundedRectangleBorder(radius=8)))

    feed_view = ft.Column([ft.Container(search_field, padding=25), job_list, ft.Container(ft.Row([prev_btn, page_number_text, next_btn], alignment="center", spacing=20), padding=20)], expand=True)
    
    # --- 6. UI ASSEMBLY (Updated with Scroll) ---
    settings_view = ft.Column([
        ft.Container(
            content=ft.Column([
                ft.Text("Settings", size=32, weight="bold"),
                ft.Container(height=20),
                
                # AUTOMATION SECTION
                ft.Container(content=ft.Column([
                    ft.Text("AUTOMATION", size=12, color=cfg.ACCENT_COLOR, weight="bold"),
                    ft.Row([ft.Column([ft.Text("Auto-Scan Mode", size=16), ft.Text("Run every 30 minutes.", size=12, color=cfg.TEXT_GREY)], expand=True), 
                            ft.Switch(value=engine.is_auto_mode, active_color=cfg.ACCENT_COLOR, on_change=lambda e: (setattr(engine, 'is_auto_mode', e.control.value), engine.save_auth_value("AUTO_SCAN_ENABLED", str(e.control.value)), on_pipeline_finish()))]),
                ], spacing=10), padding=25, bgcolor=cfg.CARD_BG, border_radius=15),
                
                
                
                # AI TOGGLE SECTION
    ft.Container(content=ft.Column([
        ft.Text("AI PROCESSING", size=12, color=cfg.ACCENT_COLOR, weight="bold"),
        ft.Row([
            ft.Column([
                ft.Text("Enable AI Brain", size=16), 
                ft.Text("AI will filter for junior roles and extract tech stack.", size=12, color=cfg.TEXT_GREY),
                ft.Text("⚠️ WARNING: Uses API credits. Turn off to save money.", size=11, color=cfg.ERROR_COLOR)
            ], expand=True), 
            ft.Switch(
                value=engine.ai_enabled, 
                active_color=cfg.ACCENT_COLOR, 
                on_change=lambda e: (
                    setattr(engine, 'ai_enabled', e.control.value), 
                    engine.save_auth_value("AI_ENABLED", str(e.control.value))
                )
            )
        ]),
    ], spacing=10), padding=25, bgcolor=cfg.CARD_BG, border_radius=15),

    # FILTER TOGGLE SECTION
    ft.Container(content=ft.Column([
        ft.Text("SCRAPER FILTERS", size=12, color=cfg.ACCENT_COLOR, weight="bold"),
        ft.Row([
            ft.Column([
                ft.Text("Enable Keyword Filtering", size=16), 
            ], expand=True), 
            ft.Switch(
                value=engine.filter_enabled, 
                active_color=cfg.ACCENT_COLOR, 
                on_change=lambda e: (
                    setattr(engine, 'filter_enabled', e.control.value), 
                    engine.save_auth_value("FILTER_ENABLED", str(e.control.value))
                )
            )
        ]),
    ], spacing=10), padding=25, bgcolor=cfg.CARD_BG, border_radius=15),
                
                # NOTIFICATIONS SECTION
                ft.Container(content=ft.Column([
                    ft.Text("NOTIFICATIONS", size=12, color=cfg.ACCENT_COLOR, weight="bold"),
                    ft.Row([ft.Text("Email Alerts", expand=True, size=16), ft.Switch(value=engine.email_enabled, active_color=cfg.ACCENT_COLOR, on_change=lambda e: setattr(engine, 'email_enabled', e.control.value))]),
                    ft.TextField(label="Recipient Email", value=engine.user_email, on_change=lambda e: (setattr(engine, 'user_email', e.control.value), engine.save_auth_value("RECIPIENT_EMAIL", e.control.value))),
                ], spacing=15), padding=25, bgcolor=cfg.CARD_BG, border_radius=15),
                
                ft.Container(height=15),
                
                # SYSTEM FILES SECTION
                ft.Container(content=ft.Column([
                    ft.Text("SYSTEM FILES", size=12, color=cfg.ACCENT_COLOR, weight="bold"),
                    ft.Row([
                        ft.Column([
                            ft.Text("System Credentials", size=16),
                            ft.Text("Edit API keys and recipient email.", size=12, color=cfg.TEXT_GREY)
                        ], expand=True),
                        ft.TextButton("EDIT AUTH", on_click=lambda _: engine.open_file("authorization.txt"))
                    ]),
                    ft.Row([
                        ft.Column([
                            ft.Text("Exclusion Filters", size=16),
                            ft.Text("Edit keywords to skip specific job titles.", size=12, color=cfg.TEXT_GREY)
                        ], expand=True),
                        ft.TextButton("EDIT FILTERS", on_click=lambda _: engine.open_file("filters.txt"))
                    ]),
                ], spacing=15), padding=25, bgcolor=cfg.CARD_BG, border_radius=15)
                
            ]), padding=40
        )
    ], expand=True, visible=False, scroll=ft.ScrollMode.AUTO) # FIXED: Added scroll mode

    feed_nav = ft.ListTile(leading=ft.Icon(ft.Icons.DASHBOARD, color=cfg.ACCENT_COLOR), title=ft.Text("Job Feed", color="white"), on_click=on_nav_change)
    settings_nav = ft.ListTile(leading=ft.Icon(ft.Icons.SETTINGS, color=cfg.TEXT_GREY), title=ft.Text("Settings", color=cfg.TEXT_GREY), on_click=on_nav_change)

    # --- 7. SIDEBAR ASSEMBLY ---
    sidebar = ft.Container(content=ft.Column([
        ft.Row([ft.Icon(ft.Icons.AUTO_AWESOME, color=cfg.ACCENT_COLOR), ft.Text("JobAgent", size=28, weight="bold")]),
        ft.Container(height=20),
        ft.Container(content=ft.Column([
            ft.Text("SYSTEM STATUS", size=10, color=cfg.TEXT_GREY, weight="bold"), 
            ft.Row([status_dot, status_text, progress_ring], spacing=8), 
            last_run_label
        ], spacing=8), padding=15, bgcolor=cfg.CARD_BG, border_radius=12),
        feed_nav, settings_nav,
        # MARGIN FIX: Wrap text in Container
        ft.Container(content=ft.Text("LIVE LOGS", size=10, color=cfg.TEXT_GREY, weight="bold"), margin=ft.margin.only(top=10)),
        ft.Container(content=log_view, bgcolor="#000000", border_radius=10, height=200, border=ft.border.all(1, "#222222")),
        ft.Container(expand=True), run_button
    ]), width=280, bgcolor=cfg.SIDEBAR_BG, padding=30)

    page.add(ft.Row([sidebar, ft.Stack([feed_view, settings_view], expand=True)], expand=True))
    load_jobs_from_db()

    def auto_scan_loop():
        while True:
            if engine.is_auto_mode and not engine.is_running:
                on_run_click(None) 
                time.sleep(1800)
            time.sleep(10)
    threading.Thread(target=auto_scan_loop, daemon=True).start()

if __name__ == "__main__":
    ft.app(target=main)