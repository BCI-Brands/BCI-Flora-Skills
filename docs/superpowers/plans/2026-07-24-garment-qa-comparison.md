# Garment QA Comparison — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build v1 of the garment QA comparison feature from `docs/specs/garment-qa-comparison.md` — after a user picks favorite outputs from a `flora-batch` run, resolve each back to its input photo, have Claude judge color and construction drift against an explicit rubric, and produce a report the user can act on.

**Architecture:** Extend `floralib.py` with three pure, unit-tested functions (`resolve_qa_pairs`, `qa_overall_flag`, `render_qa_report_md`) and add two thin CLI scripts (`qa_resolve.py`, `qa_report.py`) that bridge state to Claude and back — the same shape as `compose.py`/`contact_sheet.py`. The actual color/construction comparison is a **Claude-vision judgment step**, documented as a new `SKILL.md` section, not code. TDD applies to the `floralib` functions and script plumbing; the judgment step itself is not (and cannot be) unit-tested.

**Tech Stack:** Python 3.9+ standard library (`argparse`, `json`, `os`), `pytest`, Claude's own multimodal image reading (no new library, no new MCP dependency).

## Global Constraints

- No new pip dependencies — Python 3.9+ stdlib only, matching the rest of `flora-batch`.
- v1 scope is **per-image batches only**. Compose (multi-input) QA is explicitly out of scope — see spec Open Question 1 (`docs/specs/garment-qa-comparison.md`) — do not implement `resolve_qa_pairs_compose` in this plan.
- No pixel-level/deterministic colorimetry. The color and construction checks are a Claude-vision qualitative judgment against the rubric added to `SKILL.md`, not new code or a new model.
- Zero additional Flora spend. Nothing in this feature calls any Flora MCP `run`/`technique` endpoint.
- All deterministic logic (resolving outputs to inputs, computing the flag, rendering the report) lives in `floralib.py` and is unit-tested. The visual-judgment step is not unit-testable — say so plainly in code/doc comments rather than pretending otherwise.
- Follow existing conventions: `sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))` then `from floralib import ...` in every script; one commit per task, conventional-commit style scoped `feat(flora-batch): ...` / `docs(flora-batch): ...`; never commit to `main`.

---

## Context & Motivation

`docs/specs/garment-qa-comparison.md` designed this feature after noticing `flora-batch` has no automated check that Flora rendered a garment faithfully — color can drift (navy → royal blue) and construction details can be hallucinated, omitted, or altered (buttons, zippers, pockets, logos, prints). BCI's pipeline feeds real product listings, so this is a real defect class, not an aesthetic nit.

The spec's design (already accepted, not re-litigated here):
- Chat-driven trigger — the user names the outputs they liked after reviewing the contact sheet; QA runs on just that subset.
- Deterministic input resolution lives in `floralib.py`, exactly like the rest of the module.
- The comparison itself is Claude reading both images and judging them against a fixed rubric — no new dependency.
- Reports: `qa_report.json` (machine-readable) + `qa_report.md` (human-readable) + a concise chat summary of only the flagged items.
- Zero additional Flora spend.

## File Structure

| File | Action | Responsibility |
|---|---|---|
| `skills/flora-batch/scripts/floralib.py` | **Modify** | Add `resolve_qa_pairs`, `qa_overall_flag`, `render_qa_report_md` — pure, network-free, unit-tested. |
| `skills/flora-batch/scripts/qa_resolve.py` | **Create** | CLI: selected output filenames + `batch_state.json` → `qa_manifest.json` (output/input pairs). |
| `skills/flora-batch/scripts/qa_report.py` | **Create** | CLI: Claude's judged verdicts (`qa_results.json`) → `qa_report.json` + `qa_report.md`, prints only flagged items. |
| `skills/flora-batch/scripts/tests/test_floralib.py` | **Modify** | Unit tests for the three new functions. |
| `skills/flora-batch/SKILL.md` | **Modify** | New "Garment QA" section (trigger, rubric tables, process steps, cost note); refresh Scripts list + Common mistakes. |
| `README.md` | **Modify** | Replace the "planned, not built" Roadmap bullet with real usage docs; update "What's in here"; add a changelog line. |

## Conventions for the implementer

- **Branch:** work on `feat/garment-qa-comparison` (create with `git switch -c feat/garment-qa-comparison`). Never commit to `main`.
- **Tests:** `pytest`. If missing: `python3 -m pip install --quiet pytest`. Run from repo root: `python3 -m pytest skills/flora-batch/scripts/tests -q`.
- **Import pattern:** wrapper scripts do `sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))` then `from floralib import ...`.
- **Commits:** one per task (conventional commits). Frequent and small.
- **DRY / YAGNI:** all pure logic lives in `floralib`; scripts stay thin. Don't add config knobs nobody asked for (no `--compose` flag on these scripts — that's a future plan).

---

### Task 1: `floralib.resolve_qa_pairs` — map selected outputs back to their input photo

**Files:**
- Modify: `skills/flora-batch/scripts/floralib.py`
- Test: `skills/flora-batch/scripts/tests/test_floralib.py`

**Interfaces:**
- Produces: `resolve_qa_pairs(state, selected_outputs) -> {"pairs": [{"output": str, "input": str}, ...], "unresolved": [str, ...]}`. `state` is a parsed `batch_state.json` dict (`{"input": ..., "items": [{"rel", "stem", "files", ...}, ...]}`). `selected_outputs` is a list of output basenames (e.g. `"shirt_MCP_1.png"`). An item's `files` list (set by `download.py`) holds the downloaded output paths; `rel` is the input's path relative to `state["input"]`. Any selected name not found in any item's `files` goes into `unresolved`, never silently dropped.

- [ ] **Step 1: Write the failing tests**

Append to `skills/flora-batch/scripts/tests/test_floralib.py`:

```python
def test_resolve_qa_pairs_maps_outputs_to_inputs():
    state = {
        "input": "/photos",
        "items": [
            {"rel": "shirt.jpg", "stem": "shirt", "files": [
                "/out/shirt_MCP_1.png", "/out/shirt_MCP_2.png"]},
            {"rel": "sub/pants.jpg", "stem": "pants", "files": [
                "/out/sub/pants_MCP_1.png"]},
        ],
    }
    result = floralib.resolve_qa_pairs(state, ["shirt_MCP_1.png", "pants_MCP_1.png"])
    assert result["pairs"] == [
        {"output": "/out/shirt_MCP_1.png", "input": "/photos/shirt.jpg"},
        {"output": "/out/sub/pants_MCP_1.png", "input": "/photos/sub/pants.jpg"},
    ]
    assert result["unresolved"] == []


def test_resolve_qa_pairs_flags_unresolved_selection():
    state = {
        "input": "/photos",
        "items": [{"rel": "shirt.jpg", "stem": "shirt", "files": ["/out/shirt_MCP_1.png"]}],
    }
    result = floralib.resolve_qa_pairs(state, ["shirt_MCP_1.png", "ghost_MCP_9.png"])
    assert result["pairs"] == [{"output": "/out/shirt_MCP_1.png", "input": "/photos/shirt.jpg"}]
    assert result["unresolved"] == ["ghost_MCP_9.png"]
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m pytest skills/flora-batch/scripts/tests/test_floralib.py -k resolve_qa_pairs -q`
Expected: FAIL — `AttributeError: module 'floralib' has no attribute 'resolve_qa_pairs'`.

- [ ] **Step 3: Implement** (append to `skills/flora-batch/scripts/floralib.py`)

```python
def resolve_qa_pairs(state, selected_outputs):
    """Map selected per-image output filenames back to their input photo, using
    the existing batch_state.json record -- item['files'] holds the downloaded
    output paths (set by download.py), item['rel'] the input's path relative to
    state['input']. This is a lookup, not new tracking. Per-image batches only;
    compose (multi-input) resolution is out of scope for v1 (see
    docs/specs/garment-qa-comparison.md, Open Question 1).

    Returns {"pairs": [{"output","input"}, ...], "unresolved": [name, ...]} --
    any selected name not found in state is surfaced, never guessed at.
    """
    by_basename = {}
    for item in state.get("items", []):
        input_path = os.path.join(state["input"], item["rel"])
        for f in item.get("files", []):
            by_basename[os.path.basename(f)] = {"output": f, "input": input_path}
    pairs, unresolved = [], []
    for name in selected_outputs:
        if name in by_basename:
            pairs.append(by_basename[name])
        else:
            unresolved.append(name)
    return {"pairs": pairs, "unresolved": unresolved}
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python3 -m pytest skills/flora-batch/scripts/tests/test_floralib.py -k resolve_qa_pairs -q`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add skills/flora-batch/scripts/floralib.py skills/flora-batch/scripts/tests/test_floralib.py
git commit -m "feat(flora-batch): add floralib.resolve_qa_pairs (output-to-input lookup for QA)"
```

---

### Task 2: `floralib.qa_overall_flag` — single pass/flag decision from both verdicts

**Files:**
- Modify: `skills/flora-batch/scripts/floralib.py`
- Test: `skills/flora-batch/scripts/tests/test_floralib.py`

**Interfaces:**
- Consumes: nothing from Task 1.
- Produces: `qa_overall_flag(color_verdict, construction_verdict) -> bool`. `color_verdict` is one of `"match"`/`"minor_shift"`/`"mismatch"`; `construction_verdict` is one of `"match"`/`"minor_deviation"`/`"mismatch"`. Used by Task 5's `qa_report.py`.

- [ ] **Step 1: Write the failing tests**

Append to `skills/flora-batch/scripts/tests/test_floralib.py`:

```python
def test_qa_overall_flag_clean_match_is_not_flagged():
    assert floralib.qa_overall_flag("match", "match") is False


def test_qa_overall_flag_any_non_match_is_flagged():
    assert floralib.qa_overall_flag("minor_shift", "match") is True
    assert floralib.qa_overall_flag("match", "mismatch") is True
    assert floralib.qa_overall_flag("minor_shift", "minor_deviation") is True
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m pytest skills/flora-batch/scripts/tests/test_floralib.py -k qa_overall_flag -q`
Expected: FAIL — `AttributeError: module 'floralib' has no attribute 'qa_overall_flag'`.

- [ ] **Step 3: Implement** (append to `skills/flora-batch/scripts/floralib.py`)

```python
def qa_overall_flag(color_verdict, construction_verdict):
    """True unless BOTH checks are a clean 'match' -- minor_shift/minor_deviation
    and mismatch all count as worth a human look. Keeps the flag decision
    deterministic instead of asking Claude to self-report it."""
    return not (color_verdict == "match" and construction_verdict == "match")
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python3 -m pytest skills/flora-batch/scripts/tests/test_floralib.py -k qa_overall_flag -q`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add skills/flora-batch/scripts/floralib.py skills/flora-batch/scripts/tests/test_floralib.py
git commit -m "feat(flora-batch): add floralib.qa_overall_flag (deterministic flag decision)"
```

---

### Task 3: `floralib.render_qa_report_md` — human-readable report table

**Files:**
- Modify: `skills/flora-batch/scripts/floralib.py`
- Test: `skills/flora-batch/scripts/tests/test_floralib.py`

**Interfaces:**
- Consumes: nothing from Tasks 1–2 directly (takes pre-shaped input), but the field names it reads (`color`, `construction`, `overall_flag`) match what Task 5's `qa_report.py` will have already computed with `qa_overall_flag`.
- Produces: `render_qa_report_md(results) -> str`. `results` is a list of `{"output": str, "input": str, "color": {"verdict": str, "notes": str}, "construction": {"verdict": str, "notes": str}, "overall_flag": bool}`. Returns a Markdown table.

- [ ] **Step 1: Write the failing test**

Append to `skills/flora-batch/scripts/tests/test_floralib.py`:

```python
def test_render_qa_report_md_builds_table_with_flag_column():
    results = [
        {
            "output": "/out/shirt_MCP_1.png", "input": "/in/shirt.jpg",
            "color": {"verdict": "match", "notes": "navy matches"},
            "construction": {"verdict": "match", "notes": "all buttons present"},
            "overall_flag": False,
        },
        {
            "output": "/out/shirt_MCP_2.png", "input": "/in/shirt.jpg",
            "color": {"verdict": "mismatch", "notes": "navy rendered bright blue"},
            "construction": {"verdict": "match", "notes": "ok"},
            "overall_flag": True,
        },
    ]
    md = floralib.render_qa_report_md(results)
    assert md.splitlines()[0].startswith("| Output |")
    assert "shirt_MCP_1.png" in md
    assert "shirt_MCP_2.png" in md
    assert "mismatch" in md
    assert "navy rendered bright blue" in md
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python3 -m pytest skills/flora-batch/scripts/tests/test_floralib.py -k render_qa_report_md -q`
Expected: FAIL — `AttributeError: module 'floralib' has no attribute 'render_qa_report_md'`.

- [ ] **Step 3: Implement** (append to `skills/flora-batch/scripts/floralib.py`)

```python
def render_qa_report_md(results):
    """results: [{"output","input","color":{"verdict","notes"},
    "construction":{"verdict","notes"},"overall_flag"}, ...]. Returns a
    Markdown table -- the human-readable half of the QA report (the other
    half is the same records dumped as qa_report.json)."""
    lines = ["| Output | Color | Construction | Flagged |", "|---|---|---|---|"]
    for r in results:
        c, k = r["color"], r["construction"]
        lines.append("| %s | %s — %s | %s — %s | %s |" % (
            os.path.basename(r["output"]),
            c["verdict"], c["notes"],
            k["verdict"], k["notes"],
            "yes" if r["overall_flag"] else "no",
        ))
    return "\n".join(lines)
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `python3 -m pytest skills/flora-batch/scripts/tests/test_floralib.py -q`
Expected: PASS (all `floralib` tests, including the new ones).

- [ ] **Step 5: Commit**

```bash
git add skills/flora-batch/scripts/floralib.py skills/flora-batch/scripts/tests/test_floralib.py
git commit -m "feat(flora-batch): add floralib.render_qa_report_md (human-readable QA table)"
```

---

### Task 4: `qa_resolve.py` — CLI to build `qa_manifest.json`

**Files:**
- Create: `skills/flora-batch/scripts/qa_resolve.py`

**Interfaces:**
- Consumes: `resolve_qa_pairs(state, selected_outputs)` from Task 1.

- [ ] **Step 1: Create `qa_resolve.py`**

```python
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
```

- [ ] **Step 2: Smoke-test against a fake batch_state.json**

Run:
```bash
cd /tmp && rm -rf qa_smoke && mkdir qa_smoke && cd qa_smoke
cat > batch_state.json <<'EOF'
{
  "input": "/tmp/qa_smoke/photos",
  "items": [
    {"rel": "shirt.jpg", "stem": "shirt", "files": ["/tmp/qa_smoke/out/shirt_MCP_1.png"]}
  ]
}
EOF
python3 /Users/fbrinadze/projects/bci-flora-skills/skills/flora-batch/scripts/qa_resolve.py \
  --state batch_state.json --selected shirt_MCP_1.png
cat qa_manifest.json
```
Expected: prints `resolved  : 1`, `manifest  : .../qa_manifest.json`, exits 0 (no `UNRESOLVED` line); `qa_manifest.json` contains `[{"output": "/tmp/qa_smoke/out/shirt_MCP_1.png", "input": "/tmp/qa_smoke/photos/shirt.jpg"}]`.

- [ ] **Step 3: Smoke-test the unresolved-selection exit path**

Run:
```bash
cd /tmp/qa_smoke
python3 /Users/fbrinadze/projects/bci-flora-skills/skills/flora-batch/scripts/qa_resolve.py \
  --state batch_state.json --selected ghost_MCP_9.png; echo "exit=$?"
```
Expected: prints `UNRESOLVED (not found in state -- check spelling): ['ghost_MCP_9.png']` and `exit=1`.

- [ ] **Step 4: Commit**

```bash
git add skills/flora-batch/scripts/qa_resolve.py
git commit -m "feat(flora-batch): add qa_resolve.py (selected outputs -> qa_manifest.json)"
```

---

### Task 5: `qa_report.py` — CLI to render the QA report from Claude's verdicts

**Files:**
- Create: `skills/flora-batch/scripts/qa_report.py`

**Interfaces:**
- Consumes: `qa_overall_flag(color_verdict, construction_verdict)` from Task 2, `render_qa_report_md(results)` from Task 3.

- [ ] **Step 1: Create `qa_report.py`**

```python
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
from floralib import qa_overall_flag, render_qa_report_md


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", required=True)
    ap.add_argument("--out-dir", required=True)
    a = ap.parse_args()

    results = json.load(open(a.results))
    for r in results:
        r["overall_flag"] = qa_overall_flag(r["color"]["verdict"], r["construction"]["verdict"])

    os.makedirs(a.out_dir, exist_ok=True)
    json.dump(results, open(os.path.join(a.out_dir, "qa_report.json"), "w"), indent=2)
    open(os.path.join(a.out_dir, "qa_report.md"), "w").write(render_qa_report_md(results))

    flagged = [r for r in results if r["overall_flag"]]
    print("checked   :", len(results))
    print("flagged   :", len(flagged))
    for r in flagged:
        print("FLAG  %s  color=%s  construction=%s" % (
            os.path.basename(r["output"]), r["color"]["verdict"], r["construction"]["verdict"]))


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Smoke-test with one clean pair and one flagged pair**

Run:
```bash
cd /tmp/qa_smoke
cat > qa_results.json <<'EOF'
[
  {"output": "/tmp/qa_smoke/out/shirt_MCP_1.png", "input": "/tmp/qa_smoke/photos/shirt.jpg",
   "color": {"verdict": "match", "notes": "navy matches"},
   "construction": {"verdict": "match", "notes": "all buttons present"}},
  {"output": "/tmp/qa_smoke/out/shirt_MCP_2.png", "input": "/tmp/qa_smoke/photos/shirt.jpg",
   "color": {"verdict": "mismatch", "notes": "navy rendered bright blue"},
   "construction": {"verdict": "match", "notes": "ok"}}
]
EOF
python3 /Users/fbrinadze/projects/bci-flora-skills/skills/flora-batch/scripts/qa_report.py \
  --results qa_results.json --out-dir report_out
cat report_out/qa_report.json
cat report_out/qa_report.md
```
Expected: stdout shows `checked   : 2`, `flagged   : 1`, and one `FLAG  shirt_MCP_2.png  color=mismatch  construction=match` line; `report_out/qa_report.json` has `"overall_flag": false` on the first record and `true` on the second; `report_out/qa_report.md` starts with `| Output | Color | Construction | Flagged |`.

- [ ] **Step 3: Commit**

```bash
git add skills/flora-batch/scripts/qa_report.py
git commit -m "feat(flora-batch): add qa_report.py (render qa_report.json + qa_report.md)"
```

---

### Task 6: `SKILL.md` — add the Garment QA section, refresh Scripts + Common mistakes

**Files:**
- Modify: `skills/flora-batch/SKILL.md`

- [ ] **Step 1: Insert a new "Garment QA" section after "Compose (multi-input) techniques" and before "Hard-won rules"**

Find (end of the Compose section, exact text at the current end of that section):
```markdown
Many looks = one subfolder per look = one run each; throttle as usual.

## Hard-won rules — do NOT skip (each caused a real failure)
```
Replace with:
```markdown
Many looks = one subfolder per look = one run each; throttle as usual.

## Garment QA (after the user picks favorites)

Once the user has reviewed the contact sheet / outputs and told you which ones they like, check the picks for two failure modes before calling the batch done: **color drift** and **construction drift**. **Per-image batches only in v1** — compose (multi-input) runs aren't supported yet (see `docs/specs/garment-qa-comparison.md`).

**Zero additional Flora spend.** This step makes no MCP `run`/`technique` calls — only local file reads plus your own vision.

1. **Resolve** the picks back to their input photos: `python3 scripts/qa_resolve.py --state batch_state.json --selected out1.png,out2.png` → writes `qa_manifest.json` (`[{"output","input"}, ...]`). If it prints `UNRESOLVED`, those filenames don't match anything in `batch_state.json` — confirm the spelling with the user rather than guessing.
2. **Judge each pair** by reading the `output` and `input` images directly and scoring them against the rubrics below. If you can't see a detail clearly, say so in `notes` instead of forcing a verdict.
3. **Write your verdicts** to `qa_results.json`: `[{"output":path,"input":path,"color":{"verdict":...,"notes":...},"construction":{"verdict":...,"notes":...}}, ...]`.
4. **Render the report:** `python3 scripts/qa_report.py --results qa_results.json --out-dir DIR` → writes `DIR/qa_report.json` + `DIR/qa_report.md`, and prints only the flagged items.
5. **Relay only the flagged items** to the user, by filename, with the verdict and note — not a full dump of every pair checked.

**Color rubric**

| Check | Detail |
|---|---|
| Hue family | Compare hue *family* (red vs. orange vs. pink) — your vision isn't calibrated for exact colorimetry, don't claim pixel-level precision. |
| Perceptible shift | Flag any shift big enough a human would call it "a different color" (navy → bright blue, black → dark grey). |
| Multi-color coverage | For multi-color garments/prints, check all major input colors are present in the output, not just the dominant one. |
| Verdict | `match` / `minor_shift` / `mismatch` |

**Construction rubric**

| Check | Detail |
|---|---|
| Garment type and fit | Same silhouette/cut (crew vs. v-neck, long vs. short sleeve, etc.). |
| Distinguishing features | Buttons, zippers, pockets, collar type, hems, drawstrings, logos/graphics, text, embroidery — present and correct. |
| Pattern/texture | Stripes, plaids, prints reproduced and recognizable. Position/orientation may shift naturally with model pose; the pattern itself should not change. |
| Hallucinations vs. omissions | Flag separately: features **added** in the output that weren't in the input, vs. features **missing** from the output that were in the input. |
| Verdict | `match` / `minor_deviation` / `mismatch` |

## Hard-won rules — do NOT skip (each caused a real failure)
```

- [ ] **Step 2: Add the two new scripts to the Scripts list**

Find:
```markdown
- `scripts/review.py` — legacy comparison HTML for headless-Chrome screenshotting (prefer `contact_sheet.py`).
- `scripts/tests/` — `pytest` unit tests for `floralib` + `contact_sheet` (`python3 -m pytest skills/flora-batch/scripts/tests -q`).
```
Replace with:
```markdown
- `scripts/review.py` — legacy comparison HTML for headless-Chrome screenshotting (prefer `contact_sheet.py`).
- `scripts/qa_resolve.py` — map user-picked output filenames back to their input photos, write `qa_manifest.json` (per-image only, v1).
- `scripts/qa_report.py` — render Claude's judged verdicts into `qa_report.json` + `qa_report.md`, print only the flagged items.
- `scripts/tests/` — `pytest` unit tests for `floralib` + `contact_sheet` (`python3 -m pytest skills/flora-batch/scripts/tests -q`).
```

- [ ] **Step 3: Add a Common mistakes bullet**

Find:
```markdown
- Trusting a local path across a long run. Re-`find` the state file if it moves.

## Sharing
```
Replace with:
```markdown
- Trusting a local path across a long run. Re-`find` the state file if it moves.
- Skipping the Garment QA rubric on picked outputs, or forcing a verdict when a detail isn't clearly visible — say so in `notes` instead.

## Sharing
```

- [ ] **Step 4: Verify the edits landed**

Run (from the repo root you're already working in — do NOT `cd` to a different checkout):
```bash
grep -c "## Garment QA (after the user picks favorites)" skills/flora-batch/SKILL.md   # expect 1
grep -c "qa_resolve.py" skills/flora-batch/SKILL.md                                    # expect >=2
grep -c "qa_report.py" skills/flora-batch/SKILL.md                                     # expect >=2
grep -c "minor_deviation" skills/flora-batch/SKILL.md                                  # expect 1
```
Expected: `1`, `2+`, `2+`, `1`.

- [ ] **Step 5: Commit**

```bash
git add skills/flora-batch/SKILL.md
git commit -m "docs(flora-batch): add Garment QA section (rubric + process), refresh scripts list"
```

---

### Task 7: `README.md` — document the shipped feature, drop the "planned" Roadmap bullet

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Replace the Roadmap section with a real usage section**

Find:
```markdown
## Roadmap

- **Garment QA comparison** *(planned, not built)* — after you review the contact sheet and pick outputs, Claude will check the selected outputs against their input photos for color drift and construction drift (silhouette, buttons, zippers, pockets, and other details), and flag anything that looks off. Uses Claude's own vision, so it spends no Flora credits. See the design in `docs/specs/garment-qa-comparison.md`.
```
Replace with:
```markdown
## Garment QA

After you review the contact sheet and tell Claude which outputs you like, ask it to QA them. Claude checks each pick against its input photo for two things — **color drift** (rendered color doesn't match the input) and **construction drift** (buttons, zippers, pockets, logos, prints, or other details hallucinated, missing, or altered) — and reports back only the ones worth a second look.

Uses Claude's own vision, so it spends **no Flora credits**. Per-image batches only for now; compose (multi-input) runs aren't supported yet. See the design in `docs/specs/garment-qa-comparison.md`.
```

- [ ] **Step 2: Add the two new scripts to "What's in here"**

Find:
```markdown
            ├── contact_sheet.py # portable review gallery, no headless Chrome
            ├── review.py        # legacy headless-Chrome comparison HTML
            └── tests/           # pytest unit tests
```
Replace with:
```markdown
            ├── contact_sheet.py # portable review gallery, no headless Chrome
            ├── review.py        # legacy headless-Chrome comparison HTML
            ├── qa_resolve.py    # map picked outputs back to input photos (per-image, v1)
            ├── qa_report.py     # render QA verdicts into qa_report.json/.md
            └── tests/           # pytest unit tests
```

- [ ] **Step 3: Append a changelog line**

Find:
```markdown
## Changelog

- 2026-07-22: hardened for compose (multi-input) techniques + workspace billing; corrected the 100 KB `execute` rule; host-aware downloads; portable contact-sheet review. See `docs/superpowers/plans/2026-07-22-flora-batch-hardening-and-multi-input.md`.
```
Replace with:
```markdown
## Changelog

- 2026-07-24: added garment QA comparison (color + construction drift checks on user-picked outputs, per-image batches). See `docs/superpowers/plans/2026-07-24-garment-qa-comparison.md`.
- 2026-07-22: hardened for compose (multi-input) techniques + workspace billing; corrected the 100 KB `execute` rule; host-aware downloads; portable contact-sheet review. See `docs/superpowers/plans/2026-07-22-flora-batch-hardening-and-multi-input.md`.
```

- [ ] **Step 4: Verify + run the full test suite**

Run (from the repo root you're already working in — do NOT `cd` to a different checkout; use whatever `python3`/pytest invocation this worktree's other tasks have been using, since system `python3` may not have `pytest` installed):
```bash
grep -c "## Garment QA" README.md              # expect 1
grep -c "qa_resolve.py" README.md               # expect 1
grep -c "planned, not built" README.md          # expect 0
python3 -m pytest skills/flora-batch/scripts/tests -q   # or the venv pytest this worktree uses
```
Expected: `1`, `1`, `0`, and all tests pass.

- [ ] **Step 5: Commit**

```bash
git add README.md
git commit -m "docs: document garment QA usage in README, drop planned-roadmap bullet"
```

---

## Self-Review

**Spec coverage** (`docs/specs/garment-qa-comparison.md` → task):
- Chat-driven trigger, no new UI → Task 6 Step 1 (process steps 1–5 in the new SKILL.md section).
- Input resolution (`resolve_qa_pairs`) → Task 1.
- Compose resolution explicitly deferred → Global Constraints + Task 1's docstring + Task 4's docstring + Task 6 Step 1's opening line.
- Color rubric / construction rubric, reproduced for the agent that actually runs them → Task 6 Step 1.
- Output artifacts (`qa_report.json`, `qa_report.md`, flagged-only chat summary) → Task 3 (render function), Task 5 (`qa_report.py`), Task 6 Step 1 (process step 5: relay only flagged items).
- Zero additional Flora spend, stated explicitly → Task 6 Step 1 opening + Global Constraints.
- Testing section (pure functions unit-tested, judgment step not) → Tasks 1–3 (tests) + Global Constraints (explicit statement, not a placeholder).
- "Next step" pointer in the spec (write this plan) → this document.

**Placeholder scan:** every code step has complete code; every doc step has exact Find/Replace text; every test step has a command + expected output. No TBD/TODO. `resolve_qa_pairs_compose` is intentionally not implemented (Global Constraints scopes it out) rather than stubbed.

**Type consistency:** `resolve_qa_pairs(state, selected_outputs) -> {"pairs","unresolved"}` (Task 1) is consumed by `qa_resolve.py` (Task 4) exactly as defined. `qa_overall_flag(color_verdict, construction_verdict) -> bool` (Task 2) and `render_qa_report_md(results) -> str` (Task 3) are both consumed by `qa_report.py` (Task 5) with matching field names (`color`/`construction`/`overall_flag`, each a dict with `verdict`/`notes`). `qa_report.py`'s output schema (`qa_report.json` records) matches the schema documented in `docs/specs/garment-qa-comparison.md`.

**Notes for the executor:**
- `qa_resolve.py` and `qa_report.py` are deliberately not given `pytest` unit tests of their own — the CLI plumbing (argparse + file I/O) is thin, and the logic underneath is already covered via `floralib`'s tests, matching how `compose.py` and `init.py` are smoke-tested rather than unit-tested elsewhere in this codebase.
- Nothing in this plan touches `contact_sheet.py`, `download.py`, `upload.py`, `compose.py`, or `init.py` — the feature is additive.
- Task 6 and Task 7 both touch documentation only; Task 7 Step 4 runs the full test suite as a final sanity check that nothing upstream broke.
