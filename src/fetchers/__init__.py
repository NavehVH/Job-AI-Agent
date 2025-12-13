from .workday import WorkdayFetcher
from .smartrecruiters import SmartRecruitersFetcher
from .greenhouse import GreenhouseFetcher
from .comeet import ComeetFetcher
from .lever import LeverFetcher
from .jobspy_aggr import JobSpyFetcher

class Fetcher:
    def fetch(self, target_config):
        fetcher_type = target_config.get('type')
        
        if fetcher_type == 'workday':
            return WorkdayFetcher().fetch(target_config)
        elif fetcher_type == 'smartrecruiters':
            return SmartRecruitersFetcher().fetch(target_config)
        elif fetcher_type == 'greenhouse':
            return GreenhouseFetcher().fetch(target_config)
        elif fetcher_type == 'comeet':
            return ComeetFetcher().fetch(target_config)
        elif fetcher_type == 'lever':      # <--- NEW LOGIC
            return LeverFetcher().fetch(target_config)
        elif fetcher_type == 'jobspy':
            return JobSpyFetcher().fetch(target_config)
        else:
            print(f"[!] Unknown fetcher type: {fetcher_type}")
            return []