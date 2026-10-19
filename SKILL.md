---
name: hatch-pet
description: Create, repair, review, and package Codex pets or profile-driven animated character assets from concepts, brand cues, or references. Uses the installed imagegen skill for production art and a resumable Python pipeline for extraction, validation, previews, exports, and optional local installation.
---

# Hatch Pet

Use the default Codex profile for a Codex pet. For another application, use a validated custom profile and describe the result as a local asset export; example configurations do not establish a production integration.

Read [workflow.md](references/workflow.md) for commands and lifecycle details, [qa-rubric.md](references/qa-rubric.md) before visual acceptance, and [profiles-and-exports.md](references/profiles-and-exports.md) when changing the animation contract. The versioned default is `profiles/codex-v1.json`; the structural schema is `profiles/profile.schema.json`. The [animation table](references/animation-rows.md) is generated from the default.

## Non-negotiable production gates

- Production artwork must use the installed `$imagegen` skill. Read its installed `SKILL.md` before generation and follow its tool, permission, attachment, and final-output rules. Hatch-pet does not provide another generation backend.
- Only the base may be text-only. Attach every input image listed in the claimed row job, including the canonical base and layout guide. Original references and any additional identity inputs remain required when listed. A path mentioned in text is not an attached image.
- Preserve explicit user requirements, avoidances, style choices, and approved references through base, row, retry, and repair prompts. Keep researched brand guidance separate from user instructions, with source URLs and uncertainty. Report conflicts rather than silently dropping a requirement.
- Every state needs its own generated animation. In the default profile, only explicitly approved framewise mirroring of `running-right` into `running-left` may replace generation. Check asymmetric markings, prop side, readable marks, lighting, and direction first; preserve temporal order.
- Fixtures are for deterministic tests only. Label them as fixtures, and never represent their validation or visual-review receipts as production artwork acceptance.
- Deterministic validation and a persisted, hash-bound visual review must pass before packaging or installation. Measurements cannot establish identity, facing direction, action meaning, or artistic quality.
- Installation is a separate, explicitly requested action. Package creation never implies permission to overwrite an installed pet or publish anything.

## Working method

1. **Prepare.** Infer an omitted friendly name or description when reasonable. Record the concept, style, original references, constraints, and selected profile through `scripts/hatch.py prepare`. Use `status` for durable progress; do not manually mark manifest jobs complete.
2. **Discover brand cues when needed.** For a bare brand/company/product request, research a few relevant official sources. Save a short brief covering palette, personality, motifs, avoidances, sources, and inferred guidance. Pass discovery's `avoid` values as well as its other handoff fields into preparation. Skip unnecessary research when the user already supplied a concrete character.
3. **Generate the canonical base.** Claim the base job, read its exact handoff, generate via `$imagegen`, inspect the selected image, and ingest it. Inspect the base color analysis, then record `base-review` before rows. The initial text-only chroma key is provisional; a fallback selection is not evidence that the key is safe. Prefer preserved alpha where available. Use `configure` to change the key or extraction policy; this regenerates prompts and invalidates affected outputs. `pet_request.json` stays immutable during calibration.
4. **Generate rows.** Claim only ready jobs. Generate and inspect one strip per job using every listed identity reference and guide. Start with idle and directional movement when useful for early style checks. A failed call is recorded with `fail`; retry only within the recorded attempt limit. Reuse the same identity references and structured constraints.
5. **Extract and validate.** Use `validate` to extract changed source strips, check provenance and frame indices, compose the atlas, measure consistency, and render QA assets. Preserve intended motion with the profile's coordinate/scale policy. `slot` preserves the source viewport; `center` and `baseline` deliberately align individual poses and are unsuitable for preserving jumps. Shared calibration uses `shared_scale` in `extraction-settings.json`. Ambiguous segmentation is a source/layout problem, not permission to guess which poses belong in the animation.
6. **Review.** Inspect the canonical identity reference, contact sheet, and actual timed playback. Read numerical warnings in context. Record one verdict and repair note per state using `review`. If any state fails, repair the smallest affected row and repeat validation and review. Changed assets invalidate prior approval.
7. **Deliver.** Export the accepted assets, create a verified local package, and report the actual receipt state and paths. `export` also supports validated evaluation assets before acceptance and labels their review state; it never installs them. Install only when requested, with a recoverable previous package. Keep the compact repair archive by default; preview cleanup before applying it.

Keep progress concise and factual: preparation, base, rows, deterministic checks, review, and package are different milestones. Report pending, failed, or unverified stages honestly. Do not claim the app, OBS, a game engine, or a device was exercised unless it actually was.

## Delegation and image payloads

Where delegation is authorized and available, one worker may own one claimed generation job or the final visual review. Keep the controller as the sole manifest owner, and do not launch another worker for a running claim. Without delegation, execute the same workflow sequentially. No additional permission ritual is implied by this skill.

A generation handoff contains the claimed job ID/token, prompt path, all image paths and roles, output selection instructions, and current constraints. Workers load and follow the installed imagegen skill; its required image/tool/final output behavior takes precedence over a preferred concise hatch-pet handoff. After satisfying that behavior, return the selected source path and a short QA note. Do not ask workers to suppress imagegen-required output. Workers do not mutate manifests, install, publish, or delete inputs.

The reviewer must see enough visual evidence to assess every state, including actual timing and intended vertical motion. Do not substitute textual descriptions or aggregate metrics for viewing the art. Delegating review does not weaken the acceptance criteria.

Image payloads already embedded in tool results or prior rollouts cannot be removed by deleting generated files. Cleanup only affects files explicitly owned by the run. Never delete external generation outputs, user inputs, shared assets, or installed packages as an incidental cleanup step.

## Default Codex semantics

The default remains nine states, 192×208 cells, eight columns, and a 1536×1872 atlas with transparent unused cells. Counts and exact durations come from the versioned profile.

- `idle`: quiet breathing/blinking; the static alternative must read well. Low amplitude is valid, complete visual stasis needs review.
- `running-right` / `running-left`: directional locomotion with the correct facing and alternating gait.
- `waving`: limb gesture; no decorative wave marks.
- `jumping`: anticipation, lift, peak, descent, settle; preserve vertical displacement.
- `failed`: readable deflation or sadness. Any effects must satisfy the profile's detail policy.
- `waiting`: expectant, needs-input behavior distinct from idle and review.
- `running`: active task work/processing; this is not foot-running.
- `review`: focused inspection, with no newly invented props.

Keep identity, materials, palette, proportions, and approved props consistent. For the default profile, avoid detached decorations, shadows, scenery, labels, guide marks, dust, glows, and motion trails. Other profiles may allow detached details deliberately; an extraction policy must preserve rather than accidentally discard them.

## Recovery and retention

Use `resume` for the same inputs and run identity. A running generation claim is not an invitation to generate again: reconcile its selected output or explicitly record failure first. Input replacement is deliberate and invalidates affected generation, extraction, reviews, and package receipts. Preserve failure history.

The default `repair` retention mode preserves the canonical reference, request/profile, constraints, source strips needed for row repair, hashes, prompts, provenance, and review receipts. `minimal-delivery` explicitly discards run-owned row-strip copies and omits them from the archive; those rows need new generation before extraction can resume. Original external inputs and imagegen outputs are never cleanup targets. See the cleanup preview and [workflow](references/workflow.md) before discarding anything.
