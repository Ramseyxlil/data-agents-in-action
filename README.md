# Data Agents in Action

This is the code for the book "Data Agents in Action" by Abdulrafiu
Izuafa, published by Manning. In the book you build one data agent for a
made-up retailer called Kora. The agent answers business questions in
plain English, queries Kora's data, checks its own answers, and only
shows people the data they are allowed to see. It is written in plain
Python with no agent framework, and it works with OpenAI, Anthropic or
Azure-hosted models.

- Book page: [link added at MEAP launch]
- Reader forum (liveBook): [link added at MEAP launch]

## What you need

- Python 3.11 or newer
- An API key for one model provider: OpenAI, Anthropic, or an
  Azure-hosted model. You only need one.
- No cloud data platform. Everything runs on your laptop.

## Get started

On macOS or Linux:

```bash
git clone https://github.com/Ramseyxlil/data-agents-in-action.git
cd data-agents-in-action
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Open .env and add your API key
python scripts/setup_kora.py
pytest
```

On Windows (PowerShell):

```powershell
git clone https://github.com/Ramseyxlil/data-agents-in-action.git
cd data-agents-in-action
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
# Open .env and add your API key
python scripts/setup_kora.py
pytest
```

The `setup_kora.py` step builds Kora's database and writes it to
`data/kora.duckdb` (about 70 MB). It takes about 30 seconds on a
normal laptop and prints a row count for every table when it is done.
If the database is already there, the script leaves it alone. Add
`--force` to rebuild it. The same seed gives the same data every time,
so a rebuild never changes the book's numbers.

To run the tests and the style checks, install the developer tools too:

```bash
pip install -r requirements-dev.txt
```

## How the repo is organized

| Folder | What's in it |
| --- | --- |
| `kora/` | Kora's dataset generator (built in chapter 1, see appendix A) |
| `ch01` to `ch11` | Code for each chapter. From chapter 2 on, each chapter has a `start/` folder (where the chapter begins) and an `end/` folder (the finished code), so you can jump in at any chapter. |
| `appendix-a/` | Setting up the project and the sample dataset |
| `appendix-b/` | The evaluation dataset starter kit |
| `appendix-c/` | A governance and security review checklist |
| `scripts/` | Setup and helper scripts |
| `tests/` | Tests. Each chapter's tests are its definition of done. |
| `data/` | Where your local Kora database is written. Not committed to git. |

## Meet Kora

Kora is a made-up mid-size retailer with stores in four regions (North,
South, East and West) and an online shop. Its data is messy on purpose,
the same way real company data is messy. A clean dataset would let a
broken agent look fine, and the point of the book is to catch the
mistakes a real agent makes on real data.

## Model providers

You pick a model provider with the `MODEL_PROVIDER` setting in your
`.env` file. It takes one of three values:

- `openai`: set `OPENAI_API_KEY` and `OPENAI_MODEL`.
- `anthropic`: set `ANTHROPIC_API_KEY` and `ANTHROPIC_MODEL`.
- `azure`: set `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_API_KEY` and
  `AZURE_OPENAI_DEPLOYMENT`.

You only fill in the settings for the provider you chose. Keys always
live in `.env` and never in code. The `.env` file is listed in
`.gitignore`, so git will not pick it up by accident.

## Running the tests

From the repo root, with your virtual environment active:

```bash
pytest
```

Two more checks run in CI on every push, and you can run them yourself:

```bash
python scripts/check_line_length.py
ruff check .
```

The first one keeps every code line at 76 characters or fewer, the
width the book prints at. The second one is a linter.

The Kora tests build the database a few times to prove it comes out
the same on every run, so the full suite takes a couple of minutes.

## Found a problem?

Open an issue on this GitHub repo. Errata are also tracked on the book
page: [link added at MEAP launch]

## License

Code is released under the MIT License. See [LICENSE](LICENSE).
