"""Check that every code line in the repo fits the book's page width.

The book's publisher prints code at 76 characters per line. The repo
keeps the same limit, so any listing can be copied straight into the
book without someone rewrapping it by hand (and breaking it).
"""

import sys
from pathlib import Path

LIMIT = 76
REPO_ROOT = Path(__file__).resolve().parent.parent

# Folders we never check. They hold tools, caches or generated data,
# not code that ends up in the book.
SKIP_DIRS = {
    ".venv",
    "venv",
    ".git",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    "data",
}

# Every line in these files is code, so every line is checked.
CODE_SUFFIXES = {".py", ".toml", ".yml", ".yaml", ".sql"}


def files_to_check(root):
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        # Look at the folders relative to the repo, so a skipped name
        # higher up on the reader's disk doesn't hide the whole repo.
        parts = path.relative_to(root).parts[:-1]
        if any(part in SKIP_DIRS for part in parts):
            continue
        if path.suffix in CODE_SUFFIXES or path.suffix == ".md":
            yield path


def lines_to_check(path):
    lines = path.read_text(encoding="utf-8").splitlines()
    if path.suffix != ".md":
        yield from enumerate(lines, start=1)
        return

    # In Markdown, prose can be any length because it reflows. Only
    # lines inside ``` fences are code, so only those are checked.
    in_fence = False
    for number, line in enumerate(lines, start=1):
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            yield number, line


def find_problems(root):
    problems = []
    for path in files_to_check(root):
        shown = path.relative_to(root).as_posix()
        for number, line in lines_to_check(path):
            if len(line) > LIMIT:
                problems.append(
                    f"{shown}:{number}: length {len(line)} "
                    f"(limit {LIMIT})"
                )
            # Tabs print at different widths in different places, so
            # Python files must use spaces only.
            if path.suffix == ".py" and "\t" in line:
                problems.append(
                    f"{shown}:{number}: tab character (use spaces)"
                )
    return problems


def main():
    problems = find_problems(REPO_ROOT)
    for problem in problems:
        print(problem)
    if problems:
        print(f"{len(problems)} problem(s) found.")
        return 1
    print(f"All code lines are {LIMIT} characters or fewer.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
