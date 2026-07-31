#!/usr/bin/env python3
"""Pure, network-free helpers for the flora-batch skill. Unit-tested; imported by
the thin CLI scripts (download.py, compose.py, contact_sheet.py)."""
import base64
import json
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


def save_json_atomic(obj, path, indent=2):
    """Write JSON via temp-file + os.replace so an interrupt can never leave a
    truncated file. The state files are the pipeline's only checkpoint -- a
    half-written batch_state.json loses the whole batch's recovery story.
    Temp file lives in the same directory so os.replace stays atomic."""
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(obj, f, indent=indent)
    os.replace(tmp, path)


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


def is_output_artifact(filename, suffix):
    """True if filename looks like a batch OUTPUT (<stem><suffix>_<n>.<ext>).
    Guards init.py enumeration: the 'same' convention writes outputs into the
    input folder, so a re-init there would otherwise enqueue prior outputs as
    new inputs -- and pay to run the technique on its own outputs."""
    return re.search(re.escape(suffix) + r"_\d+\.[A-Za-z0-9]+$", filename) is not None


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

    A recursive batch (init.py --recurse, mirror/sibling convention) can have
    two different input photos in different subfolders produce outputs with
    the identical basename (e.g. red/shirt.jpg and blue/shirt.jpg both yield
    shirt_MCP_1.png in their own output subfolders). If a basename maps to
    two items with different resolved input paths, picking one would silently
    pair the user's selection with a possibly-wrong reference photo -- never
    guess; surface it instead (same philosophy as map_files_to_roles above,
    which splits unmatched_files/unfilled_roles rather than guessing).

    Returns {"pairs": [{"output","input"}, ...], "unresolved": [name, ...],
    "ambiguous": [name, ...]}. A selected name not present in state at all
    goes into "unresolved"; a selected name whose basename collides across
    different input photos goes into "ambiguous" -- a distinct failure mode,
    never silently resolved into "pairs".
    """
    by_basename = {}
    ambiguous_basenames = set()
    for item in state.get("items", []):
        input_path = os.path.join(state["input"], item["rel"])
        for f in item.get("files", []):
            basename = os.path.basename(f)
            existing = by_basename.get(basename)
            if existing is not None and existing["input"] != input_path:
                ambiguous_basenames.add(basename)
                continue
            by_basename[basename] = {"output": f, "input": input_path}
    pairs, unresolved, ambiguous = [], [], []
    for name in selected_outputs:
        if name in ambiguous_basenames:
            ambiguous.append(name)
        elif name in by_basename:
            pairs.append(by_basename[name])
        else:
            unresolved.append(name)
    return {"pairs": pairs, "unresolved": unresolved, "ambiguous": ambiguous}


def qa_overall_flag(color_verdict, construction_verdict):
    """True unless BOTH checks are a clean 'match' -- minor_shift/minor_deviation
    and mismatch all count as worth a human look. Keeps the flag decision
    deterministic instead of asking Claude to self-report it."""
    return not (color_verdict == "match" and construction_verdict == "match")


def _sanitize_table_cell(text):
    """Sanitize free-text for safe insertion into Markdown table cells.
    Escapes backslashes and pipe characters (which delimit columns) and replaces
    newlines and carriage returns with spaces (which would break single-row
    requirement). Backslashes must be escaped first to prevent pre-existing \\|
    sequences from becoming unescaped pipes after pipe-escaping."""
    return text.replace("\\", "\\\\").replace("|", "\\|").replace("\n", " ").replace("\r", " ")


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
            c["verdict"], _sanitize_table_cell(c["notes"]),
            k["verdict"], _sanitize_table_cell(k["notes"]),
            "yes" if r["overall_flag"] else "no",
        ))
    return "\n".join(lines)


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
