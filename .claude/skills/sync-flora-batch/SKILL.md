---
name: sync-flora-batch
description: Copy the local skills/flora-batch/ folder from this repo into ~/.claude/skills/flora-batch/ so edits made here can be tested live. Use when the user says "sync the skill", "deploy flora-batch locally", "update my local flora-batch skill", or after editing anything under skills/flora-batch/ and wanting to try it out.
disable-model-invocation: true
---

# Sync flora-batch to local Claude Code

Deployment for this repo is copy-based, not symlinked: `~/.claude/skills/flora-batch/` is an independent copy of `skills/flora-batch/`. Editing files in this repo does **not** update a live installed skill until it's re-copied.

## Steps

1. Confirm `skills/flora-batch/SKILL.md` exists in the repo (fail loudly if not — don't silently no-op).
2. Run:
   ```bash
   mkdir -p ~/.claude/skills
   cp -R skills/flora-batch ~/.claude/skills/
   ```
3. Verify the copy landed:
   ```bash
   ls ~/.claude/skills/flora-batch/SKILL.md
   ```
4. Tell the user the skill is synced and that it takes effect on their **next** Claude Code session (skills are discovered at session start, not hot-reloaded).

Do not commit anything to git as part of this — it only touches files outside the repo, under `~/.claude/skills/`.
