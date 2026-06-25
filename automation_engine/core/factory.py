import os
import importlib

class ModuleFactory:
    @staticmethod
    def get_module(module_name: str):
        """
        Returns the parser class, rule engine class, validator class, 
        and paths to the config and excel templates for a specific module.
        """
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
        if module_name == "fla":
            # Dynamic imports to avoid circular dependencies and load only what's needed
            from automation_engine.modules.fla.parser import DocumentParser
            from automation_engine.modules.fla.rule_engine import RuleEngine
            from automation_engine.modules.fla.validator import ReturnValidator
            
            return {
                "parser": DocumentParser,
                "rule_engine": RuleEngine,
                "validator": ReturnValidator,
                "config_path": os.path.join(base_dir, "modules", "fla", "rules_config.json"),
                "excel_dir": os.path.join(base_dir, "modules", "fla", "excel")
            }
        elif module_name == "aoc4":
            from automation_engine.modules.aoc4.parser import AOC4Parser
            from automation_engine.modules.aoc4.rule_engine import AOC4RuleEngine
            from automation_engine.modules.aoc4.validator import AOC4Validator
            
            return {
                "parser": AOC4Parser,
                "rule_engine": AOC4RuleEngine,
                "validator": AOC4Validator,
                "config_path": os.path.join(base_dir, "modules", "aoc4", "rules_config.json"),
                "excel_dir": os.path.join(base_dir, "modules", "aoc4", "excel")
            }
        else:
            raise ValueError(f"Unknown module type: {module_name}")
