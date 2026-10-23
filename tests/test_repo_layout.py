"""Checks that the repo has the shape the book and the readme promise."""

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent

CHAPTERS = [f"ch{number:02d}" for number in range(1, 12)]
APPENDIXES = ["appendix-a", "appendix-b", "appendix-c"]

EXPECTED_FILES = [
    "README.md",
    "LICENSE",
    ".gitignore",
    ".gitattributes",
    ".editorconfig",
    ".env.example",
    "pyproject.toml",
    "requirements.txt",
    "requirements-dev.txt",
    ".github/workflows/tests.yml",
    "kora/__init__.py",
    "kora/README.md",
    "kora/config.py",
    "kora/calendar.py",
    "kora/generate.py",
    "kora/load.py",
    "kora/story.py",
    "kora/numbers.py",
    "ch01/listing_1_1.sql",
    "ch01/run_listing_1_1.py",
    "ch01/numbers.json",
    "tests/kora/__init__.py",
    "tests/kora/conftest.py",
    "scripts/setup_kora.py",
    "scripts/check_line_length.py",
    "data/.gitkeep",
    "tests/__init__.py",
    "tests/test_repo_layout.py",
    "tests/test_line_length.py",
]
EXPECTED_FILES += [f"{folder}/README.md" for folder in CHAPTERS]
EXPECTED_FILES += [f"{folder}/README.md" for folder in APPENDIXES]

EXPECTED_DIRS = [".github/workflows", "kora", "scripts", "data", "tests"]
EXPECTED_DIRS += CHAPTERS + APPENDIXES

# These settings are not secrets, so they may ship with a default.
# Everything else in .env.example must be blank.
NON_SECRET_SETTINGS = {"MODEL_PROVIDER", "KORA_DB_PATH"}

# The repo doesn't use these words anywhere, not even in this file, so
# each one is split in two and joined back together here.
BANNED_WORDS = [
    "power" + "ful",
    "rob" + "ust",
    "cutting" + "-edge",
    "seam" + "less",
    "del" + "ve",
    "lever" + "age",
    "un" + "lock",
    "ele" + "vate",
    "compre" + "hensive",
    "transfor" + "mative",
    "ground" + "breaking",
    "game" + "-changing",
    "revolu" + "tionary",
    "state" + "-of-the-art",
]

# Built in pieces so this file doesn't trip its own check.
TOOL_NAME = "clau" + "de"
TOOL_COMPANY = "anthro" + "pic"
COAUTHOR_LINE = "co-" + "authored-by"

# The company name is also a model provider the book supports, so the
# readme and the settings template must be able to name it. Anywhere
# else it would only show up as a tool credit.
PROVIDER_NAME_ALLOWED = {"README.md", ".env.example"}

# data/ holds the generated database, which git never sees, so it is
# not part of the repo and can be hundreds of megabytes to read.
SKIP_DIRS = {
    ".venv",
    "venv",
    ".git",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    "data",
}


def repo_files():
    for path in sorted(REPO_ROOT.rglob("*")):
        parts = path.relative_to(REPO_ROOT).parts[:-1]
        if path.is_file() and not any(p in SKIP_DIRS for p in parts):
            yield path


def env_example_settings():
    settings = {}
    text = (REPO_ROOT / ".env.example").read_text(encoding="utf-8")
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        name, _, value = line.partition("=")
        settings[name.strip()] = value.strip()
    return settings


@pytest.mark.parametrize("relative_path", EXPECTED_FILES)
def test_expected_file_exists(relative_path):
    """Readers follow the readme, so every file it relies on must exist."""
    assert (REPO_ROOT / relative_path).is_file(), relative_path


@pytest.mark.parametrize("relative_path", EXPECTED_DIRS)
def test_expected_folder_exists(relative_path):
    """Chapters point readers at these folders, so they must be there."""
    assert (REPO_ROOT / relative_path).is_dir(), relative_path


def test_env_example_has_no_secrets():
    """A filled-in .env.example could push a real key to GitHub."""
    settings = env_example_settings()
    assert settings, ".env.example has no settings in it"
    filled = [
        name
        for name, value in settings.items()
        if value and name not in NON_SECRET_SETTINGS
    ]
    assert not filled, f"These must be blank in .env.example: {filled}"


def test_gitignore_ignores_env():
    """The real .env holds API keys and must never be committed."""
    text = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8")
    lines = [line.strip() for line in text.splitlines()]
    assert ".env" in lines


def test_readme_avoids_banned_words():
    """These words read as hype, and the readme should sound human."""
    text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    found = [
        word
        for word in BANNED_WORDS
        if re.search(rf"\b{re.escape(word)}\b", text, re.IGNORECASE)
    ]
    assert not found, f"README.md uses banned words: {found}"


def test_no_tool_credits_anywhere():
    """The only author of this repo is Abdulrafiu Izuafa."""
    problems = []
    for path in repo_files():
        text = path.read_text(encoding="utf-8", errors="ignore").lower()
        shown = path.relative_to(REPO_ROOT).as_posix()
        banned = [TOOL_NAME, COAUTHOR_LINE]
        if shown not in PROVIDER_NAME_ALLOWED:
            banned.append(TOOL_COMPANY)
        problems += [f"{shown}: {word}" for word in banned if word in text]
    assert not problems, f"Tool credits found: {problems}"
