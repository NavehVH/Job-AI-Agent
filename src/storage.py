import sqlite3
import json

class JobStorage:
    def __init__(self, db_path="jobs.db"):
        self.conn = sqlite3.connect(db_path, check_same_thread=False) # Added for GUI safety
        self.cursor = self.conn.cursor()
        self._initialize_db()

    def _initialize_db(self):
        """Creates the table with specific AI columns."""
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY,
                company TEXT,
                title TEXT,
                location TEXT,
                url TEXT,
                posted_on TEXT,
                description TEXT,           -- We keep the ORIGINAL here
                is_relevant INTEGER DEFAULT 0,
                ai_reason TEXT,             -- NEW: AI summary
                tech_stack TEXT,            -- NEW: List of tech
                years_required INTEGER,     -- NEW: Experience count
                sent_email INTEGER DEFAULT 0,
                found_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        self.conn.commit()

    def job_exists(self, job_id):
        self.cursor.execute("SELECT 1 FROM jobs WHERE id = ?", (job_id,))
        return self.cursor.fetchone() is not None

    def save_job(self, job):
        try:
            # We don't need to specify is_relevant here, it defaults to 0
            self.cursor.execute("""
                INSERT INTO jobs (id, company, title, location, url, posted_on, description)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                job['id'], 
                job['company'], 
                job['title'], 
                job['location'], 
                job['url'], 
                job['posted_on'],
                job.get('description', 'No description found')
            ))
            self.conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False