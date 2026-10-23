"""Readers build this on ordinary laptops, so it has to stay quick."""

import pytest


@pytest.mark.slow
def test_full_build_is_under_two_minutes(kora_db):
    """A slow setup step is where readers give up on a book's code."""
    assert kora_db.seconds < 120, f"Build took {kora_db.seconds:.1f}s"
