import sqlite3
import json

class JobStorage:
    def __init__(self, db_path="jobs.db"):
        self.conn = sqlite3.connect(db_path)
        self.cursor = self.conn.cursor()
        self._initialize_db()

    def _initialize_db(self):
        """Creates the table if it doesn't exist."""
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY,
                company TEXT,
                title TEXT,
                location TEXT,
                url TEXT,
                posted_on TEXT,
                description TEXT,  -- <--- NEW COLUMN
                is_junior BOOLEAN DEFAULT NULL,
                tech_stack TEXT,
                found_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        self.conn.commit()

    def job_exists(self, job_id):
        self.cursor.execute("SELECT 1 FROM jobs WHERE id = ?", (job_id,))
        return self.cursor.fetchone() is not None

    def save_job(self, job):
        try:
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
                job.get('description', 'No description found') # <--- Save it!
            ))
            self.conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False