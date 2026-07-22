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
| **Flora MCP connected** | Connect your own Flora account via Claude's Connectors (or `claude mcp add`). The skill finds it automatically — no IDs to configure. |
| **Flora credits** | Each run bills the technique's `run_cost`; N images ≈ N × cost. |
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

---

## Quickstart

In a Claude Code session, ask in plain language:

> **"Run `<technique>` on `<this folder of images>`."**

(`<technique>` can be a Flora technique URL or slug.) The skill will:

1. Scan the folder + retrieve the technique, then show you **N images × $run_cost = $total** and **wait for your approval** before spending anything.
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
| **"Flora MCP not connected"** | Connect your Flora account in Claude's Connectors (or `claude mcp add`) and retry. |
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
        └── scripts/            # local byte-movers (init / upload / download / review)
```

Everything is **portable by design** — no hardcoded accounts, workspace IDs, or file paths. Each teammate uses their own Flora connector and credits.

---

## Support

Questions or breakage: **Nicholas Swerdlowe — nswerdlowe@pierrepontadvisors.com**
