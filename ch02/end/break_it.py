"""Run every question in questions.py through the agent and score it.

    python ch02/end/break_it.py --provider openai --runs 3
    python ch02/end/break_it.py --rescore ch02/end/results/<file>.json

This is the section 2.5 experiment. The naive agent should get the easy
questions right and the hard ones wrong, and the saved results show
exactly how it went wrong.
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
sys.path.append(str(REPO_ROOT))

from agent import AgentResult, result_to_dict, run_agent  # noqa: E402
from answer import Answer  # noqa: E402
from models import MissingSetting, make_model  # noqa: E402
from questions import (  # noqa: E402
    QUESTIONS,
    TOLERANCES,
    accepted_answers,
    check_against_numbers,
)

from kora.config import resolve_db_path  # noqa: E402

LEVELS = ("easy", "medium", "hard")


def parse_args(argv):
    parser = argparse.ArgumentParser(
        description="Score the agent on the chapter 2 questions.")
    parser.add_argument("--provider", choices=["openai", "anthropic"],
                        help="overrides MODEL_PROVIDER in .env")
    parser.add_argument("--runs", type=int, default=1,
                        help="ask every question this many times")
    parser.add_argument("--db", help="path to the Kora database")
    parser.add_argument("--max-turns", type=int, default=6)
    parser.add_argument("--rescore", metavar="PATH",
                        help="judge a saved results file again with "
                             "today's answers, without calling a model")
    return parser.parse_args(argv)


def matches(kind, expected, number):
    """True if the agent's number is close enough to expected.

    How close depends on the kind of answer: to the cent for money,
    exactly for counts, 0.05 percentage points for percents.
    """
    if number is None:
        return False
    candidates = [number]
    if kind == "percent":
        # "Down 6%" may come back as -6 or as the fraction -0.06. Both
        # mean the same, so accept either scale. The sign still has to
        # be right: +6 says North grew, which is the wrong answer.
        candidates = [number, number * 100]
    margin = TOLERANCES[kind]
    return any(abs(c - expected) <= margin for c in candidates)


def judge(accepted, result):
    """PASS, WRONG (a wrong number) or NO_ANSWER.

    accepted is every right answer as (kind, value). Matching any one
    of them, under that answer's own rules, is a pass.
    """
    if result.answer is None:
        return "NO_ANSWER"
    number = result.answer.number
    if any(matches(kind, value, number) for kind, value in accepted):
        return "PASS"
    return "WRONG"


def short(text, width):
    return text if len(text) <= width else text[:width - 3] + "..."


def show(number):
    return "-" if number is None else f"{number:,.2f}"


def print_table(records):
    print(f"{'id':<4}{'level':<8}{'question':<42}"
          f"{'expected':>16}{'agent':>16}  verdict")
    for r in records:
        number = r["answer"]["number"] if r["answer"] else None
        print(f"{r['id']:<4}{r['level']:<8}"
              f"{short(r['question'], 40):<42}"
              f"{show(r['expected']):>16}{show(number):>16}"
              f"  {r['verdict']}")
    for r in records:
        if r["verdict"] != "WRONG":
            continue
        print(f"\n{r['id']} (run {r['run']}) WRONG: {r['question']}")
        print(f"  trap: {r['why_hard'] or '-'}")
        for line in r["answer"]["sql"].strip().splitlines():
            print(f"  sql:  {line}")
        for assumption in r["answer"]["assumptions"]:
            print(f"  assumed: {assumption}")


def print_summary(records):
    print("\nPasses by level:")
    for level in LEVELS:
        rows = [r for r in records if r["level"] == level]
        passed = sum(r["verdict"] == "PASS" for r in rows)
        print(f"  {level:<7} {passed}/{len(rows)}")


def save(records, provider):
    folder = HERE / "results"
    folder.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = folder / f"break_it_{provider}_{stamp}.json"
    path.write_text(json.dumps(records, indent=2), encoding="utf-8")
    return path


def saved_result(record):
    """Rebuild just enough of an AgentResult to judge it again."""
    answer = record.get("answer")
    if answer is None:
        return AgentResult()
    return AgentResult(answer=Answer.model_validate(answer))


def rescore(path, db_path):
    """Judge a saved run again with today's answers. No model calls.

    Model runs cost money and vary from run to run. When only the
    scoring rules change, rescoring the saved answers is the fair way
    to compare: same answers, new rules.
    """
    records = json.loads(path.read_text(encoding="utf-8"))
    by_id = {q.id: q for q in QUESTIONS}
    accepted = {}
    rescored = []
    for record in records:
        question = by_id.get(record["id"])
        if question is None:
            print(f"Skipping {record['id']}: no such question any more.")
            continue
        if question.id not in accepted:
            accepted[question.id] = accepted_answers(question, db_path)
        answers = accepted[question.id]
        record["expected"] = answers[0][1]
        record["accepted"] = [{"kind": kind, "value": value}
                              for kind, value in answers]
        record["verdict"] = judge(answers, saved_result(record))
        rescored.append(record)

    print_table(rescored)
    print_summary(rescored)
    out = path.with_name(f"{path.stem}_rescored.json")
    out.write_text(json.dumps(rescored, indent=2), encoding="utf-8")
    print(f"\nSaved {out}")
    return 0


def main(argv=None):
    args = parse_args(argv)
    load_dotenv(REPO_ROOT / ".env")
    db_path = resolve_db_path(args.db)
    if not db_path.exists():
        print(f"No database at {db_path}. Run scripts/setup_kora.py.")
        return 1
    # If the right answers disagree with chapter 1, scoring is useless.
    problems = check_against_numbers(db_path)
    if problems:
        print("Truth SQL disagrees with ch01/numbers.json:")
        print("\n".join(f"  {problem}" for problem in problems))
        return 1
    if args.rescore:
        return rescore(Path(args.rescore), db_path)
    try:
        model = make_model(args.provider)
    except MissingSetting as error:
        print(error)
        return 1
    provider = args.provider or os.getenv("MODEL_PROVIDER") or "openai"

    accepted = {q.id: accepted_answers(q, db_path) for q in QUESTIONS}
    records = []
    for run in range(1, args.runs + 1):
        for q in QUESTIONS:
            print(f"run {run}, {q.id}: {q.question}", flush=True)
            result = run_agent(q.question, model, db_path,
                               args.max_turns)
            records.append({
                "run": run, "id": q.id, "level": q.level,
                "question": q.question, "why_hard": q.why_hard,
                "truth_sql": q.truth_sql.strip(),
                # The main answer, shown in the table.
                "expected": accepted[q.id][0][1],
                "accepted": [{"kind": kind, "value": value}
                             for kind, value in accepted[q.id]],
                "verdict": judge(accepted[q.id], result),
                **result_to_dict(result)})

    print()
    print_table(records)
    print_summary(records)
    print(f"\nSaved {save(records, provider.lower())}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
