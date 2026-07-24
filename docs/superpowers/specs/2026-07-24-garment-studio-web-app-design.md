# Garment QA Studio — Web App Design

**Status:** design approved (including UX mockup), ready for implementation planning.
**Mockup:** `docs/superpowers/specs/2026-07-24-garment-studio-web-app-mockup/index.html` — open directly in a browser. Approved as-is on 2026-07-24.

## Problem

`flora-batch` (the Claude Code skill) and its garment QA comparison feature only work inside a Claude Code session — a developer runs it via chat, orchestrating Flora MCP calls themselves. BCI's actual users for this workflow are **designers and photo studio staff**, not developers, and they need a tool they can use directly: upload garment photos, generate on-model renders via Flora, review results, and run the same color/construction QA check — all through a web UI, with no Claude Code session required.

## Goals

- Let a non-technical BCI team member upload garment photos, run a pre-approved Flora technique across them, and download results, entirely through a web UI.
- Reproduce the existing garment QA check (color drift + construction drift against a rubric) as a first-class step in that same UI, triggered on whichever outputs the user selects.
- Give an admin a way to manage which Flora techniques are available to run, without touching code.
- Feel like a premium, considered internal tool — the audience (designers, photo studio staff) will judge this the way they judge any creative tool they use daily.

## Non-goals (v1)

- Multi-tenant / multi-org support. This is a single internal BCI tool against the existing BCI Brands Flora workspace.
- Compose (multi-input) Flora techniques. The curated technique list is per-image only, matching the existing QA feature's v1 scope.
- Building a Flora-native QA technique (see "QA judgment" below) — documented as a future option, not built now.
- Our own object storage for images. v1 relies on Flora's asset URLs.
- Deterministic/pixel-level colorimetry. QA judgment stays a qualitative LLM-vision check, same rubric as the existing Claude Code skill.

---

## Approach

The one genuinely open architectural question was how to handle the multi-minute async Flora pipeline (upload → run → poll → download) plus the new QA judgment step, which has no equivalent today outside an interactive Claude Code session. Three approaches were considered:

1. **In-process background worker** — simplest, but doesn't survive a restart mid-batch and scales poorly.
2. **Task queue (Celery/RQ + Redis), polling-based** — robust and standard, but polls Flora repeatedly for status.
3. **Task queue + Flora webhooks (chosen)** — same robustness as (2), but Flora POSTs back to us on run completion (`callback_url`, already supported by `techniques.runs.create`/`runs.startTechnique`) instead of us polling. A slow fallback poll sweep (~every 5 min) catches anything a dropped webhook missed. This directly serves the live-status requirement below with far less API chatter.

---

## Architecture

### Backend — Python (FastAPI)

| Module | Responsibility |
|---|---|
| `api/` | REST endpoints (create batch, list curated techniques, batch/job status, select outputs for QA, get QA results, admin technique CRUD) + an SSE endpoint for live status + a webhook receiver for Flora's completion callbacks. |
| `worker/` | RQ (Redis Queue) tasks, one per pipeline stage: `upload_asset`, `start_run`, `handle_run_webhook` (+ `poll_sweep` fallback), `download_output`, `judge_qa_pair`. |
| `flora_client.py` | Thin HTTP wrapper around Flora's REST API — replaces the "Claude + MCP" call surface with direct calls using a server-held Flora API key (not per-user OAuth; this is a single-workspace internal tool). |
| `floralib` (ported) | The pure logic from the existing skill — cost estimate, host-aware download URL selection, GCS reservation validation, `resolve_qa_pairs`, `qa_overall_flag` — carries over almost as-is; it already operates on plain dicts. The CLI-specific, local-filesystem pieces (`init.py`/`upload.py`/`download.py`'s file-writing) are replaced by task functions that read/write DB rows instead of `batch_state.json`. |
| `qa_judge.py` | New: calls the Anthropic API directly with the two image URLs + the rubric (ported verbatim from `SKILL.md`'s Garment QA section) and gets back a structured verdict (tool-use / JSON schema matching `qa_checks`). |
| `db/` | Postgres via SQLAlchemy. See Data Model below. |

### QA judgment: direct Claude API (primary), Flora technique (documented future option)

Investigated whether Flora itself could do the two-image comparison natively:

- Flora has **no built-in image-comparison capability** today.
- Flora **does** route vision-capable models (including Claude, GPT, Gemini) through its own API as `image-to-text` generations — single-image vision analysis is natively possible through Flora.
- For a **two-image** comparison, the clean Flora-native path would be a custom **Technique** with two image inputs (`original_photo`, `rendered_output`) plus the rubric baked in, returning a text verdict. Techniques can only be created through Flora's own Technique Builder UI — there's no API to provision one, so this requires a one-time manual setup step by someone with Flora technique-builder access, outside this codebase.

**Decision:** v1 calls the Anthropic API directly (same rubric, same model class Claude Code already uses for this judgment today, invoked headlessly instead of interactively). If a "Garment QA Compare" technique is later built in Flora, swapping `qa_judge.py`'s implementation to call it instead is a contained change — the rest of the system (DB schema, API, frontend) doesn't need to know which path produced the verdict.

### Frontend — JS/TS (React)

Screens (all shown in the approved mockup):

1. **New Batch** — drag-drop upload, curated technique picker (radio list, cost per run visible), sticky cost-gate bar showing `N images × $run_cost = $total`, requiring an explicit click to spend.
2. **Live Status** — dense per-image job table (thumbnail, filename, status badge, progress, retry action on failure), live-updating via SSE.
3. **Results & Select** — image-forward gallery, each card showing the rendered output with the source photo as a small corner thumbnail, click-to-select, sticky "Check selected" action bar.
4. **QA Verdicts** — flagged items surfaced first in their own section, each as a card with input/output shown side by side (not stacked — this is the one place fidelity comparison actually happens, so it gets the most screen space) plus per-category verdict badges and notes.
5. **Admin — Techniques** — table of curated techniques (name, Flora technique ID, run cost, input count, active toggle), add/edit, with non-per-image techniques visible but disabled and labeled why.
6. **Admin — Audit Log** — who ran what batch, who ran QA on what, who changed the technique list, when.

**Design language:** a mix of Linear/Vercel/Stripe precision (restrained neutral palette, one sharp accent color, crisp type, subtle motion) and Palantir/Retool density on job-management screens, where studio users need to scan many images/statuses at once. Because the audience is designers judging color and construction fidelity, image presentation is core UX, not decoration: large high-fidelity previews, side-by-side comparison on the QA screen, and the app must not itself introduce color shift (careless compression/resizing/color-space handling) — that would undermine the entire QA premise.

---

## Data Model (Postgres)

| Table | Key columns |
|---|---|
| `users` | id, email, name (BCI-internal accounts only, see Auth) |
| `techniques` | id, flora_technique_id, name, description, run_cost, input_count, active (bool), added_by, created_at — the curated admin-managed list |
| `batches` | id, name, technique_id, created_by, status, total_cost, created_at |
| `batch_items` | id, batch_id, input_asset_url, status (`pending`/`uploading`/`running`/`done`/`failed`), flora_run_id, output_urls (jsonb array), error_message |
| `qa_checks` | id, batch_item_id, output_url, input_url, color_verdict, color_notes, construction_verdict, construction_notes, overall_flag, checked_by, checked_at |
| `audit_log` | id, user_id, action, detail (jsonb), created_at |

## Data Flow

1. User uploads N images, picks a technique from the curated (per-image only) list. Backend computes `N × run_cost` and shows it; user confirms (the cost gate — a UI button, same mandatory-approval principle as the existing skill's chat-based gate).
2. `batches` row created, one `batch_items` row per image, upload+run tasks enqueued per item.
3. Worker uploads each image to Flora (signed URL reserve → PUT bytes → complete, same dance as today) and starts the technique run with `callback_url` pointing at our webhook endpoint.
4. Flora POSTs completion to the webhook → `batch_items` row updated with `output_urls` and `status=done` → SSE event published to the batch's status page. A fallback poll sweep reconciles anything stuck `running` past a timeout in case a webhook is missed.
5. User reviews the results gallery, selects the outputs they care about, clicks "Check selected."
6. One `judge_qa_pair` task per selected output calls `qa_judge.py` (Anthropic API, vision) with both image URLs + the rubric, gets a structured verdict, computes `overall_flag` (ported `qa_overall_flag`), persists a `qa_checks` row.
7. QA Verdicts screen shows flagged items first, full results underneath.

## Auth

Internal BCI tool, single workspace, small trusted user base. Recommended: **Google OAuth restricted to the BCI email domain** — no password management to build or store, standard library support in FastAPI, and it's a real identity (not a shared login) for the audit log to attribute actions to. No roles beyond "user" and "admin" (admin = can edit the curated technique list) in v1.

## Error Handling

- Expired upload URL (400/403) → retry via `assets.retry()`, same as today, bounded retries.
- Run failure → mark item failed, surface the reason, offer a retry button (fresh idempotency key — re-running a failed run needs a new one).
- `insufficient_credits` (402) → mark the batch blocked, show a clear "top up Flora credits" message, no auto-retry.
- Missed webhook → fallback poll sweep reconciles anything stuck `running` past a timeout threshold.
- QA judgment call failure (Anthropic API error/timeout) → bounded retry with backoff, surfaced per-item, doesn't fail the whole batch.

## Testing

- Backend: pytest. The ported `floralib` pure functions reuse (and extend) the existing test suite directly. New tests for `flora_client.py` (mocked HTTP), `qa_judge.py` (mocked Anthropic call, asserting the rubric/schema are sent and parsed correctly), the webhook handler (payload validation, idempotency), and task orchestration.
- No production Flora spend in CI — the Flora API client is fully mocked in tests, matching the existing "tests are network-free" convention already established in `floralib.py`'s suite.
- Frontend: component tests for the upload form, status grid, and QA results view; one end-to-end smoke test (upload → mocked backend → see results) via Playwright.
- The QA judgment step itself remains inherently non-deterministic (same caveat as the existing skill) — validated by spot-checking known-good/known-bad pairs during implementation, not by asserting exact model output.

## Open Questions

1. Should the curated technique list eventually support compose (multi-input) techniques, with QA simply skipped for those runs? Explicitly deferred — v1 keeps the list per-image only.
2. If a Flora-native "Garment QA Compare" technique is built later, does that replace the direct Anthropic API call entirely, or run alongside it for comparison? Not decided — `qa_judge.py`'s interface is designed so this is a contained swap either way.
3. Retention policy for `batches`/`qa_checks` history — how long do old batches stay queryable before archival? Not addressed in v1; flag for a future pass once real usage patterns exist.

## Next Step

Hand off to `superpowers:writing-plans` for a task-by-task implementation plan. Given the scope (backend service, worker/queue infra, frontend app, admin panel), expect that plan to sequence roughly: data model + `flora_client.py` + ported `floralib` first (testable in isolation, no UI needed) → upload/run/webhook pipeline → QA judgment → frontend screens in the order shown in the mockup → admin panel last.
