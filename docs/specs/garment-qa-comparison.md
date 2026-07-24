# Garment QA Comparison — Spec

**Status:** planned, not built. Extends `flora-batch` after the existing contact-sheet review step.

Flora sometimes renders a garment's color or construction wrong, and nothing today checks the output against the input photo before it ships.

---

## Problem

After a `flora-batch` run finishes and the user reviews the auto-generated contact sheet (`skills/flora-batch/scripts/contact_sheet.py`), there's no automated check that Flora rendered the garment faithfully. Two failure modes matter:

1. **Color drift** — the garment's rendered color doesn't match the input reference photo (navy input rendered as royal blue).
2. **Construction drift** — Flora hallucinates, omits, or alters garment details (silhouette, buttons, zippers, pockets, collar, hems, logos, text, prints, stitching) relative to the input.

BCI's photo pipeline feeds real product listings. An inaccurate garment render is a real-world defect, not an aesthetic nit.

## Goals

- Let the user flag color and construction drift on the specific outputs they picked from the contact sheet, without re-running Flora.
- Produce a machine-readable and human-readable report the user can act on.
- Keep the check chat-driven, matching how the rest of `flora-batch` already works — no new UI.

## Non-goals (v1)

- No new persistent app UI or contact-sheet multi-select widget (see Open Questions).
- No deterministic/pixel-level colorimetry — this is a Claude-vision qualitative check, not a calibrated color tool.
- No new ML model, library, or MCP dependency.
- Compose (multi-input) technique support is not committed for v1 — see Open Questions.

---

## Design

### Trigger

Chat-driven, not a new UI. After the user reviews the contact sheet and tells Claude (in the Claude Code conversation) which output filenames they liked, Claude runs QA on just that selected subset — not the whole batch. This matches how the rest of `flora-batch` is already orchestrated: no persistent app, the chat is the interface.

### Input resolution

A new script, `skills/flora-batch/scripts/qa_resolve.py`, backed by new pure functions in `floralib.py` — same style as the rest of that module: no network, no image decoding, fully unit-testable.

| Function | Pipeline | What it does |
|---|---|---|
| `resolve_qa_pairs(state, selected_outputs)` | Per-image | Maps each `<stem>_MCP_N.png` back to its input file via the existing `batch_state.json` record (`rel`/`stem`/`files`). This mapping already exists in state — it's a lookup, not new tracking. |
| `resolve_qa_pairs_compose(compose_state, outputs_json, selected_output_ids)` | Compose (multi-input) | Maps each `output_id` (e.g. `full-1`, `top-crop-1`, `top-detail-1`) back to the correct **role** input file — `top-crop-*` / `top-detail-*` → the `top` role's file; `full-*` → all roles. |

**Known v1 limitation (compose only):** there's no reliable universal rule for `output_id` → role — naming varies per technique. See Open Question 1 for the two ways to handle this.

CLI:

```bash
python3 scripts/qa_resolve.py --state batch_state.json --selected out1.png,out2.png
```

writes `qa_manifest.json` — an array of:

```json
{"output": "<path>", "input": "<path>"}
```

or, for compose:

```json
{"output": "<path>", "inputs": {"top": "<path>", "bottom": "<path>"}}
```

### The comparison itself

This is a **Claude-vision judgment step, not a new ML model or new dependency.** Once `qa_manifest.json` exists, the orchestrating Claude agent reads each output/input pair directly (multimodal read, no OCR, no pixel library) and judges it against the rubric below.

**Color rubric**

| Check | Detail |
|---|---|
| Hue family | Compare hue *family* (red vs. orange vs. pink) — Claude's vision isn't calibrated for exact colorimetry, don't claim pixel-level precision. |
| Perceptible shift | Flag any shift big enough a human would call it "a different color" (navy → bright blue, black → dark grey). |
| Multi-color coverage | For multi-color garments/prints, check all major input colors are present in the output, not just the dominant one. |
| Verdict | `match` / `minor_shift` / `mismatch` |

**Construction rubric**

| Check | Detail |
|---|---|
| Garment type and fit | Same silhouette/cut (crew vs. v-neck, long vs. short sleeve, etc.). |
| Distinguishing features | Buttons, zippers, pockets, collar type, hems, drawstrings, logos/graphics, text, embroidery — present and correct. |
| Pattern/texture | Stripes, plaids, prints reproduced and recognizable. Position/orientation may shift naturally with model pose; the pattern itself should not change. |
| Hallucinations vs. omissions | Flag separately: features **added** in the output that weren't in the input, vs. features **missing** from the output that were in the input. Different failure modes, worth distinguishing in the report. |
| Verdict | `match` / `minor_deviation` / `mismatch` |

### Output artifacts

- `qa_report.json` next to the batch outputs — array of:
  ```json
  {
    "output": "...",
    "input": "...",
    "color": {"verdict": "...", "notes": "..."},
    "construction": {"verdict": "...", "notes": "..."},
    "overall_flag": true
  }
  ```
- `qa_report.md` — human-readable table version of the same data.
- A concise chat summary Claude posts directly to the user — only flagged/mismatched items, called out by name, not a full dump of every pair. This is the "show the results to the end user" requirement; keep it short and actionable, matching how `SKILL.md`'s auto-review step already summarizes results.

### Cost

**Zero additional Flora spend.** This step makes no MCP `run`/`technique` calls — only local file reads plus Claude's own vision. Stated up front because this repo is obsessive about the cost gate (see `SKILL.md`'s "Cost gate (MANDATORY)" section) and a reader will immediately ask whether this spends credits.

### Testing

- `resolve_qa_pairs` and `resolve_qa_pairs_compose` get real `pytest` unit tests, same as the rest of `floralib.py` — pure functions, no network, no image decoding, fully deterministic.
- The visual-judgment step itself is inherently non-deterministic and **can't be meaningfully unit-tested** — say this plainly rather than pretending there's a test for it. Its calibration should instead be validated by spot-checking a handful of known-good and known-bad pairs during implementation.

---

## Open Questions

1. **Per-image vs. compose-technique QA scope for v1.** No reliable universal rule maps `output_id` → role for compose techniques (naming varies per technique). Options: (a) require a `--map` override the user supplies, similar to how `compose.py` already handles ambiguous file→role mapping, or (b) scope compose-technique QA out of v1 entirely and ship per-image QA first, compose QA as a fast-follow. **Recommendation: (b)** — but this is a decision for the reviewer, not foreclosed here.
2. Does Flora already offer a native "compare/QA" technique worth checking via `search_docs` / `client.techniques.list()` before building a bespoke one?
3. Should a future v2 add deterministic colorimetric checks (e.g. via Pillow, average/dominant color extraction from a garment crop) as a supplement to Claude's qualitative color judgment? Explicitly out of scope for v1 — it would add a new dependency and garment-segmentation complexity.
4. Should the contact sheet (`contact_sheet.py`) eventually grow a real multi-select UI (checkboxes + "export selected" button) instead of the user naming filenames in chat? Explicitly out of scope for v1.

---

## Next step

Per `CLAUDE.md`'s dev workflow: once this spec is accepted, the next step is a dated implementation plan under `docs/superpowers/plans/`, executed task-by-task with `superpowers:subagent-driven-development` (TDD for the `floralib.py` resolution functions). That plan isn't written here — this document is the design input for it.
