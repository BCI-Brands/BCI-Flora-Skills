#!/usr/bin/env python3
"""Resolve user-picked output filenames back to their input photos for QA.
Per-image batches only in v1 -- compose (multi-input) support is deferred,
see docs/specs/garment-qa-comparison.md, Open Question 1.

Usage:
  qa_resolve.py --state batch_state.json --selected out1.png,out2.png

Writes qa_manifest.json next to --state: [{"output": path, "input": path}].
Any selected filename not found in --state is printed under UNRESOLVED
instead of being silently dropped. Any selected filename whose basename
collides across two different input photos (a recursive-batch edge case --
see resolve_qa_pairs docstring) is printed under AMBIGUOUS instead of being
silently paired with a possibly-wrong input. Either case exits 1 and qa_manifest.json is NOT written (any stale manifest
from a prior run is deleted) -- a partial manifest must never silently shrink
QA coverage.
"""
import argparse, os, json, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from floralib import resolve_qa_pairs, save_json_atomic


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--state", required=True)
    ap.add_argument("--selected", required=True, help="comma-separated output filenames")
    a = ap.parse_args()

    state = json.load(open(a.state))
    selected = [s.strip() for s in a.selected.split(",") if s.strip()]
    result = resolve_qa_pairs(state, selected)

    manifest_path = os.path.join(os.path.dirname(os.path.abspath(a.state)), "qa_manifest.json")
    if result["unresolved"] or result["ambiguous"]:
        if os.path.exists(manifest_path):
            os.remove(manifest_path)      # never leave a stale manifest to reuse
        if result["unresolved"]:
            print("UNRESOLVED (not found in state -- check spelling):", result["unresolved"])
        if result["ambiguous"]:
            print("AMBIGUOUS (same filename, multiple different inputs -- resolve manually):",
                  result["ambiguous"])
        print("qa_manifest.json NOT written -- fix the selections above and re-run")
        sys.exit(1)

    save_json_atomic(result["pairs"], manifest_path)
    print("resolved  :", len(result["pairs"]))
    print("manifest  :", manifest_path)


if __name__ == "__main__":
    main()
