"""One real question per provider. Costs a little, so off by default.

Run with:  pytest -m live ch02/end/tests/test_live.py
Each test skips unless its key and model are set in .env.
"""

import os

import pytest
from agent import run_agent
from dotenv import load_dotenv
from models import make_model

from kora.config import REPO_ROOT, resolve_db_path

load_dotenv(REPO_ROOT / ".env")
DB_PATH = resolve_db_path()


@pytest.mark.live
@pytest.mark.parametrize("provider, key, model_name", [
    ("openai", "OPENAI_API_KEY", "OPENAI_MODEL"),
    ("anthropic", "ANTHROPIC_API_KEY", "ANTHROPIC_MODEL"),
])
def test_live_easy_question(provider, key, model_name):
    """A real model must answer an easy question correctly."""
    if not (os.getenv(key) and os.getenv(model_name)):
        pytest.skip(f"{key} and {model_name} are not set")
    if not DB_PATH.exists():
        pytest.skip("Build Kora first: python scripts/setup_kora.py")
    result = run_agent("How many stores are in the North region?",
                       make_model(provider), DB_PATH)
    assert result.stopped_reason == "answered", result.error
    assert result.answer.number == 10
