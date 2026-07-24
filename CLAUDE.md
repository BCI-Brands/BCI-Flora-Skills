# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

A small library of Claude Code **skills** built on Flora (a generative-media platform, reached via its MCP connector). Delivered by Pierrepont Advisors for the BCI team — **internal use only, not for external distribution**. There's no app, server, or build — just skill definitions (Markdown + YAML frontmatter) and thin Python CLI scripts under `skills/<skill-name>/`.

Currently one skill: `skills/flora-batch/` — runs a Flora technique across a folder of images with a mandatory cost gate and checkpointed, resumable state. Read `skills/flora-batch/SKILL.md` before touching its scripts; it documents the full pipeline and the "hard-won rules" below in more detail.

## Commands

Run tests from repo root (pure-Python stdlib, no manifest — install pytest ad hoc if missing):

```bash
python3 -m pip install --quiet pytest   # only if not already installed
python3 -m pytest skills/flora-batch/scripts/tests -q
```

Unit tests are fully offline (`floralib.py` logic only, no network/API calls). There is no formatter or CI configured in this repo.

Lint (via `ruff`, config in `pyproject.toml`):

```bash
ruff check skills/flora-batch/scripts
```

Scoped to `select = ["F"]` (pyflakes only — real bugs like unused/undefined names) since the existing scripts intentionally use compact one-liners and combined imports; don't "fix" that style.

## Dev workflow

For new features or fixes, follow the same process used for the existing hardening work (see `docs/superpowers/plans/`):
1. Write a dated implementation plan under `docs/superpowers/plans/`, broken into numbered tasks with TDD steps.
2. Execute it with `superpowers:subagent-driven-development` (or `superpowers:executing-plans`), task-by-task.
3. TDD for logic in `floralib.py` and the scripts that wrap it: write a failing test, verify it fails, implement, verify it passes, commit.

## Repo conventions

- **Branching:** work on feature branches (e.g. `feat/flora-batch-hardening`, created with `git switch -c ...`). Never commit directly to `main`.
- **Commits:** one per task, conventional commit style (`feat(flora-batch): ...`, `docs(flora-batch): ...`). Frequent and small.
- **DRY/YAGNI:** all pure, network-free logic lives in `floralib.py`; the CLI scripts (`init.py`, `upload.py`, `download.py`, `compose.py`, `contact_sheet.py`) stay thin wrappers over it. Don't add config knobs nobody asked for.
- **Import pattern** in scripts: `sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))` then `from floralib import ...`. Tests get the same path via `conftest.py`.
- **Never hardcode a Flora MCP server id or workspace/account id.** Find the Flora tool by `ToolSearch` for `flora` — the id differs per person/session. Everything in `flora-batch` is portable by design (no hardcoded accounts, workspace IDs, or file paths).
- Runtime artifacts (`batch_state.json`, `compose_state.json`, `*_MCP_*.png/jpg/jpeg`) are gitignored — never commit them, they contain local paths and proprietary filenames.
- Skill deployment to a user's Claude Code is copy-based, not symlinked (`cp -R skills/flora-batch ~/.claude/skills/`) — editing files in this repo does not update anyone's live skill until they re-copy. Use `/sync-flora-batch` to do this locally after edits.

## Flora API hard-won rules (flora-batch)

These caused real production failures — see `skills/flora-batch/SKILL.md` for full context:

- **Cost gate is mandatory before any spend.** Per-image technique: 1 run/image. Compose (multi-input) technique: 1 run per *look* (group of files), never multiplied by output count or file count.
- **Upload backend (ImageKit vs GCS) is not fixed** — read `reservation.upload.url` + `.form_fields` fresh every time and send exactly those fields, with `file` last in the multipart POST.
- **Signed upload URLs expire in ~15 minutes.** Upload in time-bounded chunks; on 400/403, `assets.retry(asset_id)` and re-upload only the failed ones.
- **Idempotency keys:** same key = safe retry of the same attempt (no double charge). A run that actually **failed** needs a **new** key to re-execute.
- **Throttle concurrency to ~6–8** for heavy techniques. Even one heavy run can `GENERATION_PROVIDER_TIMEOUT` after 10–15 min — retry once with a fresh idempotency key. Failed runs are not billed.
- **`insufficient_credits` = stop and tell the user to top up.** Never attempt to purchase credits on their behalf.
- **Keep sandbox `execute` calls short** — chunk API loops (~10 at a time), prefer single-shot `retrieve` over long sleep loops (long calls hit `502`).
- **`execute` output hard-caps at 100,000 bytes and errors — there is no auto-save/file bridge.** Keep returns small; write files like `reservations.json` locally yourself.
- **Pristine downloads are host-specific:** `?tr=orig-true` is ImageKit-only; `media.flora.ai` outputs are already full-res PNG and must be downloaded bare. `floralib.output_variants` handles this.
- Two run routes bill differently: `techniques.runs.create(...)` bills the default workspace; `runs.startTechnique({technique_id, workspace_id, inputs})` bills a chosen workspace (and its `inputs` is an id→value map, not an array). Poll top-level/compose runs with `generations.retrieve(run_id)` — the nested retrieve 404s for `startTechnique` runs.
