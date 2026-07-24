#!/usr/bin/env python3
"""Resolve user-picked output filenames back to their input photos for QA.
Per-image batches only in v1 -- compose (multi-input) support is deferred,
see docs/specs/garment-qa-comparison.md, Open Question 1.

Usage:
  qa_resolve.py --state batch_state.json --selected out1.png,out2.png

Writes qa_manifest.json next to --state: [{"output": path, "input": path}].
Any selected filename not found in --state is printed under UNRESOLVED
instead of being silently dropped, and the script exits 1.
"""
import argparse, os, json, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from floralib import resolve_qa_pairs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--state", required=True)
    ap.add_argument("--selected", required=True, help="comma-separated output filenames")
    a = ap.parse_args()

    state = json.load(open(a.state))
    selected = [s.strip() for s in a.selected.split(",") if s.strip()]
    result = resolve_qa_pairs(state, selected)

    manifest_path = os.path.join(os.path.dirname(os.path.abspath(a.state)), "qa_manifest.json")
    json.dump(result["pairs"], open(manifest_path, "w"), indent=2)

    print("resolved  :", len(result["pairs"]))
    print("manifest  :", manifest_path)
    if result["unresolved"]:
        print("UNRESOLVED (not found in state -- check spelling):", result["unresolved"])
        sys.exit(1)


if __name__ == "__main__":
    main()
