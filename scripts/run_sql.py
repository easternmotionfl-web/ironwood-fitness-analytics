"""Run every statement in a .sql file against the Ironwood database and print each result.

Usage, from the repo root with the virtual environment active:
    python scripts/run_sql.py checks/01_reconcile.sql

Start each query with a comment line (-- 1. what it checks); it is printed as the title.
Don't put semicolons inside comments: they split the file into statements.
"""
import sys
from pathlib import Path

import duckdb

DB_PATH = Path(__file__).resolve().parents[1] / "data" / "ironwood.duckdb"


def main(sql_file: str) -> None:
    text = Path(sql_file).read_text()
    statements = [s.strip() for s in text.split(";")]
    with duckdb.connect(str(DB_PATH), read_only=True) as con:
        for statement in statements:
            code_lines = [ln for ln in statement.splitlines() if ln.strip() and not ln.strip().startswith("--")]
            if not code_lines:
                continue
            title = statement.splitlines()[0] if statement.startswith("--") else code_lines[0]
            print(f"\n{title}")
            result = con.sql(statement)
            if result is not None:
                result.show()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("Usage: python scripts/run_sql.py <file.sql>")
    main(sys.argv[1])
