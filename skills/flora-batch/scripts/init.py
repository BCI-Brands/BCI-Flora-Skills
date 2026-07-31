#!/usr/bin/env python3
"""Init a flora-batch: enumerate images, build the output tree, write batch_state.json.

Usage:
  init.py --input DIR --technique tech_xxx --input-id INPUT_ID \
          --convention {same|sibling|mirror} [--suffix _MCP] [--recurse] [--run-cost 0.72]

Conventions:
  same    -> outputs land in the input folder,           files: <stem><suffix>_N.png
  sibling -> outputs land in  <input>+<suffix>/          (flat)
  mirror  -> outputs mirror the input tree, every folder gets <suffix>
State file is written INTO the output root as batch_state.json (resume-aware).
"""
import argparse, os, json
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from floralib import save_json_atomic
from collections import Counter

EXTS = (".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif", ".tif", ".tiff")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--technique", required=True)
    ap.add_argument("--input-id", required=True)
    ap.add_argument("--convention", choices=["same", "sibling", "mirror"], required=True)
    ap.add_argument("--suffix", default="_MCP")
    ap.add_argument("--recurse", action="store_true")
    ap.add_argument("--run-cost", type=float, default=0.0)
    a = ap.parse_args()
    IN = os.path.abspath(a.input)

    # enumerate
    rels = []
    if a.recurse:
        for root, _d, files in os.walk(IN):
            for f in files:
                if f.lower().endswith(EXTS):
                    rels.append(os.path.relpath(os.path.join(root, f), IN))
    else:
        rels = [f for f in os.listdir(IN) if f.lower().endswith(EXTS) and os.path.isfile(os.path.join(IN, f))]
    rels.sort()

    OUT = IN if a.convention == "same" else IN + a.suffix
    def out_subdir(rel):
        d = os.path.dirname(rel)
        if a.convention != "mirror" or d in ("", "."):
            return ""
        return os.path.join(*[p + a.suffix for p in d.split(os.sep)])

    prev = {}
    state_path = os.path.join(OUT, "batch_state.json")
    if os.path.exists(state_path):
        prev = {e["rel"]: e for e in json.load(open(state_path)).get("items", [])}

    items = []
    for rel in rels:
        if rel in prev:
            items.append(prev[rel])
        else:
            items.append({"rel": rel, "stem": os.path.splitext(os.path.basename(rel))[0],
                          "out_subdir": out_subdir(rel), "stage": "pending", "asset_id": None,
                          "run_id": None, "outputs": [], "files": [], "error": None})
        os.makedirs(os.path.join(OUT, items[-1]["out_subdir"]), exist_ok=True)

    state = {"input": IN, "output": OUT, "technique": a.technique, "input_id": a.input_id,
             "suffix": a.suffix, "convention": a.convention, "run_cost": a.run_cost, "items": items}
    save_json_atomic(state, state_path)
    print(f"images     : {len(items)}")
    print(f"output root: {OUT}")
    print(f"state file : {state_path}")
    print(f"est. cost  : {len(items)} x ${a.run_cost} = ${len(items)*a.run_cost:.2f}")
    print(f"stages     : {dict(Counter(i['stage'] for i in items))}")

if __name__ == "__main__":
    main()
