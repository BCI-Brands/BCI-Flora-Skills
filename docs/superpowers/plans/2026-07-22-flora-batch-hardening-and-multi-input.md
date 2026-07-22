# FLORA Batch Skill Hardening & Multi-Input Support — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Harden the `flora-batch` skill so runs like the 2026-07-22 "LOOK 9" job work first-try — correct three stale/incorrect rules, add workspace-billed runs, and add first-class support for multi-input "compose" techniques — with the new logic covered by unit tests.

**Architecture:** Extract all pure, network-free logic into a new, unit-tested `floralib.py`. Keep the existing thin, state-file-driven CLI scripts (`upload.py`, `download.py`) and add two small ones (`compose.py`, `contact_sheet.py`) that import `floralib`. Rewrite the stale "hard-won rules" in `SKILL.md` and add two new sections (Workspace Billing, Compose Techniques). TDD applies to `floralib` + the scripts that wrap it; `SKILL.md` changes are documentation verified by content grep.

**Tech Stack:** Python 3.9+ standard library (`argparse`, `json`, `subprocess`, `base64`, `re`, `os`), `pytest`, `curl`, the FLORA MCP (`execute` / `search_docs`), `git`.

---

## Context & Motivation

Findings from the 2026-07-22 LOOK 9 run (`front-pocket-2k-nfs`, 3 role inputs → 1 run → 24 outputs, billed to the BCI Brands workspace):

1. **Compose techniques are unsupported.** The skill assumes 1 image → 1 run → generic `_N.png` outputs. A technique with `top`/`bottom`/`shoes` inputs and 24 named outputs broke `init.py` (single `--input-id`), the state schema, `download.py` naming, and the cost model.
2. **The "oversized `execute` auto-saves to a file" rule is false.** The current MCP server hard-errors `Output exceeded 100000 bytes` with no file path. The skill's only documented defense against hand-copying GCS signatures does not exist.
3. **Cost-gate math is wrong for compose techniques** (`N images × cost × outputs` → $12.96+; real cost = 1 run × $4.32).
4. **Workspace billing is unmodeled.** Credits are per-workspace; the nested `techniques.runs.create` route bills the default workspace; billing a chosen workspace requires `runs.startTechnique({workspace_id, inputs})` with an id→value `inputs` map, polled via `generations.retrieve` (the nested retrieve 404s).
5. **Retry semantics + single-run timeouts** aren't covered: a single heavy run can `GENERATION_PROVIDER_TIMEOUT` and needs a *fresh* idempotency key to re-run; failed runs are not billed.
6. **Download `?tr=orig-true` is ImageKit-only**; outputs arrived on `media.flora.ai` where the bare URL is already full-res.
7. **Review via headless Chrome doesn't work in-harness**; a portable self-contained contact sheet + programmatic checks (count/dims/size) do.

## File Structure

| File | Action | Responsibility |
|---|---|---|
| `skills/flora-batch/scripts/floralib.py` | **Create** | Pure helpers: host-aware download variants, download planning, cost estimate, file→role mapping, GCS reservation validation, compose-state builder. No network, no side effects. |
| `skills/flora-batch/scripts/download.py` | **Modify** | Import `floralib.output_variants`/`plan_downloads`; add a `--outputs`/`--out-dir` compose mode that saves by `output_id`. Keep the per-image `--state` mode. |
| `skills/flora-batch/scripts/compose.py` | **Create** | CLI: build `compose_state.json` for a multi-input technique from a folder (auto/explicit role map) and print the correct cost gate. |
| `skills/flora-batch/scripts/contact_sheet.py` | **Create** | CLI + `render_contact_sheet()`: emit a portable, self-contained review gallery (relative `<img>` refs, press-D dev mode). No headless Chrome. |
| `skills/flora-batch/scripts/tests/conftest.py` | **Create** | Put the `scripts/` dir on `sys.path` for tests. |
| `skills/flora-batch/scripts/tests/test_floralib.py` | **Create** | Unit tests for every `floralib` function. |
| `skills/flora-batch/scripts/tests/test_contact_sheet.py` | **Create** | Unit test for `render_contact_sheet()`. |
| `skills/flora-batch/SKILL.md` | **Modify** | Fix cost gate, file-bridge rule, idempotency/retry, throttle/timeout, pristine-download rows; add Workspace Billing + Compose sections; refresh Scripts list + Common mistakes. |
| `README.md` | **Modify** | Add the three new scripts + a one-line changelog entry. |

## Conventions for the implementer

- **Branch:** work on `feat/flora-batch-hardening` (create with `git switch -c feat/flora-batch-hardening`). Never commit to `main`.
- **Tests:** `pytest`. If missing: `python3 -m pip install --quiet pytest`. Run from repo root: `python3 -m pytest skills/flora-batch/scripts/tests -q`.
- **Import pattern:** wrapper scripts do `sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))` then `from floralib import ...`. Tests rely on `conftest.py` for the same path.
- **Commits:** one per task (conventional commits). Frequent and small.
- **DRY / YAGNI:** all pure logic lives in `floralib`; scripts stay thin. Don't add config knobs nobody asked for.

---

### Task 1: Create `floralib.py` with `output_variants` (host-aware downloads)

**Files:**
- Create: `skills/flora-batch/scripts/floralib.py`
- Create: `skills/flora-batch/scripts/tests/conftest.py`
- Test: `skills/flora-batch/scripts/tests/test_floralib.py`

- [ ] **Step 1: Write the conftest so tests can import the module**

Create `skills/flora-batch/scripts/tests/conftest.py`:

```python
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
```

- [ ] **Step 2: Write the failing test**

Create `skills/flora-batch/scripts/tests/test_floralib.py`:

```python
import floralib


def test_output_variants_imagekit_tries_orig_true_first():
    url = "https://ik.imagekit.io/flora/run_abc/output_3.png"
    assert floralib.output_variants(url) == [url + "?tr=orig-true", url]


def test_output_variants_media_flora_is_bare_only():
    url = "https://media.flora.ai/node-inputs/2026/7/22/anonymous/abc.png"
    assert floralib.output_variants(url) == [url]


def test_output_variants_compressed_is_always_bare():
    url = "https://ik.imagekit.io/flora/run_abc/output_3.png"
    assert floralib.output_variants(url, compressed=True) == [url]


def test_output_variants_imagekit_with_existing_query_uses_ampersand():
    url = "https://ik.imagekit.io/flora/x.png?v=2"
    assert floralib.output_variants(url) == [url + "&tr=orig-true", url]
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `python3 -m pytest skills/flora-batch/scripts/tests/test_floralib.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'floralib'`.

- [ ] **Step 4: Create the module with the minimal implementation**

Create `skills/flora-batch/scripts/floralib.py`:

```python
#!/usr/bin/env python3
"""Pure, network-free helpers for the flora-batch skill. Unit-tested; imported by
the thin CLI scripts (download.py, compose.py, contact_sheet.py)."""
import base64
import os
import re


def output_variants(url, compressed=False):
    """Ordered list of URLs to try when downloading one output.

    ImageKit URLs try the pristine ?tr=orig-true transform first, then bare.
    media.flora.ai (and every other host) are already full-res -> bare only.
    """
    if compressed:
        return [url]
    if "ik.imagekit.io" in url:
        sep = "&" if "?" in url else "?"
        return [url + sep + "tr=orig-true", url]
    return [url]
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `python3 -m pytest skills/flora-batch/scripts/tests/test_floralib.py -q`
Expected: PASS (4 passed).

- [ ] **Step 6: Commit**

```bash
git add skills/flora-batch/scripts/floralib.py skills/flora-batch/scripts/tests/conftest.py skills/flora-batch/scripts/tests/test_floralib.py
git commit -m "feat(flora-batch): add floralib.output_variants (host-aware downloads)"
```

---

### Task 2: `plan_downloads` (name compose outputs by `output_id`)

**Files:**
- Modify: `skills/flora-batch/scripts/floralib.py`
- Test: `skills/flora-batch/scripts/tests/test_floralib.py`

- [ ] **Step 1: Write the failing test** (append to `test_floralib.py`)

```python
def test_plan_downloads_names_by_output_id():
    outputs = [
        {"output_id": "full-1", "url": "https://media.flora.ai/a.png"},
        {"output_id": "top-detail-2", "url": "https://media.flora.ai/b.png"},
    ]
    assert floralib.plan_downloads(outputs, "/out") == [
        ("https://media.flora.ai/a.png", "/out/full-1.png"),
        ("https://media.flora.ai/b.png", "/out/top-detail-2.png"),
    ]
```

- [ ] **Step 2: Run to verify it fails**

Run: `python3 -m pytest skills/flora-batch/scripts/tests/test_floralib.py::test_plan_downloads_names_by_output_id -q`
Expected: FAIL — `AttributeError: module 'floralib' has no attribute 'plan_downloads'`.

- [ ] **Step 3: Implement** (append to `floralib.py`)

```python
def plan_downloads(outputs, out_dir):
    """Map compose-run outputs to (url, dest_path); dest = out_dir/<output_id>.png."""
    return [(o["url"], os.path.join(out_dir, o["output_id"] + ".png")) for o in outputs]
```

- [ ] **Step 4: Run to verify it passes**

Run: `python3 -m pytest skills/flora-batch/scripts/tests/test_floralib.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add skills/flora-batch/scripts/floralib.py skills/flora-batch/scripts/tests/test_floralib.py
git commit -m "feat(flora-batch): add floralib.plan_downloads (name outputs by output_id)"
```

---

### Task 3: `estimate_cost` (flat per-run pricing)

**Files:**
- Modify: `skills/flora-batch/scripts/floralib.py`
- Test: `skills/flora-batch/scripts/tests/test_floralib.py`

- [ ] **Step 1: Write the failing test** (append)

```python
def test_estimate_cost_is_flat_per_run():
    assert floralib.estimate_cost(4.32, 1) == 4.32     # one compose look
    assert floralib.estimate_cost(0.72, 10) == 7.2     # ten per-image runs
    assert floralib.estimate_cost(4.32, 0) == 0.0
```

- [ ] **Step 2: Run to verify it fails**

Run: `python3 -m pytest skills/flora-batch/scripts/tests/test_floralib.py::test_estimate_cost_is_flat_per_run -q`
Expected: FAIL — no attribute `estimate_cost`.

- [ ] **Step 3: Implement** (append)

```python
def estimate_cost(run_cost, num_runs):
    """Total USD = run_cost x number of RUNS. Outputs-per-run are free; do not
    multiply by output count. Compose look = 1 run; per-image batch = N runs."""
    return round(run_cost * num_runs, 2)
```

- [ ] **Step 4: Run to verify it passes**

Run: `python3 -m pytest skills/flora-batch/scripts/tests/test_floralib.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add skills/flora-batch/scripts/floralib.py skills/flora-batch/scripts/tests/test_floralib.py
git commit -m "feat(flora-batch): add floralib.estimate_cost (flat per-run pricing)"
```

---

### Task 4: `map_files_to_roles` (auto role assignment for compose)

**Files:**
- Modify: `skills/flora-batch/scripts/floralib.py`
- Test: `skills/flora-batch/scripts/tests/test_floralib.py`

- [ ] **Step 1: Write the failing tests** (append)

```python
def test_map_files_to_roles_look9_maps_cleanly():
    files = [
        "91526272_143_OATMEAL_061226_5564.jpg",
        "PROP_DENIM_JEANS_01_050526_9884.jpg",
        "PROP_SHOE_01_050526_9890.jpg",
    ]
    res = floralib.map_files_to_roles(files, ["top", "bottom", "shoes"])
    assert res["mapping"] == {
        "top": "91526272_143_OATMEAL_061226_5564.jpg",
        "bottom": "PROP_DENIM_JEANS_01_050526_9884.jpg",
        "shoes": "PROP_SHOE_01_050526_9890.jpg",
    }
    assert res["unmatched_files"] == []
    assert res["unfilled_roles"] == []


def test_map_files_to_roles_flags_ambiguity():
    files = ["a_shirt.jpg", "b_tee.jpg", "x_jean.jpg"]
    res = floralib.map_files_to_roles(files, ["top", "bottom", "shoes"])
    assert res["mapping"] == {"bottom": "x_jean.jpg"}
    assert set(res["unmatched_files"]) == {"a_shirt.jpg", "b_tee.jpg"}
    assert set(res["unfilled_roles"]) == {"top", "shoes"}
```

- [ ] **Step 2: Run to verify it fails**

Run: `python3 -m pytest skills/flora-batch/scripts/tests/test_floralib.py -k map_files -q`
Expected: FAIL — no attribute `map_files_to_roles`.

- [ ] **Step 3: Implement** (append)

```python
DEFAULT_ROLE_KEYWORDS = {
    "top": ["top", "shirt", "tee", "tshirt", "knit", "sweater", "cardigan",
            "blouse", "jacket", "blazer", "coat", "hoodie"],
    "bottom": ["bottom", "jean", "denim", "pant", "trouser", "skirt", "skort",
               "short", "legging", "chino"],
    "shoes": ["shoe", "heel", "sneaker", "boot", "sandal", "mule", "loafer",
              "pump", "flat"],
    "dress": ["dress", "gown", "jumpsuit", "romper"],
    "bag": ["bag", "purse", "tote", "clutch", "handbag"],
}


def map_files_to_roles(files, role_ids, keywords=None):
    """Best-effort assignment of filenames to a technique's input ids by keyword.

    Returns {"mapping": {role: file}, "unmatched_files": [...], "unfilled_roles": [...]}.
    A role is filled only on a UNIQUE keyword match. If exactly one role and one
    file remain after keyword matching, they are paired (the common 'the labelled
    props are jeans+shoes, so the remaining SKU is the top' case). Anything left
    over is surfaced for the agent to confirm — never guessed further.
    """
    kw = keywords or DEFAULT_ROLE_KEYWORDS
    mapping = {}
    remaining = list(files)
    for role in role_ids:
        words = kw.get(role, [role])
        matches = [f for f in remaining if any(w in f.lower() for w in words)]
        if len(matches) == 1:
            mapping[role] = matches[0]
            remaining.remove(matches[0])
    unfilled = [r for r in role_ids if r not in mapping]
    if len(unfilled) == 1 and len(remaining) == 1:
        mapping[unfilled[0]] = remaining.pop()
        unfilled = []
    return {"mapping": mapping, "unmatched_files": remaining, "unfilled_roles": unfilled}
```

- [ ] **Step 4: Run to verify it passes**

Run: `python3 -m pytest skills/flora-batch/scripts/tests/test_floralib.py -k map_files -q`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add skills/flora-batch/scripts/floralib.py skills/flora-batch/scripts/tests/test_floralib.py
git commit -m "feat(flora-batch): add floralib.map_files_to_roles (compose role mapping)"
```

---

### Task 5: `validate_gcs_reservation` (lint transcribed signatures before upload)

**Files:**
- Modify: `skills/flora-batch/scripts/floralib.py`
- Test: `skills/flora-batch/scripts/tests/test_floralib.py`

- [ ] **Step 1: Write the failing tests** (append)

```python
GOOD_RES = {
    "url": "https://storage.googleapis.com/flora-assets-prod/",
    "form_fields": {
        "Content-Type": "image/jpeg",
        "key": "mcp-uploads/x.jpg",
        "x-goog-date": "20260722T144942Z",
        "x-goog-credential": "svc/20260722/auto/storage/goog4_request",
        "x-goog-algorithm": "GOOG4-RSA-SHA256",
        "policy": "eyJhIjoxfQ==",
        "x-goog-signature": "ab" * 256,   # 512 lowercase hex chars
    },
}


def test_validate_good_reservation_has_no_problems():
    assert floralib.validate_gcs_reservation(GOOD_RES) == []


def test_validate_catches_non_hex_signature():
    bad = {"url": GOOD_RES["url"], "form_fields": dict(GOOD_RES["form_fields"])}
    bad["form_fields"]["x-goog-signature"] = "zz" + "ab" * 255
    assert any("hex" in p for p in floralib.validate_gcs_reservation(bad))


def test_validate_catches_missing_field():
    bad = {"url": GOOD_RES["url"], "form_fields": dict(GOOD_RES["form_fields"])}
    del bad["form_fields"]["policy"]
    assert any("policy" in p for p in floralib.validate_gcs_reservation(bad))
```

- [ ] **Step 2: Run to verify it fails**

Run: `python3 -m pytest skills/flora-batch/scripts/tests/test_floralib.py -k validate -q`
Expected: FAIL — no attribute `validate_gcs_reservation`.

- [ ] **Step 3: Implement** (append)

```python
_REQUIRED_FF = ["Content-Type", "key", "x-goog-date", "x-goog-credential",
                "x-goog-algorithm", "policy", "x-goog-signature"]


def validate_gcs_reservation(res):
    """Cheap lint for a GCS presigned-POST reservation after transcription.
    Returns a list of problem strings ([] == looks good). Catches the common
    hand-copy failures (truncated/altered signature, dropped field) BEFORE the
    curl spends a request. Not a substitute for upload.py's HTTP-status check."""
    if not isinstance(res, dict):
        return ["reservation is not an object"]
    problems = []
    url = res.get("url")
    if not (isinstance(url, str) and url.startswith("http")):
        problems.append("missing/invalid url")
    ff = res.get("form_fields")
    if not isinstance(ff, dict):
        return problems + ["missing form_fields"]
    for k in _REQUIRED_FF:
        if k not in ff:
            problems.append("form_fields missing " + k)
    sig = ff.get("x-goog-signature", "")
    if not re.fullmatch(r"[0-9a-f]+", sig or ""):
        problems.append("x-goog-signature not lowercase hex")
    elif len(sig) < 256:
        problems.append("x-goog-signature suspiciously short (%d)" % len(sig))
    try:
        base64.b64decode(ff.get("policy", ""), validate=True)
    except Exception:
        problems.append("policy is not valid base64")
    return problems
```

- [ ] **Step 4: Run to verify it passes**

Run: `python3 -m pytest skills/flora-batch/scripts/tests/test_floralib.py -k validate -q`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add skills/flora-batch/scripts/floralib.py skills/flora-batch/scripts/tests/test_floralib.py
git commit -m "feat(flora-batch): add floralib.validate_gcs_reservation (pre-upload lint)"
```

---

### Task 6: `build_compose_state` (state schema for multi-input runs)

**Files:**
- Modify: `skills/flora-batch/scripts/floralib.py`
- Test: `skills/flora-batch/scripts/tests/test_floralib.py`

- [ ] **Step 1: Write the failing test** (append)

```python
def test_build_compose_state_shape():
    st = floralib.build_compose_state(
        "/looks/LOOK 9", "tech_x", {"top": "a.jpg", "bottom": "b.jpg"}, 4.32)
    assert st["mode"] == "compose"
    assert st["technique"] == "tech_x"
    assert st["run_cost"] == 4.32
    assert st["run_id"] is None and st["run_stage"] == "pending"
    assert st["outputs"] == []
    assert st["inputs"]["top"] == {"file": "a.jpg", "asset_id": None, "stage": "pending"}
    assert set(st["inputs"]) == {"top", "bottom"}
```

- [ ] **Step 2: Run to verify it fails**

Run: `python3 -m pytest skills/flora-batch/scripts/tests/test_floralib.py -k compose_state -q`
Expected: FAIL — no attribute `build_compose_state`.

- [ ] **Step 3: Implement** (append)

```python
def build_compose_state(input_dir, technique_id, role_map, run_cost):
    """Resumable state for one compose run: N role inputs -> 1 run -> named outputs.
    Stages per input: pending -> uploaded. run_stage: pending -> run_started ->
    outputs_ready -> done (or run_failed / run_blocked)."""
    d = os.path.abspath(input_dir)
    return {
        "mode": "compose",
        "input": d,
        "output": d,
        "technique": technique_id,
        "run_cost": run_cost,
        "inputs": {role: {"file": fn, "asset_id": None, "stage": "pending"}
                   for role, fn in role_map.items()},
        "run_id": None,
        "run_stage": "pending",
        "outputs": [],
    }
```

- [ ] **Step 4: Run to verify it passes**

Run: `python3 -m pytest skills/flora-batch/scripts/tests/test_floralib.py -q`
Expected: PASS (all floralib tests).

- [ ] **Step 5: Commit**

```bash
git add skills/flora-batch/scripts/floralib.py skills/flora-batch/scripts/tests/test_floralib.py
git commit -m "feat(flora-batch): add floralib.build_compose_state (compose run schema)"
```

---

### Task 7: Refactor `download.py` — host-aware + compose `--outputs` mode

**Files:**
- Modify: `skills/flora-batch/scripts/download.py` (full rewrite below)

- [ ] **Step 1: Replace `download.py` with the two-mode, floralib-backed version**

```python
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
from floralib import output_variants, plan_downloads


def dl(url, dest, compressed):
    for candidate in output_variants(url, compressed):
        p = subprocess.run(
            ["curl", "-sS", "--connect-timeout", "30", "--max-time", "600",
             "-o", dest, "-w", "%{http_code} %{size_download}", candidate],
            capture_output=True, text=True)
        parts = p.stdout.strip().split()
        if len(parts) >= 2 and parts[0] == "200" and int(parts[1]) > 0:
            return int(parts[1])
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
    def save(): json.dump(s, open(state_path, "w"), indent=2)
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
```

- [ ] **Step 2: Smoke-test compose mode against a fake manifest (no network for the skip path)**

Run:
```bash
cd /tmp && printf '[{"output_id":"full-1","url":"https://media.flora.ai/x.png"}]' > o.json \
  && mkdir -p dlout && : > dlout/full-1.png && printf 'x' >> dlout/full-1.png \
  && python3 /Users/nicholasfjellbergswerdlowe/Dropbox/2026/PA/BCI/BCI-FLORA-MCP/skills/flora-batch/scripts/download.py --outputs o.json --out-dir dlout
```
Expected: prints `SKIP full-1.png` then `--- downloaded 1/1  (0.0 MB)` and exits 0 (the pre-existing non-empty file is skipped — proves routing + skip logic without a network call).

- [ ] **Step 3: Verify per-image `--state` mode still parses**

Run: `python3 /Users/nicholasfjellbergswerdlowe/Dropbox/2026/PA/BCI/BCI-FLORA-MCP/skills/flora-batch/scripts/download.py 2>&1 | head -1`
Expected: usage error mentioning `--state` / `--outputs` (argparse guard fires; no crash).

- [ ] **Step 4: Commit**

```bash
git add skills/flora-batch/scripts/download.py
git commit -m "refactor(flora-batch): host-aware download + compose --outputs mode"
```

---

### Task 8: `compose.py` — build compose state + correct cost gate

**Files:**
- Create: `skills/flora-batch/scripts/compose.py`

- [ ] **Step 1: Create `compose.py`**

```python
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
from floralib import map_files_to_roles, build_compose_state, estimate_cost

EXTS = (".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif", ".tif", ".tiff")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--technique", required=True)
    ap.add_argument("--run-cost", type=float, required=True)
    ap.add_argument("--roles", required=True, help="comma-separated input ids, e.g. top,bottom,shoes")
    ap.add_argument("--map", help="explicit role=file pairs, comma-separated (overrides auto)")
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
    else:
        res = map_files_to_roles(files, role_ids)
        role_map, unmatched, unfilled = res["mapping"], res["unmatched_files"], res["unfilled_roles"]

    state = build_compose_state(IN, a.technique, role_map, a.run_cost)
    json.dump(state, open(os.path.join(IN, "compose_state.json"), "w"), indent=2)

    print("role mapping:")
    for r in role_ids:
        print("  %-8s <- %s" % (r, role_map.get(r, "??? UNFILLED")))
    if unmatched:
        print("unmatched files:", unmatched)
    if unfilled:
        print("UNFILLED roles :", unfilled, " (resolve with --map before running)")
    print("cost gate      : 1 run x $%s = $%s" % (a.run_cost, estimate_cost(a.run_cost, 1)))
    print("state          :", os.path.join(IN, "compose_state.json"))


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Integration-test the auto-map + cost gate on a temp folder**

Run:
```bash
cd /tmp && rm -rf look9 && mkdir look9 \
  && : > "look9/91526272_143_OATMEAL_061226_5564.jpg" \
  && : > "look9/PROP_DENIM_JEANS_01_050526_9884.jpg" \
  && : > "look9/PROP_SHOE_01_050526_9890.jpg" \
  && python3 /Users/nicholasfjellbergswerdlowe/Dropbox/2026/PA/BCI/BCI-FLORA-MCP/skills/flora-batch/scripts/compose.py \
       --input look9 --technique tech_x --run-cost 4.32 --roles top,bottom,shoes
```
Expected output includes:
```
role mapping:
  top      <- 91526272_143_OATMEAL_061226_5564.jpg
  bottom   <- PROP_DENIM_JEANS_01_050526_9884.jpg
  shoes    <- PROP_SHOE_01_050526_9890.jpg
cost gate      : 1 run x $4.32 = $4.32
```
And `cat /tmp/look9/compose_state.json` shows `"mode": "compose"` with the three inputs at `stage: "pending"`.

- [ ] **Step 3: Commit**

```bash
git add skills/flora-batch/scripts/compose.py
git commit -m "feat(flora-batch): add compose.py (multi-input state + correct cost gate)"
```

---

### Task 9: `contact_sheet.py` — portable review gallery (no headless Chrome)

**Files:**
- Create: `skills/flora-batch/scripts/contact_sheet.py`
- Test: `skills/flora-batch/scripts/tests/test_contact_sheet.py`

- [ ] **Step 1: Write the failing test**

Create `skills/flora-batch/scripts/tests/test_contact_sheet.py`:

```python
import contact_sheet


def test_render_contains_inputs_outputs_and_devmode():
    html = contact_sheet.render_contact_sheet(
        title="LOOK 9",
        subtitle="3 inputs -> 24 outputs",
        inputs=[("TOP", "top.jpg"), ("BOTTOM", "jeans.jpg")],
        groups=[("Full", ["full-1.png", "full-2.png"])],
    )
    assert "LOOK 9" in html
    assert 'src="top.jpg"' in html
    assert 'src="full-1.png"' in html
    assert "DEV MODE" in html            # press-D developer mode present
    assert "<!doctype html>" not in html.lower()  # fragment; opened directly is fine
```

- [ ] **Step 2: Run to verify it fails**

Run: `python3 -m pytest skills/flora-batch/scripts/tests/test_contact_sheet.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'contact_sheet'`.

- [ ] **Step 3: Create `contact_sheet.py`**

```python
#!/usr/bin/env python3
"""Portable, self-contained review gallery for a finished run. Relative <img>
refs (works by double-click, no server, no headless Chrome). Press D for a
developer mode that copies a tile's name on click.

Usage:
  contact_sheet.py --dir DIR --outputs OUTPUTS.json \
      [--title T] [--subtitle S] [--inputs role=FILE,role=FILE]
Writes DIR/_contact_sheet.html.
"""
import argparse, os, json, html as _html

_CSS = """
:root{--bg:#f6f6f4;--panel:#fff;--ink:#1b221d;--muted:#6b7168;--line:#e3e3de;--accent:#2743E3;}
@media (prefers-color-scheme:dark){:root{--bg:#14150f;--panel:#1c1e18;--ink:#f2f2ec;--muted:#9a9f92;--line:#2c2f27;}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:14px/1.4 system-ui,sans-serif}
header{padding:22px 26px 8px}h1{margin:0;font-size:20px}.sub{color:var(--muted);margin-top:4px;font-size:13px}
h2{margin:26px 26px 10px;font-size:13px;text-transform:uppercase;letter-spacing:.12em;color:var(--muted);border-top:1px solid var(--line);padding-top:18px}
.grid{display:grid;gap:12px;padding:0 26px;grid-template-columns:repeat(auto-fill,minmax(150px,1fr))}
figure{margin:0;background:var(--panel);border:1px solid var(--line);border-radius:10px;overflow:hidden}
figure img{display:block;width:100%;height:auto;background:#fff}
figcaption{padding:7px 9px;font-size:12px;color:var(--muted)}.inputs figure{border-color:var(--accent)}
body.dev [data-el]{outline:1px dashed rgba(39,67,227,.4)}body.dev [data-el]:hover{outline:2px solid #2743E3;cursor:crosshair}
.dev-badge{position:fixed;top:12px;left:50%;transform:translateX(-50%);z-index:9;display:none;padding:7px 14px;font:600 11px/1 system-ui;letter-spacing:.14em;text-transform:uppercase;color:#fff;background:#2743E3;border-radius:999px}
body.dev .dev-badge{display:block}.dev-toast{position:fixed;bottom:70px;left:50%;transform:translateX(-50%);z-index:9;opacity:0;padding:9px 16px;font:600 12px/1 system-ui;color:#fff;background:#1B2FA8;border-radius:999px;transition:opacity .2s}.dev-toast.show{opacity:1}
"""

_JS = """
(function(){var toast=document.getElementById('t'),tT=null;
function isDev(){return document.body.classList.contains('dev');}
function copy(x){try{navigator.clipboard.writeText(x);}catch(e){}}
function msg(m){toast.textContent=m;toast.classList.add('show');clearTimeout(tT);tT=setTimeout(function(){toast.classList.remove('show');},1400);}
document.addEventListener('keydown',function(e){if(e.key==='d'||e.key==='D')document.body.classList.toggle('dev');});
document.addEventListener('click',function(e){if(!isDev())return;var el=e.target.closest('[data-el]');if(!el)return;e.preventDefault();e.stopPropagation();var n=el.getAttribute('data-el');copy(n);msg('Copied: '+n);},true);})();
"""


def _fig(src, caption, el):
    return ('<figure data-el="%s"><img src="%s"><figcaption>%s</figcaption></figure>'
            % (_html.escape(el, quote=True), _html.escape(src, quote=True), _html.escape(caption)))


def render_contact_sheet(title, subtitle, inputs, groups):
    """inputs: [(label, filename)]; groups: [(heading, [filename, ...])]. Returns HTML."""
    parts = ["<meta charset='utf-8'><title>%s</title><style>%s</style>" % (_html.escape(title), _CSS)]
    parts.append("<header><h1>%s</h1><div class='sub'>%s</div></header>"
                 % (_html.escape(title), _html.escape(subtitle)))
    parts.append("<h2>Inputs</h2><div class='grid inputs'>")
    for label, fn in inputs:
        parts.append(_fig(fn, label + " — " + fn, "input " + label))
    parts.append("</div>")
    for heading, files in groups:
        parts.append("<h2>%s</h2><div class='grid'>" % _html.escape(heading))
        for fn in files:
            parts.append(_fig(fn, fn, "output " + fn))
        parts.append("</div>")
    parts.append('<div class="dev-badge">DEV MODE · click a tile to copy its name · press D to exit</div>')
    parts.append('<div class="dev-toast" id="t"></div>')
    parts.append("<script>%s</script>" % _JS)
    return "\n".join(parts)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True)
    ap.add_argument("--outputs", required=True)
    ap.add_argument("--title", default="Contact sheet")
    ap.add_argument("--subtitle", default="")
    ap.add_argument("--inputs", default="", help="role=FILE,role=FILE (optional)")
    a = ap.parse_args()

    inputs = []
    if a.inputs:
        for pair in a.inputs.split(","):
            role, fn = pair.split("=", 1)
            inputs.append((role.strip(), fn.strip()))

    outs = json.load(open(a.outputs))
    groups_map = {}
    for o in outs:
        oid = o["output_id"]
        prefix = oid.rsplit("-", 1)[0] if "-" in oid else oid   # full / top-crop / top-detail
        groups_map.setdefault(prefix, []).append(oid + ".png")
    groups = [(k, sorted(v)) for k, v in sorted(groups_map.items())]

    html = render_contact_sheet(a.title, a.subtitle, inputs, groups)
    out = os.path.join(a.dir, "_contact_sheet.html")
    open(out, "w").write(html)
    print("wrote", out)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run to verify it passes**

Run: `python3 -m pytest skills/flora-batch/scripts/tests/test_contact_sheet.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add skills/flora-batch/scripts/contact_sheet.py skills/flora-batch/scripts/tests/test_contact_sheet.py
git commit -m "feat(flora-batch): add contact_sheet.py (portable review, no headless Chrome)"
```

---

### Task 10: SKILL.md — fix cost gate + the five hard-won rules

**Files:**
- Modify: `skills/flora-batch/SKILL.md`

- [ ] **Step 1: Replace the Cost gate section**

Find (lines ~39–41):
```markdown
## Cost gate (MANDATORY — never spend without it)

Scan the folder, retrieve the technique, then show: **N images × $run_cost × outputs = $total**, the output-path preview, and **wait for explicit approval.** Uploads are free; the spend is the **run** phase.
```
Replace with:
```markdown
## Cost gate (MANDATORY — never spend without it)

Scan the folder, retrieve the technique, then show **`(number of runs) × $run_cost = $total`**, the output-path preview, and **wait for explicit approval.** Uploads are free; only the **run** phase spends.

- **Per-image technique** (ONE input): number of runs = number of images.
- **Compose technique** (MULTIPLE role inputs, e.g. `top`/`bottom`/`shoes`): one run consumes a *group* of files, so number of runs = number of groups (looks). A single look = **1 run**. Do **not** multiply by "# outputs" — outputs per run are free; the price is flat. Use `floralib.estimate_cost(run_cost, num_runs)`.

**No balance pre-check exists.** There is no API to read a workspace balance — you only learn it from a `402 insufficient_credits` (which does not charge). Since uploads are free and failed/blocked runs are not billed, it is safe to proceed and treat a 402 as the "top up" signal.
```

- [ ] **Step 2: Replace the file-bridge rule row**

Find (line ~65):
```markdown
| **Oversized `execute` results are auto-saved to a local file** (path in the error). Bash reads that file **verbatim** — never hand-copy long signed strings. To force it for large reservation sets, pad the return over the limit. | Reproducing 38 × 512-char GCS signatures by hand is error-prone; the file bridge is exact. |
```
Replace with:
```markdown
| **`execute` output hard-caps at 100 000 bytes and ERRORS — there is NO auto-save / file bridge.** Keep returns small (for reservations return only `{asset_id, url, form_fields}`; ~10 fit under the cap and render inline). Move signed data to local by writing `reservations.json` yourself, then **rely on `upload.py`'s HTTP-status check as the safety net** — a mis-copied `policy`/`x-goog-signature` yields a loud 400/403 and `assets.retry(asset_id)` + re-run repairs just that item. Optionally lint each reservation with `floralib.validate_gcs_reservation` first. For big batches, **chunk** reservation calls (~10/`execute`), writing each chunk before the next. | Padding a return to "force a file save" just throws `Error: Output exceeded 100000 bytes`. Verify-and-retry, not a file bridge, is what makes transcription safe (proven on LOOK 9). |
```

- [ ] **Step 3: Replace the idempotency-key rule row**

Find (line ~61):
```markdown
| **Idempotency keys on every run** (`gp4k-${asset_id}` etc.). | The code server throws `502` often; keys make retries free — no double-charge. |
```
Replace with:
```markdown
| **Idempotency keys on every run — and split the two retry cases.** **Same key** = safe re-submit of the *same* attempt after a 502/timeout (returns `idempotency_duplicate`, no double charge). **Re-running a FAILED run needs a NEW key** (e.g. `…-run2`); the same key would only return the dead run. | The code server 502s often, so network retries must be free. But a failed generation is a *new* run and needs a fresh key to actually re-execute. |
```

- [ ] **Step 4: Replace the throttle rule row**

Find (line ~62):
```markdown
| **Throttle concurrency for heavy techniques** (upscalers, multi-model). Cap concurrent runs (~6–8) and let a wave finish before the next. | Firing 35 concurrent 4K/Magnific runs → 18 `GENERATION_PROVIDER_TIMEOUT`. Fewer-at-once succeeds. |
```
Replace with:
```markdown
| **Heavy techniques time out — throttle *and* expect single-run timeouts.** Cap concurrent runs (~6–8). A **single** heavy run (e.g. a 2K technique fanning to ~24 outputs) can still `GENERATION_PROVIDER_TIMEOUT` after ~10–15 min at concurrency 1 — transient; **retry once with a fresh idempotency key** (usually succeeds). Failed runs are **not billed** (no `charged_cost`). | 35 concurrent 4K runs → 18 timeouts; LOOK 9 (1 run, 24 × 2K) also timed out once, then succeeded on retry. |
```

- [ ] **Step 5: Replace the pristine-download rule row**

Find (line ~66):
```markdown
| **Pristine downloads:** append `?tr=orig-true` for the lossless original; fall back to the bare URL if it 404s. | The bare URL is CDN-compressed; `orig-true` is the real deliverable. |
```
Replace with:
```markdown
| **Pristine downloads are host-specific.** `?tr=orig-true` is an **ImageKit** transform — apply it only to `ik.imagekit.io` URLs (fall back to bare on 404). **`media.flora.ai` outputs are already full-res PNG** — download the **bare** URL. `download.py` / `floralib.output_variants` do this automatically. | Appending `?tr=orig-true` to a `media.flora.ai` URL wastes a request and can fetch an unexpected response. |
```

- [ ] **Step 6: Verify the edits landed and the stale claims are gone**

Run:
```bash
cd /Users/nicholasfjellbergswerdlowe/Dropbox/2026/PA/BCI/BCI-FLORA-MCP
grep -c "auto-saved to a local file" skills/flora-batch/SKILL.md    # expect 0
grep -c "Output exceeded 100000 bytes" skills/flora-batch/SKILL.md  # expect 1
grep -c "number of runs) × \$run_cost" skills/flora-batch/SKILL.md  # expect 1
grep -c "media.flora.ai. outputs are already full-res" skills/flora-batch/SKILL.md  # expect 1
```
Expected: `0`, then `1`, `1`, `1`.

- [ ] **Step 7: Commit**

```bash
git add skills/flora-batch/SKILL.md
git commit -m "docs(flora-batch): correct cost gate + file-bridge/idempotency/throttle/download rules"
```

---

### Task 11: SKILL.md — add the Workspace Billing section

**Files:**
- Modify: `skills/flora-batch/SKILL.md`

- [ ] **Step 1: Update the Prerequisites "Credits" bullet**

Find (line ~26):
```markdown
2. **Credits.** Each run bills `technique.run_cost`; N images charge ≈ N × cost. If the account is dry you'll get `402 insufficient_credits`.
```
Replace with:
```markdown
2. **Credits are per-workspace.** Each run bills `technique.run_cost` to a **specific workspace's** USD balance (see **Workspace billing** below). There is no balance-read API — a `402 insufficient_credits` (which does not charge) is the only signal, and its `available:` figure is that workspace's balance.
```

- [ ] **Step 2: Insert a new section immediately after the Cost gate section (before `## Pipeline`)**

Insert:
```markdown
## Workspace billing (which wallet pays)

Credits/balance are **per-workspace**, and an account can have several (e.g. a personal one and a team one). Get them with `client.workspaces.list()` → `[{workspace_id, name, role}]`. **Confirm which workspace should pay before spending** (ask if unsure; honor any saved preference).

Two run routes exist — they bill differently:

- `client.techniques.runs.create(tech, {inputs:[{id,type,value}], mode:"async", idempotency_key})` — the nested route. **Has no `workspace_id` and bills the API key's DEFAULT workspace.** Fine only when the default is the wallet you want.
- `client.runs.startTechnique({ technique_id:"tech_…", workspace_id:"ws_…", inputs })` — the top-level route. **Use this to bill a chosen workspace.** Its `inputs` is an **id→value map** (`{ top:url, bottom:url, shoes:url }`), *not* the `[{id,type,value}]` array.

**Poll a top-level run with `client.generations.retrieve(run_id)`.** The nested `techniques.runs.retrieve(run_id,{techniqueId})` returns **404** for `startTechnique` runs.

Assets are portable: an asset uploaded/`complete`d in workspace A yields an HTTPS URL usable as an `imageUrl` input for a run billed to workspace B. For tidiness you *may* stage assets in the billing workspace, but it isn't required.
```

- [ ] **Step 3: Verify**

Run:
```bash
cd /Users/nicholasfjellbergswerdlowe/Dropbox/2026/PA/BCI/BCI-FLORA-MCP
grep -c "## Workspace billing" skills/flora-batch/SKILL.md            # expect 1
grep -c "runs.startTechnique" skills/flora-batch/SKILL.md             # expect >=1
grep -c "generations.retrieve" skills/flora-batch/SKILL.md            # expect >=1
```
Expected: `1`, `1` (or more), `1` (or more).

- [ ] **Step 4: Commit**

```bash
git add skills/flora-batch/SKILL.md
git commit -m "docs(flora-batch): add workspace-billing section (startTechnique + generations.retrieve)"
```

---

### Task 12: SKILL.md — add the Compose (multi-input) section + fix Pipeline routes

**Files:**
- Modify: `skills/flora-batch/SKILL.md`

- [ ] **Step 1: Generalize the Pipeline Run/Poll steps**

Find (lines ~50–51):
```markdown
2. **Run** — `techniques.runs.create(tech,{inputs,mode:"async",idempotency_key})` per image. **Throttle** (see rules). Persist `run_id`.
3. **Poll** — `techniques.runs.retrieve(run_id,{techniqueId})` until `completed`/`failed`; collect the 2 output URLs. **Re-run** `failed` (fresh idempotency key), ideally in a smaller concurrent wave.
```
Replace with:
```markdown
2. **Run** — per-image: `techniques.runs.create(...)` per image (**throttle**). Workspace-billed / compose: `runs.startTechnique({technique_id, workspace_id, inputs})` (see **Workspace billing** and **Compose techniques**). Persist `run_id`.
3. **Poll** — nested runs: `techniques.runs.retrieve(run_id,{techniqueId})`; top-level/compose runs: `generations.retrieve(run_id)`. Poll with one short call (≤~24 s sleep + one retrieve) — long calls hit the code-server 502. `status` is truth; `progress` is coarse/non-linear. **Re-run** a `failed` run with a **fresh** idempotency key.
```

- [ ] **Step 2: Insert a new "Compose techniques" section after the Pipeline section (before `## Hard-won rules`)**

Insert:
```markdown
## Compose (multi-input) techniques

Some techniques are not "one image → outputs" but **"one run consumes several ROLE inputs"** — e.g. `front-pocket-2k-nfs` takes `top` + `bottom` + `shoes` and emits 24 named outputs (`full-1…8`, `top-crop-1…8`, `top-detail-1…8`). Detect this from `technique.inputs`: **more than one input id ⇒ compose.**

Handle a folder that represents ONE look like this:

1. **Map files → role inputs.** `python3 scripts/compose.py --input DIR --technique tech_… --run-cost <c> --roles top,bottom,shoes` auto-maps by filename keyword and writes `compose_state.json`. **View the images and confirm the mapping before spending** — if it prints `UNFILLED roles` / `unmatched files`, resolve with `--map top=FILE,bottom=FILE,shoes=FILE`.
2. **Cost gate:** 1 look = **1 run** = `run_cost` (compose.py prints this). Get approval.
3. **Upload** each role's file (reserve → `curl` → `complete`) exactly as for per-image; record `asset_id`s.
4. **Run** via `runs.startTechnique({technique_id, workspace_id, inputs:{top:urlTop, bottom:urlBottom, shoes:urlShoes}})` with an idempotency key. Persist `run_id`.
5. **Poll** with `generations.retrieve(run_id)`; on `completed`, `outputs` is `[{output_id, url}]` (~24 items — fits inline, no file bridge needed).
6. **Download** by name: write `outputs.json` = `[{output_id,url}]`, then `python3 scripts/download.py --outputs outputs.json --out-dir DIR`. Files land as `<output_id>.png`.
7. **Review:** `python3 scripts/contact_sheet.py --dir DIR --outputs outputs.json --title "LOOK 9" --inputs top=FILE,bottom=FILE,shoes=FILE` → `DIR/_contact_sheet.html`. Plus programmatic checks: count == expected, `sips -g pixelWidth -g pixelHeight` non-zero, file sizes > 0.

Many looks = one subfolder per look = one run each; throttle as usual.
```

- [ ] **Step 3: Verify**

Run:
```bash
cd /Users/nicholasfjellbergswerdlowe/Dropbox/2026/PA/BCI/BCI-FLORA-MCP
grep -c "## Compose (multi-input) techniques" skills/flora-batch/SKILL.md   # expect 1
grep -c "more than one input id" skills/flora-batch/SKILL.md                # expect 1
```
Expected: `1`, `1`.

- [ ] **Step 4: Commit**

```bash
git add skills/flora-batch/SKILL.md
git commit -m "docs(flora-batch): add compose (multi-input) section + correct pipeline routes"
```

---

### Task 13: SKILL.md Scripts/Mistakes + README refresh

**Files:**
- Modify: `skills/flora-batch/SKILL.md`
- Modify: `README.md`

- [ ] **Step 1: Replace the Scripts list**

Find (lines ~69–78, the `## Scripts (bundled, adapt paths)` block through the paragraph ending "…passing data through files (see the oversized-result rule).") and replace the bullet list + trailing paragraph with:
```markdown
Local drivers live in `scripts/` and are **state-file-driven** (read the state JSON, do only what's pending, checkpoint after each item):

- `scripts/floralib.py` — pure, unit-tested helpers (host-aware download variants, cost estimate, file→role mapping, reservation lint, compose-state builder). Imported by the others.
- `scripts/init.py` — per-image: enumerate + build output tree + write `batch_state.json`.
- `scripts/upload.py` — reservations file + state → GCS/ImageKit POST per image (auto-detects backend by form fields).
- `scripts/download.py` — two modes: per-image `--state`, or compose `--outputs outputs.json --out-dir DIR` (names by `output_id`). Host-aware.
- `scripts/compose.py` — multi-input: map files → roles, write `compose_state.json`, print the correct cost gate.
- `scripts/contact_sheet.py` — portable self-contained review gallery (relative `<img>` refs; opens by double-click; press-D dev mode). No headless Chrome.
- `scripts/review.py` — legacy comparison HTML for headless-Chrome screenshotting (prefer `contact_sheet.py`).
- `scripts/tests/` — `pytest` unit tests for `floralib` + `contact_sheet` (`python3 -m pytest skills/flora-batch/scripts/tests -q`).

The orchestrating agent makes the FLORA MCP calls (reserve / complete / run / poll) and runs these scripts for byte transfers. Reservation/output data crosses from the sandbox to local by writing a JSON file yourself (the 100 KB `execute` cap means there is no auto-file-bridge — see the hard-won rules).
```

- [ ] **Step 2: Replace the stale "Common mistakes" file-bridge bullet**

Find (line ~85):
```markdown
- Hand-copying signed reservations from `execute` output. Use the file bridge.
```
Replace with:
```markdown
- Assuming an auto "file bridge" for big `execute` results (there isn't one — 100 KB cap errors). Keep returns small; verify uploads by HTTP status and re-reserve on 4xx.
- Using `techniques.runs.create` (default workspace) when a specific workspace must pay — use `runs.startTechnique({workspace_id})`.
- Multiplying the cost gate by "# outputs", or by "# files" for a compose look. One look = one run.
```

- [ ] **Step 3: Update README.md scripts/changelog**

Open `README.md`. If it enumerates the scripts, add `floralib.py`, `compose.py`, and `contact_sheet.py` alongside the existing entries with one-line descriptions matching Step 1. Append a changelog line:
```markdown
- 2026-07-22: hardened for compose (multi-input) techniques + workspace billing; corrected the 100 KB `execute` rule; host-aware downloads; portable contact-sheet review. See `docs/superpowers/plans/2026-07-22-flora-batch-hardening-and-multi-input.md`.
```

- [ ] **Step 4: Verify + full test suite**

Run:
```bash
cd /Users/nicholasfjellbergswerdlowe/Dropbox/2026/PA/BCI/BCI-FLORA-MCP
grep -c "scripts/floralib.py" skills/flora-batch/SKILL.md   # expect >=1
grep -c "contact_sheet.py" README.md                        # expect >=1
python3 -m pytest skills/flora-batch/scripts/tests -q
```
Expected: `1+`, `1+`, and all tests pass.

- [ ] **Step 5: Commit**

```bash
git add skills/flora-batch/SKILL.md README.md
git commit -m "docs(flora-batch): refresh scripts list, common mistakes, README changelog"
```

---

## Self-Review

**Spec coverage** (each after-action finding → task):
- Compose techniques unsupported → Tasks 4, 6, 8, 9, 12 (mapping, state, CLI, review, docs).
- False file-bridge rule → Task 10 Step 2 (+ Task 5 lint as the real safety net).
- Cost-gate math → Task 3 + Task 10 Step 1 + Task 8.
- Workspace billing unmodeled → Task 11 (+ Task 12 route fixes).
- Retry / single-run timeout → Task 10 Steps 3–4 (+ compose run step Task 12).
- Failed runs not billed → Task 10 Step 4.
- `?tr=orig-true` host-specificity → Task 1 + Task 7 + Task 10 Step 5.
- Review without headless Chrome → Task 9 + Task 12 Step 7 (contact sheet + programmatic checks).

**Placeholder scan:** every code step contains complete code; every doc step contains the exact replacement/insert text; every test step has a command + expected output. No TBD/TODO.

**Type consistency:** `floralib` function names/signatures used identically across scripts and tests — `output_variants(url, compressed=False)`, `plan_downloads(outputs, out_dir)`, `estimate_cost(run_cost, num_runs)`, `map_files_to_roles(files, role_ids, keywords=None)` → `{"mapping","unmatched_files","unfilled_roles"}`, `validate_gcs_reservation(res)` → list, `build_compose_state(input_dir, technique_id, role_map, run_cost)`, `render_contact_sheet(title, subtitle, inputs, groups)`. `download.py` imports `output_variants`/`plan_downloads`; `compose.py` imports `map_files_to_roles`/`build_compose_state`/`estimate_cost`; consistent.

**Notes for the executor:**
- `init.py` and `upload.py` are unchanged and stay valid for per-image batches; only `download.py` gains a second mode.
- Tests are network-free; the two curl smoke-tests (Task 7 Step 2, Task 8 Step 2) use empty/`SKIP` paths so they don't hit FLORA.
- The MCP call sequence (reserve/complete/startTechnique/generations.retrieve) is agent behavior documented in SKILL.md, not scripted — there is nothing to unit-test there; the compose CLI + helpers are the testable surface.
