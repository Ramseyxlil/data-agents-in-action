"""Set up Kora's local database.

For now this only checks your environment and prepares the data/
folder. The dataset generator arrives with chapter 1.
"""

import os
import sys
from pathlib import Path

# The repo root is one level up from scripts/. We resolve paths from
# here so the script works no matter which folder you run it from.
REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = "data/kora.duckdb"


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


def load_settings():
    # Import here, not at the top, so a missing package gets a friendly
    # hint instead of an ImportError before anything else runs.
    try:
        from dotenv import load_dotenv
    except ImportError:
        print("python-dotenv is not installed.")
        print("Run: pip install -r requirements.txt")
        sys.exit(1)

    # A .env file is optional. If it is missing, we use the defaults.
    env_file = REPO_ROOT / ".env"
    if env_file.exists():
        load_dotenv(env_file)

    db_path = Path(os.getenv("KORA_DB_PATH") or DEFAULT_DB_PATH)

    # A relative path in .env means "relative to the repo", not to
    # wherever the reader happens to be standing in the terminal.
    if not db_path.is_absolute():
        db_path = REPO_ROOT / db_path
    return db_path


def main():
    check_python_version()
    db_path = load_settings()

    # Create the folder now, so the generator never trips over a
    # missing directory when it arrives.
    db_path.parent.mkdir(parents=True, exist_ok=True)

    print("The Kora dataset generator arrives with chapter 1.")
    print("Once it does, this script will build the database at:")
    print(f"    {db_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
