"""Every chapter's start/ folder must match what its end/ generates."""

import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "make_start.py"

# A chapter takes part once it has a start_stubs.toml.
CHAPTERS = sorted(path.parent.name
                  for path in REPO_ROOT.glob("ch*/start_stubs.toml"))


def test_some_chapter_has_a_start_folder():
    """If this finds nothing, the check below would silently pass."""
    assert "ch02" in CHAPTERS


@pytest.mark.parametrize("chapter", CHAPTERS)
def test_start_matches_end(chapter):
    """A fix in end/ must reach start/, or readers start from old code."""
    result = subprocess.run(
        [sys.executable, str(SCRIPT), chapter, "--check"],
        capture_output=True, text=True, cwd=REPO_ROOT,
    )
    assert result.returncode == 0, result.stdout + result.stderr
