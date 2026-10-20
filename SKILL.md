---
name: hatch-pet
description: Create, import, decompose, review, and package Codex pets or reusable raster assets. Turn existing artwork into source-bound editable components, combine character state packs by anatomy, compile profiles and event recipes, or make process illustrations, product variants, printable frames, pictograms, research stimuli, cursors and craft grids. Uses installed imagegen for production generation and a local, resumable validation/export pipeline. Does not install, publish, or certify external integrations implicitly.
---

# Hatch Pet

Use `profiles/codex-v1.json` for a Codex pet. Its state order, counts, durations, 192×208 cells, 8 columns, transparency rules and package contract are fixed. Existing `examples/*.json` remain supported. For another purpose, use a validated profile or one of the ten [purpose-specific presets](references/additional-uses.md).

## Choose the source and contract

- **Generate artwork:** read the installed `$imagegen` skill and use it for every production model call. Hatch-pet has no alternate generation backend. Follow its attachment, transparency, output-display and save-path rules. Only an unreferenced base may be text-only. Every image in a claimed handoff must actually be attached, including original references, canonical identity and the layout guide. Preserve explicit constraints on every retry and repair.
- **Import existing artwork:** use `import-source` with an explicit origin and ordered image, strip or frame source. Imports never become imagegen output. Validate and visually review them. See [sources and identity](references/sources-and-identity.md) for the complete import-and-review recipe, reference roles and structured identity specification.
- **Decompose one existing character:** read [character decomposition](references/character-decomposition.md). Use `decompose` for immutable image import, foreground analysis and exact visible-pixel extraction; supply semantic annotations or correct the local review desk. Automatic geometry does not establish component meaning. Preserve unassigned regions, anatomical uncertainty and review status. Enable assisted reconstruction explicitly and retain original extracted pixels; never label inferred artwork as source evidence. Export this format separately from the fixed Codex pet package, and use `decompose-prepare` to carry identity and selected component references into an ordinary generation run.
- **Develop/test:** use labeled synthetic fixtures. A fixture receipt tests the gate; it is not production artwork acceptance. Never relabel fixtures as user artwork or model output.

Run `python scripts/hatch.py doctor` before unfamiliar workflows; `capabilities` lists bounded interfaces. Use [workflow](references/workflow.md) for lifecycle commands. Unsupported formats, policies and excessive allocations must fail clearly.

## Select expanded character states

Read [character states](references/character-states.md) for catalog discovery, packs, archetypes, recipes and complete examples. Use `python scripts/hatch.py states list`, `states search curious`, `states show running`, `states packs` and `states archetypes` to inspect definitions and generation requirements. The catalog's `running` remains task processing; directional running uses separate identifiers.

Compile a selected subset before preparing artwork:

```bash
python scripts/hatch.py states compile --selection examples/state-selections/expressive-cat.json --output output/cat-profile.json
python scripts/hatch.py prepare --run-dir output/cat-run --profile output/cat-profile.json --pet-name Miso --reference art/cat.png
```

Read the compilation estimates, substitutions and omissions. Confirm the chosen archetype/capabilities against the actual reference; presets are assumptions. Use explicit `--anatomy-policy substitute` or `filter` only when that behavior is intended. Reconcile required props with `identity.approved_props`. The adjacent `.selection.json` is validated, copied into the run, and retained with review/export evidence. Keep it with the profile. Select new states in a new run; `revise-profile` retains original selection provenance as history.

Treat every catalog entry as a definition, not generated artwork. `states preview` reports available assets and their origin/review status; an ungenerated state has no animation preview. Never build or generate the Complete Character Studio as one atlas. Use bounded subsets, inspect state/frame/memory/call estimates, and retain the existing attempt/concurrency/budget controls. Use `--reduced-motion` at compilation for one expressive still per selected state, or the ordinary per-state still alternatives in browser playback. Expanded profiles are custom exports; they do not extend Codex's fixed nine rows.

## Select and preserve visual style

Use `python scripts/hatch.py styles` to enumerate the versioned visual library, `styles --search WORD` or `--category ID` to narrow it, and `style --style-preset ID` to inspect the full artistic direction and limitations. Add `--json` for agent-readable metadata. Read [the style catalog](references/style-catalog.md) for every ID, category quick starts, composition rules and contributor instructions; do not load the entire catalog into a generation prompt.

Select a stable ID or declared alias with the existing `--style-preset`. Add explicit refinements with `--style-notes` and zero to four separate themes with repeated `--style-modifier`; enumerate those with `style-modifiers`. Keep themes, treatments and aliases separate from the technique count. Preserve the original nine presets and existing profile semantics.

Resolve the style once during preparation. Keep `pet_request.json.resolved_style`, its version/hash and exact contract unchanged across canonical-base generation, rows, retries, repair, resume and archive restoration. Every profile receives the complete selected instructions. Explicit requirements/avoidances, approved references/identity and the profile contract take precedence. For an imported base, preserve its approved existing rendering; do not restyle it or label it generated because a preset was requested. For reference-guided `auto`, lock the exact rendering through canonical visual review.

Read compatibility warnings before generation. Adapt glass, light effects, fibers, fine marks and decorative techniques into a readable isolated silhouette. Resolve unsupported chroma combinations using alpha or a deliberate supported adaptation before proceeding. New runs use the style's recommended extraction fallback; explicit profile filters win. Use nearest for crisp grids and filtered edges for continuous media, preserving fixed geometry. Review actual-size consistency and edge quality; record notes for every current warning. Automated catalog tests do not establish subjective imagegen artwork quality.

## Execute and preserve evidence

1. **Prepare** a new run with profile, concept, style, user constraints, structured identity and required references. Keep inferred brand guidance separate, attributed and subordinate to explicit requirements. Report unresolved conflicts. Structured identity helps inspection; it does not prove visual consistency.
2. **Acquire the base** through a claimed imagegen handoff or explicit import. Inspect canonical identity, transparency and color analysis, then record `base-review` before states.
3. **Acquire each state.** Claim only ready jobs. Keep the existing claim/token until its output is ingested or failure is recorded. Optional mirroring is not a generation dependency. Derive only where the profile permits it and explicit approval covers asymmetries, markings, props and direction; never when identity forbids mirroring.
4. **Extract and validate.** Preserve the conservative default. Use exact, hash-bound annotations for legitimate disconnected components or non-strip layouts; never disable validation globally. Keep one shared viewport and scale, including intended jump displacement. Choose validated resampling for the artwork. See [extraction and review](references/extraction-and-review.md) for diagnostics and calibration.
5. **Review actual artifacts.** Build `review-ui`, inspect references, sources, extracted frames and actual-size timed playback on multiple backgrounds. Record identity, action, direction, loop, extraction and reduced-motion verdicts plus warning-specific notes. Submit the exact bound receipt. A change to covered artifacts requires fresh review; numerical QA cannot supply a semantic verdict.
6. **Export/package.** An evaluation export may be unreviewed and must say so. Packaging requires current deterministic validation and passing visual review. Report source origin, fixture status, review status and exact output locations separately from integration status.

## Recovery and operational scope

`status` and `resume` reconcile existing claims and explain stale inputs; they never start duplicate model calls. Configure attempt, concurrency and call limits; optional budgets use explicit user estimates, not invented prices. Deterministic calibration changes reuse generation. Use `revise-profile` for controlled playback/extraction/export revisions. See [portability and operations](references/portability-and-operations.md) for migrations, verified archives and restoration.

Installation is a separate, explicitly requested action with verified backups and rollback. Package creation, exported adapters, local browser exercises, installation and live integration are different outcomes. Do not claim an external consumer was exercised without evidence. No live installation, publishing or deployment is implied. Never shut down or terminate WSL.

When authorized to delegate, one worker may own one existing generation claim or visual review; keep a single manifest owner. Handoffs retain token, prompt, image roles/hashes, identity and failure history. Workers follow imagegen's required output behavior and return the selected original source plus a QA note. Without delegation, execute sequentially.

## Reference map

- [Workflow](references/workflow.md): preparation, acquisition, validation, review and delivery commands.
- [Style catalog](references/style-catalog.md): complete IDs, aliases, thematic modifiers, materials, compatibility, frozen specifications and extension schema.
- [Sources and identity](references/sources-and-identity.md): schemas and complete import recipe.
- [Extraction and review](references/extraction-and-review.md): annotations, filters, calibration and evidence UI.
- [Character decomposition](references/character-decomposition.md): reverse image-to-layers workflow, semantic masks, correction, reconstruction, portable packages and forward reuse; includes fixture and real-image acceptance requirements.
- [Portability and operations](references/portability-and-operations.md): limits, stale work, schema migration, archives and restore.
- [Playback and extensions](references/playback-and-extensions.md): state-machine and exporter/consumer contracts.
- [Character states](references/character-states.md): versioned catalog, composable packs, anatomy rules, compilation, selective generation and migration.
- [Character state validation](references/character-state-validation.md): acceptance mapping, tested workflows and capability boundaries.
- [Ten uses](references/additional-uses.md): inputs, semantics, constraints, commands and external requirements.
- [Profiles and exports](references/profiles-and-exports.md), [QA rubric](references/qa-rubric.md), [Codex contract](references/codex-pet-contract.md), [default animation table](references/animation-rows.md).
- [Traceability](references/traceability.md): L01–L10 / I01–I10 / U01–U10 and validation evidence.

Cleanup affects only exact run-owned files. Preview it first. Keep repair archives, original inputs, external imagegen outputs, failure history and unrelated files. Removing files cannot remove image payloads already embedded in a conversation.
