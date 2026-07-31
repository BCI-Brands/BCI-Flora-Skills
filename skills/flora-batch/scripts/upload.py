#!/usr/bin/env python3
"""Backend-agnostic uploader for a flora-batch, state-driven and resumable.

Usage: upload.py --state STATE --reservations RES.json

RES.json is a JSON object KEYED BY EACH ITEM'S rel:
    {"<rel>": {"asset_id": "...", "url": "<POST endpoint>", "form_fields": {...}}}
Only items still at stage "pending" need an entry, so re-reserving just the
failed/expired items produces a naturally-partial file. (The old positional
LIST format is rejected with an error -- it silently mispaired items when the
order drifted.)

form_fields are sent EXACTLY as given (works for ImageKit token/signature AND
GCS policy/x-goog-signature -- this script never assumes a backend). The file
part is sent LAST (required by S3/GCS presigned POST). Success = HTTP 200/204.

Reservations expire (~15 min). Any item that returns 400/403 stays "pending"
for the agent to assets.retry() and re-run this script with fresh entries.
"""
import argparse, os, json, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from floralib import save_json_atomic, match_reservations, build_curl_upload_args

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--state", required=True)
    ap.add_argument("--reservations", required=True)
    a = ap.parse_args()
    s = json.load(open(a.state)); IN, items = s["input"], s["items"]
    res = json.load(open(a.reservations))
    if not isinstance(res, dict):
        print('reservations must be a JSON object keyed by item rel: '
              '{"<rel>": {"asset_id","url","form_fields"}} -- the old '
              "positional-list format is no longer supported")
        sys.exit(2)
    m = match_reservations(res, items)
    if m["unknown_rels"]:
        print("UNKNOWN reservation keys (not in state -- typo?):", m["unknown_rels"])
    if m["missing_rels"]:
        print("MISSING reservations for pending items:", m["missing_rels"])

    def save(): save_json_atomic(s, a.state)
    ok, fail = 0, []
    for it in items:
        if it["stage"] != "pending":
            ok += 1; continue
        r = m["matched"].get(it["rel"])
        if not isinstance(r, dict) or "url" not in r or "form_fields" not in r:
            it["error"] = "no reservation"; fail.append(it["rel"]); save(); continue
        src = os.path.join(IN, it["rel"])
        if not os.path.isfile(src):
            it["error"] = "missing source"; fail.append(it["rel"]); save(); continue
        args = build_curl_upload_args(r["url"], r["form_fields"], src)
        p = subprocess.run(args, capture_output=True, text=True)
        code = p.stdout.strip()
        if code in ("200", "204"):
            it["asset_id"] = r["asset_id"]; it["stage"] = "uploaded"; it["error"] = None
            ok += 1; print(f"OK {code} {it['rel']}", flush=True)
        else:
            it["error"] = f"upload {code}"; fail.append(it["rel"])
            print(f"FAIL {code} {it['rel']}", flush=True)
        save()
    print(f"--- uploaded {ok}/{len(items)}  fail {len(fail)}")
    if fail: print("EXPIRED/FAILED (assets.retry + re-run):", json.dumps(fail))

if __name__ == "__main__":
    main()
