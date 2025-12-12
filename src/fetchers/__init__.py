from .workday import WorkdayFetcher
from .smartrecruiters import SmartRecruitersFetcher

class Fetcher:
    """
    Factory Class: Decides which specific fetcher to use.
    """
    def fetch(self, target_config):
        fetcher_type = target_config.get('type')
        
        if fetcher_type == 'workday':
            return WorkdayFetcher().fetch(target_config)
        
        elif fetcher_type == 'smartrecruiters':
            return SmartRecruitersFetcher().fetch(target_config)
            
        else:
            print(f"[!] Unknown fetcher type: {fetcher_type}")
            return []