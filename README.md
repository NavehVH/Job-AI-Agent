# AI Agent Job Hunter

An AI agent for automated job search. Still working on it and adding ideas.
This tool scans major tech company career sites for Junior / Student positions in Israel, or any role type you configure.

The project is designed to solve the "Junior Problem": endless scrolling through career sites only to discover roles that secretly require years of experience.

The agent fetches job data from multiple platforms, filters strictly for Israel, and uses OpenAI gpt-4o-mini to analyze the actual job description (not just the title) in order to decide whether a role is truly entry-level and worth notifying about.

---

## Next steps to add to this project
Right now we get data from around 40 companies and ability to read linkedin 24 last hours posts. The next phase focuses on transforming the sequential data collector into a robust, high-performance, and cost-efficient AI agent. This involves transitioning to a multi-threaded architecture consisting of four distinct fetcher/analysis threads to maximize concurrency and bypass platform limitations (Workday heavy load, JobSpy delays). To ensure cost-efficiency, we will implement Pre-Database Filtering (simple text checks for senior-level keywords like 'VP', 'Director', 'בכיר') to discard irrelevant jobs before they are stored and processed. The core goal is the creation and integration of the AI Brain, which will use the OpenAI API to perform the final, sophisticated junior/seniority classification. Following this, the agent will gain a professional UI Dashboard to display the most relevant classified jobs and an integrated Notification System to alert the user immediately upon a highly-relevant job being posted.


## Features

### Multi-Platform and Comprehensive Coverage

The agent adapts its fetching strategy to four different Applicant Tracking Systems (ATS) and aggregates results from job boards to provide a broad and realistic market view.

#### Direct Company Sources (ATS)
- Workday (Intel, Nvidia, Dell, etc.)
- Greenhouse (Wiz, Riskified, Melio, etc.)
- Comeet (Fiverr, Moon Active, Team8, etc.)
- SmartRecruiters (CyberArk, Western Digital, etc.)

#### Job Board Aggregation
- Uses JobSpy to scan LinkedIn, Glassdoor, and similar boards for new jobs added in the last 24 hours
- Helps detect so-called hidden junior roles from companies not explicitly targeted

---

### Intelligent Filtering and Analysis

- AI-powered vetting: GPT reads the full job description and searches for experience indicators such as 0-2 years, new grad, student, or intern
- Title override: misleading titles are ignored in favor of description-based analysis
- Strict location filtering: only Israel-based roles are analyzed (Tel Aviv, Haifa, Yokneam, etc.)
- Deduplication: an SQLite database ensures each job is stored only once, even if found via multiple sources

---

### Performance and Architecture

- Lazy loading: full job descriptions are fetched only for relevant Israel-based roles to reduce bandwidth and API usage
- Modular design: adding a new company or source requires only a configuration change

---

## Tech Stack

- Language: Python 3.10+
- Database: SQLite (local, zero-configuration)
- AI Engine: OpenAI API (gpt-4o-mini)
- Libraries:
  - requests
  - pydantic
  - sqlite3
  - python-jobspy
  - pandas

---

## Installation

### 1) Clone the repository

### 2) Install dependencies
```bash
pip install requests openai pydantic python-jobspy pandas
```

### 3) Set up OpenAI API key
1. Obtain an API key from the OpenAI Platform
2. Create a file named openai_key.txt in the project root
3. Paste your key inside (single line, starting with sk-)
4. This file is git-ignored for security

---

## Usage

### 1) Run the agent
```bash
python run_pipeline.py
```

### 2) View results
```bash
sqlite3 jobs.db "SELECT company, title, location, url FROM jobs WHERE is_junior = 1;"
```

---

## Configuration

Edit:
```
config/targets.json
```

### Example: Greenhouse company
```json
{
  "name": "Wiz",
  "board_token": "wizinc",
  "type": "greenhouse"
}
```

### Example: Job board aggregation
```json
{
  "name": "Aggregator: Broad Search",
  "type": "jobspy",
  "sites": ["linkedin", "glassdoor"],
  "search_term": "Software Engineer",
  "location": "Israel",
  "limit": 30
}
```

---

## Project Structure

```
.
├── config/
│   └── targets.json
├── src/
│   ├── fetchers/
│   │   ├── __init__.py
│   │   ├── workday.py
│   │   ├── greenhouse.py
│   │   ├── comeet.py
│   │   └── jobspy_aggr.py
│   ├── brain.py
│   └── storage.py
├── run_pipeline.py
├── jobs.db
└── openai_key.txt
```

---

## License

This project is open-source.  
Feel free to fork, extend, and help the junior developer community.
