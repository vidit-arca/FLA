"""
IDP Studio Module.

Organized into structured domain subpackages:
  - core: Database engine, session management, and SQLAlchemy ORM models.
  - forms: Instruction kit parser, form registry, and dynamic semantic form filler.
  - extractors: Document classifier, spatial extractor, and FLA bridge adapter.
  - dom_learner: Intelligent DOM learning engine (untouched).
"""

from .core.db import engine, SessionLocal, Base, get_db, init_db, DB_PATH
from .core.models import SchemaAliasRule, IdpTemplate, DomExtractionRule
from .forms.kit_parser import InstructionKitParser
from .forms.registry import FormRegistry
from .forms.filler import DynamicFormFiller
from .extractors.classifier import classify_document, detect_operative_statutory_branch
from .extractors.spatial import apply_spatial_overrides, get_spatial_rules, get_effective_rules, get_scenario_lexicon
from .extractors.fla_bridge import FLABridgeAdapter
from .router import router

__all__ = [
    # Core
    "engine",
    "SessionLocal",
    "Base",
    "get_db",
    "init_db",
    "DB_PATH",
    "SchemaAliasRule",
    "IdpTemplate",
    "DomExtractionRule",
    # Forms
    "InstructionKitParser",
    "FormRegistry",
    "DynamicFormFiller",
    # Extractors
    "classify_document",
    "detect_operative_statutory_branch",
    "apply_spatial_overrides",
    "get_spatial_rules",
    "get_effective_rules",
    "get_scenario_lexicon",
    "FLABridgeAdapter",
    # Router
    "router",
]
