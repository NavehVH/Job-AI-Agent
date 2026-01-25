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
        """Executes the scraper and handles the post-processing logic."""
        try:
            # Refresh toggle states from the authorization file
            self.ai_enabled = self.get_auth_value("AI_ENABLED") == "True"
            self.filter_enabled = self.get_auth_value("FILTER_ENABLED") == "True"

            # Prepare the environment variables for the child process
            env = os.environ.copy()
            env["PYTHONIOENCODING"] = "utf-8"
            env["ENABLE_FILTERS"] = "True" if self.filter_enabled else "False"
            
            # THE FIX: Tell the scraper if AI is OFF so it can auto-approve jobs
            env["AI_DISABLED_MODE"] = "True" if not self.ai_enabled else "False"

            # Hide the black terminal window on Windows platforms
            startupinfo = None
            if os.name == 'nt':
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = 0 

            # Start the scraper process using the bundled Python executable
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

            # Read the scraper output in real-time
            while True:
                line = self.pipeline_process.stdout.readline()
                if not line:
                    break
                clean_line = line.strip()
                
                # Use your existing dual logging style, but with EXE crash protection
                if sys.stdout:
                    print(clean_line) 
                    try:
                        sys.stdout.flush()
                    except:
                        pass
                
                log_callback(clean_line)

            # Wait for the scraper to finish
            self.pipeline_process.wait()
            
            # Record the scan time
            finish_ts = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            self.save_auth_value("LAST_SCAN_TIME", finish_ts)
            
            # --- POST-PROCESSING LOGIC ---
            if self.pipeline_process.returncode == 0:
                if self.ai_enabled:
                    # Run AI Brain Analysis if the toggle is ON
                    if self.get_auth_value("OPENAI_API_KEY"):
                        self.run_ai_analysis(log_callback)
                    else:
                        msg = "SYSTEM: AI enabled but API Key is missing in authorization.txt"
                        if sys.stdout: print(msg)
                        log_callback(msg)
                else:
                    # Logic when AI is OFF: Scraper already marked jobs as relevant
                    msg = "SYSTEM: AI Processing is OFF. Jobs automatically approved for Feed."
                    if sys.stdout: print(msg)
                    log_callback(msg)

            # Always check for email notifications if the run was successful
            if self.email_enabled and self.pipeline_process.returncode == 0:
                self.check_and_send_notifications()
                
            final_msg = "\n--- ALL SYSTEMS COMPLETE ---"
            if sys.stdout: print(final_msg)
            log_callback(final_msg)

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

    def run_ai_analysis(self, log_callback):
        from src.brain import JobBrain
        brain = JobBrain()
        
        self.storage.conn.commit()
        cursor = self.storage.conn.cursor()
        
        # FIX: Use utcnow() so it matches the UTC timestamps in the DB
        now_utc = datetime.datetime.now(datetime.timezone.utc)
        time_threshold = (now_utc - datetime.timedelta(minutes=20)).strftime('%Y-%m-%d %H:%M:%S')
        
        msg = "[*] Starting AI Brain Analysis..."
        print(msg)
        log_callback(msg)
        
        # DIAGNOSTIC: Check if any unprocessed jobs exist at all before the time filter
        cursor.execute("SELECT COUNT(*) FROM jobs WHERE is_relevant = 0")
        total_unprocessed = cursor.fetchone()[0]
        
        # The actual filtered query
        cursor.execute("""
            SELECT id, title, description 
            FROM jobs 
            WHERE is_relevant = 0 AND found_at > ?
        """, (time_threshold,))
        
        pending_jobs = cursor.fetchall()
        
        if not pending_jobs:
            msg = f"AI: Found {total_unprocessed} total pending jobs, but 0 within the 20m window."
            print(msg)
            log_callback(msg)
            return

        for j_id, title, desc in pending_jobs:
            analysis = brain.analyze(title, desc or "")
            if analysis:
                status = 1 if analysis.is_relevant else -1
                
                # Update specific AI columns in the database
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
                
                # Formulate the result log
                log_line = f"  {'RELEVANT' if status == 1 else 'SKIPPED'}: {title[:30]}"
                print(log_line) # <--- THIS PRINT SHOWS IN VS CODE
                log_callback(log_line)
                
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