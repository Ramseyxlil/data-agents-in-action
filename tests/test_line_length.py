"""Runs the line length check as part of the normal test suite."""

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "check_line_length.py"


def test_all_code_lines_fit_the_page():
    """A line over 76 characters won't fit on a printed book page."""
    # Use the same Python that runs pytest, so it works inside any
    # virtual environment without guessing the interpreter name.
    result = subprocess.run(
        [sys.executable, str(SCRIPT)],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    assert result.returncode == 0, result.stdout + result.stderr
