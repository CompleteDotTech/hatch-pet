# Continuity foundation: current behavior and compatibility baseline

This assessment completes the audit in [#112](https://github.com/CompleteTech-Skills/hatch-pet/issues/112),
under [P0 #108](https://github.com/CompleteTech-Skills/hatch-pet/issues/108) and
[mission #107](https://github.com/CompleteTech-Skills/hatch-pet/issues/107).
It establishes an implementation boundary; it does not implement persistent 3D
continuity or approve production artwork.

## Audited revision and coordination

The starting default branch was `main` at
`7b966a639bcaf23bd3a0d037f46f29e2edfcc273` on 2026-10-22. The isolated branch is
`agent/issue-112-continuity-baseline-f637`. The baseline ran against a separate,
unchanged checkout of that exact commit. `README.md`, `SKILL.md`, both workflow
definitions, production/rig contracts, operations, rendering, source/identity,
delivery and acceptance references were inspected. No `AGENTS.md` or
`CONTRIBUTING.md` exists in the audited tree.

Initial GitHub inventory contained 180 open issues, no open PRs or drafts, no
labels or milestones on the open issues, and 168 child issues. The two other
remote branches, `feat/3d-character-rigging` and `fix/public-production-delivery`,
were already merged through PRs #9 and #8. Their code is part of this baseline.
Both latest main workflows passed: [rigging/compatibility, nine jobs](https://github.com/CompleteTech-Skills/hatch-pet/actions/runs/39421253425)
and [public delivery, three operating systems](https://github.com/CompleteTech-Skills/hatch-pet/actions/runs/39421253433).
Those historical CI results are separate from the local executions below.

The [ownership claim](https://github.com/CompleteTech-Skills/hatch-pet/issues/112#issuecomment-6348213225)
covers this audit only. At the subsequent coordination check, other sessions
were claiming Director audit #23 and physics audit #166. Their changes were
not present in the audited base. Future contributors must refresh GitHub before
claiming #113–#127; this document is a dated inventory, not a lock on that work.

## Existing behavior, observed rather than inferred

The runnable [baseline probe](../tests/continuity_baseline_probe.py) builds only
temporary synthetic projects through the existing fixture builder and reloads
changed manifests through the real project loader. Its retained
[observations](../tests/results/continuity-baseline-probes.json) demonstrate:

| Observation | Actual v1 result | Consequence for continuity work |
| --- | --- | --- |
| A 12-frame root track moves 12 pixels | Position at displayed frame 11 is `[111, 140]`; terminal frame 12 is `[112, 140]` | Preserve terminal-N evaluation; do not compare N−1 with the next shot. |
| A prop handoff occurs at frame 6 | Owner is `a` at 5 and `b` at 6 and 12 | Existing shot-local ownership is inclusive of events at the queried frame. |
| A linked incoming shot moves a character one pixel | Loading fails with a continuity position mismatch | Explicit links already enforce evaluated 2D position across scene files. |
| The same incoming reset has no continuity link | Loading succeeds | No persistent state is inherited or checked automatically. |
| Incoming ownership changes to a different character version | Loading fails with a prop ownership mismatch | Existing links compare declared asset/owner identity. |
| Two instances use the same character version and ownership changes between them | Loading succeeds | Owner comparison collapses instances to `character@version`; distinct repeated actors need an explicit identity fix. |
| Owner stays the same but its attachment changes | Loading succeeds | The continuity validator does not compare attachment/socket state or boundary contact geometry. |

These are observations at the pinned revision, not tests requiring future code
to preserve gaps. The probe's successful exit means it completed its measurements;
it does not mean every observed input was correctly admitted. It records no
review, performs no model call and never alters original pilot assets.

### Contract and evaluator authority

[`production_contracts.py`](../scripts/production_contracts.py) owns the closed
v1 project/cast/clip/scene/shot schemas (`schema_definitions`, `schemas`) and
`load_project`, `validate_cast`, `validate_clip`, `validate_shot`, `validate_scene`.
The loader checks actual files, hashes, image headers, resource budgets, unique
scene/shot IDs, versioned references and semantic relationships. Diagnostic
missing-leaf loading cannot waive unsafe paths, contradictory hashes, missing
manifests or invalid semantics. It calls `validate_continuity` and
`validate_transition_limits` before returning a usable bundle.

[`production_performance.py`](../scripts/production_performance.py) owns
`evaluate_track`, `evaluate_clip`, `evaluate_instance_performance`, `prop_owner`
and `validate_continuity`. Evaluation uses bounded integer frames and returns
copied values. Instance evaluation accumulates clip root displacement and shot
overrides. A terminal query at N is permitted, while a query beyond shot duration
is rejected. Once clips evaluate terminal root motion at N but hold their final
displayed component pose at N−1, subject to the declared completion policy.
That existing distinction must not become an accidental 3D pose contract.

Continuity links select `costume`, `scale`, `position` and/or `prop_ownership`.
They resolve shots project-wide, including different scene files. Characters
use exact version keys; repeated characters are paired by instance ID for
character checks. Position compares evaluated terminal N against incoming 0
with a 1e−6 pixel tolerance; scale compares shot cast scale with a 1e−9 tolerance.
Prop comparison currently uses prop-instance ID, prop version and owner character
version, which explains the repeated-actor limitation above. Validation raises
`ValueError`; it is not a versioned rule/diagnostic engine.

`validate_shot` already rejects inconsistent ownership history, unordered events,
bad attachments and unsynchronized interaction markers. Actual 2D anchor/contact
checks live in [`production_render.py`](../scripts/production_render.py).
Metadata alignment alone does not prove a convincing contact, and these checks
are not a 3D socket/skin evaluator.

## Reuse and extension map

| Authority and actual entry points | Existing behavior | Decision for #107 |
| --- | --- | --- |
| `hatch.py`, `asset_contracts.py`: native claims, receipts, `hash_object`; `production_workflow.bind_generation_run`, `claim_generation`, ingest/fail/repair | Original request/identity/coverage binding, locks, bounded attempts and project budgets; delegates existing Hatch tokens | **Reuse.** No second imagegen backend or competing acquisition ledger. |
| `production_workflow.import_component`, `adopt_generated_component` | Preserves original source/receipts, creates a new character version and content-addressed cast, validates before promotion, leaves new view review pending | **Reuse; adapt for 3D identities.** Do not silently rebind old `id@version` consumers. |
| `production_workflow._continuity_projection`, `shot_dependencies` | Hashes actual relevant source bytes, selected drawings/clips and both endpoints of all touching continuity links; outgoing projection uses N | **Reuse and extend through a versioned adapter.** Include exact state/evaluator references without changing old snapshot meaning. |
| `production_workflow.dependency_snapshot`, `impact_report` | Per-shot dependency maps, affected/reusable shot classification and suggested actions; no provider call or generation | **Extend.** These are dependency inventories, not temporal world-state snapshots or a transitive causal graph. |
| `production_workflow.review_template`, `record_review`, `review_status` | Exact evidence hashes, per-dimension dependency filtering, receipt chain, scoped staleness, separate human/assistant/synthetic decisions | **Reuse with compatible new scopes.** Preserve the review authority and history; do not create parallel approvals. |
| `production_workflow._render_artifacts`, `_has_final_visual_evidence` | Checks target/settings/timing, complete frame inventory and hashes; final visual review requires a rendered frame/layer | **Reuse.** Metadata, audio or a manifest alone cannot establish visual acceptance. |
| `production_workflow.archive_project`, `restore_project`, `migrate_project` | Bounded verified inventory, path/symlink safety, active-token rejection, staging/no-clobber publication, cache freshness, exact migration backup | **Reuse for new state payloads.** A continuity-specific repair transaction and revision precondition are still new work. |
| `rig_models.load_rig`, `rig_geometry.analyze_geometry`, `rig_animation.evaluate_animation`, `rig_skeleton.evaluate_fk`, `rig_skinning.evaluate_deformation` | Real source/mesh/skin/animation verification, geometric analysis, evaluated pose/deformation/root/IK/contact information | **Reuse through bounded adapters.** Unsupported channels and approximate anatomy remain explicit. |
| `rig_jobs.save_rig`, `rig_review.apply_review`, `rig_package` | Content-addressed revisions, retained prior manifests, exact rig/evidence binding and portable packages | **Adapt without replacing.** Preserve native rig lifecycle and identify which revision/evidence the continuity adapter consumes. |
| `rig_render.render_rig_preview`, `rig_blender`, `rig_http.RigServer`, `rig_operations.mutate` | Real triangle preview, trusted Blender worker and authenticated loopback rig operations | **Capability-gated reuse.** This is not the general scene/PBR renderer or professional scene editor. |

The workflow's `_dimension_dependencies` deliberately preserves unaffected
review dimensions. Unused drawings/characters do not invalidate an unrelated
shot; a camera-only change does not stale identity construction. `impact_report`
suggests repair work but neither executes it nor reports affected frame ranges.
Archive restore recalculates cached shot/scene freshness and preserves historical
review decisions. None of these facts implies persistent narrative state.

## Ownership with the other 3D missions

| Owner | Continuity should consume | Remaining integration boundary |
| --- | --- | --- |
| #10 — model assets | Exact asset/source revisions and observed geometry/material data | General generation/reconstruction is not continuity's responsibility. |
| #11 — rigs | Existing rig manifests, FK/deformation, sockets, clips and native review | Do not replace implemented rig math, binding or animation controllers. |
| #12 — scenes | Stable node/entity references, evaluated hierarchy and explicit world mappings | Closed pixel-space production v1 is not a general 3D scene graph. |
| #13 — animation | Exact-time requests into supported evaluators, pose/root/contact/phase evidence | Existing rig seconds need a documented rational-time adapter. |
| #14 — cameras | Evaluated view/projection, calibrated screen direction and framing | 2D pan/zoom is not cinematic projection or eyeline verification. |
| #15 — look development | Immutable material/texture/look and evaluated environment references | Legacy lighting declarations are planning metadata, not physical lighting. |
| #16 — rendering | Verified scene snapshots, actual frame hashes, backend/configuration identity | The rig preview cannot stand in for a completed scene-rendering integration. |
| #17 — editor | Validated commands/revisions and continuity diagnostics | Reuse the rig server where applicable; a general scene GUI is not available in this base. |
| #18 — Director | Admission, queries, typed repair proposals and scoped results | Planning must not bypass validation or infer approval from intent. |

The new continuity-owned responsibilities are persistent entity/world/narrative
state; immutable state revisions; exact events and boundary queries; explicit
scene mappings; atomic cross-scene ownership; rules/exceptions/diagnostics;
transitive impacts; and transactional selective repair. General asset storage
must coordinate with #128/#137–#149, and physical state/cache continuation with
#153/#166 onward. A missing complete umbrella implementation must not prevent an
independent operation supported by an exact tested capability.

## Protected compatibility and rollback boundaries

| Boundary | Existing contract to preserve | Required new behavior |
| --- | --- | --- |
| Fixed Codex profile | `profiles/codex-v1.json`, 8×9 atlas, 192×208 cells, exact order/counts/durations/transparency | Keep it byte-for-byte unchanged. Extended states remain custom profiles. |
| Profiles, catalog, playback | Existing profile schema, playback JS, state catalog IDs/aliases and all examples | Reuse their owners; a definition is not a finished clip or production performance. |
| Production v1 | Closed five-schema contract, pixel X-right/Y-down coordinates, clockwise degrees, integer frames and rational FPS, audio-capable output | Use separately versioned opt-in 3D/continuity documents and explicit adapters. Never append undeclared fields to v1 or reinterpret pixels as meters. |
| Rig coordinates | Right-handed +Y up/+Z forward, meters, radians, XYZW quaternions, column vectors, `world = parent @ local` | Reuse `rig_math.BLENDER_FROM_CANONICAL`; glTF serializes matrices column-major. No second coordinate convention. |
| Time | Legacy milliseconds, production frames and rig floating-point seconds are different contracts | Preserve exact rational story/presentation time and explicit before/after/terminal semantics until the documented evaluator boundary. |
| Integrity | File SHA-256 and semantic hashes have different purposes | `rig_signature` excludes review/validation; it is not the byte digest of `rig.json`. Store hash purpose and exact source revision. |
| Reviews and sources | Historical source/license/acquisition bytes, receipt chains and previous decisions | Never synthesize missing originals or treat prior approvals as approval of changed data. |
| Optional dependencies | Ordinary 2D commands and test discovery work without NumPy, Blender or WebGL | Keep 3D imports lazy; missing required capabilities produce explicit blocked/unverified outcomes. |

The receipt records hashes of the protected files and audited implementation.
This PR adds audit/probe/evidence files only; reverting those files removes it
without changing runtime data. Future continuity writes must use expected
revision checks, verified staging and immutable history; preserve original
project/manifests for explicit rollback. Migration must be opt-in with exact
backups, and failed repair/restore must leave the previous valid project usable.

## Local verification and source status

The machine-readable [baseline receipt](../tests/results/continuity-baseline.json)
contains exact commands, environment, observed counts, skip reasons and SHA-256
digests. The complete discovery output is retained in
[`continuity-baseline.log`](../tests/results/continuity-baseline.log).
The [source/archive report](../tests/results/continuity-source-delivery.json)
records reconstruction independently of rendering and visual review.

| Local execution | Observed result |
| --- | --- |
| Full existing unittest discovery | 867 tests in 312.499 seconds: 862 passed, zero failures/errors, five explicit skips. |
| Separate actual Three.js vertex/playback/UI integration | One test passed in 2.825 seconds; the original full-suite skip accounting is unchanged. |
| Original source verification and fresh archive restore | Passed; exact source and historical review evidence preserved. |
| Raster/rig doctor and generated schema/template drift checks | Passed; optional native capabilities remain explicitly unavailable. |
| Focused continuity probe | Completed; accepted and rejected cases are recorded above and in the JSON observations. |

The five original skips were native Krita, two Blender cases, gated Three.js and
Khronos validation. Three.js subsequently ran in the separate passing invocation.
The environment used Python 3.12.14, Pillow 13.0.0, jsonschema 4.26.0,
Playwright 1.64.0, NumPy 2.3.5, pygltflib 1.16.5, Node 24.19.0,
FFmpeg/ffprobe 6.1.1 and actual Chromium 156.0.8078.4. This combines the delivery
raster pins with optional Python rig dependencies; it is not an exact recreation
of the separately pinned rig-test environment.

Setup history is recorded separately: restricted-process dependency/browser
launch probes failed, and one browser download was corrupt. The authorized
installation completed, an existing matching browser binary was selected
explicitly, and the actual browser/loopback tests passed. These setup failures
are not counted as code regressions.

The prior missing-pilot-media failure described by older audit documents is
**not present at this revision**: source verification and fresh restoration
passed with all five source transports. Both original characters, 20 clips,
five original audio recordings, both scenes and all 20 historical assistant
review records were restored. The archive roundtrip contains 168 files and
preserves the source hashes and review history. No replacement artwork, speech
or fabricated approval was introduced.

The source/archive invocation intentionally did not run the full film render or
video delivery gate; its `complete_delivery_gate` is false. Local absence of
native Blender/Krita and the unexecuted Khronos integration are separate from
the passing baseline and from previously successful main CI. Neither the probe,
regression suite nor historical CI supplies new production-art approval.

Reproduce the audit after installing the recorded dependencies/browser:

```bash
python -m unittest discover -s tests -v
python scripts/production_sources.py verify-delivery
python scripts/verify_public_delivery.py --destination NEW_AUDIT_DIRECTORY
python scripts/generate_schemas.py --check
python scripts/generate_rig_templates.py --check
python tests/continuity_baseline_probe.py
```

The receipt includes the actual browser-selection variables and separate
targeted browser command. Reproduction must report its own versions and skips;
do not copy these results onto a different checkout or environment.

## Downstream implementation order and required evidence

1. **#113:** add strict continuity contracts and immutable revisions, separate
   from existing production/rig schemas. Suggested new authority:
   `continuity_contracts.py`; no such module is claimed implemented here.
2. **#114 and #115:** connect actual rig/mesh inspection and versioned capability
   admission. Use existing loaders and real byte/geometry tests; reject corrupted
   meshes, stale hashes and unsupported channels. A diagnostic-only load is never
   approval or permission to render.
3. **#116–#118:** add `continuity_state.py` and supported adapters for exact replay,
   scene/world/narrative state and atomic handoffs. Test out-of-order query
   equivalence, terminal N versus N−1, before/after events, rational rates,
   duplicate IDs, multiple actors sharing a character revision, and ownership
   persistence without manual state duplication. Resolve the observed repeated
   actor owner gap explicitly; do not freeze it as compatibility behavior.
4. **#119–#123:** add rules/diagnostics and evaluated motion/camera/look/visual
   adapters, then extend existing review participation. Test intentional scoped
   exceptions, unsupported capabilities, actual transformed sockets/deformation,
   false metadata identity claims, real reference renders and scoped staleness.
5. **#124–#127:** implement causal impact, transactional repair and operational
   integration; verify restore/recovery, affected-frame regeneration and
   unaffected reuse. Execute the full two-scene demonstration and 15 injected
   failures before claiming final acceptance.

Keep the existing production contract, performance, workflow, review, source,
pilot, render, preview, adapter and archive suites running. In particular,
`test_rig_compatibility.py` pins frozen legacy bytes and verifies lazy optional
imports, while workflow regressions protect unused-asset reuse, camera-only
invalidation and append-only reviews. New tests must join the applicable CI
gate; the rig workflow uses explicit module selectors. Schema or fixture success
cannot substitute for any later real-backend or visual acceptance requirement.
