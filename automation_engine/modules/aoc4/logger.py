import logging
import os
from logging.handlers import RotatingFileHandler

_MODULE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(_MODULE_DIR, "logs")

#: Each AOC-4 engine persists to its OWN log file so the Common Error and
#: Compliance (and RPT / Rule-Engine) histories stay separate and auditable.
LOG_FILES = {
    "AOC4_CommonErrorEngine": "aoc4_common_error.log",
    "AOC4_ComplianceEngine": "aoc4_compliance.log",
    "AOC4_RPTLoansEngine": "aoc4_rpt_loans.log",
    "AOC4_RuleEngine": "aoc4_rule_engine.log",
    "AOC4_LLMJudge": "aoc4_llm_judge.log",
    "AOC4": "aoc4_system.log",
}
DEFAULT_LOG_FILE = "aoc4_system.log"

_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
_MAX_BYTES = 5 * 1024 * 1024   # 5 MB per file
_BACKUP_COUNT = 5              # keep aoc4_*.log.1 .. .5

_BAR = "=" * 90


def _ensure_log_dir():
    os.makedirs(LOG_DIR, exist_ok=True)
    return LOG_DIR


def get_aoc4_logger(name="AOC4"):
    """Return the AOC-4 logger for ``name`` that persists to a per-engine file.

    ``AOC4_CommonErrorEngine`` -> ``logs/aoc4_common_error.log``
    ``AOC4_ComplianceEngine``  -> ``logs/aoc4_compliance.log``
    ``AOC4_RPTLoansEngine``    -> ``logs/aoc4_rpt_loans.log``
    ``AOC4_RuleEngine``        -> ``logs/aoc4_rule_engine.log``
    ``AOC4_LLMJudge``          -> ``logs/aoc4_llm_judge.log``
    anything else              -> ``logs/aoc4_system.log``

    Handlers are attached only once per logger and a rotating file handler keeps
    each file bounded so long-running/peated usage never fills the disk.
    """
    logger = logging.getLogger(name)

    # Avoid adding multiple handlers if logger is already configured
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        _ensure_log_dir()
        log_file = os.path.join(LOG_DIR, LOG_FILES.get(name, DEFAULT_LOG_FILE))

        file_handler = RotatingFileHandler(
            log_file, maxBytes=_MAX_BYTES, backupCount=_BACKUP_COUNT,
            encoding="utf-8")
        file_handler.setFormatter(logging.Formatter(_FORMAT))

        logger.addHandler(file_handler)
        # Don't bubble into the root logger (which could duplicate/redirect).
        logger.propagate = False

    return logger


def log_run_start(logger, engine, details=None):
    """Write a delimited banner marking the start of ONE engine usage.

    Every call to an engine's ``execute`` records one of these blocks, so each
    run (each 'usage') is clearly separated in the log file.
    """
    logger.info(_BAR)
    logger.info("RUN START | engine=%s", engine)
    for key, value in (details or {}).items():
        logger.info("    input  | %s = %r", key, value)
    return None


def log_run_end(logger, engine, flags=None, details=None):
    """Write the flag summary and a closing banner for one engine usage."""
    if flags is not None:
        counts = {}
        for flag in flags:
            status = flag.get("status")
            counts[status] = counts.get(status, 0) + 1
        logger.info("    result | %d flag(s) -> %s", len(flags), counts)
    for key, value in (details or {}).items():
        logger.info("    output | %s = %r", key, value)
    logger.info("RUN END   | engine=%s", engine)
    logger.info(_BAR)


def log_flags(logger, flags, indent="    "):
    """Persist each individual flag (used where per-decision detail is wanted)."""
    for flag in flags or []:
        logger.info(
            "%sflag | id=%s | status=%s | value=%r | %s | reason=%s",
            indent,
            flag.get("id") or flag.get("rule_id"),
            flag.get("status"),
            flag.get("user_value"),
            str(flag.get("particulars", ""))[:70],
            flag.get("rationale") or flag.get("reason"),
        )

