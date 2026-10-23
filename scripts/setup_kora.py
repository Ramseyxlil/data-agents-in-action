"""Build Kora's local database.

Run it from the repo root:

    python scripts/setup_kora.py

Add --force to rebuild, --parquet to also export Parquet files, and
--noise-tables N to add N extra tables that mean nothing (chapter 5).
"""

import argparse
import sys
from pathlib import Path

# The repo root is one level up from scripts/. Python only looks in
# scripts/ by default, so we add the root to find the kora package.
REPO_ROOT = Path(__file__).resolve().parent.parent


def check_python_version():
    # Fail early so readers see a clear message, not a stack trace
    # from some newer feature deep inside the code.
    if sys.version_info < (3, 11):
        found = ".".join(str(part) for part in sys.version_info[:3])
        print(
            f"This project needs Python 3.11 or newer. "
            f"You are running Python {found}."
        )
        print("Install a newer Python, then create a fresh .venv.")
        sys.exit(1)


def parse_args(argv):
    parser = argparse.ArgumentParser(
        description="Build Kora's DuckDB database."
    )
    parser.add_argument(
        "--db-path",
        help="where to write the database (default: KORA_DB_PATH "
             "from .env, or data/kora.duckdb)",
    )
    parser.add_argument(
        "--force", action="store_true",
        help="overwrite the database if it already exists",
    )
    parser.add_argument(
        "--parquet", action="store_true",
        help="also export every table to a parquet/ folder next to "
             "the database",
    )
    parser.add_argument(
        "--noise-tables", type=int, default=0, metavar="N",
        help="also create N extra tables named noise_0001 and so on",
    )
    return parser.parse_args(argv)


def main(argv=None):
    check_python_version()
    args = parse_args(argv)

    sys.path.insert(0, str(REPO_ROOT))
    # Import after the version check, and with a friendly hint if the
    # packages aren't installed yet.
    try:
        import kora
        from kora.config import resolve_db_path
    except ImportError as error:
        print(f"A package is missing: {error.name}")
        print("Run: pip install -r requirements.txt")
        return 1

    db_path = resolve_db_path(args.db_path)
    if db_path.exists() and not args.force:
        # Leave an existing database alone. Rebuilding gives the same
        # data anyway, so there is no reason to do it by surprise.
        print(f"Kora's database already exists at {db_path}")
        print("Nothing to do. Use --force to rebuild it.")
        return 0

    parquet_dir = db_path.parent / "parquet" if args.parquet else None
    print(f"Building Kora's database at {db_path} ...")
    result = kora.build(db_path, noise_tables=args.noise_tables,
                        parquet_dir=parquet_dir)

    width = max(len(name) for name in result.row_counts)
    for name, count in result.row_counts.items():
        print(f"    {name:<{width}}  {count:>9,}")
    if parquet_dir is not None:
        print(f"Parquet files written to {parquet_dir}")
    print(f"Done in {result.seconds:.1f} seconds.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
