import subprocess, os, threading, time, datetime, sys
from src.notifications import send_job_email

class AppEngine:
    def __init__(self, storage):
        self.storage = storage
        self.pipeline_process = None
        self.is_running = False
        self.last_run_timestamp = 0
        
        # Load persistent settings
        self.user_email = self.get_auth_value("RECIPIENT_EMAIL") or "navehhadas@gmail.com"
        auto_val = self.get_auth_value("AUTO_SCAN_ENABLED")
        self.is_auto_mode = True if auto_val == "True" else False
        self.email_enabled = True

    def get_auth_value(self, key_name):
        """Reads settings from authorization.txt."""
        try:
            if not os.path.exists("authorization.txt"): return None
            with open("authorization.txt", "r") as f:
                for line in f:
                    if "=" in line:
                        k, v = line.split("=", 1)
                        if k.strip() == key_name: return v.strip()
        except: return None
        return None

    def save_auth_value(self, key_name, new_value):
        """Saves settings to authorization.txt."""
        lines = []
        found = False
        if os.path.exists("authorization.txt"):
            with open("authorization.txt", "r") as f:
                lines = f.readlines()
        with open("authorization.txt", "w") as f:
            for line in lines:
                if line.startswith(f"{key_name}="):
                    f.write(f"{key_name}={new_value}\n")
                    found = True
                else:
                    f.write(line)
            if not found:
                f.write(f"{key_name}={new_value}\n")

    def open_file(self, filename):
        """Opens a file using the system's default application."""
        try:
            if not os.path.exists(filename):
                with open(filename, "w") as f:
                    f.write(f"# Created {filename}\n")
            
            if os.name == 'nt':  # Windows
                os.startfile(filename)
            elif sys.platform == 'darwin':  # macOS
                subprocess.Popen(['open', filename])
            else:  # Linux
                subprocess.Popen(['xdg-open', filename])
        except Exception as e:
            print(f"Error opening file {filename}: {e}")

    def stop_pipeline(self):
        """Terminates the scraper process."""
        if self.pipeline_process:
            self.pipeline_process.terminate()

    def run_pipeline(self, log_callback, finish_callback):
        """Starts the scraper, runs AI analysis, then sends notifications."""
        try:
            env = os.environ.copy()
            env["PYTHONIOENCODING"] = "utf-8" # Fix for emoji crashes

            startupinfo = None
            if os.name == 'nt':
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = 0 

            # 1. Start the Scraper Subprocess
            self.pipeline_process = subprocess.Popen(
                ["python", "-u", "run_pipeline.py"], 
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, encoding='utf-8', errors='replace',
                env=env, bufsize=1
            )

            # 2. Live Log Streaming to GUI and Terminal
            while True:
                line = self.pipeline_process.stdout.readline()
                if not line: break
                clean_line = line.strip()
                print(clean_line) 
                sys.stdout.flush()
                log_callback(clean_line)

            self.pipeline_process.wait() 
            
            # 3. Update Scan Heartbeat
            finish_ts = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            self.save_auth_value("LAST_SCAN_TIME", finish_ts)
            
            # 4. RUN AI ANALYSIS
            # Crucial: Must finish before Email sends to catch relevant roles
            if self.pipeline_process.returncode == 0:
                self.run_ai_analysis(log_callback)

            # 5. SEND NOTIFICATIONS
            if self.email_enabled and self.pipeline_process.returncode == 0:
                self.check_and_send_notifications()

        except Exception as e:
            log_callback(f"SYSTEM ERROR: {repr(e)}")
        finally:
            self.is_running = False
            finish_callback()

    def get_last_scan_display(self):
        """Retrieves the scan heartbeat."""
        val = self.get_auth_value("LAST_SCAN_TIME")
        return val if val else "Never"

    def run_ai_analysis(self, log_callback):
        from src.brain import JobBrain
        brain = JobBrain()
        
        self.storage.conn.commit()
        cursor = self.storage.conn.cursor()
        
        cursor.execute("SELECT id, title, description FROM jobs WHERE is_relevant = 0")
        pending_jobs = cursor.fetchall()

        for j_id, title, desc in pending_jobs:
            analysis = brain.analyze(title, desc or "")
            if analysis:
                status = 1 if analysis.is_relevant else -1
                
                # --- CORRECT SAVING LOGIC ---
                # We update the NEW columns and keep the description untouched!
                cursor.execute("""
                    UPDATE jobs SET 
                        is_relevant = ?, 
                        ai_reason = ?, 
                        tech_stack = ?,
                        years_required = ?
                    WHERE id = ?
                """, (
                    status, 
                    analysis.reason, 
                    ", ".join(analysis.tech_stack), 
                    analysis.years_required,
                    j_id
                ))
                self.storage.conn.commit()
                log_callback(f"  {'+' if status == 1 else 'x'} {title[:30]}")

    def check_and_send_notifications(self):
        """Processes only AI-approved jobs for email alerts."""
        self.storage.conn.commit()
        cursor = self.storage.conn.cursor()
        
        # Only select jobs that are RELEVANT (1) and haven't been emailed yet (0)
        cursor.execute("""
            SELECT company, title, location, url, found_at 
            FROM jobs 
            WHERE sent_email = 0 AND is_relevant = 1
        """)
        newly_found = [{"company": r[0], "title": r[1], "location": r[2], "url": r[3], "found_at": r[4]} for r in cursor.fetchall()]
        
        if newly_found:
            send_job_email(newly_found, self.user_email)
            # Mark these specific jobs as sent
            cursor.execute("UPDATE jobs SET sent_email = 1 WHERE sent_email = 0 AND is_relevant = 1")
            self.storage.conn.commit()