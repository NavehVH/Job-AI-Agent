import flet as ft
import datetime
import os
import sqlite3
import math
import subprocess
import threading
import signal
from src.storage import JobStorage

def main(page: ft.Page):
    # --- 1. WINDOW CONFIG ---
    page.title = "JobAgent Pro - Command Center"
    page.theme_mode = ft.ThemeMode.DARK
    page.bgcolor = "#0B0B0B" 
    page.window_width = 1200
    page.window_height = 900
    page.padding = 0

    # --- 2. DATABASE CONNECTION (Multi-Thread Safe) ---
    storage = JobStorage(db_path="jobs.db")
    storage.conn = sqlite3.connect("jobs.db", check_same_thread=False)

    # --- 3. PERSISTENT "LAST SCAN" LOGIC ---
    def get_db_last_run():
        cursor = storage.conn.cursor()
        try:
            cursor.execute("SELECT MAX(found_at) FROM jobs")
            db_res = cursor.fetchone()[0]
            return db_res.split(" ")[1] if db_res else "Never"
        except:
            return "Never"

    # --- 4. INITIALIZE STATE VARIABLES ---
    is_running = False
    is_auto_mode = False 
    email_enabled = True
    user_email = "naveh@example.com"
    current_page = 0
    results_per_page = 10
    pipeline_process = None 

    # --- 5. UI STATE COMPONENTS ---
    status_dot = ft.Container(width=10, height=10, bgcolor="#6A6A6A", border_radius=5)
    status_text = ft.Text("System Idle", color="#6A6A6A", size=12, weight="bold")
    last_run_label = ft.Text(f"Last Scan: {get_db_last_run()}", color="#B3B3B3", size=11)
    progress_ring = ft.ProgressRing(width=14, height=14, stroke_width=2, visible=False)
    page_number_text = ft.Text("Page 1 of 1", color="white", weight="bold")

    def get_time_ago(timestamp_str):
        try:
            found_dt = datetime.datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
            diff = datetime.datetime.now() - found_dt
            if diff.days > 0: return f"{diff.days}d ago"
            hours = diff.seconds // 3600
            if hours > 0: return f"{hours}h ago"
            minutes = (diff.seconds % 3600) // 60
            return f"{minutes}m ago"
        except: return "Just now"

    # --- 6. JOB CARD GENERATOR ---
    def create_job_card(job_data, is_new=False):
        found_display = get_time_ago(job_data.get('found_at', ''))
        return ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Column([
                        ft.Text(job_data['title'], weight=ft.FontWeight.BOLD, size=18, color="white", no_wrap=True),
                        ft.Row([ft.Text(job_data['company'], color="#1DB954", weight="w600"), ft.Text(" • "), ft.Text(job_data['location'], color="#B3B3B3")]),
                    ], expand=True),
                    ft.Container(content=ft.Text("NEW", size=10, weight="bold", color="black"), bgcolor="#1DB954", padding=ft.padding.symmetric(horizontal=8, vertical=2), border_radius=5, visible=is_new)
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                ft.Row([
                    ft.Container(content=ft.Text("Junior", size=11, color="#B3B3B3"), bgcolor="#222222", padding=ft.padding.symmetric(horizontal=10, vertical=4), border_radius=15),
                    ft.Row([
                        ft.Text(f"🔍 Found {found_display}", size=11, color="#6A6A6A"),
                        ft.IconButton(icon=ft.Icons.OPEN_IN_NEW, icon_color="#1DB954", icon_size=18, on_click=lambda _: page.launch_url(job_data['url']))
                    ], spacing=10)
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
            ], spacing=12),
            padding=20, bgcolor="#121212", border_radius=15, border=ft.border.all(1, "#222222"),
            on_hover=lambda e: (setattr(e.control, "bgcolor", "#1A1A1A" if e.data == "true" else "#121212"), setattr(e.control, "border", ft.border.all(1, "#1DB954" if e.data == "true" else "#222222")), e.control.update())
        )

    job_list = ft.ListView(expand=True, spacing=15, padding=25)

    # --- 7. DATA LOADING & PAGINATION ---
    def load_jobs_from_db(search_query=""):
        nonlocal current_page
        job_list.controls.clear()
        cursor = storage.conn.cursor()
        
        count_query = "SELECT COUNT(*) FROM jobs"
        if search_query:
            cursor.execute(count_query + " WHERE title LIKE ? OR company LIKE ?", (f"%{search_query}%", f"%{search_query}%"))
        else:
            cursor.execute(count_query)
        total_jobs = cursor.fetchone()[0]
        total_pages = max(1, math.ceil(total_jobs / results_per_page))

        cursor.execute("SELECT MAX(found_at) FROM jobs")
        max_time_str = cursor.fetchone()[0]
        max_time = datetime.datetime.strptime(max_time_str, '%Y-%m-%d %H:%M:%S') if max_time_str else None

        offset = current_page * results_per_page
        query = "SELECT company, title, location, url, found_at FROM jobs "
        if search_query:
            query += "WHERE title LIKE ? OR company LIKE ? ORDER BY found_at DESC LIMIT ? OFFSET ?"
            cursor.execute(query, (f"%{search_query}%", f"%{search_query}%", results_per_page, offset))
        else:
            query += "ORDER BY found_at DESC LIMIT ? OFFSET ?"
            cursor.execute(query, (results_per_page, offset))
        
        rows = cursor.fetchall()
        for row in rows:
            job_dict = {"company": row[0], "title": row[1], "location": row[2], "url": row[3], "found_at": row[4]}
            is_new = False
            if max_time:
                job_time = datetime.datetime.strptime(row[4], '%Y-%m-%d %H:%M:%S')
                if (max_time - job_time).total_seconds() < 900: is_new = True 
            job_list.controls.append(create_job_card(job_dict, is_new))
        
        page_number_text.value = f"Page {current_page + 1} of {total_pages}"
        prev_btn.disabled = (current_page == 0)
        next_btn.disabled = (current_page + 1 >= total_pages)
        page.update()

    # --- 8. PIPELINE TASK & UI RESET ---
    def reset_ui_to_idle():
        nonlocal is_running
        is_running = False
        progress_ring.visible = False
        run_button.text = "RUN JOB SEARCH"
        run_button.bgcolor = "#1DB954"
        status_dot.bgcolor = "#1DB954" if is_auto_mode else "#6A6A6A"
        status_text.value = "AUTO-MODE (30m)" if is_auto_mode else "System Idle"
        status_text.color = "#1DB954" if is_auto_mode else "#6A6A6A"
        last_run_label.value = f"Last Scan: {get_db_last_run()}"
        page.update()

    def run_pipeline_task():
        nonlocal pipeline_process
        try:
            pipeline_process = subprocess.Popen(["python", "run_pipeline.py"])
            pipeline_process.wait() 
        except Exception as e:
            print(f"Pipeline Error: {e}")
        finally:
            # This block always runs when process ends (naturally or killed)
            reset_ui_to_idle()
            load_jobs_from_db(search_field.value)

    # --- 9. RUN/STOP TOGGLE ---
    def on_run_click(e):
        nonlocal is_running, pipeline_process
        
        if is_running:
            # Force stop
            if pipeline_process:
                pipeline_process.terminate()
            status_text.value = "TERMINATING..."
            status_text.color = "#CF6679"
            page.update()
            return

        is_running = True
        progress_ring.visible = True
        run_button.text = "STOP SEARCH" 
        run_button.bgcolor = "#CF6679"
        status_dot.bgcolor = "#1DB954"
        status_text.value = "SEARCHING..."
        status_text.color = "#1DB954"
        page.update()
        threading.Thread(target=run_pipeline_task, daemon=True).start()

    # --- 10. SAFETY CLEANUP (Close window = Kill scraper) ---
    def cleanup_on_close(e):
        if pipeline_process:
            pipeline_process.kill()

    page.on_close = cleanup_on_close

    # --- 11. UI ASSEMBLY ---
    search_field = ft.TextField(hint_text="Search jobs or companies...", prefix_icon=ft.Icons.SEARCH, border_radius=15, bgcolor="#121212", border_color="#222222", on_change=lambda e: load_jobs_from_db(e.control.value))
    
    def change_page(delta):
        nonlocal current_page
        current_page += delta
        load_jobs_from_db(search_field.value)

    prev_btn = ft.IconButton(ft.Icons.ARROW_BACK_IOS_NEW, on_click=lambda _: change_page(-1))
    next_btn = ft.IconButton(ft.Icons.ARROW_FORWARD_IOS, on_click=lambda _: change_page(1))
    run_button = ft.ElevatedButton("RUN JOB SEARCH", icon=ft.Icons.PLAY_ARROW, on_click=on_run_click, style=ft.ButtonStyle(bgcolor="#1DB954", color="white", shape=ft.RoundedRectangleBorder(radius=8)))

    feed_view = ft.Column([
        ft.Container(content=search_field, padding=ft.padding.only(top=30, left=25, right=25)),
        job_list,
        ft.Container(content=ft.Row([prev_btn, page_number_text, next_btn], alignment=ft.MainAxisAlignment.CENTER, spacing=20), padding=ft.padding.only(bottom=20))
    ], expand=True, visible=True)

    def navigate(e):
        feed_view.visible = (e.control == feed_nav)
        settings_view.visible = (e.control == settings_nav)
        feed_nav.selected = feed_view.visible
        settings_nav.selected = settings_view.visible
        page.update()

    settings_view = ft.Column([
        ft.Container(content=ft.Column([
            ft.Text("Settings", size=32, weight="bold", color="white"),
            ft.Container(height=20),
            ft.Container(content=ft.Column([
                ft.Text("AUTOMATION", size=12, color="#1DB954", weight="bold"),
                ft.Row([ft.Column([ft.Text("Auto-Scan Mode", size=16), ft.Text("Run every 30 minutes.", size=12, color="#6A6A6A")], expand=True), ft.Switch(value=is_auto_mode, active_color="#1DB954")]),
            ], spacing=10), padding=25, bgcolor="#121212", border_radius=15, border=ft.border.all(1, "#222222")),
            ft.Container(height=15),
            ft.Container(content=ft.Column([
                ft.Text("NOTIFICATIONS", size=12, color="#1DB954", weight="bold"),
                ft.Row([ft.Text("Email Alerts", expand=True, size=16), ft.Switch(value=email_enabled, active_color="#1DB954")]),
                ft.TextField(label="Recipient Email", value=user_email, border_radius=10, bgcolor="#0B0B0B", border_color="#222222"),
            ], spacing=15), padding=25, bgcolor="#121212", border_radius=15, border=ft.border.all(1, "#222222"))
        ]), padding=40)
    ], expand=True, visible=False)

    feed_nav = ft.ListTile(leading=ft.Icon(ft.Icons.DASHBOARD), title=ft.Text("Job Feed"), selected=True, on_click=navigate)
    settings_nav = ft.ListTile(leading=ft.Icon(ft.Icons.SETTINGS), title=ft.Text("Settings"), on_click=navigate)

    sidebar = ft.Container(
        content=ft.Column([
            ft.Row([ft.Icon(ft.Icons.AUTO_AWESOME, color="#1DB954"), ft.Text("JobAgent", size=28, weight="bold")]),
            ft.Container(height=20),
            ft.Container(content=ft.Column([ft.Text("SYSTEM STATUS", size=10, color="#6A6A6A", weight="bold"), ft.Row([status_dot, status_text, progress_ring], spacing=8), last_run_label], spacing=8), padding=15, bgcolor="#121212", border_radius=12, border=ft.border.all(1, "#222222")),
            ft.Container(height=10),
            feed_nav, settings_nav,
            ft.Container(expand=True),
            run_button
        ]),
        width=280, bgcolor="#000000", padding=30
    )

    page.add(ft.Row([sidebar, ft.Stack([feed_view, settings_view], expand=True)], expand=True, spacing=0))
    load_jobs_from_db()

if __name__ == "__main__":
    ft.app(target=main)