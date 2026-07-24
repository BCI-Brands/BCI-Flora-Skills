# Graph Report - .  (2026-07-24)

## Corpus Check
- Corpus is ~12,713 words - fits in a single context window. You may not need a graph.

## Summary
- 94 nodes · 144 edges · 13 communities
- Extraction: 95% EXTRACTED · 5% INFERRED · 0% AMBIGUOUS · INFERRED: 7 edges (avg confidence: 0.81)
- Token cost: 0 input · 127,932 output

## Community Hubs (Navigation)
- [[_COMMUNITY_Compose (Multi-Input) Techniques|Compose (Multi-Input) Techniques]]
- [[_COMMUNITY_Host-Aware Downloads|Host-Aware Downloads]]
- [[_COMMUNITY_Batch State & Run Polling|Batch State & Run Polling]]
- [[_COMMUNITY_Flora Run Routes & Workspace Billing|Flora Run Routes & Workspace Billing]]
- [[_COMMUNITY_Contact Sheet Review Gallery|Contact Sheet Review Gallery]]
- [[_COMMUNITY_Skill Deployment & Provenance|Skill Deployment & Provenance]]
- [[_COMMUNITY_floralib Core & Reservation Validation|floralib Core & Reservation Validation]]
- [[_COMMUNITY_LOOK 9 Hardening Story|LOOK 9 Hardening Story]]

## God Nodes (most connected - your core abstractions)
1. `flora-batch skill` - 29 edges
2. `CLAUDE.md (repo guidance for Claude Code)` - 16 edges
3. `README.md (BCI Flora Skills)` - 12 edges
4. `floralib.py (shared pure, network-free helper module)` - 12 edges
5. `estimate_cost()` - 7 edges
6. `render_contact_sheet()` - 6 edges
7. `output_variants()` - 6 edges
8. `FLORA Batch Hardening & Multi-Input Implementation Plan (2026-07-22)` - 6 edges
9. `compose.py — multi-input state + cost gate CLI` - 6 edges
10. `LOOK 9 / front-pocket-2k-nfs run (motivating example)` - 6 edges

## Surprising Connections (you probably didn't know these)
- `Copy-based (not symlinked) skill deployment` --semantically_similar_to--> `README.md (BCI Flora Skills)`  [INFERRED] [semantically similar]
  .claude/skills/sync-flora-batch/SKILL.md → README.md
- `contact_sheet.py — CLI wrapper for review gallery` --calls--> `render_contact_sheet()`  [EXTRACTED]
  docs/superpowers/plans/2026-07-22-flora-batch-hardening-and-multi-input.md → skills/flora-batch/scripts/contact_sheet.py
- `output_variants()` --references--> `floralib.py (shared pure, network-free helper module)`  [EXTRACTED]
  skills/flora-batch/scripts/floralib.py → docs/superpowers/plans/2026-07-22-flora-batch-hardening-and-multi-input.md
- `plan_downloads()` --references--> `floralib.py (shared pure, network-free helper module)`  [EXTRACTED]
  skills/flora-batch/scripts/floralib.py → docs/superpowers/plans/2026-07-22-flora-batch-hardening-and-multi-input.md
- `estimate_cost()` --references--> `floralib.py (shared pure, network-free helper module)`  [EXTRACTED]
  skills/flora-batch/scripts/floralib.py → docs/superpowers/plans/2026-07-22-flora-batch-hardening-and-multi-input.md

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **floralib.py: pure, unit-tested helper functions extracted from CLI scripts** — skills_flora_batch_scripts_floralib_floralib, skills_flora_batch_scripts_floralib_output_variants, skills_flora_batch_scripts_floralib_plan_downloads, skills_flora_batch_scripts_floralib_estimate_cost, skills_flora_batch_scripts_floralib_map_files_to_roles, skills_flora_batch_scripts_floralib_validate_gcs_reservation, skills_flora_batch_scripts_floralib_build_compose_state [EXTRACTED 1.00]
- **Compose (multi-input) technique workflow: role-map -> state -> cost gate -> run -> download -> review** — skills_flora_batch_skill_compose_technique, skills_flora_batch_scripts_compose_compose_module, skills_flora_batch_scripts_floralib_map_files_to_roles, skills_flora_batch_scripts_floralib_build_compose_state, skills_flora_batch_scripts_floralib_estimate_cost, skills_flora_batch_skill_compose_state_json, skills_flora_batch_scripts_contact_sheet_contact_sheet_module [INFERRED 0.85]
- **Flora API hard-won rules cross-referenced across CLAUDE.md, flora-batch SKILL.md, and the hardening plan** — claude_overview, skills_flora_batch_skill_flora_batch, docs_superpowers_plans_2026_07_22_flora_batch_hardening_and_multi_input_plan, skills_flora_batch_skill_cost_gate [INFERRED 0.75]

## Communities (13 total, 0 thin omitted)

### Community 0 - "Compose (Multi-Input) Techniques"
Cohesion: 0.20
Nodes (13): compose.py — multi-input state + cost gate CLI, main(), contact_sheet.py — CLI wrapper for review gallery, build_compose_state(), compose_state_in_progress(), estimate_cost(), map_files_to_roles(), Resumable state for one compose run: N role inputs -> 1 run -> named outputs. (+5 more)

### Community 2 - "Host-Aware Downloads"
Cohesion: 0.27
Nodes (10): dl(), download.py — host-aware, two-mode download CLI, download_outputs(), download_state(), main(), output_variants(), plan_downloads(), Ordered list of URLs to try when downloading one output.      ImageKit URLs try (+2 more)

### Community 3 - "Batch State & Run Polling"
Cohesion: 0.20
Nodes (10): init.py — per-image enumerate + output tree + state init, review.py — legacy headless-Chrome comparison HTML, upload.py — reservations + state -> GCS/ImageKit POST, assets.retry (re-reserve an expired/failed upload), batch_state.json — per-image resumable checkpoint state, compose_state.json — compose-run resumable checkpoint state, flora-batch skill, media.flora.ai (already-full-res output host) (+2 more)

### Community 4 - "Flora Run Routes & Workspace Billing"
Cohesion: 0.25
Nodes (9): Dev workflow (dated plan -> subagent-driven-development -> TDD), pytest (unit test runner), ruff (pyflakes-only lint, select=["F"]), CLAUDE.md (repo guidance for Claude Code), Google Cloud Storage (upload backend, presigned POST), generations.retrieve (poll top-level/compose runs), Idempotency-key retry pattern (same key vs fresh key), ImageKit (upload/CDN backend) (+1 more)

### Community 5 - "Contact Sheet Review Gallery"
Cohesion: 0.28
Nodes (4): _fig(), main(), inputs: [(label, filename)]; groups: [(heading, [filename, ...])]. Returns HTML., render_contact_sheet()

### Community 6 - "Skill Deployment & Provenance"
Cohesion: 0.29
Nodes (8): Copy-based (not symlinked) skill deployment, sync-flora-batch (slash command / skill), BCI team, Nicholas Swerdlowe (support contact), README.md (BCI Flora Skills), Pierrepont Advisors, Checkpointed, resumable state-file pattern, FLORA MCP connector

### Community 7 - "floralib Core & Reservation Validation"
Cohesion: 0.33
Nodes (6): DRY/YAGNI convention (pure logic in floralib.py, thin scripts), floralib.py (shared pure, network-free helper module), Cheap lint for a GCS presigned-POST reservation after transcription.     Returns, validate_gcs_reservation(), conftest.py — puts scripts/ on sys.path for tests, test_floralib.py — unit tests for floralib functions

### Community 8 - "LOOK 9 Hardening Story"
Cohesion: 0.40
Nodes (5): Feature-branch convention (never commit to main), LOOK 9 / front-pocket-2k-nfs run (motivating example), Correction: no auto file-bridge for oversized execute output, FLORA Batch Hardening & Multi-Input Implementation Plan (2026-07-22), runs.startTechnique (top-level route, bills a chosen workspace)

## Knowledge Gaps
- **13 isolated node(s):** `init.py — per-image enumerate + output tree + state init`, `upload.py — reservations + state -> GCS/ImageKit POST`, `review.py — legacy headless-Chrome comparison HTML`, `conftest.py — puts scripts/ on sys.path for tests`, `test_floralib.py — unit tests for floralib functions` (+8 more)
  These have ≤1 connection - possible missing edges or undocumented components.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `flora-batch skill` connect `Batch State & Run Polling` to `Compose (Multi-Input) Techniques`, `Host-Aware Downloads`, `Flora Run Routes & Workspace Billing`, `Skill Deployment & Provenance`, `floralib Core & Reservation Validation`, `LOOK 9 Hardening Story`?**
  _High betweenness centrality (0.360) - this node is a cross-community bridge._
- **Why does `floralib.py (shared pure, network-free helper module)` connect `floralib Core & Reservation Validation` to `Compose (Multi-Input) Techniques`, `Host-Aware Downloads`, `Batch State & Run Polling`, `Skill Deployment & Provenance`, `LOOK 9 Hardening Story`?**
  _High betweenness centrality (0.211) - this node is a cross-community bridge._
- **Why does `contact_sheet.py — CLI wrapper for review gallery` connect `Compose (Multi-Input) Techniques` to `Batch State & Run Polling`, `Contact Sheet Review Gallery`, `Skill Deployment & Provenance`?**
  _High betweenness centrality (0.162) - this node is a cross-community bridge._
- **What connects `inputs: [(label, filename)]; groups: [(heading, [filename, ...])]. Returns HTML.`, `Ordered list of URLs to try when downloading one output.      ImageKit URLs try`, `Map compose-run outputs to (url, dest_path); dest = out_dir/<output_id>.png.` to the rest of the system?**
  _21 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `floralib Unit Tests` be split into smaller, more focused modules?**
  _Cohesion score 0.14285714285714285 - nodes in this community are weakly interconnected._