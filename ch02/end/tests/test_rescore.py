"""break_it.py --rescore: judge saved answers again, no model calls."""

import json

from break_it import main


def saved(question_id, number, verdict):
    """One record the way break_it.py saves it, cut down to essentials."""
    answer = None
    if number is not None:
        answer = {"value": str(number), "number": number, "unit": None,
                  "sql": "SELECT 1", "rows_used": 1,
                  "explanation": "Worked it out.", "assumptions": []}
    return {"run": 1, "id": question_id, "level": "hard",
            "question": "?", "why_hard": None, "truth_sql": "",
            "expected": 0, "verdict": verdict, "answer": answer,
            "stopped_reason": "answered" if answer else "max_turns",
            "turns": 2, "usage": {}, "error": None, "trace": []}


def test_rescore_rejudges_with_todays_rules(kora_db, tmp_path, capsys):
    """Old verdicts are replaced, and a _rescored file is written."""
    results = tmp_path / "break_it_fake_20261108_120000.json"
    results.write_text(json.dumps([
        # Judged WRONG under older rules, right under today's.
        saved("h2", 97.0, "WRONG"),
        saved("e1", 10, "WRONG"),
        # Judged PASS before, but the sign is wrong.
        saved("h4", 6.0, "PASS"),
        saved("h1", None, "NO_ANSWER"),
        # A question that no longer exists is skipped, not crashed on.
        saved("zz", 1, "PASS"),
    ]), encoding="utf-8")

    code = main(["--rescore", str(results), "--db", str(kora_db)])

    assert code == 0
    out = tmp_path / "break_it_fake_20261108_120000_rescored.json"
    records = json.loads(out.read_text(encoding="utf-8"))
    verdicts = {r["id"]: r["verdict"] for r in records}
    assert verdicts == {"h2": "PASS", "e1": "PASS", "h4": "WRONG",
                        "h1": "NO_ANSWER"}
    h2 = next(r for r in records if r["id"] == "h2")
    assert [a["kind"] for a in h2["accepted"]] == ["percent", "money",
                                                   "percent"]

    printed = capsys.readouterr().out
    assert "Skipping zz" in printed
    assert "Passes by level:" in printed
    # The original file is left exactly as it was.
    assert json.loads(results.read_text())[0]["verdict"] == "WRONG"
