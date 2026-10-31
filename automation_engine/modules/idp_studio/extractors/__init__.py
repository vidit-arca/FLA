from .classifier import classify_document, detect_operative_statutory_branch
from .spatial import (
    apply_spatial_overrides,
    get_spatial_rules,
    get_effective_rules,
    get_scenario_lexicon,
    extract_text_from_spatial_meta,
)
from .fla_bridge import FLABridgeAdapter

__all__ = [
    "classify_document",
    "detect_operative_statutory_branch",
    "apply_spatial_overrides",
    "get_spatial_rules",
    "get_effective_rules",
    "get_scenario_lexicon",
    "extract_text_from_spatial_meta",
    "FLABridgeAdapter",
]
