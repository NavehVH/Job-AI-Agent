
# ==============================================================================
# Handles the application GUI actions
# ==============================================================================


import subprocess, os, threading, time, datetime, sys
from src.notifications import send_job_email

class AppEngine:
    def __init__(self, storage):
        self.storage = storage
        self.pipeline_process = None
        self.is_running = False
        self.last_run_timestamp = 0
        self.ai_enabled = False
        self.filter_enabled = True
        
        # Load persistent settings
        self.user_email = self.get_auth_value("RECIPIENT_EMAIL") or "navehhadas@gmail.com"
        auto_val = self.get_auth_value("AUTO_SCAN_ENABLED")
        self.is_auto_mode = True if auto_val == "True" else False
        self.email_enabled = True

    def get_auth_value(self, key_name):
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
        """Executes the self-contained scraper pipeline and logs all output."""
        try:
            # Refresh settings from the authorization file
            self.ai_enabled = self.get_auth_value("AI_ENABLED") == "True"
            self.filter_enabled = self.get_auth_value("FILTER_ENABLED") == "True"

            # Prepare environment variables for the pipeline process
            env = os.environ.copy()
            env["PYTHONIOENCODING"] = "utf-8"
            env["ENABLE_FILTERS"] = "True" if self.filter_enabled else "False"
            env["AI_DISABLED_MODE"] = "True" if not self.ai_enabled else "False"
            env["EMAIL_ENABLED"] = "True" if self.email_enabled else "False"
            env["RECIPIENT_EMAIL"] = self.user_email

            # 3. Prevent black terminal window on Windows
            startupinfo = None
            if os.name == 'nt':
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = 0 

            # 4. Launch the consolidated pipeline
            self.pipeline_process = subprocess.Popen(
                [sys.executable, "-u", "run_pipeline.py"],
                stdout=subprocess.PIPE, 
                stderr=subprocess.STDOUT,
                text=True, 
                encoding='utf-8', 
                errors='replace',
                env=env, 
                bufsize=1,
                startupinfo=startupinfo
            )

            # 5. Continuous log reading
            while True:
                line = self.pipeline_process.stdout.readline()
                if not line:
                    break
                clean_line = line.strip()
                
                if sys.stdout:
                    try:
                        print(clean_line)
                        sys.stdout.flush()
                    except:
                        pass
                
                log_callback(clean_line)

            self.pipeline_process.wait()
            
            if self.pipeline_process.returncode == 0:
                finish_ts = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                self.save_auth_value("LAST_SCAN_TIME", finish_ts)
            else:
                log_callback(f"SYSTEM: Pipeline exited with error code {self.pipeline_process.returncode}")

        except Exception as e:
            err_msg = f"SYSTEM ERROR: {repr(e)}"
            if sys.stdout: print(err_msg)
            log_callback(err_msg)
        finally:
            self.is_running = False
            finish_callback()

    def get_last_scan_display(self):
        """Retrieves the scan heartbeat."""
        val = self.get_auth_value("LAST_SCAN_TIME")
        return val if val else "Never"