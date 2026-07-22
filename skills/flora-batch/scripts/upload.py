#!/usr/bin/env python3
"""Backend-agnostic uploader for a flora-batch, state-driven and resumable.

Usage: upload.py --state STATE --reservations RES.json

RES.json is a list aligned with state["items"] order, each entry:
    {"asset_id": "...", "url": "<POST endpoint>", "form_fields": { ... }}
form_fields are sent EXACTLY as given (works for ImageKit token/signature AND GCS
policy/x-goog-signature — this script never assumes a backend). The file part is
sent LAST (required by S3/GCS presigned POST). Success = HTTP 200 or 204.

Reservations expire (~15 min). Any item that returns 400/403 stays "pending" for the
agent to assets.retry() and re-run this script on the fresh reservations.
"""
import argparse, os, json, subprocess

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--state", required=True)
    ap.add_argument("--reservations", required=True)
    a = ap.parse_args()
    s = json.load(open(a.state)); IN, items = s["input"], s["items"]
    res = json.load(open(a.reservations))
    res = res.get("result", res) if isinstance(res, dict) else res
    if isinstance(res, dict):
        res = res.get("items") or res.get("r")
    assert len(res) == len(items), f"reservation/item mismatch {len(res)} vs {len(items)}"

    def save(): json.dump(s, open(a.state, "w"), indent=2)
    ok, fail = 0, []
    for i, it in enumerate(items):
        if it["stage"] != "pending":
            ok += 1; continue
        r = res[i]
        if not isinstance(r, dict) or "url" not in r or "form_fields" not in r:
            it["error"] = "no reservation"; fail.append(it["rel"]); save(); continue
        src = os.path.join(IN, it["rel"])
        if not os.path.isfile(src):
            it["error"] = "missing source"; fail.append(it["rel"]); save(); continue
        args = ["curl", "-sS", "--connect-timeout", "30", "--max-time", "300", "-o", "/dev/null",
                "-w", "%{http_code}", "-X", "POST", r["url"]]
        for k, v in r["form_fields"].items():
            args += ["-F", f"{k}={v}"]
        args += ["-F", f"file=@{src}"]          # file LAST
        p = subprocess.run(args, capture_output=True, text=True)
        code = p.stdout.strip()
        if code in ("200", "204"):
            it["asset_id"] = r["asset_id"]; it["stage"] = "uploaded"; it["error"] = None
            ok += 1; print(f"[{i}] OK {code} {it['rel']}", flush=True)
        else:
            it["error"] = f"upload {code}"; fail.append(it["rel"])
            print(f"[{i}] FAIL {code} {it['rel']}", flush=True)
        save()
    print(f"--- uploaded {ok}/{len(items)}  fail {len(fail)}")
    if fail: print("EXPIRED/FAILED (assets.retry + re-run):", json.dumps(fail))

if __name__ == "__main__":
    main()
