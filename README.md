# BCI Flora Skills

A small library of [Claude Code](https://docs.claude.com/en/docs/claude-code) skills for the BCI AI photo pipeline, built on **Flora** (via its MCP connector).

Currently ships one skill:

- **`flora-batch`** — run a single Flora technique (garment-removal, upscale, pose-generation, PDP, …) across an **entire folder of images** and save the outputs locally. Resumable, with a mandatory **cost gate** before any spend.

> **Internal use only.** Delivered by Pierrepont Advisors for the BCI team. Not for external distribution.

---

## Prerequisites

Each teammate needs, on their own machine:

| Requirement | Notes |
|---|---|
| **Claude Code** | The skill uses your local shell to move image bytes to/from Flora. It does **not** run on claude.ai web. |
| **Flora MCP connected** | This repo ships a project-scoped `.mcp.json`, so Claude Code detects the `flora` server automatically when you open it here — approve it, then authenticate (OAuth runs on first tool call). No account/workspace IDs to configure — the skill finds them itself. Full install docs: [developer.flora.ai/mcp/install/claude-code](https://developer.flora.ai/mcp/install/claude-code/). |
| **Flora credits** | Each run bills the technique's `run_cost` — cost = **(number of runs) × run_cost** (per-image techniques: once per image; compose/multi-input techniques: once per look). |
| **`python3` + `curl`** | Standard on macOS — nothing to install. |

---

## Install (drop-in)

```bash
# 1. Clone
git clone https://github.com/PierrepontAdvisors/bci-flora-skills.git
cd bci-flora-skills

# 2. Copy the skill into your Claude Code skills folder
cp -R skills/flora-batch ~/.claude/skills/

# 3. Verify
ls ~/.claude/skills/flora-batch/SKILL.md   # should print the path
```

Skills are auto-discovered — start (or restart) a Claude Code session and `flora-batch` is available.

### Connecting Flora MCP

This repo's `.mcp.json` (project scope) means Claude Code offers to connect `flora` automatically the first time you open the repo — just approve it. If you're using the skill outside this repo, or want it available in every project, add it yourself:

```bash
# project scope (this repo — already configured via .mcp.json)
claude mcp add --transport http --scope project flora https://agents.flora.ai/mcp

# user scope (every project on your machine)
claude mcp add --transport http --scope user flora https://agents.flora.ai/mcp
```

Authentication is OAuth and runs automatically the first time a Flora tool is called — no API key to paste in. Verify with `/mcp` inside a Claude Code session; if it shows "pending," ask Claude to call a Flora tool (e.g. "list my Flora techniques") to trigger the OAuth flow. Full reference: [developer.flora.ai/mcp/install/claude-code](https://developer.flora.ai/mcp/install/claude-code/).

---

## Quickstart

In a Claude Code session, ask in plain language:

> **"Run `<technique>` on `<this folder of images>`."**

(`<technique>` can be a Flora technique URL or slug.) The skill will:

1. Scan the folder + retrieve the technique, then show you **(number of runs) × $run_cost = $total** — once per image for a per-image technique, once per look for a compose (multi-input) technique — and **wait for your approval** before spending anything.
2. Upload → run → download, checkpointing to a `batch_state.json` after every step.
3. Save outputs next to your inputs (or in a sibling / mirrored folder — your choice), named `<original>_MCP_1.png`, `_2.png`.

**Resumable:** if a run is interrupted (expired URL, timeout, credits run out), just ask it to resume — it re-reads the checkpoint and only does what's left. Nothing is double-charged.

---

## Updating

```bash
cd bci-flora-skills
git pull
cp -R skills/flora-batch ~/.claude/skills/   # re-copy to pick up fixes
```

Flora occasionally changes its backend (e.g. the upload host), which can break older copies of the skill. When that happens a fix lands here — a `git pull` + re-copy is all you need.

---

## Troubleshooting

| Symptom | What's happening / fix |
|---|---|
| **Claude doesn't see the skill** | Confirm `~/.claude/skills/flora-batch/SKILL.md` exists, then start a fresh Claude Code session. |
| **"Flora MCP not connected"** | Run `/mcp` to check status. If `flora` is missing, run `claude mcp add --transport http --scope project flora https://agents.flora.ai/mcp` (or `user` scope). If it's "pending," ask Claude to call a Flora tool to trigger the OAuth flow, then retry. |
| **`insufficient_credits` / `402`** | Top up Flora credits. Blocked images stay pending; resume the batch after topping up. |
| **Upload URL expired (`400`/`403`) mid-run** | Expected on large batches — signed URLs live ~15 min. The skill re-reserves and re-uploads automatically; just let it resume. |
| **`502` / `GENERATION_PROVIDER_TIMEOUT`** | Transient Flora load. Runs use idempotency keys, so resuming retries safely with no double-charge. |
| **Outputs look off** | The skill's auto-review builds an original → output contact sheet; check it and re-run just the affected images. |

---

## What's in here

```
bci-flora-skills/
├── README.md
└── skills/
    └── flora-batch/
        ├── SKILL.md            # the skill definition Claude reads
        └── scripts/
            ├── floralib.py      # shared helpers: downloads, cost, role-mapping, GCS lint, compose state
            ├── init.py          # per-image: enumerate + build output tree + write state
            ├── upload.py        # reservations + state -> GCS/ImageKit POST per image
            ├── download.py      # per-image (--state) or compose (--outputs/--out-dir); host-aware
            ├── compose.py       # multi-input: map files -> roles, correct cost gate
            ├── contact_sheet.py # portable review gallery, no headless Chrome
            ├── review.py        # legacy headless-Chrome comparison HTML
            └── tests/           # pytest unit tests
```

Everything is **portable by design** — no hardcoded accounts, workspace IDs, or file paths. Each teammate uses their own Flora connector and credits.

---

## Roadmap

- **Garment QA comparison** *(planned, not built)* — after you review the contact sheet and pick outputs, Claude will check the selected outputs against their input photos for color drift and construction drift (silhouette, buttons, zippers, pockets, and other details), and flag anything that looks off. Uses Claude's own vision, so it spends no Flora credits. See the design in `docs/specs/garment-qa-comparison.md`.

---

## Changelog

- 2026-07-22: hardened for compose (multi-input) techniques + workspace billing; corrected the 100 KB `execute` rule; host-aware downloads; portable contact-sheet review. See `docs/superpowers/plans/2026-07-22-flora-batch-hardening-and-multi-input.md`.

---

## Support

Questions or breakage: **Nicholas Swerdlowe — nswerdlowe@pierrepontadvisors.com**
