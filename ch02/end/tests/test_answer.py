"""The Answer model and the final_answer tool schema built from it."""

import pytest
from answer import ANSWER_TOOL, Answer, format_answer
from pydantic import ValidationError

GOOD = {
    "value": "North has 10 stores.",
    "number": 10,
    "unit": "stores",
    "sql": "SELECT COUNT(*) FROM stores WHERE region = 'North'",
    "rows_used": 1,
    "explanation": "Counted the stores whose region is North.",
    "assumptions": ["Region means the stores.region column."],
}


def test_valid_arguments_make_an_answer():
    """Well-formed final_answer arguments become an Answer."""
    answer = Answer.model_validate(GOOD)
    assert answer.number == 10.0
    assert answer.assumptions == GOOD["assumptions"]


def test_optional_fields_have_defaults():
    """A text-only answer may leave out number, unit and assumptions."""
    minimal = {k: GOOD[k] for k in ("value", "sql", "rows_used",
                                     "explanation")}
    answer = Answer.model_validate(minimal)
    assert answer.number is None and answer.assumptions == []


@pytest.mark.parametrize("broken", [
    {k: v for k, v in GOOD.items() if k != "sql"},
    {**GOOD, "rows_used": "a few"},
    {**GOOD, "number": "ten"},
])
def test_invalid_arguments_are_rejected(broken):
    """Missing or mistyped fields must fail, so the agent can retry."""
    with pytest.raises(ValidationError):
        Answer.model_validate(broken)


def test_tool_schema_matches_the_model():
    """The schema the model sees must match what we validate."""
    schema = ANSWER_TOOL["parameters"]
    assert ANSWER_TOOL["name"] == "final_answer"
    assert set(schema["properties"]) == set(Answer.model_fields)
    required = {name for name, f in Answer.model_fields.items()
                if f.is_required()}
    assert set(schema["required"]) == required


def test_format_answer_shows_value_sql_and_assumptions():
    """The printed answer must let a manager check the work."""
    text = format_answer(Answer.model_validate(GOOD))
    assert "North has 10 stores." in text
    assert "SELECT COUNT(*) FROM stores" in text
    assert "Region means the stores.region column." in text
