"""Build a chapter's start/ folder from its finished end/ folder.

    python scripts/make_start.py ch02           write ch02/start
    python scripts/make_start.py ch02 --check   only compare, exit 1
                                                if start/ is stale

Every chapter from 2 on has a start/ folder (where the reader begins)
and an end/ folder (the finished code). Writing start/ by hand means
it drifts the moment end/ changes. So start/ is generated instead.

Which functions the reader writes is listed in chNN/start_stubs.toml,
with a TODO hint for each. Those functions keep their signature,
docstring and comment lines, and their code is replaced by the TODO
and `raise NotImplementedError`. Everything else is copied as is.
"""

import argparse
import ast
import sys
import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TODO_WIDTH = 74

# Stubbed files keep every import the finished file has, so the reader
# doesn't have to guess them. Ruff would flag them as unused, so the
# note switches that one check off for these files only.
IMPORT_NOTE = [
    "",
    "# The imports below are the ones the finished file uses. Some are",
    "# unused until you fill in the TODOs.",
    "# ruff: noqa: F401",
]


def load_stubs(chapter_dir):
    """Read start_stubs.toml: {file name: {function: TODO hint}}."""
    path = chapter_dir / "start_stubs.toml"
    with open(path, "rb") as handle:
        stubs = tomllib.load(handle)["stubs"]
    # Hints may wrap in the TOML file. Squash them to one line of text.
    return {name: {func: " ".join(hint.split())
                   for func, hint in funcs.items()}
            for name, funcs in stubs.items()}


def wrap_todo(indent, text):
    """The TODO hint as comment lines that fit the page width."""
    lines, line = [], ""
    for word in ("TODO: " + text).split():
        if len(indent) + 2 + len(line) + len(word) + 1 > TODO_WIDTH:
            lines.append(line)
            line = word
        else:
            line = f"{line} {word}".strip()
    lines.append(line)
    # Follow-on lines are indented a little, so the TODO reads as one.
    return ([f"{indent}# {lines[0]}"]
            + [f"{indent}#   {rest}" for rest in lines[1:]])


def find_functions(tree, names):
    """Find each function to stub. Methods are named Class.method."""
    functions = {}
    for node in tree.body:
        if isinstance(node, ast.FunctionDef):
            functions[node.name] = node
        elif isinstance(node, ast.ClassDef):
            for item in node.body:
                if isinstance(item, ast.FunctionDef):
                    functions[f"{node.name}.{item.name}"] = item
    # A typo in the TOML file should fail loudly, not stub nothing.
    missing = sorted(set(names) - set(functions))
    if missing:
        raise SystemExit(f"start_stubs.toml names functions that are "
                         f"not in the file: {missing}")
    return [(functions[name], hint) for name, hint in names.items()]


def stub_functions(source, names):
    """Replace the bodies of the named functions with a TODO."""
    lines = source.splitlines()
    functions = find_functions(ast.parse(source), names)

    # Work from the bottom of the file up, so the line numbers of the
    # functions above don't shift as we edit.
    for node, hint in sorted(functions, key=lambda f: -f[0].lineno):
        first = node.body[0]
        has_docstring = (isinstance(first, ast.Expr)
                         and isinstance(first.value, ast.Constant)
                         and isinstance(first.value.value, str))
        # Keep the signature and docstring. Without a docstring, keep
        # everything up to the first line of the body.
        keep = first.end_lineno if has_docstring else first.lineno - 1
        indent = " " * first.col_offset

        # Comment lines explain what the missing code should do, so
        # they stay. Code lines go.
        body = lines[keep:node.end_lineno]
        comments = [indent + line.strip() for line in body
                    if line.strip().startswith("#")]
        lines[keep:node.end_lineno] = (
            comments + wrap_todo(indent, hint)
            + [f"{indent}raise NotImplementedError"])
    return lines


def add_import_note(lines):
    """Put the import note right after the module docstring."""
    end = ast.parse("\n".join(lines)).body[0].end_lineno
    return lines[:end] + IMPORT_NOTE + lines[end:]


def build_start(chapter_dir):
    """Every start/ file as {file name: text}, without writing it."""
    stubs = load_stubs(chapter_dir)
    end = chapter_dir / "end"
    files = {}
    # Only the chapter's own modules. Tests and results stay in end/.
    for path in sorted(end.glob("*.py")):
        text = path.read_text(encoding="utf-8")
        if path.name in stubs:
            lines = stub_functions(text, stubs[path.name])
            text = "\n".join(add_import_note(lines)) + "\n"
        files[path.name] = text
    unknown = set(stubs) - set(files)
    if unknown:
        raise SystemExit(f"start_stubs.toml lists files that are not "
                         f"in end/: {sorted(unknown)}")
    return files


def stale_files(chapter_dir, files):
    """Names of start/ files that differ from what we would write."""
    start = chapter_dir / "start"
    stale = []
    for name, text in files.items():
        path = start / name
        if (not path.exists()
                or path.read_text(encoding="utf-8") != text):
            stale.append(name)
    return stale


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Build chNN/start from chNN/end.")
    parser.add_argument("chapter", help="chapter folder, like ch02")
    parser.add_argument("--check", action="store_true",
                        help="compare only, exit 1 if start/ is stale")
    args = parser.parse_args(argv)

    chapter_dir = REPO_ROOT / args.chapter
    files = build_start(chapter_dir)

    if args.check:
        stale = stale_files(chapter_dir, files)
        for name in stale:
            print(f"{args.chapter}/start/{name} is out of date")
        if stale:
            print(f"Run: python scripts/make_start.py {args.chapter}")
            return 1
        print(f"{args.chapter}/start matches {args.chapter}/end.")
        return 0

    # Write files in place rather than deleting the folder first. On
    # synced folders (OneDrive, Dropbox) deleting a folder can fail.
    start = chapter_dir / "start"
    start.mkdir(exist_ok=True)
    for name, text in files.items():
        (start / name).write_text(text, encoding="utf-8", newline="\n")
    print(f"Wrote {len(files)} files to {args.chapter}/start")
    return 0


if __name__ == "__main__":
    sys.exit(main())
