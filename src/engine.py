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

    def stop_pipeline(self):
        """Terminates the scraper process."""
        if self.pipeline_process:
            self.pipeline_process.terminate()

    def run_pipeline(self, log_callback, finish_callback):
        """Starts the scraper with UTF-8 and saves heartbeat."""
        try:
            env = os.environ.copy()
            env["PYTHONIOENCODING"] = "utf-8" # Fix for emoji crashes

            startupinfo = None
            if os.name == 'nt':
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = 0 

            self.pipeline_process = subprocess.Popen(
                ["python", "-u", "run_pipeline.py"], 
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, encoding='utf-8', errors='replace',
                env=env, bufsize=1
            )

            while True:
                line = self.pipeline_process.stdout.readline()
                if not line: break
                clean_line = line.strip()
                print(clean_line) # Mirror to VSC Terminal
                sys.stdout.flush()
                log_callback(clean_line)

            self.pipeline_process.wait() 
            
            # Save the finish time to text file (Local Time)
            finish_ts = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            self.save_auth_value("LAST_SCAN_TIME", finish_ts)
            
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

    def check_and_send_notifications(self):
        """Processes new jobs for email."""
        cursor = self.storage.conn.cursor()
        cursor.execute("SELECT company, title, location, url, found_at FROM jobs WHERE sent_email = 0")
        newly_found = [{"company": r[0], "title": r[1], "location": r[2], "url": r[3], "found_at": r[4]} for r in cursor.fetchall()]
        if newly_found:
            send_job_email(newly_found, self.user_email)
            cursor.execute("UPDATE jobs SET sent_email = 1 WHERE sent_email = 0")
            self.storage.conn.commit()