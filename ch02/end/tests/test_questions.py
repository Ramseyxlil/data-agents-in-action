"""The 2.5 questions: their right answers must match chapter 1."""

import pytest
from agent import AgentResult
from answer import Answer
from break_it import judge, matches
from questions import (
    QUESTIONS,
    TOLERANCES,
    accepted_answers,
    check_against_numbers,
)


def test_hard_truths_match_numbers_json(kora_db):
    """If the truth SQL drifts from chapter 1, scoring is meaningless."""
    assert check_against_numbers(kora_db) == []


def test_question_set_shape():
    """Unique ids, a mix of levels, and a stated trap for hard ones."""
    ids = [q.id for q in QUESTIONS]
    assert len(ids) == len(set(ids))
    levels = [q.level for q in QUESTIONS]
    assert levels.count("easy") == 4 and levels.count("hard") >= 4
    assert all(q.why_hard for q in QUESTIONS if q.level == "hard")
    assert all(q.kind in TOLERANCES for q in QUESTIONS)
    assert all(a.kind in TOLERANCES
               for q in QUESTIONS for a in q.alternates)


def question(question_id):
    return next(q for q in QUESTIONS if q.id == question_id)


@pytest.mark.parametrize("number, ok", [
    (5828702.85, True),
    (5828702.854, True),
    (5828703.85, False),
    (5828702.86, False),
    (5828702.0, False),
])
def test_money_must_match_to_the_cent(number, ok):
    """A dollar off on finance's number is a wrong answer."""
    assert matches(question("h3").kind, 5828702.85, number) is ok


@pytest.mark.parametrize("number, ok", [
    (10, True), (10.0, True), (10.4, False), (11, False), (9, False),
])
def test_counts_must_match_exactly(number, ok):
    """Nine stores is not ten stores."""
    assert matches(question("e1").kind, 10, number) is ok


@pytest.mark.parametrize("number, ok", [
    (-6.0, True), (-0.06, True),
    (-6.04, True), (-0.0596, True),
    (-6.1, False), (-0.061, False),
    (6.0, False), (0.06, False),
    (-5.0, False), (-0.05, False), (None, False),
])
def test_percent_matching_accepts_either_scale_but_not_sign(number, ok):
    """'Down 6%' passes as -6 or -0.06, within 0.05 points.

    'Up 6%' must fail, and so must anything 0.1 points away.
    """
    assert matches(question("h4").kind, -6.0, number) is ok


def test_percent_matching_for_a_target_gap():
    """h2: 3% under target must not pass as 3% over."""
    h2 = question("h2")
    assert matches(h2.kind, -3.0, -3.0)
    assert matches(h2.kind, -3.0, -0.03)
    assert not matches(h2.kind, -3.0, 3.0)
    assert not matches(h2.kind, -3.0, -3.1)


def answered(number):
    """An AgentResult whose answer is just this number."""
    answer = Answer(value=str(number), number=number, sql="SELECT 1",
                    rows_used=1, explanation="Worked it out.")
    return AgentResult(answer=answer)


def test_judge_verdicts():
    """PASS, WRONG and NO_ANSWER cover every outcome."""
    accepted = [("count", 10)]
    assert judge(accepted, answered(10)) == "PASS"
    assert judge(accepted, answered(9)) == "WRONG"
    assert judge(accepted, AgentResult()) == "NO_ANSWER"


def test_h2_accepts_gap_dollars_or_attainment(kora_db):
    """'3% short', '$49,060.68 short' and '97% of target' all count."""
    accepted = accepted_answers(question("h2"), kora_db)
    assert [kind for kind, _ in accepted] == ["percent", "money",
                                              "percent"]
    assert accepted[1][1] == -49060.68
    assert round(accepted[2][1], 1) == 97.0


@pytest.mark.parametrize("number, verdict", [
    (-49060.68, "PASS"),
    (49060.68, "WRONG"),
    (-3.0, "PASS"),
    (-0.03, "PASS"),
    (3.0, "WRONG"),
    (97, "PASS"),
    (0.97, "PASS"),
    (103, "WRONG"),
    (1586295.63, "WRONG"),
    (1485113.32, "WRONG"),
])
def test_h2_verdicts(kora_db, number, verdict):
    """Any of the three right answers passes. Anything else fails."""
    accepted = accepted_answers(question("h2"), kora_db)
    assert judge(accepted, answered(number)) == verdict
