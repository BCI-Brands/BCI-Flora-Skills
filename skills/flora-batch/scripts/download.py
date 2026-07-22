#!/usr/bin/env python3
"""Download completed outputs for a flora-batch, state-driven and resumable.

Usage: download.py --state /path/to/batch_state.json [--compressed] [--bg]

Downloads every item whose stage == "outputs_ready" (its `outputs` = [url1, url2, ...]).
Saves as <out_subdir>/<stem><suffix>_<n>.png. Tries ?tr=orig-true (pristine) then bare.
Checkpoints stage -> "done" after each item. Safe to re-run (skips done).
"""
import argparse, os, json, subprocess

def dl(url, dest, compressed):
    order = ("",) if compressed else ("?tr=orig-true", "")
    for suf in order:
        p = subprocess.run(["curl", "-sS", "--connect-timeout", "30", "--max-time", "600",
                            "-o", dest, "-w", "%{http_code} %{size_download}", url + suf],
                           capture_output=True, text=True)
        parts = p.stdout.strip().split()
        if len(parts) >= 2 and parts[0] == "200" and int(parts[1]) > 0:
            return int(parts[1])
    return 0

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--state", required=True)
    ap.add_argument("--compressed", action="store_true", help="download bare CDN JPEG instead of pristine PNG")
    a = ap.parse_args()
    s = json.load(open(a.state))
    OUT, suffix, items = s["output"], s.get("suffix", "_MCP"), s["items"]

    def save(): json.dump(s, open(a.state, "w"), indent=2)

    ok, fail, tb = 0, 0, 0
    for it in items:
        if it["stage"] == "done":
            ok += 1; continue
        if it["stage"] != "outputs_ready" or not it.get("outputs"):
            continue
        d = os.path.join(OUT, it.get("out_subdir", "")); os.makedirs(d, exist_ok=True)
        files, good = [], True
        for n, url in enumerate(it["outputs"], 1):
            dest = os.path.join(d, f"{it['stem']}{suffix}_{n}.png")
            sz = dl(url, dest, a.compressed)
            if sz > 0: files.append(dest); tb += sz
            else: good = False; print(f"FAIL {it['stem']}{suffix}_{n}", flush=True)
        if good:
            it["files"] = files; it["stage"] = "done"; it["error"] = None; ok += 1
            print(f"OK   {it['stem']}", flush=True)
        else:
            fail += 1
        save()
    from collections import Counter
    print(f"--- done {ok}  ({tb/1048576:.0f} MB)  fail {fail}")
    print("stages:", dict(Counter(i["stage"] for i in items)))

if __name__ == "__main__":
    main()
