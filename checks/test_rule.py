import sys
sys.path.append('automation_engine')
from automation_engine.modules.fla.rule_engine import RuleEngine
extracted_data = {
    "fdi_investors_count": 12,
    "fdi_investor_1_name": "Pontaq Nominees Limited",
    "fdi_investor_1_country": "United Kingdom",
    "fdi_investor_1_equity_percent_py": 1.007,
    "fdi_investor_1_equity_percent_fy": 1.007,
}
engine = RuleEngine("automation_engine/rules_config.json")
cells = engine.evaluate_all(extracted_data)
print("B17:", cells["Section III"].get("B17"))
print("B29:", cells["Section III"].get("B29"))
