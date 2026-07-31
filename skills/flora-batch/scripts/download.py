#!/usr/bin/env python3
"""Download FLORA outputs, state-driven and resumable. Two modes:

  Per-image batch:  download.py --state STATE [--compressed]
      Each item with stage == "outputs_ready" -> <stem><suffix>_<n>.png.
  Compose run:      download.py --outputs OUTPUTS.json --out-dir DIR [--compressed]
      Each {output_id,url} -> DIR/<output_id>.png.

Host-aware (floralib.output_variants): ImageKit tries ?tr=orig-true then bare;
media.flora.ai downloads bare (already full-res). Safe to re-run (skips files
already present with size > 0).
"""
import argparse, os, json, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from floralib import output_variants, plan_downloads, save_json_atomic


def dl(url, dest, compressed):
    tmp = dest + ".part"
    for candidate in output_variants(url, compressed):
        p = subprocess.run(
            ["curl", "-sS", "--connect-timeout", "30", "--max-time", "600",
             "-o", tmp, "-w", "%{http_code} %{size_download}", candidate],
            capture_output=True, text=True)
        parts = p.stdout.strip().split()
        if len(parts) >= 2 and parts[0] == "200" and int(parts[1]) > 0:
            os.replace(tmp, dest)
            return int(parts[1])
        if os.path.exists(tmp):
            os.remove(tmp)
    return 0


def download_outputs(outputs, out_dir, compressed):
    os.makedirs(out_dir, exist_ok=True)
    ok, tb, fails = 0, 0, []
    for url, dest in plan_downloads(outputs, out_dir):
        if os.path.isfile(dest) and os.path.getsize(dest) > 0:
            ok += 1; tb += os.path.getsize(dest)
            print("SKIP " + os.path.basename(dest), flush=True); continue
        sz = dl(url, dest, compressed)
        if sz > 0:
            ok += 1; tb += sz
            print("OK   %s  %.2f MB" % (os.path.basename(dest), sz / 1048576), flush=True)
        else:
            fails.append(os.path.basename(dest))
            print("FAIL " + os.path.basename(dest), flush=True)
    print("--- downloaded %d/%d  (%.1f MB)" % (ok, len(outputs), tb / 1048576))
    if fails:
        print("FAILS:", json.dumps(fails))
    return len(fails)


def download_state(state_path, compressed):
    s = json.load(open(state_path))
    OUT, suffix, items = s["output"], s.get("suffix", "_MCP"), s["items"]
    def save(): save_json_atomic(s, state_path)
    ok, fail, tb = 0, 0, 0
    for it in items:
        if it["stage"] == "done":
            ok += 1; continue
        if it["stage"] != "outputs_ready" or not it.get("outputs"):
            continue
        d = os.path.join(OUT, it.get("out_subdir", "")); os.makedirs(d, exist_ok=True)
        files, good = [], True
        for n, url in enumerate(it["outputs"], 1):
            dest = os.path.join(d, "%s%s_%d.png" % (it["stem"], suffix, n))
            sz = dl(url, dest, compressed)
            if sz > 0: files.append(dest); tb += sz
            else: good = False; print("FAIL %s%s_%d" % (it["stem"], suffix, n), flush=True)
        if good:
            it["files"] = files; it["stage"] = "done"; it["error"] = None; ok += 1
            print("OK   " + it["stem"], flush=True)
        else:
            fail += 1
        save()
    print("--- done %d  (%.0f MB)  fail %d" % (ok, tb / 1048576, fail))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--state")
    ap.add_argument("--outputs")
    ap.add_argument("--out-dir")
    ap.add_argument("--compressed", action="store_true",
                    help="download bare CDN image instead of pristine ImageKit original")
    a = ap.parse_args()
    if a.outputs:
        if not a.out_dir:
            ap.error("--outputs requires --out-dir")
        rc = download_outputs(json.load(open(a.outputs)), a.out_dir, a.compressed)
        sys.exit(1 if rc else 0)
    elif a.state:
        download_state(a.state, a.compressed)
    else:
        ap.error("provide --state (per-image) or --outputs + --out-dir (compose)")


if __name__ == "__main__":
    main()
