from abc import ABC, abstractmethod
from typing import Any

class BaseComparisonPlatformModule(ABC):
    @abstractmethod
    def compare(self, source_path: str, target_path: str) -> Any:
        """
        Compare the source and target files and return a structured report.
        """
        pass
