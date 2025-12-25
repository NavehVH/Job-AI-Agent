import subprocess
import os
import threading
import time
import datetime
from src.notifications import send_job_email

class AppEngine:
    def __init__(self, storage):
        self.storage = storage
        self.pipeline_process = None
        self.is_running = False
        self.email_enabled = True
        self.user_email = "navehhadas@gmail.com"
        self.is_auto_mode = False

    def get_db_last_run(self):
        """Original DB check logic."""
        cursor = self.storage.conn.cursor()
        try:
            cursor.execute("SELECT MAX(found_at) FROM jobs")
            db_res = cursor.fetchone()[0]
            return db_res.split(" ")[1] if db_res else "Never"
        except: return "Never"

    def stop_pipeline(self):
        """Original termination logic."""
        if self.pipeline_process:
            self.pipeline_process.terminate()

    def run_pipeline(self, log_callback, finish_callback):
        """Original subprocess and notification logic."""
        try:
            # Hide console on Windows exactly as requested
            startupinfo = None
            if os.name == 'nt':
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = 0 

            self.pipeline_process = subprocess.Popen(
                ["python", "-u", "run_pipeline.py"], 
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                startupinfo=startupinfo,
                bufsize=1
            )

            # Stream logs to GUI
            while True:
                line = self.pipeline_process.stdout.readline()
                if not line: break
                log_callback(line.strip())

            self.pipeline_process.wait() 

            # Original notification logic
            if self.email_enabled and self.pipeline_process.returncode == 0:
                cursor = self.storage.conn.cursor()
                cursor.execute("SELECT company, title, location, url, found_at FROM jobs WHERE sent_email = 0")
                newly_found = [{"company": r[0], "title": r[1], "location": r[2], "url": r[3], "found_at": r[4]} for r in cursor.fetchall()]
                
                if newly_found:
                    send_job_email(newly_found, self.user_email)
                    cursor.execute("UPDATE jobs SET sent_email = 1 WHERE sent_email = 0")
                    self.storage.conn.commit()

        except Exception as e:
            log_callback(f"Pipeline Error: {e}")
        finally:
            self.is_running = False
            finish_callback()