from .workday import WorkdayFetcher
from .smartrecruiters import SmartRecruitersFetcher
from .greenhouse import GreenhouseFetcher
from .comeet import ComeetFetcher
from .lever import LeverFetcher
from .jobspy_aggr import JobSpyFetcher

class Fetcher:
    def __init__(self):
        # We initialize them once to stay efficient
        self.workday = WorkdayFetcher()
        self.smartrecruiters = SmartRecruitersFetcher()
        self.greenhouse = GreenhouseFetcher()
        self.comeet = ComeetFetcher()
        self.lever = LeverFetcher()
        self.jobspy = JobSpyFetcher()

    def fetch(self, target_config):
        """Your original full-crawl logic"""
        fetcher_type = target_config.get('type')
        
        if fetcher_type == 'workday':
            return self.workday.fetch(target_config)
        elif fetcher_type == 'smartrecruiters':
            return self.smartrecruiters.fetch(target_config)
        elif fetcher_type == 'greenhouse':
            return self.greenhouse.fetch(target_config)
        elif fetcher_type == 'comeet':
            return self.comeet.fetch(target_config)
        elif fetcher_type == 'lever':
            return self.lever.fetch(target_config)
        elif fetcher_type == 'jobspy':
            return self.jobspy.fetch(target_config)
        else:
            print(f"[!] Unknown fetcher type: {fetcher_type}")
            return []

    def fetch_single_batch(self, target_config, offset):
        """NEW: Routes the Round-Robin wave calls"""
        fetcher_type = target_config.get('type')
        
        if fetcher_type == 'workday':
            # This calls the new function we added to workday.py
            return self.workday.fetch_single_batch(target_config, offset)
        
        # For now, other types return empty because we haven't 
        # written batch logic for them yet.
        return [], False