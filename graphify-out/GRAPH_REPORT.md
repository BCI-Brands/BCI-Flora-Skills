# Graph Report - .  (2026-07-31)

## Corpus Check
- 18 files · ~25,716 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 176 nodes · 231 edges · 11 communities (10 shown, 1 thin omitted)
- Extraction: 87% EXTRACTED · 13% INFERRED · 0% AMBIGUOUS · INFERRED: 31 edges (avg confidence: 0.83)
- Token cost: 115,844 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_floralib Test Suite|floralib Test Suite]]
- [[_COMMUNITY_Core floralib & Compose CLI|Core floralib & Compose CLI]]
- [[_COMMUNITY_Garment QA Feature & CI|Garment QA Feature & CI]]
- [[_COMMUNITY_Dev Workflow & Conventions|Dev Workflow & Conventions]]
- [[_COMMUNITY_Contact Sheet Gallery|Contact Sheet Gallery]]
- [[_COMMUNITY_Download Pipeline|Download Pipeline]]
- [[_COMMUNITY_Docs & README|Docs & README]]
- [[_COMMUNITY_Upload & Hard-Won Rules|Upload & Hard-Won Rules]]
- [[_COMMUNITY_QA Report Rendering|QA Report Rendering]]
- [[_COMMUNITY_Flora MCP Config|Flora MCP Config]]

## God Nodes (most connected - your core abstractions)
1. `floralib.py (shared pure, network-free helper module)` - 10 edges
2. `Garment QA Comparison Spec` - 10 edges
3. `CLAUDE.md (repo guidance for Claude Code)` - 8 edges
4. `FLORA Batch Runner (SKILL.md)` - 8 edges
5. `Cost Gate (MANDATORY)` - 8 edges
6. `main()` - 6 edges
7. `render_contact_sheet()` - 6 edges
8. `save_json_atomic()` - 6 edges
9. `output_variants()` - 5 edges
10. `plan_downloads()` - 5 edges

## Surprising Connections (you probably didn't know these)
- `floralib.is_output_artifact` --semantically_similar_to--> `Cost Gate (MANDATORY)`  [INFERRED] [semantically similar]
  docs/superpowers/plans/2026-07-31-flora-batch-hardening-2.md → skills/flora-batch/SKILL.md
- `build_compose_state()` --references--> `floralib.py (shared pure, network-free helper module)`  [EXTRACTED]
  skills/flora-batch/scripts/floralib.py → docs/superpowers/plans/2026-07-22-flora-batch-hardening-and-multi-input.md
- `estimate_cost()` --references--> `floralib.py (shared pure, network-free helper module)`  [EXTRACTED]
  skills/flora-batch/scripts/floralib.py → docs/superpowers/plans/2026-07-22-flora-batch-hardening-and-multi-input.md
- `map_files_to_roles()` --references--> `floralib.py (shared pure, network-free helper module)`  [EXTRACTED]
  skills/flora-batch/scripts/floralib.py → docs/superpowers/plans/2026-07-22-flora-batch-hardening-and-multi-input.md
- `output_variants()` --references--> `floralib.py (shared pure, network-free helper module)`  [EXTRACTED]
  skills/flora-batch/scripts/floralib.py → docs/superpowers/plans/2026-07-22-flora-batch-hardening-and-multi-input.md

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Garment QA Feature (spec -> plan -> shipped skill)** — docs_specs_garment_qa_comparison_spec, docs_superpowers_plans_2026_07_24_garment_qa_comparison_plan, skills_flora_batch_skill_garment_qa, skills_flora_batch_skill_qa_resolve_py, skills_flora_batch_skill_qa_report_py, docs_specs_garment_qa_comparison_color_drift, docs_specs_garment_qa_comparison_construction_drift [EXTRACTED 1.00]
- **Checkpointed Resumable Batch Pattern** — skills_flora_batch_skill_batch_state_json, skills_flora_batch_skill_pipeline, skills_flora_batch_skill_sandbox_isolation, docs_superpowers_plans_2026_07_31_flora_batch_hardening_2_save_json_atomic [INFERRED 0.85]
- **Spend Safety Guardrails** — skills_flora_batch_skill_cost_gate, skills_flora_batch_skill_idempotency_keys, docs_superpowers_plans_2026_07_31_flora_batch_hardening_2_is_output_artifact [INFERRED 0.85]

## Communities (11 total, 1 thin omitted)

### Community 0 - "floralib Test Suite"
Cohesion: 0.05
Nodes (10): A recursive batch (init.py --recurse) can produce two different input     photos, Pipe characters in notes must be escaped to avoid splitting columns., Newlines in notes must be replaced to maintain one-row-per-line structure., Pre-existing backslash-pipe sequences must be escaped correctly.     Backslashes, A lone \\r (e.g. from \\r\\n line endings) must not survive into the     rendere, test_render_qa_report_md_escapes_backslash_before_pipe(), test_render_qa_report_md_escapes_pipe_in_notes(), test_render_qa_report_md_replaces_carriage_return_in_notes() (+2 more)

### Community 1 - "Core floralib & Compose CLI"
Cohesion: 0.08
Nodes (32): compose.py — multi-input state + cost gate CLI, main(), build_compose_state(), build_curl_upload_args(), compose_state_in_progress(), estimate_cost(), is_output_artifact(), map_files_to_roles() (+24 more)

### Community 2 - "Garment QA Feature & CI"
Cohesion: 0.09
Nodes (31): CI Workflow, lint-and-test Job, Chat-Driven Trigger, Claude-Vision Judgment Step, Color Drift, Color Rubric, Construction Drift, Construction Rubric (+23 more)

### Community 3 - "Dev Workflow & Conventions"
Cohesion: 0.13
Nodes (19): Copy-based (not symlinked) skill deployment, sync-flora-batch (slash command / skill), Feature-branch convention (never commit to main), Dev workflow (dated plan -> subagent-driven-development -> TDD), DRY/YAGNI convention (pure logic in floralib.py, thin scripts), pytest (unit test runner), ruff (pyflakes-only lint, select=["F"]), CLAUDE.md (repo guidance for Claude Code) (+11 more)

### Community 4 - "Contact Sheet Gallery"
Cohesion: 0.19
Nodes (7): contact_sheet.py — CLI wrapper for review gallery, _fig(), groups_from_state(), main(), inputs: [(label, filename)]; groups: [(heading, [filename, ...])]. Returns HTML., Per-image mode: [(heading, [img path relative to state['output'], ...])]     for, render_contact_sheet()

### Community 5 - "Download Pipeline"
Cohesion: 0.31
Nodes (9): dl(), download.py — host-aware, two-mode download CLI, download_outputs(), download_state(), main(), output_variants(), plan_downloads(), Ordered list of URLs to try when downloading one output.      ImageKit URLs try (+1 more)

### Community 6 - "Docs & README"
Cohesion: 0.25
Nodes (8): Architecture Decision Record (ADR), Keep a Changelog Format, README Structure Template, Technical Writer Agent, BCI Flora Skills, Cost Gate (README), flora-batch Skill, Flora MCP Connector

### Community 7 - "Upload & Hard-Won Rules"
Cohesion: 0.38
Nodes (7): floralib.build_curl_upload_args, floralib.match_reservations, 100 KB execute Output Cap, Hard-Won Rules, Idempotency Keys, Upload Backend Detection (ImageKit vs GCS), upload.py

### Community 8 - "QA Report Rendering"
Cohesion: 0.50
Nodes (5): floralib.qa_overall_flag, qa_report.py (planned CLI), floralib.render_qa_report_md, floralib.validate_qa_results, qa_report.py

## Knowledge Gaps
- **16 isolated node(s):** `contact_sheet.py — CLI wrapper for review gallery`, `conftest.py — puts scripts/ on sys.path for tests`, `test_floralib.py — unit tests for floralib functions`, `ruff (pyflakes-only lint, select=["F"])`, `flora` (+11 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **1 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `floralib.py (shared pure, network-free helper module)` connect `Dev Workflow & Conventions` to `Core floralib & Compose CLI`, `Download Pipeline`?**
  _High betweenness centrality (0.416) - this node is a cross-community bridge._
- **Why does `Cost Gate (MANDATORY)` connect `Dev Workflow & Conventions` to `Garment QA Feature & CI`, `Docs & README`?**
  _High betweenness centrality (0.390) - this node is a cross-community bridge._
- **Are the 3 inferred relationships involving `Cost Gate (MANDATORY)` (e.g. with `floralib.is_output_artifact` and `Cost Gate (README)`) actually correct?**
  _`Cost Gate (MANDATORY)` has 3 INFERRED edges - model-reasoned connections that need verification._
- **What connects `contact_sheet.py — CLI wrapper for review gallery`, `conftest.py — puts scripts/ on sys.path for tests`, `test_floralib.py — unit tests for floralib functions` to the rest of the system?**
  _42 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `floralib Test Suite` be split into smaller, more focused modules?**
  _Cohesion score 0.047619047619047616 - nodes in this community are weakly interconnected._
- **Should `Core floralib & Compose CLI` be split into smaller, more focused modules?**
  _Cohesion score 0.07823613086770982 - nodes in this community are weakly interconnected._
- **Should `Garment QA Feature & CI` be split into smaller, more focused modules?**
  _Cohesion score 0.09462365591397849 - nodes in this community are weakly interconnected._