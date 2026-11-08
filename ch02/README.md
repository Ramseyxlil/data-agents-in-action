# Chapter 2: Build your first working data agent

In this chapter you build a small but real data agent in plain Python,
with no agent framework. It reads a question, asks the model which
query to run, runs it on Kora's database, and hands back a structured
answer you can check: the number, the SQL behind it, and what it
assumed.

The agent is naive on purpose. It knows the table and column names
and today's date, nothing else. It gets easy questions right and real
business questions wrong, and those failures are the map for the rest
of the book.

## The folders

- `start/` is where the chapter begins. The files are all there, with
  the functions you write left as `raise NotImplementedError` and a
  TODO saying what goes in. `ask.py`, `break_it.py` and
  `questions.py` are complete, because you write the agent, not the
  harness.
- `end/` is the finished code, with tests.

`start/` is generated from `end/` by `scripts/make_start.py`, using
the list of functions in `start_stubs.toml`. After changing `end/`,
rebuild it with `python scripts/make_start.py ch02`.

## Set your key

Copy `.env.example` to `.env` in the repo root and fill in one
provider:

```bash
MODEL_PROVIDER=openai
OPENAI_API_KEY=your-key-here
OPENAI_MODEL=the-model-you-want
```

For Anthropic, set `MODEL_PROVIDER=anthropic`, `ANTHROPIC_API_KEY`
and `ANTHROPIC_MODEL` instead. Keys stay in `.env`, never in code.

## Run it

Build Kora's database first if you haven't
(`python scripts/setup_kora.py`). Then, from the repo root:

```bash
python ch02/end/ask.py "How many stores are in the North region?"
python ch02/end/ask.py --trace "What was North's revenue last quarter?"
python ch02/end/break_it.py --runs 3
```

`--trace` prints every step: the SQL the model wrote, how many rows
came back, and any error. `break_it.py` asks every question in
`questions.py`, scores each answer against the right one, and saves
the full run to `end/results/`.

## Test it

```bash
pytest ch02/end/tests
```

These tests use a fake model, so they need no key and cost nothing.
To try one real question per provider, run `pytest -m live`.
