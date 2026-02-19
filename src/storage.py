
# ==============================================================================
# Handles the SQLite creation and saving jobs correctly
# ==============================================================================


import sqlite3

class JobStorage:
    def __init__(self, db_path="jobs.db"):
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.cursor = self.conn.cursor()
        self._initialize_db()

    def _initialize_db(self):
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY,
                company TEXT,
                title TEXT,
                location TEXT,
                url TEXT,
                posted_on TEXT,
                description TEXT,
                is_relevant INTEGER DEFAULT 0,
                ai_reason TEXT,
                tech_stack TEXT,
                years_required INTEGER,
                sent_email INTEGER DEFAULT 0,
                found_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        self.conn.commit()

    def job_exists(self, job_id):
        self.cursor.execute("SELECT 1 FROM jobs WHERE id = ?", (job_id,))
        return self.cursor.fetchone() is not None

    def save_job(self, job, relevance=0):
        """
        Saves a job. 
        relevance=1 makes it visible in GUI immediately (used when AI is OFF).
        relevance=0 hides it for AI analysis (used when AI is ON).
        """
        try:
            self.cursor.execute("""
                INSERT INTO jobs (id, company, title, location, url, posted_on, description, is_relevant)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                job['id'], job['company'], job['title'], job['location'], 
                job['url'], job['posted_on'], job.get('description', ''),
                relevance
            ))
            self.conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False