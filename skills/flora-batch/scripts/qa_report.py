#!/usr/bin/env python3
"""Render Claude's QA verdicts into the canonical report artifacts.

Usage:
  qa_report.py --results qa_results.json --out-dir DIR

qa_results.json is written by Claude after judging each qa_manifest.json pair
against the color/construction rubric in SKILL.md's "Garment QA" section --
a JSON array of:
  {"output": path, "input": path,
   "color": {"verdict": "match|minor_shift|mismatch", "notes": str},
   "construction": {"verdict": "match|minor_deviation|mismatch", "notes": str}}

Writes DIR/qa_report.json (same records plus a computed "overall_flag") and
DIR/qa_report.md (human-readable table). Prints ONLY the flagged items --
that's what gets relayed to the user in chat, not a full dump of every pair.
"""
import argparse, os, json, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from floralib import qa_overall_flag, render_qa_report_md, save_json_atomic, validate_qa_results


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", required=True)
    ap.add_argument("--out-dir", required=True)
    a = ap.parse_args()

    results = json.load(open(a.results))
    problems = validate_qa_results(results)
    if problems:
        print("INVALID qa_results.json -- fix the verdicts and re-run:")
        for p in problems:
            print("  ", p)
        print("allowed: color = match|minor_shift|mismatch; "
              "construction = match|minor_deviation|mismatch")
        sys.exit(2)

    for r in results:
        r["overall_flag"] = qa_overall_flag(r["color"]["verdict"], r["construction"]["verdict"])

    os.makedirs(a.out_dir, exist_ok=True)
    save_json_atomic(results, os.path.join(a.out_dir, "qa_report.json"))
    open(os.path.join(a.out_dir, "qa_report.md"), "w").write(render_qa_report_md(results))

    flagged = [r for r in results if r["overall_flag"]]
    print("checked   :", len(results))
    print("flagged   :", len(flagged))
    for r in flagged:
        print("FLAG  %s  color=%s  construction=%s" % (
            os.path.basename(r["output"]), r["color"]["verdict"], r["construction"]["verdict"]))


if __name__ == "__main__":
    main()
