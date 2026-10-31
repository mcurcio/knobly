"""The shared conformance driver (spec/conformance.md): runs every case of every corpus against one binding's adapter
and compares each result with its expected output. It is the only place that compares.

    python3 conformance/driver/run.py [--level N] [--corpus NAME]... [--case NAME]... [--cwd DIR] -- ADAPTER...

ADAPTER is the command that starts the binding's adapter (it speaks the protocol on its standard input and output).
Output is TAP version 14 on standard output; the adapter's standard error passes through. Exit status: 0 when every
case run passed, 1 when one failed, 2 when the adapter could not start or the arguments are wrong.

Python 3.9+ standard library only, like tools/gen-api.py.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))

import contract  # noqa: E402
import rendered  # noqa: E402
import syntax  # noqa: E402
import written  # noqa: E402
from adapter import Adapter, AdapterFault, Thrown  # noqa: E402
from common import CONFORMANCE, REPO, CaseError, Session  # noqa: E402
from units import UNITS  # noqa: E402

LEVELS = ("L0 syntax", "L1 low level", "L2 rendered tree", "L3 extensions", "L4 adapters")
RUNNERS: Dict[str, Callable[[Session, Mapping[str, Any]], Any]] = {
    "syntax": syntax.run,
    "written": written.run,
    "load": rendered.run_load,
    "rendered": rendered.run_rendered,
    "contract": contract.run,
}


def case_level(corpus: Mapping[str, Any], case: Mapping[str, Any]) -> int:
    """A case's conformance level (corpora.json "$comment")."""
    if case.get("extensions") or "include" in case.get("needs", []):
        return 3
    level = int(corpus["level"])
    if corpus["name"] == "written":
        for step in case["steps"]:
            if step[0] == "render" or (step[0] == "edit" and step[1][0] == "rendered"):
                level = max(level, 2)
    return level


def load_corpora() -> List[Dict[str, Any]]:
    manifest = json.loads((CONFORMANCE / "corpora.json").read_text(encoding="utf-8"))
    corpora = []
    for corpus in manifest["corpora"]:
        cases = []
        for path in corpus["cases"]:
            cases.extend(json.loads((REPO / path).read_text(encoding="utf-8")))
        corpora.append({**corpus, "loaded": cases})
    return corpora


def integrity(corpus: Mapping[str, Any]) -> List[str]:
    """Names are unique, and an expected directory has exactly one file per case."""
    names = [c["name"] for c in corpus["loaded"]]
    problems = [f"duplicate case name {n}" for n in sorted({n for n in names if names.count(n) > 1})]
    if corpus["expected"] is not None:
        files = {p.stem for p in (REPO / corpus["expected"]).glob("*.json")}
        problems += [f"no expected file for {n}" for n in sorted(set(names) - files)]
        problems += [f"an expected file with no case: {n}.json" for n in sorted(files - set(names))]
    return problems


def compare(session: Session, corpus: Mapping[str, Any], case: Mapping[str, Any]) -> Tuple[str, str]:
    """``(actual, expected)`` for one case."""
    out = RUNNERS[corpus["name"]](session, case)
    if isinstance(out, tuple):
        return out
    expected = (REPO / corpus["expected"] / f"{case['name']}.json").read_text(encoding="utf-8")
    return out, expected


def first_difference(actual: str, expected: str) -> str:
    i = next((n for n, (a, b) in enumerate(zip(actual, expected)) if a != b), min(len(actual), len(expected)))
    lo = max(0, i - 60)
    return f"at character {i}: expected ...{expected[lo : i + 60]!r}, got ...{actual[lo : i + 60]!r}"


def yaml_block(message: str) -> str:
    return "  ---\n  message: " + json.dumps(message) + "\n  ...\n"


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="run.py", description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--level",
        type=int,
        choices=range(len(LEVELS)),
        help="run cases up to this level (default: the level the adapter claims)",
    )
    parser.add_argument("--corpus", action="append", default=[], help="run only this corpus (repeatable)")
    parser.add_argument("--case", action="append", default=[], help="run only the case of this name (repeatable)")
    parser.add_argument("--cwd", help="the adapter's working directory (default: the current one)")
    parser.add_argument("adapter", nargs=argparse.REMAINDER, help="-- then the command that starts the adapter")
    args = parser.parse_args(argv)
    command = args.adapter[1:] if args.adapter[:1] == ["--"] else args.adapter
    if not command:
        parser.error("give the adapter's command after --")

    corpora = load_corpora()
    known = {c["name"] for c in corpora}
    if set(args.corpus) - known:
        parser.error(f"unknown corpus {sorted(set(args.corpus) - known)}; known: {sorted(known)}")

    adapter = Adapter(command, args.cwd)
    try:
        hello = adapter.start()
    except (AdapterFault, OSError) as error:
        print(f"Bail out! the adapter did not start: {error}")
        return 2
    claimed = hello.get("level")
    if hello.get("unit") not in UNITS or not isinstance(claimed, int) or not 0 <= claimed < len(LEVELS):
        print(f"Bail out! bad hello {hello!r}: unit must be one of {UNITS}, level 0 to {len(LEVELS) - 1}")
        adapter.stop(kill=True)
        return 2
    run_level = claimed if args.level is None else args.level

    print("TAP version 14")
    print(
        f"# binding {hello.get('binding')}, unit {hello['unit']}, claims {LEVELS[claimed]}; running up to L{run_level}"
    )
    number = 0
    passed: Dict[int, int] = {}
    failed: Dict[int, int] = {}
    skipped = 0
    for corpus in corpora:
        if args.corpus and corpus["name"] not in args.corpus:
            continue
        problems = integrity(corpus)
        number += 1
        if problems:
            failed[corpus["level"]] = failed.get(corpus["level"], 0) + 1
            print(f"not ok {number} - {corpus['name']}: corpus integrity")
            print(yaml_block("; ".join(problems)), end="")
        else:
            print(f"ok {number} - {corpus['name']}: corpus integrity")
        for case in corpus["loaded"]:
            if args.case and case["name"] not in args.case:
                continue
            level = case_level(corpus, case)
            label = f"{corpus['name']}/{case['name']}"
            number += 1
            if level > run_level:
                skipped += 1
                print(f"ok {number} - {label} # SKIP L{level} is above L{run_level}")
                continue
            message = None
            try:
                actual, expected = compare(Session(adapter), corpus, case)
                if actual != expected:
                    message = first_difference(actual, expected)
            except Thrown as thrown:
                message = f"the binding raised {thrown.error!r}"
            except CaseError as error:
                message = str(error)
            except AdapterFault as error:
                message = f"adapter fault: {error}"
                try:
                    adapter.restart()
                except (AdapterFault, OSError) as again:
                    print(f"Bail out! the adapter did not restart: {again}")
                    return 2
            if message is None:
                passed[level] = passed.get(level, 0) + 1
                print(f"ok {number} - {label} # L{level}")
            else:
                failed[level] = failed.get(level, 0) + 1
                print(f"not ok {number} - {label} # L{level}")
                print(yaml_block(message), end="")
    adapter.stop()
    print(f"1..{number}")
    for level in range(len(LEVELS)):
        if level <= run_level:
            print(f"# {LEVELS[level]}: {passed.get(level, 0)} passed, {failed.get(level, 0)} failed")
    if skipped:
        print(f"# {skipped} skipped above L{run_level}")
    achieved = -1
    for level in range(run_level + 1):
        if failed.get(level, 0):
            break
        achieved = level
    if args.corpus or args.case or run_level < claimed:
        held = "not checked (only part of the cases ran)"
    else:
        held = "holds" if achieved >= claimed else "does not hold"
    print(
        f"# claimed {LEVELS[claimed]}: {held}; every case run passes up to "
        + (f"L{achieved}" if achieved >= 0 else "no level")
    )
    if claimed == len(LEVELS) - 1 or run_level == len(LEVELS) - 1:
        print("# L4 has no shared cases yet (spec/conformance.md section 7): each binding tests its adapters itself")
    return 1 if any(failed.values()) else 0


if __name__ == "__main__":
    sys.exit(main())
