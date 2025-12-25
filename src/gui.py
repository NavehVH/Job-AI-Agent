import flet as ft
import datetime
import sqlite3
import math
import threading
import time
from src.storage import JobStorage
from src.engine import AppEngine
import src.config as cfg

def main(page: ft.Page):
    # --- 1. WINDOW CONFIG ---
    page.title = "JobAgent Pro - Command Center"
    page.theme_mode = ft.ThemeMode.DARK
    page.bgcolor = cfg.BG_COLOR
    page.window_width = cfg.WINDOW_WIDTH
    page.window_height = cfg.WINDOW_HEIGHT
    page.padding = 0

    # --- 2. INITIALIZE ---
    storage = JobStorage(db_path="jobs.db")
    storage.conn = sqlite3.connect("jobs.db", check_same_thread=False)
    engine = AppEngine(storage)
    
    current_page = 0

    # --- 3. UI COMPONENTS (Refs) ---
    status_dot = ft.Container(width=10, height=10, bgcolor="#6A6A6A", border_radius=5)
    status_text = ft.Text("System Idle", color="#6A6A6A", size=12, weight="bold")
    last_run_label = ft.Text(f"Last Scan: {engine.get_db_last_run()}", color="#B3B3B3", size=11)
    progress_ring = ft.ProgressRing(width=14, height=14, stroke_width=2, visible=False)
    page_number_text = ft.Text("Page 1 of 1", color="white", weight="bold")
    log_view = ft.ListView(expand=True, spacing=2, padding=10, auto_scroll=True)
    job_list = ft.ListView(expand=True, spacing=15, padding=25)

    # --- 4. LOGIC WRAPPERS ---
    def get_time_ago(timestamp_str):
        try:
            found_dt = datetime.datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
            diff = datetime.datetime.now() - found_dt
            if diff.days > 0: return f"{diff.days}d ago"
            hours = diff.seconds // 3600
            if hours > 0: return f"{hours}h ago"
            return f"{(diff.seconds % 3600) // 60}m ago"
        except: return "Just now"

    def create_job_card(job_data, is_new=False):
        found_display = get_time_ago(job_data.get('found_at', ''))
        return ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Column([
                        ft.Text(job_data['title'], weight="bold", size=18, color="white", no_wrap=True),
                        ft.Row([ft.Text(job_data['company'], color=cfg.ACCENT_COLOR, weight="w600"), ft.Text(" • "), ft.Text(job_data['location'], color="#B3B3B3")]),
                    ], expand=True),
                    ft.Container(content=ft.Text("NEW", size=10, weight="bold", color="black"), bgcolor=cfg.ACCENT_COLOR, padding=ft.padding.symmetric(horizontal=8, vertical=2), border_radius=5, visible=is_new)
                ], alignment="spaceBetween"),
                ft.Row([
                    ft.Container(content=ft.Text("Junior", size=11, color="#B3B3B3"), bgcolor="#222222", padding=ft.padding.symmetric(horizontal=10, vertical=4), border_radius=15),
                    ft.Row([
                        ft.Text(f"🔍 Found {found_display}", size=11, color="#6A6A6A"),
                        ft.IconButton(icon=ft.Icons.OPEN_IN_NEW, icon_color=cfg.ACCENT_COLOR, icon_size=18, on_click=lambda _: page.launch_url(job_data['url']))
                    ], spacing=10)
                ], alignment="spaceBetween")
            ], spacing=12),
            padding=20, bgcolor=cfg.CARD_BG, border_radius=15, border=ft.border.all(1, "#222222"),
            on_hover=lambda e: (setattr(e.control, "bgcolor", "#1A1A1A" if e.data == "true" else cfg.CARD_BG), setattr(e.control, "border", ft.border.all(1, cfg.ACCENT_COLOR if e.data == "true" else "#222222")), e.control.update())
        )

    def load_jobs_from_db(search_query=""):
        nonlocal current_page
        job_list.controls.clear()
        cursor = storage.conn.cursor()
        
        # Determine total pages
        q_count = "SELECT COUNT(*) FROM jobs"
        if search_query:
            cursor.execute(q_count + " WHERE title LIKE ? OR company LIKE ?", (f"%{search_query}%", f"%{search_query}%"))
        else:
            cursor.execute(q_count)
        total_jobs = cursor.fetchone()[0]
        total_pages = max(1, math.ceil(total_jobs / cfg.RESULTS_PER_PAGE))

        cursor.execute("SELECT MAX(found_at) FROM jobs")
        max_ts = cursor.fetchone()[0]
        max_time = datetime.datetime.strptime(max_ts, '%Y-%m-%d %H:%M:%S') if max_ts else None

        offset = current_page * cfg.RESULTS_PER_PAGE
        query = "SELECT company, title, location, url, found_at FROM jobs "
        if search_query:
            query += "WHERE title LIKE ? OR company LIKE ? ORDER BY found_at DESC LIMIT ? OFFSET ?"
            cursor.execute(query, (f"%{search_query}%", f"%{search_query}%", cfg.RESULTS_PER_PAGE, offset))
        else:
            query += "ORDER BY found_at DESC LIMIT ? OFFSET ?"
            cursor.execute(query, (cfg.RESULTS_PER_PAGE, offset))
        
        for row in cursor.fetchall():
            job_dict = {"company": row[0], "title": row[1], "location": row[2], "url": row[3], "found_at": row[4]}
            job_time = datetime.datetime.strptime(row[4], '%Y-%m-%d %H:%M:%S')
            is_new = (max_time and (max_time - job_time).total_seconds() < 900)
            job_list.controls.append(create_job_card(job_dict, is_new))
        
        page_number_text.value = f"Page {current_page + 1} of {total_pages}"
        prev_btn.disabled = (current_page == 0)
        next_btn.disabled = (current_page + 1 >= total_pages)
        page.update()

    def change_page(delta):
        """Fixes the pagination crash."""
        nonlocal current_page
        current_page += delta
        load_jobs_from_db(search_field.value)

    # --- 5. ENGINE INTEGRATION ---
    def update_logs(msg):
        log_view.controls.append(ft.Text(msg, size=10, color="#B3B3B3", font_family="monospace"))
        page.update()

    def on_pipeline_finish():
        progress_ring.visible = False
        run_button.text = "RUN JOB SEARCH"; run_button.bgcolor = cfg.ACCENT_COLOR
        status_dot.bgcolor = cfg.ACCENT_COLOR if engine.is_auto_mode else "#6A6A6A"
        status_text.value = "AUTO-MODE (30m)" if engine.is_auto_mode else "System Idle"
        status_text.color = cfg.ACCENT_COLOR if engine.is_auto_mode else "#6A6A6A"
        last_run_label.value = f"Last Scan: {engine.get_db_last_run()}"
        load_jobs_from_db(search_field.value)
        page.update()

    def on_run_click(e):
        if engine.is_running:
            engine.stop_pipeline()
            status_text.value = "TERMINATING..."; status_text.color = cfg.ERROR_COLOR
            page.update(); return
        engine.is_running = True
        progress_ring.visible = True
        run_button.text = "STOP SEARCH"; run_button.bgcolor = cfg.ERROR_COLOR
        status_dot.bgcolor = cfg.ACCENT_COLOR; status_text.value = "SEARCHING..."; status_text.color = cfg.ACCENT_COLOR
        log_view.controls.clear()
        page.update()
        threading.Thread(target=engine.run_pipeline, args=(update_logs, on_pipeline_finish), daemon=True).start()

    # --- 6. UI ASSEMBLY ---
    search_field = ft.TextField(hint_text="Search jobs...", prefix_icon=ft.Icons.SEARCH, border_radius=15, bgcolor=cfg.CARD_BG, on_change=lambda e: load_jobs_from_db(e.control.value))
    
    # Buttons updated to use change_page
    prev_btn = ft.IconButton(ft.Icons.ARROW_BACK_IOS_NEW, on_click=lambda _: change_page(-1))
    next_btn = ft.IconButton(ft.Icons.ARROW_FORWARD_IOS, on_click=lambda _: change_page(1))
    
    run_button = ft.ElevatedButton("RUN JOB SEARCH", icon=ft.Icons.PLAY_ARROW, on_click=on_run_click, style=ft.ButtonStyle(bgcolor=cfg.ACCENT_COLOR, color="white", shape=ft.RoundedRectangleBorder(radius=8)))

    feed_view = ft.Column([ft.Container(search_field, padding=25), job_list, ft.Container(ft.Row([prev_btn, page_number_text, next_btn], alignment="center", spacing=20), padding=20)], expand=True)
    
    settings_view = ft.Column([
        ft.Container(content=ft.Column([
            ft.Text("Settings", size=32, weight="bold"),
            ft.Container(height=20),
            ft.Container(content=ft.Column([
                ft.Text("AUTOMATION", size=12, color=cfg.ACCENT_COLOR, weight="bold"),
                ft.Row([ft.Column([ft.Text("Auto-Scan Mode", size=16), ft.Text("Run every 30 minutes.", size=12, color="#6A6A6A")], expand=True), ft.Switch(value=engine.is_auto_mode, active_color=cfg.ACCENT_COLOR, on_change=lambda e: (setattr(engine, 'is_auto_mode', e.control.value), on_pipeline_finish()))]),
            ], spacing=10), padding=25, bgcolor=cfg.CARD_BG, border_radius=15),
            ft.Container(height=15),
            ft.Container(content=ft.Column([
                ft.Text("NOTIFICATIONS", size=12, color=cfg.ACCENT_COLOR, weight="bold"),
                ft.Row([ft.Text("Email Alerts", expand=True, size=16), ft.Switch(value=engine.email_enabled, active_color=cfg.ACCENT_COLOR, on_change=lambda e: setattr(engine, 'email_enabled', e.control.value))]),
                ft.TextField(label="Recipient Email", value=engine.user_email, on_change=lambda e: setattr(engine, 'user_email', e.control.value)),
            ], spacing=15), padding=25, bgcolor=cfg.CARD_BG, border_radius=15)
        ]), padding=40)
    ], expand=True, visible=False)

    sidebar = ft.Container(content=ft.Column([
        ft.Row([ft.Icon(ft.Icons.AUTO_AWESOME, color=cfg.ACCENT_COLOR), ft.Text("JobAgent", size=28, weight="bold")]),
        ft.Container(height=20),
        ft.Container(content=ft.Column([ft.Text("SYSTEM STATUS", size=10, color="#6A6A6A", weight="bold"), ft.Row([status_dot, status_text, progress_ring], spacing=8), last_run_label], spacing=8), padding=15, bgcolor=cfg.CARD_BG, border_radius=12),
        ft.ListTile(leading=ft.Icon(ft.Icons.DASHBOARD), title=ft.Text("Job Feed"), selected=True, on_click=lambda _: (setattr(feed_view, 'visible', True), setattr(settings_view, 'visible', False), page.update())),
        ft.ListTile(leading=ft.Icon(ft.Icons.SETTINGS), title=ft.Text("Settings"), on_click=lambda _: (setattr(feed_view, 'visible', False), setattr(settings_view, 'visible', True), page.update())),
        ft.Container(content=ft.Text("LIVE LOGS", size=10, color="#6A6A6A", weight="bold"), margin=ft.margin.only(top=10)),
        ft.Container(content=log_view, bgcolor="#000000", border_radius=10, height=200, border=ft.border.all(1, "#222222")),
        ft.Container(expand=True), run_button
    ]), width=280, bgcolor=cfg.SIDEBAR_BG, padding=30)

    page.add(ft.Row([sidebar, ft.Stack([feed_view, settings_view], expand=True)], expand=True, spacing=0))
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