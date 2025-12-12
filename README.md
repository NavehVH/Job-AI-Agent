# AI Agent Job Hunter

An AI Agent for job search. Automated intelligent agent that scans major tech company career sites for Junior/Student positions in Israel or whatever role type you want to define it to search.

This project is a Python-based tool designed to solve the "Junior Problem" (My current problem): endless scrolling through career sites only to find roles that require 0 years of experience.

The agent fetches jobs from multiple platforms (Workday, SmartRecruiters), filters strictly for Israel, and uses OpenAI's `gpt-4o-mini` to analyze the actual job description (not just the title) to determine whether a role is truly entry-level and send a notification.

## Features

### Multi-Platform Support
Automatically adapts to different career site technologies:
- Workday (Nvidia, Intel, Dell, etc.)
- SmartRecruiters (CyberArk, Western Digital, etc.)

### Smart Filtering
- Location filtering: strict filtering for Israel (Tel Aviv, Haifa, Yokneam, etc.)
- AI analysis: GPT reads the full job description
- Deduplication: SQLite database ensures you are never notified twice about the same job

### Performance and Architecture
- Lazy loading: full job descriptions are fetched only for relevant Israel-based jobs
- Modular design: new companies can be added easily via a JSON config file

## Tech Stack
- Language: Python 3.10+
- Database: SQLite (zero-config, local)
- AI Engine: OpenAI API (`gpt-4o-mini`)
- Libraries: `requests`, `pydantic`, `sqlite3`

## Installation

### 1) Clone the repository

### 2) Install dependencies
```bash
pip install requests openai pydantic
```

### 3) Set up OpenAI API key
1. Get an API key from the OpenAI Platform
2. Create a file named `openai_key.txt` in the project root
3. Paste your key inside (single line, starts with `sk-`)
4. This file is git-ignored for security

## Usage

### 1) Run the agent
This starts the full pipeline:
- fetch jobs
- filter for Israel
- analyze with AI
- save results to the database

```bash
python run_pipeline.py
```

### 2) View results
All matches are saved to `jobs.db`.

Using the SQLite CLI:
```bash
sqlite3 jobs.db "SELECT company, title, location FROM jobs WHERE is_junior = 1;"
```

You can also open the database using any SQLite GUI viewer.

## Configuration
To add more companies, edit:
```
config/targets.json
```

### Example: Workday company
```json
{
  "name": "Intel",
  "url": "https://intel.wd1.myworkdayjobs.com/wday/cxs/intel/External/jobs",
  "type": "workday"
}
```

### Example: SmartRecruiters company
```json
{
  "name": "CyberArk",
  "company_id": "Cyberark1",
  "type": "smartrecruiters"
}
```

## Project Structure
```
.
├── config/
│   └── targets.json        # List of companies to scan
├── src/
│   ├── fetchers/
│   │   ├── __init__.py     # Factory / router
│   │   ├── base.py         # Abstract base class
│   │   ├── workday.py
│   │   └── smartrecruiters.py
│   ├── brain.py            # OpenAI integration
│   └── storage.py          # SQLite database layer
├── run_pipeline.py         # Main entry point
├── jobs.db                 # Local database (auto-created)
└── openai_key.txt          # OpenAI API key (git-ignored)
```

## License
This project is open-source.
Feel free to fork, extend, and help the junior developer community.
