"""Apply forward-only, non-destructive SQLite migrations."""

from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DEFAULT_DB = ROOT / "data" / "platforms.sqlite3"
MIGRATIONS = ROOT / "migrations"


def sql_statements(script: str):
    """Yield complete SQLite statements without committing between them."""
    buffer = ""
    for line in script.splitlines(keepends=True):
        buffer += line
        if sqlite3.complete_statement(buffer):
            statement = buffer.strip()
            if statement:
                yield statement
            buffer = ""
    if buffer.strip():
        raise sqlite3.OperationalError("migration ends with an incomplete SQL statement")


def migrate(db_path: Path = DEFAULT_DB) -> list[str]:
    db_path = Path(db_path)
    if not db_path.is_file():
        raise FileNotFoundError(f"数据库不存在：{db_path}")
    applied_now: list[str] = []
    with sqlite3.connect(db_path) as db:
        db.execute("PRAGMA foreign_keys = ON")
        db.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations ("
            "name TEXT PRIMARY KEY, applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)"
        )
        applied = {row[0] for row in db.execute("SELECT name FROM schema_migrations")}
        for path in sorted(MIGRATIONS.glob("*.sql")):
            if path.name in applied:
                continue
            try:
                db.execute("BEGIN IMMEDIATE")
                for statement in sql_statements(path.read_text(encoding="utf-8")):
                    db.execute(statement)
                db.execute("INSERT INTO schema_migrations(name) VALUES (?)", (path.name,))
            except Exception:
                db.rollback()
                raise
            else:
                db.commit()
            applied_now.append(path.name)
    return applied_now


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="执行 SQLite 数据库迁移")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    args = parser.parse_args()
    changes = migrate(args.db)
    print("已执行：" + "、".join(changes) if changes else "数据库已经是最新结构。")
