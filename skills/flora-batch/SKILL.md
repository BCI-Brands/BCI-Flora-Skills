---
name: flora-batch
description: Use when running a FLORA technique across a whole folder of images and saving the outputs locally — "run this technique on this folder", batch garment-removal / upscale / pose-generation, N images to outputs with a naming convention, or recovering a Flora batch that stalled on upload-URL expiry, GENERATION_PROVIDER_TIMEOUT, 502 from the code server, or insufficient_credits.
---

# FLORA Batch Runner

## Overview

Run one FLORA technique across **every image in a folder** and save the outputs locally, **resumably**, with a **cost gate before any spend**.

Core constraint that shapes everything: **FLORA's compute runs in an isolated sandbox that cannot read your local files or reach the public internet.** So bytes move like this:

- **Upload:** FLORA reserves a signed upload URL (in the sandbox) → **your local shell `curl`s the bytes** to that URL → FLORA marks the asset complete.
- **Download:** the run returns output URLs → **your local shell `curl`s them down.**
- The two worlds are bridged by a **checkpointed `batch_state.json`**.

## When to use

- "Run `<technique>` on `<folder>`" / apply a Flora technique to many images / batch garment-removal, upscale, pose or PDP generation.
- A prior Flora batch stalled with: upload URLs expiring mid-run, `GENERATION_PROVIDER_TIMEOUT`, `502 Bad Gateway` from the code-tool server, or `insufficient_credits`. This skill's checkpoint makes all of those resumable.

## Prerequisites — check these first

1. **FLORA MCP connected.** Find its code tool by keyword — `ToolSearch` for `flora` and use the `…__execute` tool. **Never hardcode the MCP server id**; it differs per person and per session. If it's missing, tell the user to connect the FLORA connector (claude.ai connectors, or `claude mcp`) — you cannot run OAuth for them.
2. **Credits are per-workspace.** Each run bills `technique.run_cost` to a **specific workspace's** USD balance (see **Workspace billing** below). There is no balance-read API — a `402 insufficient_credits` (which does not charge) is the only signal, and its `available:` figure is that workspace's balance.
3. **Local shell + `curl` + `python3`** (all standard on macOS).

## Inputs (accept as flags, else prompt)

| Input | Notes |
|---|---|
| technique | URL or slug (`client.techniques.retrieve(slug)` → `technique_id`, `run_cost`, inputs, **# outputs per image**) |
| input folder | recurse or flat — confirm |
| output convention | `same-folder` · `sibling _SUFFIX` · `mirrored-tree _SUFFIX` |
| suffix | default `_MCP` |
| format | pristine (`?tr=orig-true`, lossless PNG) default, or compressed (bare URL) |

## Cost gate (MANDATORY — never spend without it)

Scan the folder, retrieve the technique, then show **`(number of runs) × $run_cost = $total`**, the output-path preview, and **wait for explicit approval.** Uploads are free; only the **run** phase spends.

- **Per-image technique** (ONE input): number of runs = number of images.
- **Compose technique** (MULTIPLE role inputs, e.g. `top`/`bottom`/`shoes`): one run consumes a *group* of files, so number of runs = number of groups (looks). A single look = **1 run**. Do **not** multiply by "# outputs" — outputs per run are free; the price is flat. Use `floralib.estimate_cost(run_cost, num_runs)`.

**No balance pre-check exists.** There is no API to read a workspace balance — you only learn it from a `402 insufficient_credits` (which does not charge). Since uploads are free and failed/blocked runs are not billed, it is safe to proceed and treat a 402 as the "top up" signal.

## Workspace billing (which wallet pays)

Credits/balance are **per-workspace**, and an account can have several (e.g. a personal one and a team one). Get them with `client.workspaces.list()` → `[{workspace_id, name, role}]`. **Confirm which workspace should pay before spending** (ask if unsure; honor any saved preference).

Two run routes exist — they bill differently:

- `client.techniques.runs.create(tech, {inputs:[{id,type,value}], mode:"async", idempotency_key})` — the nested route. **Has no `workspace_id` and bills the API key's DEFAULT workspace.** Fine only when the default is the wallet you want.
- `client.runs.startTechnique({ technique_id:"tech_…", workspace_id:"ws_…", inputs })` — the top-level route. **Use this to bill a chosen workspace.** Its `inputs` is an **id→value map** (`{ top:url, bottom:url, shoes:url }`), *not* the `[{id,type,value}]` array.

**Poll a top-level run with `client.generations.retrieve(run_id)`.** The nested `techniques.runs.retrieve(run_id,{techniqueId})` returns **404** for `startTechnique` runs.

Assets are portable: an asset uploaded/`complete`d in workspace A yields an HTTPS URL usable as an `imageUrl` input for a run billed to workspace B. For tidiness you *may* stage assets in the billing workspace, but it isn't required.

## Pipeline (each phase writes `batch_state.json` → fully resumable)

Per-image record: `rel, stem, out_subdir, stage, asset_id, run_id, outputs[], files[], error`.
Stages: `pending → uploaded → run_started → outputs_ready → done` (or `run_failed` / `run_blocked`).

0. **Init** — enumerate images, build the output tree, write `batch_state.json`. Resume = re-reading it and skipping `done`.
1. **Upload** — reserve → shell-`curl` → complete. See **Upload rules** below.
2. **Run** — per-image: `techniques.runs.create(...)` per image (**throttle**). Workspace-billed / compose: `runs.startTechnique({technique_id, workspace_id, inputs})` (see **Workspace billing** and **Compose techniques**). Persist `run_id`.
3. **Poll** — nested runs: `techniques.runs.retrieve(run_id,{techniqueId})`; top-level/compose runs: `generations.retrieve(run_id)`. Poll with one short call (≤~24 s sleep + one retrieve) — long calls hit the code-server 502. `status` is truth; `progress` is coarse/non-linear. **Re-run** a `failed` run with a **fresh** idempotency key.
4. **Download** — `curl` each output (`?tr=orig-true` for pristine) into the output convention: `<stem><suffix>_1.png`, `_2.png`.
5. **Auto-review** (if `--review`, default on) — build a comparison contact sheet (original → outputs) + a short findings note (counts, exact $ charged, any off-looking conversions), rendered via headless Chrome.

## Compose (multi-input) techniques

Some techniques are not "one image → outputs" but **"one run consumes several ROLE inputs"** — e.g. `front-pocket-2k-nfs` takes `top` + `bottom` + `shoes` and emits 24 named outputs (`full-1…8`, `top-crop-1…8`, `top-detail-1…8`). Detect this from `technique.inputs`: **more than one input id ⇒ compose.**

Handle a folder that represents ONE look like this:

1. **Map files → role inputs.** `python3 scripts/compose.py --input DIR --technique tech_… --run-cost <c> --roles top,bottom,shoes` auto-maps by filename keyword and writes `compose_state.json`. **View the images and confirm the mapping before spending** — if it prints `UNFILLED roles` / `unmatched files`, resolve with `--map top=FILE,bottom=FILE,shoes=FILE`. `compose.py` also validates `--map` (flags roles not in `--roles` and mapped files that don't exist) and refuses to overwrite an in-progress `compose_state.json` unless you pass `--force`.
2. **Cost gate:** 1 look = **1 run** = `run_cost` (compose.py prints this). Get approval.
3. **Upload** each role's file (reserve → `curl` → `complete`) exactly as for per-image; record `asset_id`s.
4. **Run** via `runs.startTechnique({technique_id, workspace_id, inputs:{top:urlTop, bottom:urlBottom, shoes:urlShoes}})` with an idempotency key. Persist `run_id`.
5. **Poll** with `generations.retrieve(run_id)`; on `completed`, `outputs` is `[{output_id, url}]` (~24 items — fits inline, no file bridge needed).
6. **Download** by name: write `outputs.json` = `[{output_id,url}]`, then `python3 scripts/download.py --outputs outputs.json --out-dir DIR`. Files land as `<output_id>.png`.
7. **Review:** `python3 scripts/contact_sheet.py --dir DIR --outputs outputs.json --title "LOOK 9" --inputs top=FILE,bottom=FILE,shoes=FILE` → `DIR/_contact_sheet.html`. Plus programmatic checks: count == expected, `sips -g pixelWidth -g pixelHeight` non-zero, file sizes > 0.

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

| Rule | Why |
|---|---|
| **Upload backend is not fixed.** Read `reservation.upload.url` + `.form_fields` each time and send *exactly* those fields (+ `file` LAST). FLORA has shipped **ImageKit** (`token/signature/…`) and **GCS** (`policy/x-goog-signature/…`). | A hardcoded ImageKit uploader silently captured `null`s the day FLORA switched to GCS. |
| **Signed upload URLs expire in ~15 min.** Upload in **time-bounded chunks**; if a `curl` returns `400`/`403` (expired), `assets.retry(asset_id)` for a fresh reservation and re-upload just those. | A 38-image upload ran past the window; the tail 400'd. Checkpoint + re-reserve recovered them. |
| **Idempotency keys on every run — and split the two retry cases.** **Same key** = safe re-submit of the *same* attempt after a 502/timeout (returns `idempotency_duplicate`, no double charge). **Re-running a FAILED run needs a NEW key** (e.g. `…-run2`); the same key would only return the dead run. | The code server 502s often, so network retries must be free. But a failed generation is a *new* run and needs a fresh key to actually re-execute. |
| **Heavy techniques time out — throttle *and* expect single-run timeouts.** Cap concurrent runs (~6–8). A **single** heavy run (e.g. a 2K technique fanning to ~24 outputs) can still `GENERATION_PROVIDER_TIMEOUT` after ~10–15 min at concurrency 1 — transient; **retry once with a fresh idempotency key** (usually succeeds). Failed runs are **not billed** (no `charged_cost`). | 35 concurrent 4K runs → 18 timeouts; LOOK 9 (1 run, 24 × 2K) also timed out once, then succeeded on retry. |
| **`insufficient_credits` = stop, tell the user to top up.** Never try to buy credits. Blocked items stay `run_blocked`; resume after top-up. | You cannot purchase on their behalf. |
| **Keep sandbox `execute` calls short.** Chunk API loops (~10) and prefer single-shot `retrieve` over long internal `sleep` loops. | Long calls hit `502` gateway timeouts; short ones get through. |
| **`execute` output hard-caps at 100 000 bytes and ERRORS — there is NO auto-save / file bridge.** Keep returns small (for reservations return only `{asset_id, url, form_fields}`; ~10 fit under the cap and render inline). Move signed data to local by writing `reservations.json` yourself, then **rely on `upload.py`'s HTTP-status check as the safety net** — a mis-copied `policy`/`x-goog-signature` yields a loud 400/403 and `assets.retry(asset_id)` + re-run repairs just that item. Optionally lint each reservation with `floralib.validate_gcs_reservation` first. For big batches, **chunk** reservation calls (~10/`execute`), writing each chunk before the next. | Padding a return to "force a file save" just throws `Error: Output exceeded 100000 bytes`. Verify-and-retry, not a file bridge, is what makes transcription safe (proven on LOOK 9). |
| **Pristine downloads are host-specific.** `?tr=orig-true` is an **ImageKit** transform — apply it only to `ik.imagekit.io` URLs (fall back to bare on 404). **`media.flora.ai` outputs are already full-res PNG** — download the **bare** URL. `download.py` / `floralib.output_variants` do this automatically. | Appending `?tr=orig-true` to a `media.flora.ai` URL wastes a request and can fetch an unexpected response. |
| **Local output folders may move** (iCloud/Dropbox/Hazel sync). If a path vanishes mid-run, `find` for `batch_state.json` and repoint. | Desktop output folders were relocated into Dropbox twice mid-session. |

## Scripts (bundled, adapt paths)

Local drivers live in `scripts/` and are **state-file-driven** (read the state JSON, do only what's pending, checkpoint after each item):

- `scripts/floralib.py` — pure, unit-tested helpers (host-aware download variants, cost estimate, file→role mapping, reservation lint, compose-state builder). Imported by the others.
- `scripts/init.py` — per-image: enumerate + build output tree + write `batch_state.json`.
- `scripts/upload.py` — reservations file + state → GCS/ImageKit POST per image (auto-detects backend by form fields).
- `scripts/download.py` — two modes: per-image `--state`, or compose `--outputs outputs.json --out-dir DIR` (names by `output_id`). Host-aware.
- `scripts/compose.py` — multi-input: map files → roles, write `compose_state.json`, print the correct cost gate.
- `scripts/contact_sheet.py` — portable self-contained review gallery (relative `<img>` refs; opens by double-click; press-D dev mode). No headless Chrome.
- `scripts/review.py` — legacy comparison HTML for headless-Chrome screenshotting (prefer `contact_sheet.py`).
- `scripts/qa_resolve.py` — map user-picked output filenames back to their input photos, write `qa_manifest.json` (per-image only, v1).
- `scripts/qa_report.py` — render Claude's judged verdicts into `qa_report.json` + `qa_report.md`, print only the flagged items.
- `scripts/tests/` — `pytest` unit tests for `floralib` + `contact_sheet` (`python3 -m pytest skills/flora-batch/scripts/tests -q`).

The orchestrating agent makes the FLORA MCP calls (reserve / complete / run / poll) and runs these scripts for byte transfers. Reservation/output data crosses from the sandbox to local by writing a JSON file yourself (the 100 KB `execute` cap means there is no auto-file-bridge — see the hard-won rules).

## Common mistakes

- Spending before the cost gate. Don't.
- Assuming the upload backend. Read the reservation every time.
- Firing the whole batch concurrently on a heavy technique. Throttle.
- Assuming an auto "file bridge" for big `execute` results (there isn't one — 100 KB cap errors). Keep returns small; verify uploads by HTTP status and re-reserve on 4xx.
- Using `techniques.runs.create` (default workspace) when a specific workspace must pay — use `runs.startTechnique({workspace_id})`.
- Multiplying the cost gate by "# outputs", or by "# files" for a compose look. One look = one run.
- Trusting a local path across a long run. Re-`find` the state file if it moves.
- Skipping the Garment QA rubric on picked outputs, or forcing a verdict when a detail isn't clearly visible — say so in `notes` instead.

## Sharing

Portable by construction: no hardcoded server ids, workspace ids, or user paths (resolve workspace via `workspaces.list`; take folder/technique/convention as inputs). To share: commit this `flora-batch/` folder to your team skills repo; teammates drop it in `~/.claude/skills/` and connect their own FLORA MCP + credits.
