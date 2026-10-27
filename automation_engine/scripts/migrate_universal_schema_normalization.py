#!/usr/bin/env python3
"""
Universal Schema Normalization Migration Script.

Features:
- Idempotent: Can be run multiple times safely without duplicate edits.
- Narrowly Scoped: Applies canonical normalization rules via FieldNormalizer.
- Backed Up: Automatically creates a timestamped copy of idp_studio.db before any modification.
- Reversible: Supports --rollback <backup_file_path> to restore the database to prior state.
- Audited: Logs all field type changes, option rejections, and provenance metadata.
"""

import sys
import os
import shutil
import sqlite3
import json
import logging
from datetime import datetime
from typing import Dict, Any, List

# Ensure repository root is on PYTHONPATH
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from automation_engine.modules.idp_studio.forms.normalizer import FieldNormalizer

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("migration.universal_normalization")

DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "../modules/idp_studio/idp_studio.db"))


def create_backup(db_path: str) -> str:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = f"{db_path}.bak_universal_{timestamp}"
    shutil.copy2(db_path, backup_path)
    logger.info(f"[Backup] Created database backup at: {backup_path}")
    return backup_path


def rollback_database(backup_path: str, target_db_path: str) -> bool:
    if not os.path.exists(backup_path):
        logger.error(f"[Rollback] Backup file not found: {backup_path}")
        return False
    shutil.copy2(backup_path, target_db_path)
    logger.info(f"[Rollback] Successfully restored {target_db_path} from {backup_path}")
    return True


def run_migration(dry_run: bool = False) -> Dict[str, Any]:
    if not os.path.exists(DB_PATH):
        raise FileNotFoundError(f"Database file not found at: {DB_PATH}")

    if not dry_run:
        backup_path = create_backup(DB_PATH)
    else:
        backup_path = None
        logger.info("[Dry Run] Running in preview mode; no files or database records will be modified.")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("SELECT template_id, template_name, fields_json FROM idp_templates")
    rows = cursor.fetchall()

    migration_summary = {
        "backup_path": backup_path,
        "total_templates_scanned": len(rows),
        "templates_updated": 0,
        "total_corrections_applied": 0,
        "template_reports": []
    }

    for template_id, template_name, fields_json in rows:
        try:
            raw_data = json.loads(fields_json)
        except Exception as e:
            logger.warning(f"Could not parse JSON for template '{template_name}' ({template_id}): {e}")
            continue

        is_list = isinstance(raw_data, list)
        schema_dict = {"fields": raw_data} if is_list else raw_data

        normalized_schema, corrections = FieldNormalizer.normalize_schema(schema_dict)

        if corrections:
            migration_summary["templates_updated"] += 1
            migration_summary["total_corrections_applied"] += len(corrections)

            template_report = {
                "template_id": template_id,
                "template_name": template_name,
                "corrections_count": len(corrections),
                "corrections": corrections
            }
            migration_summary["template_reports"].append(template_report)

            logger.info(f"[{template_name}] Applied {len(corrections)} normalization corrections.")
            for c in corrections:
                logger.info(f"   -> Field '{c.get('field_id')}': {c.get('rule')} ({c.get('reason')})")

            if not dry_run:
                # Preserve original container structure (list or dict)
                updated_json = json.dumps(
                    normalized_schema["fields"] if is_list else normalized_schema,
                    indent=2
                )
                cursor.execute(
                    "UPDATE idp_templates SET fields_json = ? WHERE template_id = ?",
                    (updated_json, template_id)
                )

    if not dry_run:
        conn.commit()
        logger.info(f"[Migration] Committed changes for {migration_summary['templates_updated']} templates.")
    else:
        conn.rollback()
        logger.info("[Dry Run] Rolled back transaction. Database is untouched.")

    conn.close()
    return migration_summary


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Universal Schema Normalization Migration")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without modifying the database")
    parser.add_argument("--rollback", type=str, help="Restore database from a specified backup path")
    args = parser.parse_args()

    if args.rollback:
        rollback_database(args.rollback, DB_PATH)
    else:
        run_migration(dry_run=args.dry_run)
