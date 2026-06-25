from typing import Any
from .modules.fla_module import FLAComparisonModule

class ComparisonPlatformManager:
    def __init__(self):
        self.modules = {
            "fla": FLAComparisonModule()
        }

    def run_comparison(self, module_name: str, source_path: str, target_path: str) -> Any:
        if module_name not in self.modules:
            raise ValueError(f"Unknown comparison module: {module_name}")
            
        engine = self.modules[module_name]
        return engine.compare(source_path, target_path)
