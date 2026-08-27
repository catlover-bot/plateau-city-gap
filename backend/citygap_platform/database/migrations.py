"""Apply immutable SQL migrations and record their checksums.

The SQL files intentionally own their transactions.  The runner therefore uses an
autocommit connection and records a migration only after the file's COMMIT succeeds.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import re
from pathlib import Path

MIGRATION_NAME = re.compile(r"^[0-9]{3}_[a-z0-9_]+\.sql$")


def migration_files(directory: str | Path) -> list[Path]:
    root = Path(directory)
    return sorted(path for path in root.glob("*.sql") if MIGRATION_NAME.fullmatch(path.name))


def checksum(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def apply_migrations(database_url: str, directory: str | Path) -> list[str]:
    """Apply pending migrations and reject an edited migration already in the DB."""

    import psycopg

    applied: list[str] = []
    with psycopg.connect(database_url, autocommit=True) as connection:
        connection.execute(
            """CREATE TABLE IF NOT EXISTS schema_migrations (
                   version text PRIMARY KEY,
                   checksum_sha256 char(64) NOT NULL,
                   applied_at timestamptz NOT NULL DEFAULT now()
               )"""
        )
        existing = dict(
            connection.execute(
                "SELECT version, checksum_sha256 FROM schema_migrations ORDER BY version"
            ).fetchall()
        )
        for path in migration_files(directory):
            digest = checksum(path)
            recorded = existing.get(path.name)
            if recorded is not None:
                if recorded.strip() != digest:
                    raise RuntimeError(f"Applied migration checksum changed: {path.name}")
                continue
            connection.execute(path.read_text(encoding="utf-8"), prepare=False)
            connection.execute(
                "INSERT INTO schema_migrations (version, checksum_sha256) VALUES (%s, %s)",
                (path.name, digest),
            )
            applied.append(path.name)
    return applied


def migration_status(database_url: str, directory: str | Path) -> dict[str, object]:
    import psycopg

    expected = {path.name: checksum(path) for path in migration_files(directory)}
    try:
        with psycopg.connect(database_url) as connection:
            rows = connection.execute(
                "SELECT version, checksum_sha256 FROM schema_migrations ORDER BY version"
            ).fetchall()
    except psycopg.Error:
        return {"ready": False, "expected": sorted(expected), "applied": [], "problems": ["unavailable"]}
    actual = {name: digest.strip() for name, digest in rows}
    problems = [f"missing:{name}" for name in expected.keys() - actual.keys()]
    problems.extend(f"unexpected:{name}" for name in actual.keys() - expected.keys())
    problems.extend(
        f"checksum:{name}" for name in expected.keys() & actual.keys() if expected[name] != actual[name]
    )
    return {
        "ready": not problems,
        "expected": sorted(expected),
        "applied": sorted(actual),
        "problems": sorted(problems),
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="CITY GAP migration runner")
    parser.add_argument("command", choices=("upgrade", "status"))
    parser.add_argument(
        "--database-url",
        default=os.getenv("CITYGAP_DATABASE_URL"),
        help="PostgreSQL URL (or CITYGAP_DATABASE_URL)",
    )
    parser.add_argument("--directory", default="infra/migrations")
    return parser


def main() -> None:
    args = _parser().parse_args()
    if not args.database_url:
        raise SystemExit("CITYGAP_DATABASE_URL or --database-url is required")
    if args.command == "upgrade":
        for name in apply_migrations(args.database_url, args.directory):
            print(f"applied {name}")
    else:
        status = migration_status(args.database_url, args.directory)
        print(status)
        raise SystemExit(0 if status["ready"] else 1)


if __name__ == "__main__":
    main()
