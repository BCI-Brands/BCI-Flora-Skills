#!/usr/bin/env python3
"""Build a compose (multi-input) run for a technique whose ONE run consumes
several role inputs (e.g. top/bottom/shoes) and emits many named outputs.

Usage:
  compose.py --input DIR --technique tech_xxx --run-cost 4.32 \
             --roles top,bottom,shoes [--map top=FILE,bottom=FILE,shoes=FILE]

Writes DIR/compose_state.json and prints the role mapping + the correct cost
gate (1 run x run_cost). Without --map, files are auto-mapped to roles by
filename keywords; any ambiguity is printed for you to confirm before running.
"""
import argparse, os, json, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from floralib import map_files_to_roles, build_compose_state, estimate_cost, compose_state_in_progress, save_json_atomic

EXTS = (".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif", ".tif", ".tiff")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--technique", required=True)
    ap.add_argument("--run-cost", type=float, required=True)
    ap.add_argument("--roles", required=True, help="comma-separated input ids, e.g. top,bottom,shoes")
    ap.add_argument("--map", help="explicit role=file pairs, comma-separated (overrides auto)")
    ap.add_argument("--force", action="store_true", help="overwrite an in-progress compose_state.json")
    a = ap.parse_args()

    IN = os.path.abspath(a.input)
    role_ids = [r.strip() for r in a.roles.split(",") if r.strip()]
    files = sorted(f for f in os.listdir(IN)
                   if f.lower().endswith(EXTS) and os.path.isfile(os.path.join(IN, f)))

    if a.map:
        role_map = {}
        for pair in a.map.split(","):
            role, fn = pair.split("=", 1)
            role_map[role.strip()] = fn.strip()
        unmatched, unfilled = [], [r for r in role_ids if r not in role_map]
        bad_roles = [r for r in role_map if r not in role_ids]
        for r in bad_roles:
            del role_map[r]
        missing = [(r, fn) for r, fn in role_map.items() if not os.path.isfile(os.path.join(IN, fn))]
    else:
        res = map_files_to_roles(files, role_ids)
        role_map, unmatched, unfilled = res["mapping"], res["unmatched_files"], res["unfilled_roles"]
        bad_roles, missing = [], []

    state_path = os.path.join(IN, "compose_state.json")
    if os.path.exists(state_path) and not a.force:
        if compose_state_in_progress(json.load(open(state_path))):
            print("refusing to overwrite in-progress compose_state.json (pass --force to reset)")
            sys.exit(2)

    state = build_compose_state(IN, a.technique, role_map, a.run_cost)
    save_json_atomic(state, state_path)

    print("role mapping:")
    for r in role_ids:
        print("  %-8s <- %s" % (r, role_map.get(r, "??? UNFILLED")))
    if unmatched:
        print("unmatched files:", unmatched)
    if unfilled:
        print("UNFILLED roles :", unfilled, " (resolve with --map before running)")
    if bad_roles:
        print("IGNORED --map roles not in --roles:", bad_roles)
    if missing:
        print("MISSING files (fix before running):", [fn for _, fn in missing])
    print("cost gate      : 1 run x $%s = $%s" % (a.run_cost, estimate_cost(a.run_cost, 1)))
    print("state          :", state_path)
    sys.exit(1 if (unfilled or bad_roles or missing) else 0)


if __name__ == "__main__":
    main()
