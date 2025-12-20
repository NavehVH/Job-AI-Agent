import flet as ft
import datetime

def main(page: ft.Page):
    # --- WINDOW CONFIG ---
    page.title = "JobAgent Pro - Command Center"
    page.theme_mode = ft.ThemeMode.DARK
    page.bgcolor = "#0B0B0B" 
    page.window_width = 1200
    page.window_height = 900
    page.padding = 0

    # --- STATE ---
    is_running = False
    is_auto_mode = False  # New state for the 30-min timer
    last_run = "Never"
    email_enabled = True
    user_email = "naveh@example.com"

    # --- UI STATE COMPONENTS ---
    status_dot = ft.Container(width=10, height=10, bgcolor="#6A6A6A", border_radius=5)
    status_text = ft.Text("System Idle", color="#6A6A6A", size=12, weight="bold")
    last_run_label = ft.Text(f"Last Scan: {last_run}", color="#B3B3B3", size=11)
    progress_ring = ft.ProgressRing(width=14, height=14, stroke_width=2, visible=False)

    def toggle_script(e):
        nonlocal is_running, last_run
        is_running = not is_running
        
        progress_ring.visible = is_running
        run_button.text = "STOP SEARCH" if is_running else "RUN JOB SEARCH"
        run_button.bgcolor = "#CF6679" if is_running else "#1DB954"
        
        # Update Status Display
        if is_running:
            status_dot.bgcolor = "#1DB954"
            status_text.value = "SEARCHING..."
            status_text.color = "#1DB954"
        else:
            status_dot.bgcolor = "#1DB954" if is_auto_mode else "#6A6A6A"
            status_text.value = "AUTO-MODE (30m)" if is_auto_mode else "System Idle"
            status_text.color = "#1DB954" if is_auto_mode else "#6A6A6A"
            last_run = datetime.datetime.now().strftime("%H:%M:%S")
            last_run_label.value = f"Last Scan: {last_run}"
        
        page.update()

    def update_auto_mode(e):
        nonlocal is_auto_mode
        is_auto_mode = e.control.value
        if not is_running:
            status_dot.bgcolor = "#1DB954" if is_auto_mode else "#6A6A6A"
            status_text.value = "AUTO-MODE (30m)" if is_auto_mode else "System Idle"
            status_text.color = "#1DB954" if is_auto_mode else "#6A6A6A"
        page.update()

    run_button = ft.ElevatedButton(
        "RUN JOB SEARCH",
        icon=ft.Icons.PLAY_ARROW,
        on_click=toggle_script,
        style=ft.ButtonStyle(bgcolor="#1DB954", color="white", shape=ft.RoundedRectangleBorder(radius=8)),
    )

    # --- VIEW NAVIGATION ---
    def navigate(e):
        feed_nav.selected = (e.control == feed_nav)
        settings_nav.selected = (e.control == settings_nav)
        feed_view.visible = feed_nav.selected
        settings_view.visible = settings_nav.selected
        page.update()

    # --- JOB FEED (STYLE PRESERVED) ---
    def create_job_card(job):
        return ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Column([
                        ft.Text(job["title"], weight=ft.FontWeight.BOLD, size=18, color="white"),
                        ft.Row([ft.Text(job["company"], color="#1DB954", weight="w600"), ft.Text(" • ", color="#6A6A6A"), ft.Text(job["location"], color="#B3B3B3")]),
                    ], expand=True),
                    ft.Container(content=ft.Text("NEW", size=10, weight="bold", color="black"), bgcolor="#1DB954", padding=ft.padding.symmetric(horizontal=8, vertical=2), border_radius=5)
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                ft.Row([
                    ft.Container(content=ft.Text("R&D", size=11, color="#B3B3B3"), bgcolor="#222222", padding=ft.padding.symmetric(horizontal=10, vertical=4), border_radius=15),
                    ft.Text(f"🕒 {job['posted']}", size=11, color="#6A6A6A"),
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
            ], spacing=12),
            padding=20, bgcolor="#121212", border_radius=15, border=ft.border.all(1, "#222222"),
            on_hover=lambda e: (setattr(e.control, "bgcolor", "#1A1A1A" if e.data == "true" else "#121212"), setattr(e.control, "border", ft.border.all(1, "#1DB954" if e.data == "true" else "#222222")), e.control.update())
        )

    job_list = ft.ListView(expand=True, spacing=15, padding=25)
    for job in [{"title": "Senior Engineer", "company": "Nvidia", "location": "Tel Aviv", "posted": "2h ago"}, {"title": "Full Stack", "company": "Salesforce", "location": "Herzliya", "posted": "5h ago"}]:
        job_list.controls.append(create_job_card(job))

    feed_view = ft.Column([
        ft.Container(content=ft.TextField(hint_text="Search companies...", prefix_icon=ft.Icons.SEARCH, border_radius=15, bgcolor="#121212", border_color="#222222"), padding=ft.padding.only(top=30, left=25, right=25)),
        job_list
    ], expand=True, visible=True)

    # --- SETTINGS VIEW (AUTO-SEARCH ADDED) ---
    settings_view = ft.Column([
        ft.Container(
            content=ft.Column([
                ft.Text("Settings", size=32, weight="bold", color="white"),
                ft.Container(height=20),
                
                # Automation Section
                ft.Container(
                    content=ft.Column([
                        ft.Text("AUTOMATION", size=12, color="#1DB954", weight="bold"),
                        ft.Row([
                            ft.Column([ft.Text("Auto-Scan Mode", size=16), ft.Text("Run the scraper automatically every 30 minutes.", size=12, color="#6A6A6A")], expand=True),
                            ft.Switch(value=is_auto_mode, active_color="#1DB954", on_change=update_auto_mode)
                        ]),
                    ], spacing=10),
                    padding=25, bgcolor="#121212", border_radius=15, border=ft.border.all(1, "#222222")
                ),
                
                ft.Container(height=15),

                # Email Section
                ft.Container(
                    content=ft.Column([
                        ft.Text("NOTIFICATIONS", size=12, color="#1DB954", weight="bold"),
                        ft.Row([ft.Text("Email Alerts", expand=True, size=16), ft.Switch(value=email_enabled, active_color="#1DB954")]),
                        ft.TextField(label="Recipient Email", value=user_email, border_radius=10, bgcolor="#0B0B0B", border_color="#222222"),
                    ], spacing=15),
                    padding=25, bgcolor="#121212", border_radius=15, border=ft.border.all(1, "#222222")
                ),
            ]),
            padding=40
        )
    ], expand=True, visible=False)

    # --- SIDEBAR NAVIGATION ---
    feed_nav = ft.ListTile(leading=ft.Icon(ft.Icons.DASHBOARD), title=ft.Text("Job Feed"), selected=True, on_click=navigate)
    settings_nav = ft.ListTile(leading=ft.Icon(ft.Icons.SETTINGS), title=ft.Text("Settings"), on_click=navigate)

    sidebar = ft.Container(
        content=ft.Column([
            ft.Row([ft.Icon(ft.Icons.AUTO_AWESOME, color="#1DB954"), ft.Text("JobAgent", size=28, weight="bold")]),
            ft.Container(height=20),
            ft.Container(content=ft.Column([ft.Text("SYSTEM STATUS", size=10, color="#6A6A6A", weight="bold"), ft.Row([status_dot, status_text, progress_ring], spacing=8), last_run_label], spacing=8), padding=15, bgcolor="#121212", border_radius=12, border=ft.border.all(1, "#222222")),
            ft.Container(height=10),
            feed_nav,
            settings_nav,
            ft.Container(expand=True),
            run_button
        ]),
        width=280, bgcolor="#000000", padding=30
    )

    page.add(ft.Row([sidebar, ft.Stack([feed_view, settings_view], expand=True)], expand=True, spacing=0))

if __name__ == "__main__":
    ft.app(target=main)