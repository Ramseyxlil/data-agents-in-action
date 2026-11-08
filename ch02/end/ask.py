"""Ask Kora's data agent one question from the command line.

    python ch02/end/ask.py "How many stores are in the North region?"
"""

import argparse
import json
import sys
from pathlib import Path

from dotenv import load_dotenv

# Python already looks in this folder, so agent.py and friends import
# by name. Add the repo root too, so the kora package can be found.
REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.append(str(REPO_ROOT))

from agent import format_trace, result_to_dict, run_agent  # noqa: E402
from answer import format_answer  # noqa: E402
from models import MissingSetting, make_model  # noqa: E402

from kora.config import resolve_db_path  # noqa: E402


def parse_args(argv):
    parser = argparse.ArgumentParser(
        description="Ask Kora's data agent a question.")
    parser.add_argument("question", help="the question, in quotes")
    parser.add_argument("--provider", choices=["openai", "anthropic"],
                        help="overrides MODEL_PROVIDER in .env")
    parser.add_argument("--trace", action="store_true",
                        help="print every step the agent took")
    parser.add_argument("--db", help="path to the Kora database")
    parser.add_argument("--max-turns", type=int, default=6)
    parser.add_argument("--json", action="store_true",
                        help="print the full result as JSON")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    load_dotenv(REPO_ROOT / ".env")
    db_path = resolve_db_path(args.db)
    if not db_path.exists():
        print(f"No database at {db_path}.")
        print("Build it first: python scripts/setup_kora.py")
        return 1
    try:
        model = make_model(args.provider)
    except MissingSetting as error:
        print(error)
        return 1

    result = run_agent(args.question, model, db_path, args.max_turns)

    if args.json:
        print(json.dumps(result_to_dict(result), indent=2))
        return 0
    if args.trace:
        print(format_trace(result.trace), end="\n\n")
    if result.answer:
        print(format_answer(result.answer))
    else:
        print(f"No answer (stopped: {result.stopped_reason}). "
              f"{result.error or ''}".rstrip())
    return 0


if __name__ == "__main__":
    sys.exit(main())
