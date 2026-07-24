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


def plan_downloads(outputs, out_dir):
    """Map compose-run outputs to (url, dest_path); dest = out_dir/<output_id>.png."""
    return [(o["url"], os.path.join(out_dir, o["output_id"] + ".png")) for o in outputs]


def estimate_cost(run_cost, num_runs):
    """Total USD = run_cost x number of RUNS. Outputs-per-run are free; do not
    multiply by output count. Compose look = 1 run; per-image batch = N runs."""
    return round(run_cost * num_runs, 2)


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


def compose_state_in_progress(state):
    """True if a compose state has work worth preserving (an asset uploaded or a run
    started) — used to refuse clobbering it on a re-run without --force."""
    if state.get("run_id") or state.get("run_stage", "pending") != "pending":
        return True
    for v in (state.get("inputs") or {}).values():
        if v.get("asset_id") or v.get("stage", "pending") != "pending":
            return True
    return False


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
