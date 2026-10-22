# AI Scene Director: repository baseline and compatibility audit

This is the executed baseline for [issue #23](https://github.com/CompleteTech-Skills/hatch-pet/issues/23),
the first task in Director phase P0. It establishes the starting implementation,
ownership, regression results and protected contracts for later work. It does
not establish completion of the P0 contracts, the five-second MVP or the full
30-second production mission.

## Audited revision and instructions

The audit starts at `main` commit
`7b966a639bcaf23bd3a0d037f46f29e2edfcc273`, Git tree
`9c0e9bc0f8b3bf2b0d63d8a49b5250f59b3643ab`, on 2026-10-22.
The regressions ran from a separate detached worktree at that exact commit so
documentation edits could not change the inputs during validation.

`README.md` and `SKILL.md` are the root instructions. There is no `AGENTS.md` or
`CONTRIBUTING.md` anywhere in the audited tree. The applicable detailed
contracts are `references/codex-pet-contract.md`,
`references/production-contracts.md`, `references/production-operations.md`,
`references/production-rendering.md`, `references/sources-and-identity.md`,
`references/character-decomposition.md` and `references/3d-rigging.md`.
Read these together with the source code, rather than treating historical
validation reports as new execution evidence.

The [complete requirement and interface map](director-requirements-map.md)
maps the original [Director mission #18](https://github.com/CompleteTech-Skills/hatch-pet/issues/18),
its continuation and its mandatory-interface addendum to actual source
symbols, existing tests, future work and subsystem owners.

## Repository and coordination snapshot

The initial paginated GitHub inventory found 180 open issues, numbered
#10–#189, no open PRs (including drafts), and no issue assignments, labels or
milestones. The initial 16 repository issue comments contained mission
continuations, scope/dependency documentation and historical PR evidence;
none was an implementation claim. Issue #23 has no native blocked-by dependency.

| Remote branch | Head at audit | Interpretation |
| --- | --- | --- |
| `main` | `7b966a639bcaf23bd3a0d037f46f29e2edfcc273` | Current baseline, merged PR #9 |
| `feat/3d-character-rigging` | `662c966f9097ff80a7cada8b8b472566ff233204` | Retained head already merged in PR #9 |
| `fix/public-production-delivery` | `f8ee94da606193da61368ab12a56469412cd3a47` | Retained head already merged in PR #8 |

Recent merged PRs #1–#9 were inventoried. PR #8 recovered and verified the
original production delivery; PR #9 added the genuine 3D rig engine and kept
the public 2D gate independent of optional 3D dependencies. Retained branches
are not evidence of unfinished PRs and are not owned by this audit.

Session `hatch-director-audit-20261022` claimed only #23 on branch
`agent/issue-23-director-baseline-20261022` in
[the ownership comment](https://github.com/CompleteTech-Skills/hatch-pet/issues/23#issuecomment-6348216993).
A later overlapping #23 claim was detected and addressed in
[the coordination update](https://github.com/CompleteTech-Skills/hatch-pet/issues/23#issuecomment-6348271967).
Recheck that thread and current PRs before starting further work; this audit
does not reserve #24–#42 or any other subsystem issue.

The branch endpoint reported `protected: false` with status-check enforcement
off, and the ruleset collection was empty. The detailed branch-protection
endpoint returned HTTP 403 because the integration lacks access to that
endpoint. These observations are retained separately: an inaccessible endpoint
is not treated as proof of its policy. Merge permissions, checks and review
state must be refreshed for the actual PR.

### Default-branch CI

Both workflows below completed successfully at the exact audited SHA. These
are observed GitHub results, separate from the local reproduction below and
from any later PR or post-merge run.

| Workflow | Baseline run |
| --- | --- |
| 3D rigging and compatibility gates | [39421253425](https://github.com/CompleteTech-Skills/hatch-pet/actions/runs/39421253425) |
| Public production delivery | [39421253433](https://github.com/CompleteTech-Skills/hatch-pet/actions/runs/39421253433) |

The workflow definitions are `.github/workflows/rig-3d.yml` and
`.github/workflows/public-delivery.yml`. The latter runs the complete 2D
delivery on Linux, macOS and Windows; the rig workflow has separate schema,
skinning, animation, interchange, Blender, browser, demonstration and archive
jobs. A green workflow is not a new artistic review or a guarantee that the
future Director interfaces exist.

## Actual local validation

The [machine-readable audit receipt](../tests/results/director-baseline.json)
retains exact commands, environment, complete stdout/stderr where applicable,
optional skips, source hashes and report/log hashes. The
[strict delivery report](../tests/results/director-baseline-delivery.json),
[2D log](../tests/results/director-baseline-2d.log),
[rig log](../tests/results/director-baseline-rig.log) and
[GitHub snapshot](../tests/results/director-baseline-github.json) accompany it.

| Executed check | Observed result | Evidence boundary |
| --- | --- | --- |
| Strict 2D delivery regression scope | 790 tests in 288.169 seconds; zero failures/errors; one native-Krita skip; no unexpected skips | Actual Chromium playback/decomposition checks and retained-source tests ran. Native Krita was unavailable. |
| Complete rig test discovery | 77 tests in 10.430 seconds; zero failures/errors; two optional Blender skips | Actual Khronos/pygltflib interchange and Three.js browser checks ran. Blender reopen and CPU rendering did not run locally. |
| Original source verification, project reconstruction and portable archive roundtrip | Passed; all 20 review records preserved; verified archive SHA-256 `2d22f6804d9c379dcab00dfc6ae2a59c60577904cd1bcbdbfa2e1e044cfc4401` | Original non-fixture inputs; no provider, TTS or new approval. |
| Generated schemas, rig templates and style reference | Each `--check` exited 0 | Existing definitions and generated files agree; this does not create Director schemas. |
| Historical Codex atlas validation | Exit 0 | Existing atlas geometry/alpha contract, not new acquisition or app integration. |
| Frozen source checkout | Initially clean and unchanged after the strict gate | The full report retains per-file input SHA-256 values and the exact baseline commit. |

The two suites contain 867 tests in total, with three explicitly reported
optional skips and no failures/errors. Only the 2D gate applies its strict
skip allowlist. The rig run is separately classified and is not represented
as a complete Blender integration run.

| Retained artifact | SHA-256 |
| --- | --- |
| `director-baseline-delivery.json` | `b4101a11633ba94b9df9922cc99ef13b58a640b43023d290e2a6aed10b867d72` |
| `director-baseline-2d.log` | `959aff61dd88a892220a950d79f498a994c4eb8d8f75743d4b6e46d59a753715` |
| `director-baseline-rig.log` | `9802681d47370f893125b60c0011aba5ce03d95a1314bee1bb178465c75199be` |

The audit receipt also binds the GitHub snapshot and preserves the exact
runtime version/probe outputs. The logs are retained verbatim, including
expected test-fixture diagnostics and skip reasons.

### Reproduce the audited scope

Use a clean checkout of the audited commit and a new output directory. The
local run used Python 3.12.14 and the pinned delivery dependencies, with NumPy
2.3.5 and pygltflib 1.16.5 added for optional rig tests. This is one explicitly
recorded combined environment; it does not reproduce the different
Pillow/jsonschema/Playwright pins in `requirements-rig-test.txt`.

```bash
python -m venv ../hatch-audit-venv
# Activate that environment using the command appropriate for your shell.
python -m pip install -r requirements-delivery.txt numpy==2.3.5 pygltflib==1.16.5
python -m playwright install chromium
npm ci --ignore-scripts --prefix tools/rig
python scripts/production_sources.py verify-delivery
python scripts/generate_schemas.py --check
python scripts/generate_rig_templates.py --check
python scripts/generate_style_reference.py --check
python scripts/validate_atlas.py assets/pet/spritesheet.webp
python scripts/verify_public_delivery.py --destination ../hatch-director-audit-output --tests --test-scope 2d
HATCH_RIG_INTEROP_TEST=1 HATCH_RIG_BROWSER_TEST=1 python -m unittest discover -s tests -p 'test_rig_*.py' -v
```

Keep the environment and output directory outside the checkout, as shown, so
generated files do not change the source-inventory snapshot. Set the two
`HATCH_RIG_*` variables using the equivalent syntax on Windows.
The strict 2D runner enables the decomposition browser checks itself. The
audit used `HATCH_BROWSER_EXECUTABLE` to select the already installed matching
Chromium 156.0.8078.4 headless shell after the full-browser download returned
an invalid ZIP. Actual Chromium tests executed; the download problem was not
converted into a passing test or an unexpected skip.

The audit command deliberately has no `--render` or `--video` flag. Its
source reconstruction, archive roundtrip and regression results must not be
reported as a newly completed 696-frame production delivery. The existing
default-branch CI is the separately linked full-delivery evidence.

## Original media and review history

Current source verification resolves an outdated warning in parent #18 §2:
the original pilot inputs are available at this revision. Five pinned
ordinary-Git transports contain 129 logical files and 462 unique parts.
Verification checks the four original imagegen acquisitions, five original
speech recordings, all 20 historical assistant review records and 13 distinct
supporting evidence files. All seven published media/provenance files verify.
The source command reports `fixture: false`, `provider_called: false`,
`tts_called: false`, `new_approval_recorded: false`, and
`visual_review_performed: false`.

The last preserved review-chain hash is
`a02a3f5242e6c48a69053961d822f21e38aa7a32ec3d64a81679faa257198934`.
Original review identities remain `assistant`; human review remains false.
Restoration and the portable archive retain the 20 historical records, with a
new restoration event rather than rewriting the decisions. Exact inventory,
archive and checkout hashes are in the retained delivery report.

Historical missing-media failures in `tests/results/production-*.log` and
earlier rig baseline logs describe their own checkouts. They are not current
failures at `7b966a6`. Future missing or modified source bytes must still fail
verification; do not replace them with synthetic art, newly generated speech
or recomputed approvals.

## Protected compatibility boundaries

| Contract | Existing authority and invariants | Boundary for Director work |
| --- | --- | --- |
| Codex atlas and package | `profiles/codex-v1.json`, `profile_spec.py`, `compose_atlas.py`, `validate_atlas.py`: 8 columns, 9 fixed rows, 192×208 cells, 1536×1872 atlas, existing state order/counts/millisecond durations and transparent unused cells | Additional 3D animation or custom states must not change the fixed atlas or installed package format. |
| Profiles, styles and playback | `profiles/profile.schema.json`, `state_catalog.py`, `state_selection.py`, `style_registry.py`, `assets/playback.js` | Preserve existing IDs, aliases, compilation, selected-style hashes, profile/export semantics and reduced-motion behavior. Catalog definitions do not imply generated art or completed clips. |
| 2D production documents | `production_contracts.py` and the five generated `profiles/production-*.schema.json` files | Keep schema v1 strict, including rejection of unknown fields. Introduce separately versioned Director/3D data or explicit adapters; do not insert undeclared fields into v1 documents. |
| Time and space | `production_performance.py` uses integer production frames and rational project rates; 2D coordinates are X-right/Y-down pixels and degree rotations. `rig_contracts.COORDINATES` uses right-handed +Y-up/+Z-forward meters, radians, XYZW quaternions, column vectors and seconds | Preserve both existing meanings. Director frames/subframes need explicit exact-time conversion, and `rig_math.BLENDER_FROM_CANONICAL` is the established 3D basis adapter. Never relabel pixel art as geometry. |
| Source and identity | `source_interface.py`, `asset_contracts.py`, `production_sources.py`, `production_delivery.py`, `character_decomposition.py`, `rig_import.py` | Preserve exact original bytes, source roles/hashes, immutable character versions, permissions/attribution, fixture classification and inferred-art distinctions. |
| Acquisition and repair | `hatch.claim/ingest/fail/reconcile`; `production_workflow.bind_generation_run/claim_generation/ingest_generation/fail_generation` | Wrap the existing binding and claim lifecycle. Preserve claim tokens and uncertain outcomes; a Director retry must not start a competing billable attempt. Existing call limits are not a transactional monetary ledger. |
| Review and cache evidence | `production_workflow.record_review/review_status/dependency_snapshot/impact_report`, `rig_review.py`, `decomposition_review.py` | Preserve historical decisions, exact artifact/dependency hashes and scoped stale status. Numerical success cannot create artistic or human approval; changed renderer dependencies require fresh evidence. |
| Rendering and exports | `production_render.py` owns 2D PNG/PCM rendering and AAC-bearing video; `rig_render.py` and `rig_blender.py` own bounded single-rig previews | Keep existing 2D audio behavior. New Director silent video needs independently verified zero-audio export through the authoritative 3D rendering integration. Rig previews do not satisfy general scene rendering. |
| Optional dependencies | `rig_doctor.py`, the lazy rig dispatch in `hatch.py`, `verify_public_delivery.build_regression_suite` | Ordinary 2D discovery and commands must continue without NumPy, Blender, pygltflib or optional 3D tooling. Do not merge conflicting environment pins into a mandatory 2D installation. |

`tests/test_rig_compatibility.py` independently freezes four legacy file hashes
and tests discovery with optional imports blocked. The full 2D suite covers
profile, raster, style/state, source, review, playback, decomposition,
production, delivery and transport behavior. The preflight receipt additionally
pins the source instructions, style catalog, delivery manifest and all five
production schemas.

### Rollback and failure preservation

1. **Code:** keep future changes additive and independently reviewable. Revert
   only the owning change through the repository workflow; do not reset shared
   branches, rewrite another contributor's history or change preserved source
   transports to make a test pass.
2. **Projects:** use `production_workflow.archive_project` and
   `restore_project` into a new directory. Restoration checks exact inventory
   and hashes, retains review history, appends a restoration event and
   recomputes renderer/review freshness. An older approval is not automatically
   valid under a different renderer.
3. **Schema migrations:** `production_workflow.migrate_project` is explicit.
   Its supported workflow-v1-to-v2 migration writes a hash-verified backup,
   preserves acquisition bindings/history and requires fresh review. This is
   separate from production document schema v1; no Director or 2D-to-3D
   migration currently exists. A future migration needs its own versioned
   contract, rollback data and negative tests.
4. **Character edits:** retain previous character versions, source-bound
   components and immutable rig revisions. `decomposition_review.restore_revision`
   verifies source/revision/asset hashes and reapplies a recorded annotation;
   it does not manufacture the old approval. `rig_jobs.save_rig` preserves
   prior manifests and invalidates dependent evidence on a new revision.
5. **Installed pets:** the existing `hatch.rollback` verifies both backup
   hashes and the current installation receipt before restoring a package.
   It preserves the displaced version and refuses unrelated changes. This
   audit performs no installation or rollback of a user's actual pet.
6. **Failures and uncertain operations:** retain source files, failed attempts,
   receipts, claims and diagnostics. Cancel only owned workers; never terminate
   unrelated sessions. Cleanup is scoped to owned output paths, not shared
   worktrees, historical evidence or another agent's branches.

## Handoff and completion boundary

Issue #23 supplies the executed baseline and ownership/compatibility map.
The next dependent task is #24 (Director schemas and mandatory interfaces),
then #25 (capability admission) and #26 (traceable graph compilation).
Refresh the current issue/PR inventory before claiming any of them.

The requirement map identifies reuse and extension points in the existing
rig, acquisition, archive, review and production implementations, and names
the gaps owned by Model3D #10, Rig #11, Scene3D #12, Animation3D #13,
Camera3D #14, LookDev3D #15, Render3D #16 and Editor3D #17. No competing
controller, schema implementation, provider client, scene editor or renderer
is introduced by this audit.

No new production visual approval, human signoff, paid provider execution,
general AI planning, new silent 3D film, Blender execution or final Director
acceptance is claimed. The optional local Blender/Krita gaps and the separate
CI evidence remain explicit in the validation records.
