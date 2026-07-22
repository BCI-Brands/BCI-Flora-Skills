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
2. **Credits.** Each run bills `technique.run_cost`; N images charge ≈ N × cost. If the account is dry you'll get `402 insufficient_credits`.
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

Scan the folder, retrieve the technique, then show: **N images × $run_cost × outputs = $total**, the output-path preview, and **wait for explicit approval.** Uploads are free; the spend is the **run** phase.

## Pipeline (each phase writes `batch_state.json` → fully resumable)

Per-image record: `rel, stem, out_subdir, stage, asset_id, run_id, outputs[], files[], error`.
Stages: `pending → uploaded → run_started → outputs_ready → done` (or `run_failed` / `run_blocked`).

0. **Init** — enumerate images, build the output tree, write `batch_state.json`. Resume = re-reading it and skipping `done`.
1. **Upload** — reserve → shell-`curl` → complete. See **Upload rules** below.
2. **Run** — `techniques.runs.create(tech,{inputs,mode:"async",idempotency_key})` per image. **Throttle** (see rules). Persist `run_id`.
3. **Poll** — `techniques.runs.retrieve(run_id,{techniqueId})` until `completed`/`failed`; collect the 2 output URLs. **Re-run** `failed` (fresh idempotency key), ideally in a smaller concurrent wave.
4. **Download** — `curl` each output (`?tr=orig-true` for pristine) into the output convention: `<stem><suffix>_1.png`, `_2.png`.
5. **Auto-review** (if `--review`, default on) — build a comparison contact sheet (original → outputs) + a short findings note (counts, exact $ charged, any off-looking conversions), rendered via headless Chrome.

## Hard-won rules — do NOT skip (each caused a real failure)

| Rule | Why |
|---|---|
| **Upload backend is not fixed.** Read `reservation.upload.url` + `.form_fields` each time and send *exactly* those fields (+ `file` LAST). FLORA has shipped **ImageKit** (`token/signature/…`) and **GCS** (`policy/x-goog-signature/…`). | A hardcoded ImageKit uploader silently captured `null`s the day FLORA switched to GCS. |
| **Signed upload URLs expire in ~15 min.** Upload in **time-bounded chunks**; if a `curl` returns `400`/`403` (expired), `assets.retry(asset_id)` for a fresh reservation and re-upload just those. | A 38-image upload ran past the window; the tail 400'd. Checkpoint + re-reserve recovered them. |
| **Idempotency keys on every run** (`gp4k-${asset_id}` etc.). | The code server throws `502` often; keys make retries free — no double-charge. |
| **Throttle concurrency for heavy techniques** (upscalers, multi-model). Cap concurrent runs (~6–8) and let a wave finish before the next. | Firing 35 concurrent 4K/Magnific runs → 18 `GENERATION_PROVIDER_TIMEOUT`. Fewer-at-once succeeds. |
| **`insufficient_credits` = stop, tell the user to top up.** Never try to buy credits. Blocked items stay `run_blocked`; resume after top-up. | You cannot purchase on their behalf. |
| **Keep sandbox `execute` calls short.** Chunk API loops (~10) and prefer single-shot `retrieve` over long internal `sleep` loops. | Long calls hit `502` gateway timeouts; short ones get through. |
| **Oversized `execute` results are auto-saved to a local file** (path in the error). Bash reads that file **verbatim** — never hand-copy long signed strings. To force it for large reservation sets, pad the return over the limit. | Reproducing 38 × 512-char GCS signatures by hand is error-prone; the file bridge is exact. |
| **Pristine downloads:** append `?tr=orig-true` for the lossless original; fall back to the bare URL if it 404s. | The bare URL is CDN-compressed; `orig-true` is the real deliverable. |
| **Local output folders may move** (iCloud/Dropbox/Hazel sync). If a path vanishes mid-run, `find` for `batch_state.json` and repoint. | Desktop output folders were relocated into Dropbox twice mid-session. |

## Scripts (bundled, adapt paths)

Local drivers live in `scripts/` and are **state-file-driven** (read `batch_state.json`, do only what's pending, checkpoint after each item):

- `scripts/upload.py` — reservations file + state → GCS/ImageKit POST per image (auto-detects backend by form fields).
- `scripts/download.py` — run→outputs map + state → `orig-true` download to the naming convention.
- `scripts/init.py` — enumerate + build output tree + write initial state.
- `scripts/review.py` — build the comparison/gallery HTML for headless-Chrome screenshotting.

The orchestrating agent makes the FLORA MCP calls (reserve / complete / run / poll) and runs these scripts for the byte transfers, passing data through files (see the oversized-result rule).

## Common mistakes

- Spending before the cost gate. Don't.
- Assuming the upload backend. Read the reservation every time.
- Firing the whole batch concurrently on a heavy technique. Throttle.
- Hand-copying signed reservations from `execute` output. Use the file bridge.
- Trusting a local path across a long run. Re-`find` the state file if it moves.

## Sharing

Portable by construction: no hardcoded server ids, workspace ids, or user paths (resolve workspace via `workspaces.list`; take folder/technique/convention as inputs). To share: commit this `flora-batch/` folder to your team skills repo; teammates drop it in `~/.claude/skills/` and connect their own FLORA MCP + credits.
