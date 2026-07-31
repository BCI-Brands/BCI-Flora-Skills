# flora-batch Hardening Round 2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the seven correctness/safety gaps found in the 2026-07-31 code review: output re-enqueue footgun, positional reservation pairing, non-atomic state writes, curl `-F` injection surface, legacy review tooling, unvalidated QA verdict vocabulary, and partial QA manifests.

**Architecture:** All new logic lands as pure, unit-tested functions in `floralib.py`; the CLI scripts stay thin wrappers. Two documented breaking changes (reservations file format, `review.py` deletion) update `SKILL.md` in the same task that makes the code change.

**Tech Stack:** Python 3 stdlib only, pytest for tests, ruff (pyflakes-only) for lint.

## Global Constraints

- **Working directory:** ALL commands run from `/Users/fbrinadze/projects/bci-flora-skills/.claude/worktrees/garment-qa-comparison` (an isolated git worktree, branch `feat/flora-batch-hardening-2`). NEVER `cd` to `/Users/fbrinadze/projects/bci-flora-skills` (the main checkout — a prior task polluted a branch that way). Before every commit run `git rev-parse --show-toplevel` and `git branch --show-current`; if they are not the worktree path and `feat/flora-batch-hardening-2`, STOP and report BLOCKED.
- **Test command:** `python3 -m pytest skills/flora-batch/scripts/tests -q`. If pytest is missing (externally-managed Python), install with `python3 -m pip install --user pytest 2>/dev/null || python3 -m pip install --user --break-system-packages pytest`.
- **Lint:** `ruff check skills/flora-batch/scripts` must stay clean (pyflakes rules only; do not "fix" the compact one-liner style).
- **Layering:** pure/network-free logic in `floralib.py` (TDD mandatory); scripts are thin wrappers using the repo import pattern: `sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))` then `from floralib import ...`.
- **Verdict vocabulary (exact):** color = `match` | `minor_shift` | `mismatch`; construction = `match` | `minor_deviation` | `mismatch`.
- **Commits:** conventional style, one per task, e.g. `fix(flora-batch): ...` / `feat(flora-batch): ...`.
- Python stdlib only — no new dependencies.

---

### Task 1: Atomic JSON writes (`floralib.save_json_atomic`) wired into every state/manifest writer

**Files:**
- Modify: `skills/flora-batch/scripts/floralib.py` (add `import json` at top with existing imports; add function after `estimate_cost`)
- Modify: `skills/flora-batch/scripts/init.py`, `upload.py`, `download.py`, `compose.py`, `qa_resolve.py`, `qa_report.py` (swap `json.dump(..., open(path, "w"), indent=2)` call sites)
- Test: `skills/flora-batch/scripts/tests/test_floralib.py`

**Interfaces:**
- Consumes: nothing new.
- Produces: `save_json_atomic(obj, path, indent=2) -> None` — later tasks (3, 7) call it from scripts they touch.

- [ ] **Step 1: Write the failing tests**

Add to `test_floralib.py` (add `import json`, `import os` to the top of the file alongside `import floralib`):

```python
def test_save_json_atomic_writes_valid_json_and_leaves_no_tmp(tmp_path):
    p = str(tmp_path / "state.json")
    floralib.save_json_atomic({"a": 1}, p)
    assert json.load(open(p)) == {"a": 1}
    assert sorted(os.listdir(str(tmp_path))) == ["state.json"]  # no .tmp left behind


def test_save_json_atomic_replaces_existing_file(tmp_path):
    p = str(tmp_path / "state.json")
    open(p, "w").write("old garbage")
    floralib.save_json_atomic([1, 2], p)
    assert json.load(open(p)) == [1, 2]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest skills/flora-batch/scripts/tests/test_floralib.py -q -k save_json_atomic`
Expected: FAIL with `AttributeError: module 'floralib' has no attribute 'save_json_atomic'`

- [ ] **Step 3: Implement**

In `floralib.py`, add `import json` to the imports (currently `base64`, `os`, `re`), then after `estimate_cost`:

```python
def save_json_atomic(obj, path, indent=2):
    """Write JSON via temp-file + os.replace so an interrupt can never leave a
    truncated file. The state files are the pipeline's only checkpoint -- a
    half-written batch_state.json loses the whole batch's recovery story.
    Temp file lives in the same directory so os.replace stays atomic."""
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(obj, f, indent=indent)
    os.replace(tmp, path)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest skills/flora-batch/scripts/tests/test_floralib.py -q`
Expected: all PASS

- [ ] **Step 5: Swap the six call sites**

Each script keeps behavior identical; only the write changes.

`init.py` — add after the existing `import argparse, os, json` line:
```python
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from floralib import save_json_atomic
```
and replace `json.dump(state, open(state_path, "w"), indent=2)` with `save_json_atomic(state, state_path)`.

`upload.py` — add after `import argparse, os, json, subprocess`:
```python
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from floralib import save_json_atomic
```
and replace `def save(): json.dump(s, open(a.state, "w"), indent=2)` with `def save(): save_json_atomic(s, a.state)`.

`download.py` — extend the existing import line `from floralib import output_variants, plan_downloads` to `from floralib import output_variants, plan_downloads, save_json_atomic`; replace `def save(): json.dump(s, open(state_path, "w"), indent=2)` with `def save(): save_json_atomic(s, state_path)`.

`compose.py` — extend the existing floralib import with `save_json_atomic`; replace `json.dump(state, open(state_path, "w"), indent=2)` with `save_json_atomic(state, state_path)`.

`qa_resolve.py` — extend `from floralib import resolve_qa_pairs` to `from floralib import resolve_qa_pairs, save_json_atomic`; replace `json.dump(result["pairs"], open(manifest_path, "w"), indent=2)` with `save_json_atomic(result["pairs"], manifest_path)`.

`qa_report.py` — extend `from floralib import qa_overall_flag, render_qa_report_md` to `from floralib import qa_overall_flag, render_qa_report_md, save_json_atomic`; replace `json.dump(results, open(os.path.join(a.out_dir, "qa_report.json"), "w"), indent=2)` with `save_json_atomic(results, os.path.join(a.out_dir, "qa_report.json"))`.

Do NOT touch `review.py` (deleted in Task 5).

- [ ] **Step 6: Full test run + lint**

Run: `python3 -m pytest skills/flora-batch/scripts/tests -q` → all PASS
Run: `ruff check skills/flora-batch/scripts` → clean (note: `json` may become unused in `qa_resolve.py`'s import line only if nothing else uses it — it is still used by `json.load`, so the combined `import argparse, os, json, sys` lines stay valid everywhere).

- [ ] **Step 7: Commit**

```bash
git add skills/flora-batch/scripts
git commit -m "fix(flora-batch): atomic state/manifest writes via floralib.save_json_atomic"
```

---

### Task 2: `init.py` must not re-enqueue prior outputs as inputs

**Files:**
- Modify: `skills/flora-batch/scripts/floralib.py` (add `is_output_artifact` after `save_json_atomic`)
- Modify: `skills/flora-batch/scripts/init.py` (filter enumeration, print skip count)
- Test: `skills/flora-batch/scripts/tests/test_floralib.py`

**Interfaces:**
- Consumes: nothing from other tasks.
- Produces: `is_output_artifact(filename: str, suffix: str) -> bool`.

**Why:** `EXTS` includes `.png` and the `same` convention (actively used by the team) writes outputs into the input folder. Re-running `init.py` there enumerates `shirt_MCP_1.png` as a new pending item — which would then be uploaded and RUN, i.e. paid money to process a prior output.

- [ ] **Step 1: Write the failing tests**

```python
def test_is_output_artifact_matches_suffix_number_pattern():
    assert floralib.is_output_artifact("shirt_MCP_1.png", "_MCP") is True
    assert floralib.is_output_artifact("shirt_MCP_12.PNG", "_MCP") is True


def test_is_output_artifact_ignores_plain_inputs():
    assert floralib.is_output_artifact("shirt.jpg", "_MCP") is False
    assert floralib.is_output_artifact("shirt_MCP_1_final.jpg", "_MCP") is False  # pattern not at end


def test_is_output_artifact_respects_the_configured_suffix():
    assert floralib.is_output_artifact("shirt_MCP_1.png", "_AI") is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest skills/flora-batch/scripts/tests/test_floralib.py -q -k is_output_artifact`
Expected: FAIL with `AttributeError`

- [ ] **Step 3: Implement in floralib.py**

```python
def is_output_artifact(filename, suffix):
    """True if filename looks like a batch OUTPUT (<stem><suffix>_<n>.<ext>).
    Guards init.py enumeration: the 'same' convention writes outputs into the
    input folder, so a re-init there would otherwise enqueue prior outputs as
    new inputs -- and pay to run the technique on its own outputs."""
    return re.search(re.escape(suffix) + r"_\d+\.[A-Za-z0-9]+$", filename) is not None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest skills/flora-batch/scripts/tests/test_floralib.py -q`
Expected: all PASS

- [ ] **Step 5: Wire into init.py enumeration**

Extend init.py's floralib import (from Task 1) to `from floralib import save_json_atomic, is_output_artifact`. Replace the enumeration block:

```python
    # enumerate (skipping prior outputs -- see floralib.is_output_artifact)
    rels, skipped = [], 0
    if a.recurse:
        for root, _d, files in os.walk(IN):
            for f in files:
                if not f.lower().endswith(EXTS):
                    continue
                if is_output_artifact(f, a.suffix):
                    skipped += 1
                    continue
                rels.append(os.path.relpath(os.path.join(root, f), IN))
    else:
        for f in os.listdir(IN):
            if not (f.lower().endswith(EXTS) and os.path.isfile(os.path.join(IN, f))):
                continue
            if is_output_artifact(f, a.suffix):
                skipped += 1
                continue
            rels.append(f)
    rels.sort()
```

And after the `print(f"images     : {len(items)}")` line add:

```python
    if skipped:
        print(f"skipped    : {skipped} prior output files (*{a.suffix}_N.*)")
```

- [ ] **Step 6: Full test run + lint**

Run: `python3 -m pytest skills/flora-batch/scripts/tests -q` → all PASS
Run: `ruff check skills/flora-batch/scripts` → clean

- [ ] **Step 7: Commit**

```bash
git add skills/flora-batch/scripts
git commit -m "fix(flora-batch): init.py skips prior outputs during enumeration (same-convention money footgun)"
```

---

### Task 3: rel-keyed reservations for `upload.py` (breaking format change + SKILL.md)

**Files:**
- Modify: `skills/flora-batch/scripts/floralib.py` (add `match_reservations`)
- Modify: `skills/flora-batch/scripts/upload.py` (new format, docstring rewrite)
- Modify: `skills/flora-batch/SKILL.md` (two lines, exact edits below)
- Test: `skills/flora-batch/scripts/tests/test_floralib.py`

**Interfaces:**
- Consumes: `save_json_atomic` (Task 1) — already imported in upload.py.
- Produces: `match_reservations(reservations: dict, items: list) -> {"matched": {rel: res}, "missing_rels": [...], "unknown_rels": [...]}`.

**Why:** the current RES.json is a positional list; same-length-wrong-order pairs the wrong `asset_id` with the wrong image silently, and the documented "re-reserve just the failed ones" resume flow actually requires a full-length list with junk in non-pending slots. Keying by `rel` makes the file self-describing and partial re-reservation natural.

- [ ] **Step 1: Write the failing tests**

```python
def test_match_reservations_matches_pending_items_by_rel():
    items = [
        {"rel": "a.jpg", "stage": "pending"},
        {"rel": "b.jpg", "stage": "uploaded"},
    ]
    res = {"a.jpg": {"asset_id": "as_1", "url": "https://u", "form_fields": {}}}
    m = floralib.match_reservations(res, items)
    assert m["matched"] == {"a.jpg": res["a.jpg"]}
    assert m["missing_rels"] == []
    assert m["unknown_rels"] == []


def test_match_reservations_flags_missing_pending_and_unknown_keys():
    items = [
        {"rel": "a.jpg", "stage": "pending"},
        {"rel": "b.jpg", "stage": "pending"},
    ]
    res = {"a.jpg": {"asset_id": "as_1", "url": "https://u", "form_fields": {}},
           "ghost.jpg": {"asset_id": "as_9", "url": "https://u", "form_fields": {}}}
    m = floralib.match_reservations(res, items)
    assert m["missing_rels"] == ["b.jpg"]
    assert m["unknown_rels"] == ["ghost.jpg"]


def test_match_reservations_uploaded_items_need_no_reservation():
    items = [{"rel": "done.jpg", "stage": "uploaded"}]
    m = floralib.match_reservations({}, items)
    assert m == {"matched": {}, "missing_rels": [], "unknown_rels": []}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest skills/flora-batch/scripts/tests/test_floralib.py -q -k match_reservations`
Expected: FAIL with `AttributeError`

- [ ] **Step 3: Implement in floralib.py**

```python
def match_reservations(reservations, items):
    """Match rel-keyed upload reservations ({rel: {asset_id,url,form_fields}})
    to state items. Only items still at stage 'pending' need one. Replaces the
    old positional-list pairing, where a same-length wrong-order file silently
    attached the wrong asset_id to the wrong image.

    Returns {"matched": {rel: reservation}, "missing_rels": [...],
    "unknown_rels": [...]} -- missing = pending item with no reservation,
    unknown = reservation key not present in items at all (likely a typo)."""
    all_rels = {it["rel"] for it in items}
    pending = {it["rel"] for it in items if it.get("stage") == "pending"}
    matched = {rel: r for rel, r in reservations.items() if rel in pending}
    return {
        "matched": matched,
        "missing_rels": sorted(pending - set(reservations)),
        "unknown_rels": sorted(set(reservations) - all_rels),
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest skills/flora-batch/scripts/tests/test_floralib.py -q`
Expected: all PASS

- [ ] **Step 5: Rewrite upload.py to consume the new format**

Full new `upload.py` (docstring + main; imports carry Task 1's additions):

```python
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
from floralib import save_json_atomic, match_reservations

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
        args = ["curl", "-sS", "--connect-timeout", "30", "--max-time", "300", "-o", "/dev/null",
                "-w", "%{http_code}", "-X", "POST", r["url"]]
        for k, v in r["form_fields"].items():
            args += ["-F", f"{k}={v}"]
        args += ["-F", f"file=@{src}"]          # file LAST
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
```

(Note: the curl `-F` lines are intentionally unchanged here — Task 4 replaces them with `--form-string` via a tested helper. Do not do Task 4's work early.)

- [ ] **Step 6: Update SKILL.md (two exact edits)**

Edit 1 — in the `## Scripts (bundled, adapt paths)` list, replace:
```
- `scripts/upload.py` — reservations file + state → GCS/ImageKit POST per image (auto-detects backend by form fields).
```
with:
```
- `scripts/upload.py` — rel-keyed reservations file (`{"<rel>": {asset_id,url,form_fields}}`, pending items only) + state → GCS/ImageKit POST per image (auto-detects backend by form fields).
```

Edit 2 — in the hard-won rules row about the 100 KB `execute` cap, replace the parenthetical:
```
(for reservations return only `{asset_id, url, form_fields}`; ~10 fit under the cap and render inline)
```
with:
```
(for reservations return only `{rel: {asset_id, url, form_fields}}` keyed by each item's `rel`; ~10 fit under the cap and render inline)
```

- [ ] **Step 7: Full test run + lint**

Run: `python3 -m pytest skills/flora-batch/scripts/tests -q` → all PASS
Run: `ruff check skills/flora-batch/scripts` → clean

- [ ] **Step 8: Commit**

```bash
git add skills/flora-batch/scripts skills/flora-batch/SKILL.md
git commit -m "feat(flora-batch)!: rel-keyed upload reservations (replaces positional list)"
```

---

### Task 4: `--form-string` for curl form fields (injection guard)

**Files:**
- Modify: `skills/flora-batch/scripts/floralib.py` (add `build_curl_upload_args`)
- Modify: `skills/flora-batch/scripts/upload.py` (use it)
- Test: `skills/flora-batch/scripts/tests/test_floralib.py`

**Interfaces:**
- Consumes: Task 3's upload.py shape.
- Produces: `build_curl_upload_args(url: str, form_fields: dict, filepath: str) -> list[str]`.

**Why:** `curl -F key=value` treats a leading `@` or `<` in *value* as "read this local file". Reservation fields are server-supplied; `--form-string` sends values literally. The file part legitimately needs `-F file=@path`.

- [ ] **Step 1: Write the failing tests**

```python
def test_build_curl_upload_args_uses_form_string_for_fields_and_F_only_for_file():
    args = floralib.build_curl_upload_args(
        "https://storage.googleapis.com/b/", {"key": "k/x.jpg", "policy": "@evil"}, "/in/x.jpg")
    assert args[-2:] == ["-F", "file=@/in/x.jpg"]          # file part LAST, via -F
    assert "--form-string" in args
    i = args.index("--form-string")
    assert args[i + 1] == "key=k/x.jpg"
    assert "-F" not in args[:-2]                            # no -F except the file part
    assert "policy=@evil" in args                           # sent literally via --form-string


def test_build_curl_upload_args_preserves_field_order_and_url():
    ff = {"Content-Type": "image/jpeg", "key": "k"}
    args = floralib.build_curl_upload_args("https://u", ff, "/f.jpg")
    assert args[args.index("-X") + 1] == "POST"
    assert "https://u" in args
    joined = " ".join(args)
    assert joined.index("Content-Type=image/jpeg") < joined.index("key=k")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest skills/flora-batch/scripts/tests/test_floralib.py -q -k build_curl`
Expected: FAIL with `AttributeError`

- [ ] **Step 3: Implement in floralib.py**

```python
def build_curl_upload_args(url, form_fields, filepath):
    """curl argv for one presigned-POST upload. Form fields go through
    --form-string so a value starting with '@' or '<' is sent literally
    (with -F curl would read a local file). Only the file part uses -F,
    and it goes LAST (required by S3/GCS presigned POST)."""
    args = ["curl", "-sS", "--connect-timeout", "30", "--max-time", "300",
            "-o", "/dev/null", "-w", "%{http_code}", "-X", "POST", url]
    for k, v in form_fields.items():
        args += ["--form-string", "%s=%s" % (k, v)]
    args += ["-F", "file=@%s" % filepath]
    return args
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest skills/flora-batch/scripts/tests/test_floralib.py -q`
Expected: all PASS

- [ ] **Step 5: Use it in upload.py**

Extend the import to `from floralib import save_json_atomic, match_reservations, build_curl_upload_args`. Replace the inline argv construction (the `args = ["curl", ...]` block, the form-fields loop, and the `args += ["-F", f"file=@{src}"]` line) with:

```python
        args = build_curl_upload_args(r["url"], r["form_fields"], src)
```

- [ ] **Step 6: Full test run + lint**

Run: `python3 -m pytest skills/flora-batch/scripts/tests -q` → all PASS
Run: `ruff check skills/flora-batch/scripts` → clean

- [ ] **Step 7: Commit**

```bash
git add skills/flora-batch/scripts
git commit -m "fix(flora-batch): send form fields via curl --form-string (injection guard)"
```

---

### Task 5: per-image `--state` mode for contact_sheet.py; delete legacy review.py

**Files:**
- Modify: `skills/flora-batch/scripts/contact_sheet.py` (add `groups_from_state`, `--state` mode)
- Delete: `skills/flora-batch/scripts/review.py`
- Modify: `skills/flora-batch/SKILL.md` (pipeline step 5 + scripts list)
- Test: `skills/flora-batch/scripts/tests/test_contact_sheet.py`

**Interfaces:**
- Consumes: nothing from other tasks.
- Produces: `contact_sheet.groups_from_state(state: dict) -> list[tuple[str, list[str]]]`.

**Why:** SKILL.md says "prefer contact_sheet.py" but it only handles compose runs; per-image batches had only the "legacy" review.py (remote URLs + headless Chrome). One tool, two modes; delete the legacy one.

- [ ] **Step 1: Write the failing test**

Read `tests/test_contact_sheet.py` first to match its import style; add (with `import os` if not present):

```python
def test_groups_from_state_groups_done_items_by_out_subdir():
    state = {"output": "/out", "items": [
        {"rel": "a.jpg", "out_subdir": "", "files": ["/out/a_MCP_1.png", "/out/a_MCP_2.png"]},
        {"rel": "s/b.jpg", "out_subdir": "s_MCP", "files": ["/out/s_MCP/b_MCP_1.png"]},
        {"rel": "c.jpg", "out_subdir": "", "files": []},   # not downloaded -> excluded
    ]}
    assert contact_sheet.groups_from_state(state) == [
        ("(root)", ["a_MCP_1.png", "a_MCP_2.png"]),
        ("s_MCP", [os.path.join("s_MCP", "b_MCP_1.png")]),
    ]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest skills/flora-batch/scripts/tests/test_contact_sheet.py -q`
Expected: FAIL with `AttributeError: module 'contact_sheet' has no attribute 'groups_from_state'`

- [ ] **Step 3: Implement `groups_from_state` in contact_sheet.py**

Add after `render_contact_sheet`:

```python
def groups_from_state(state):
    """Per-image mode: [(heading, [img path relative to state['output'], ...])]
    for every item with downloaded files, grouped by out_subdir. Relative paths
    keep the gallery portable (it lives at state['output']/_contact_sheet.html)."""
    out = state["output"]
    groups = {}
    for it in state.get("items", []):
        if not it.get("files"):
            continue
        heading = it.get("out_subdir", "") or "(root)"
        for f in it["files"]:
            groups.setdefault(heading, []).append(os.path.relpath(f, out))
    return [(h, groups[h]) for h in sorted(groups)]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest skills/flora-batch/scripts/tests/test_contact_sheet.py -q`
Expected: PASS

- [ ] **Step 5: Add the `--state` CLI mode**

In `main()`: change `--dir` and `--outputs` to optional (`ap.add_argument("--dir")`, `ap.add_argument("--outputs")`), add `ap.add_argument("--state")`, and insert after arg parsing:

```python
    if a.state:
        s = json.load(open(a.state))
        groups = groups_from_state(s)
        title = a.title if a.title != "Contact sheet" else os.path.basename(s["output"])
        n = sum(len(files) for _h, files in groups)
        sub = a.subtitle or "%d outputs · technique %s" % (n, s.get("technique", ""))
        html = render_contact_sheet(title, sub, [], groups)
        out = os.path.join(s["output"], "_contact_sheet.html")
        open(out, "w").write(html)
        print("wrote", out)
        return
    if not (a.dir and a.outputs):
        ap.error("provide --state (per-image) or --dir + --outputs (compose)")
```

- [ ] **Step 6: Delete review.py**

```bash
git rm skills/flora-batch/scripts/review.py
```

- [ ] **Step 7: Update SKILL.md (two exact edits)**

Edit 1 — pipeline step 5, replace:
```
5. **Auto-review** (if `--review`, default on) — build a comparison contact sheet (original → outputs) + a short findings note (counts, exact $ charged, any off-looking conversions), rendered via headless Chrome.
```
with:
```
5. **Auto-review** (if `--review`, default on) — `python3 scripts/contact_sheet.py --state batch_state.json` builds a portable gallery (opens by double-click, no headless Chrome) + a short findings note (counts, exact $ charged, any off-looking conversions).
```

Edit 2 — scripts list: replace the contact_sheet bullet and DELETE the review.py bullet:
```
- `scripts/contact_sheet.py` — portable self-contained review gallery (relative `<img>` refs; opens by double-click; press-D dev mode). No headless Chrome.
- `scripts/review.py` — legacy comparison HTML for headless-Chrome screenshotting (prefer `contact_sheet.py`).
```
becomes:
```
- `scripts/contact_sheet.py` — portable self-contained review gallery, two modes: per-image `--state batch_state.json`, or compose `--dir DIR --outputs outputs.json`. Relative `<img>` refs; opens by double-click; press-D dev mode. No headless Chrome.
```

- [ ] **Step 8: Full test run + lint**

Run: `python3 -m pytest skills/flora-batch/scripts/tests -q` → all PASS
Run: `ruff check skills/flora-batch/scripts` → clean

- [ ] **Step 9: Commit**

```bash
git add -A skills/flora-batch
git commit -m "feat(flora-batch): per-image --state mode for contact_sheet.py; drop legacy review.py"
```

---

### Task 6: QA verdict vocabulary validation

**Files:**
- Modify: `skills/flora-batch/scripts/floralib.py` (add constants + `validate_qa_results`)
- Modify: `skills/flora-batch/scripts/qa_report.py` (validate before writing)
- Test: `skills/flora-batch/scripts/tests/test_floralib.py`

**Interfaces:**
- Consumes: nothing from other tasks.
- Produces: `COLOR_VERDICTS`, `CONSTRUCTION_VERDICTS` (frozenset), `validate_qa_results(results: list) -> list[str]` (problem strings, `[]` == valid).

- [ ] **Step 1: Write the failing tests**

```python
def test_validate_qa_results_accepts_canonical_vocabulary():
    results = [{"output": "/o/a.png", "input": "/i/a.jpg",
                "color": {"verdict": "minor_shift", "notes": ""},
                "construction": {"verdict": "minor_deviation", "notes": ""}}]
    assert floralib.validate_qa_results(results) == []


def test_validate_qa_results_flags_unknown_and_cross_domain_verdicts():
    results = [
        {"output": "/o/a.png", "input": "/i/a.jpg",
         "color": {"verdict": "Match", "notes": ""},                 # wrong case
         "construction": {"verdict": "match", "notes": ""}},
        {"output": "/o/b.png", "input": "/i/b.jpg",
         "color": {"verdict": "match", "notes": ""},
         "construction": {"verdict": "minor_shift", "notes": ""}},   # color vocab in construction
    ]
    problems = floralib.validate_qa_results(results)
    assert len(problems) == 2
    assert any("a.png" in p and "Match" in p for p in problems)
    assert any("b.png" in p and "minor_shift" in p for p in problems)


def test_validate_qa_results_flags_missing_verdict_key():
    results = [{"output": "/o/a.png", "input": "/i/a.jpg",
                "color": {"notes": "forgot verdict"},
                "construction": {"verdict": "match", "notes": ""}}]
    problems = floralib.validate_qa_results(results)
    assert len(problems) == 1 and "None" in problems[0]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest skills/flora-batch/scripts/tests/test_floralib.py -q -k validate_qa_results`
Expected: FAIL with `AttributeError`

- [ ] **Step 3: Implement in floralib.py**

```python
COLOR_VERDICTS = frozenset(["match", "minor_shift", "mismatch"])
CONSTRUCTION_VERDICTS = frozenset(["match", "minor_deviation", "mismatch"])


def validate_qa_results(results):
    """Problem strings for records whose verdicts are outside the canonical
    vocabulary ([] == all valid). Typos would flag conservatively downstream
    (qa_overall_flag treats any non-'match' as flagged) but corrupt the
    machine-readable report the PhotoStudio app will consume -- catch them."""
    problems = []
    for i, r in enumerate(results):
        name = os.path.basename(r.get("output", "record %d" % i))
        c = (r.get("color") or {}).get("verdict")
        k = (r.get("construction") or {}).get("verdict")
        if c not in COLOR_VERDICTS:
            problems.append("%s: unknown color verdict %r" % (name, c))
        if k not in CONSTRUCTION_VERDICTS:
            problems.append("%s: unknown construction verdict %r" % (name, k))
    return problems
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest skills/flora-batch/scripts/tests/test_floralib.py -q`
Expected: all PASS

- [ ] **Step 5: Wire into qa_report.py**

Extend the import to `from floralib import qa_overall_flag, render_qa_report_md, save_json_atomic, validate_qa_results`. In `main()` immediately after `results = json.load(open(a.results))`:

```python
    problems = validate_qa_results(results)
    if problems:
        print("INVALID qa_results.json -- fix the verdicts and re-run:")
        for p in problems:
            print("  ", p)
        print("allowed: color = match|minor_shift|mismatch; "
              "construction = match|minor_deviation|mismatch")
        sys.exit(2)
```

- [ ] **Step 6: Full test run + lint**

Run: `python3 -m pytest skills/flora-batch/scripts/tests -q` → all PASS
Run: `ruff check skills/flora-batch/scripts` → clean

- [ ] **Step 7: Commit**

```bash
git add skills/flora-batch/scripts
git commit -m "feat(flora-batch): qa_report.py validates verdict vocabulary before writing"
```

---

### Task 7: no clean `qa_manifest.json` when picks fail to resolve

**Files:**
- Modify: `skills/flora-batch/scripts/qa_resolve.py`
- Modify: `skills/flora-batch/SKILL.md` (qa_resolve bullet + Garment QA step 1 sentence)

**Interfaces:**
- Consumes: `resolve_qa_pairs`, `save_json_atomic` (already imported).
- Produces: script behavior only — no new floralib API (the resolve logic is already pure and tested; this changes WHEN the script writes).

**Why:** today the script writes a partial manifest AND exits 1 — an agent that misses the exit code proceeds with silently-shrunk QA coverage. On failure: delete any stale manifest, write nothing, exit 1.

- [ ] **Step 1: Rewrite the write/exit logic in qa_resolve.py `main()`**

Replace everything after `result = resolve_qa_pairs(state, selected)` with:

```python
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
```

Also update the script docstring's last paragraph from "Either case exits 1." to:

```
Either case exits 1 and qa_manifest.json is NOT written (any stale manifest
from a prior run is deleted) -- a partial manifest must never silently shrink
QA coverage.
```

- [ ] **Step 2: Update SKILL.md (two exact edits)**

Edit 1 — scripts list, replace:
```
- `scripts/qa_resolve.py` — map user-picked output filenames back to their input photos, write `qa_manifest.json` (per-image only, v1).
```
with:
```
- `scripts/qa_resolve.py` — map user-picked output filenames back to their input photos, write `qa_manifest.json` (per-image only, v1). Written only when EVERY pick resolves — unresolved/ambiguous picks exit 1 with no manifest.
```

Edit 2 — Garment QA section step 1, replace:
```
If it prints `UNRESOLVED`, those filenames don't match anything in `batch_state.json` — confirm the spelling with the user rather than guessing.
```
with:
```
If it prints `UNRESOLVED` (filename not in `batch_state.json`) or `AMBIGUOUS` (same basename from two different inputs), no manifest is written — confirm with the user rather than guessing, then re-run.
```

- [ ] **Step 3: Full test run + lint**

Run: `python3 -m pytest skills/flora-batch/scripts/tests -q` → all PASS (no test changes in this task; the pure logic was already covered)
Run: `ruff check skills/flora-batch/scripts` → clean

- [ ] **Step 4: Commit**

```bash
git add skills/flora-batch/scripts/qa_resolve.py skills/flora-batch/SKILL.md
git commit -m "fix(flora-batch): qa_resolve.py writes no manifest when any pick is unresolved/ambiguous"
```
