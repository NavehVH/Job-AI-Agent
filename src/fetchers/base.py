from abc import ABC, abstractmethod

class BaseFetcher(ABC):
    """
    Abstract Base Class that all fetchers must inherit from.
    Enforces that every fetcher has a fetch() method.
    """
    
    @abstractmethod
    def fetch(self, target_config):
        """
        Input: target_config (dict)
        Output: List of job dictionaries
        """
        pass