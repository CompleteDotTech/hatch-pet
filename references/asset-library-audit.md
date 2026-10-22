# Asset Library: verified repository baseline and integration boundaries

This audit addresses [#137](https://github.com/CompleteTech-Skills/hatch-pet/issues/137), using the actual source and executed checks required by [#128](https://github.com/CompleteTech-Skills/hatch-pet/issues/128), sections 2–3 and 25 and its continuation. It establishes reusable authorities and the boundaries for the next foundation task, #138. It does not implement a unified asset registry or complete phase #129 or the Asset Library mission.

## Source, instructions and active ownership

The baseline is default branch `main` at **`7b966a639bcaf23bd3a0d037f46f29e2edfcc273`**, from a clean isolated public checkout. The session date is 2026-10-22; evidence records preserve exact execution timestamps, commands, tool versions and input/output hashes. The contribution branch is `agent/issue-137-asset-library-baseline-2a0543d` and its [claim](https://github.com/CompleteTech-Skills/hatch-pet/issues/137#issuecomment-6348337500) covers this audit leaf only.

The initial GitHub inventory contained **180 open issues, no open PRs including drafts**, and three branches: `main`, `feat/3d-character-rigging`, and `fix/public-production-delivery`. Both non-default branches were already merged. The complete issue/comment/dependency inventory was inspected across the audit agents. At that snapshot issues had no labels, assignees or milestones; absence of those fields does not imply absence of agent ownership.

Concurrent claims became visible on refresh. This session yielded overlapping Director audit #23 to its earlier owner in [the coordination reply](https://github.com/CompleteTech-Skills/hatch-pet/issues/23#issuecomment-6348337045). #23 (`hatch-director-audit-20261022`), #112 (`hatch-f637139fcc7a`, continuity audit) and #166 (`astra-36752e25-physics-audit`, physics audit) are separate ongoing work. No competing #137 claim or covering PR was present before this claim. Refresh GitHub before subsequent work; this dated inventory is not a permanent lock.

Recent foundations are [PR #8](https://github.com/CompleteTech-Skills/hatch-pet/pull/8), which restored the original production payload, and [PR #9](https://github.com/CompleteTech-Skills/hatch-pet/pull/9), which added substantial real 3D rigging. At the baseline SHA, [rigging CI 39421253425](https://github.com/CompleteTech-Skills/hatch-pet/actions/runs/39421253425) passed nine jobs; [delivery CI 39421253433](https://github.com/CompleteTech-Skills/hatch-pet/actions/runs/39421253433) passed Linux, macOS and Windows. These remote runs are distinct from the local evidence below. Branch metadata reported `protected: false` and rulesets were empty; the detailed protection endpoint returned integration HTTP 403, so its contents were unavailable. Existing merge history uses merge commits. The engineering mission still requires independent review.

Read instructions: `README.md`, `SKILL.md`, `DELIVERY_STATUS.md`, the production contracts/operations/rendering/traceability/public-validation references, profiles-and-exports, portability-and-operations, sources-and-identity, character decomposition/states, style catalog, and existing 3D rigging audit/guide/acceptance. No `AGENTS.md` or `CONTRIBUTING.md` exists in the tracked tree. Applicable contracts require source-origin preservation, deterministic validation, separate evidence and review states, fixed pet compatibility, bounded writes and explicit integrations.

## Executed baseline and exact historical delivery

The immutable [evidence index](../tests/results/asset-library-baseline-20261022/evidence-index.json) records retained file sizes and SHA-256 digests, original output locations, source revision, exact command arrays and limitations. The raw logs/reports are in the same directory. No pre-existing tracked source, test, schema, media or review file was changed to obtain these results.

### Regression and integration results

The inventory contains **867 distinct test IDs: 790 legacy and 77 rigging tests**. The initial full discovery returned exit 0 and `OK (skipped=4)`, reporting 853 tests in 263.851 seconds. Two skips were class setup failures, suppressing 14 individual browser cases; the other skips were one browser export case and the optional native Krita case. The expected full Chromium binary was absent, although the installed Chromium headless shell worked.

The supported `HATCH_BROWSER_EXECUTABLE` setting then enabled the three affected browser modules without source changes. Those separate runs passed all 15 cases. [Exact per-ID reconciliation](../tests/results/asset-library-baseline-20261022/combined-test-coverage.json) proves **866 distinct passes, zero failures/errors and no missing outcomes** across the unchanged-source runs. Only `test_production_adapter.ProductionAdapterTests.test_actual_local_krita_import_export_and_layer_roundtrip` remains unexecuted because native Krita is unavailable. This is not a claim that one invocation passed all 867 tests.

| Executed command, using the recorded virtual-environment Python | Observed result | Raw receipt |
|---|---|---|
| `-m unittest discover -s tests -v` | 853 reported tests; exit 0; four skip records; 263.851 s | [full-suite-report.json](../tests/results/asset-library-baseline-20261022/full-suite-report.json) and full-suite stdout/stderr logs |
| `-m unittest discover -s tests -p test_exports.py -v` | 1 passed; no skips; 2.441 s | [browser-recovery-report.json](../tests/results/asset-library-baseline-20261022/browser-recovery-report.json) and module logs |
| `-m unittest discover -s tests -p test_playback_extended.py -v` | 10 passed; no skips; 23.222 s | Same recovery receipt; separate module logs |
| `-m unittest discover -s tests -p test_production_preview.py -v` | 4 passed; no skips; 4.130 s | Same recovery receipt; separate module logs |
| `scripts/generate_schemas.py --check` and `scripts/generate_rig_templates.py --check` | Both exit 0 | [generated-definition-checks.json](../tests/results/asset-library-baseline-20261022/generated-definition-checks.json) |
| Initial schema/math, skinning, animation/IK gates | 12, 7 and 27 passed respectively; overlap the full suite | [initial-nonbrowser-rig-checks.json](../tests/results/asset-library-baseline-20261022/initial-nonbrowser-rig-checks.json) |

The full run enabled `HATCH_DECOMPOSITION_BROWSER_TEST=1`, `HATCH_RIG_INTEROP_TEST=1`, `HATCH_RIG_BROWSER_TEST=1` and `HATCH_RIG_BLENDER_TEST=1`, with the exact provisioned `HATCH_BLENDER` path. It passed both actual Blender save/reopen and Cycles CPU pose-render cases, Khronos/pygltflib checks, real Three.js skinned-vertex/UI tests, decomposition browser editing and existing FFmpeg tests. The recovery runs exercised exported playback, reduced motion and production-preview pixel controls. Native `rig_interop.compare_imported` alone reports `independent=False`; the separate external-validator/reader tests provide the executed independent interchange checks.

All exact paths and overrides are retained in the receipts. The interpreter was `/workspace/scratch/2a0543d2545a/hatch-venv/bin/python`; browser recovery used `/root/.cache/ms-playwright/chromium_headless_shell-1248/chrome-headless-shell-linux64/chrome-headless-shell`. Browser execution required the environment's permitted unsandboxed process context. An initial full-Chromium CDN download returned a non-ZIP error page; the existing working headless shell was used instead. Blender's 377,397,328-byte CI-pinned archive was SHA-256 verified as `975c58fcb244273838534bba771e64ad87739216b0f9b39a888531a49a72d845` before extraction.

| Runtime | Executed version |
|---|---|
| Python / platform | 3.12.14 / Linux x86-64 |
| Pillow / jsonschema | 13.0.0 / 4.26.0 |
| Playwright / Chromium headless shell | 1.64.0 / 156.0.8078.4 |
| NumPy / pygltflib | 2.3.5 / 1.16.5 |
| Node / Three.js / gltf-validator | 24.19.0 / 0.180.0 / 2.0.0-dev.3.10 |
| Blender | 4.5.3 LTS |
| FFmpeg / ffprobe | 6.1.1-3ubuntu5 |
| Native Krita | Unavailable; optional integration not executed |

[Runtime output](../tests/results/asset-library-baseline-20261022/test-runtime-versions.json) and [Blender provisioning evidence](../tests/results/asset-library-baseline-20261022/blender-provision.json) preserve the actual versions. This combined environment used the delivery requirements plus 3D dependencies; it is not a claim to reproduce the separate rig-test requirements lock exactly. The test harness hashed 197 existing tracked files under `scripts`, `tests` and `profiles` before and after execution: none changed. Fixture and automated browser evidence, including the retained decomposition screenshot, establish engineering behavior only; they do not confer production-art approval or prove a live generation-provider integration.

### Original source and package verification

Both recorded commands exited 0:

```text
/workspace/scratch/2a0543d2545a/hatch-venv/bin/python scripts/production_sources.py verify-delivery
/workspace/scratch/2a0543d2545a/hatch-venv/bin/python scripts/verify_public_delivery.py --destination /workspace/scratch/2a0543d2545a/director-delivery-baseline
```

The destination name predates the coordination handoff and is only an owned temporary output directory. [Source verification](../tests/results/asset-library-baseline-20261022/verify-delivery.json) and the unchanged [public-delivery report](../tests/results/asset-library-baseline-20261022/public-delivery-report.json) verify the current original payload. The historical shortages described in earlier mission text were repaired by PR #8; they are **not missing at this baseline**.

| Original source bundle | Logical files | Unique parts | Bundle SHA-256 |
|---|---:|---:|---|
| Artwork | 36 | 207 | `7ed8daad15ba0be16aee297e77e1ee9ca9561a866c9668800c27850aafd41fe6` |
| Audio | 16 | 39 | `62a25bf2764210d0616e374cf04c0202fa311e18682f4208f7ea0e27b7ecb6e9` |
| Evidence | 10 | 60 | `008567c7346b7bd76156e8050a2e51bbfb3ce18cbcb185897c1affab924aea40` |
| Reconstruction | 66 | 92 | `59757fc164dd4538d6bc8593b55010ec01b194ec0c6f1e5781c9249528d5ccf1` |
| Reviews | 1 | 64 | `454bfdb6daad191cdcf1c20ea8dfe487dae0bb7a3576d2258cbe6c8b4f99c5dc` |

All 129 logical files across 462 parts, the four original artwork acquisitions, five original audio recordings and seven public deliverables verified. The 20-record review history has SHA-256 `cce42c52460d4525f18eb00f7525f8df8d99ebda9e31b3d875dccba6d93220d4`; its chain and evidence verified, including 13 supporting evidence files. Its reviewer kind is `assistant`, with `human_review=false`. No original media, license or review was synthesized or modified, no provider/TTS call was made, and no new approval or visual review was recorded.

The command restored the real pilot and verified a portable project archive/restore roundtrip: **168 files, all 20 historical reviews preserved, renderer unchanged, restoration event appended**. This run's archive SHA-256 is `07283a0db2eef14c14f04816abffb6cf0cca70ab2c90e50a52728fddbd813f3d`. Timestamped restoration records mean this is an observed output hash, not a promise that subsequent archives have the same digest. The source report preserved the 1,504-file checkout hash inventory and confirmed `checkout_unchanged=true`, from a clean baseline checkout.

The delivery invocation did **not** request `--tests`, `--render`, `--video` or `--compact`; it truthfully reports `complete_delivery_gate=false`. The separately executed regression suite above is not a fresh full-pilot render or video acceptance pass. Historical artifact integrity, successful engineering tests, current visual approval, human signoff and external integration remain distinct.


## Existing owners and reuse decisions

No unified `AssetLibrary`, asset schema family or SQLite index exists at this SHA. Adapt the owners below; state/style catalogs are definitions, not verified mesh stores. All module paths below are relative to `scripts/`.

| Responsibility | Actual owner/functions | Reuse boundary and missing behavior |
| --- | --- | --- |
| Registry and identity | `production_contracts.py::asset_key`, `load_project`, `validate_cast`; `rig_models.py::load_rig`; `asset_contracts.py::validate_identity` | Preserve `id@version`, exact rig/source hashes and fixture origin. One facade resolves native records; no rewritten IDs or competing authority. |
| Definition catalogs | `state_catalog.py::load_library`, `compile_selection`; `style_registry.py::load_catalog`, `resolve_style`, `validate_snapshot` | Preserve versions/frozen snapshots. Definitions do not establish artwork, mesh availability or authored 3D animation. |
| Immutable versions/storage | `production_workflow.py::import_component`, `_write_immutable`; `rig_jobs.py::save_rig`, `next_version`; `rig_models.py::save_geometry`, `save_weights`, `_store` | Production versions and content-addressed rig NPZ blobs retain predecessors. Shared manifests, annotation revisions, scoped resolution/deduplication/indexing remain #138/#141/#142. Atomic replacement is not journaled database recovery. |
| Actual artifact inspection | `rig_import.py::load_character_model`; `rig_models.py::validate_geometry`, `load_geometry`; `rig_geometry.py::analyze_geometry`; `rig_validation.py::validate_rig`; `rig_animation.py::validate_animation` | Reuse real GLB/glTF/OBJ/optional Blender inspection. Labels do not prove compatibility. Prefab closure and other formats need measured adapters (#139/#140). |
| Hashes, JSON, paths | `asset_contracts.py::sha`, `hash_object`, `portable`; `production_contracts.py::file_sha`, `read_json`, `safe_path`; `rig_errors.py::sha256`, `object_hash`, `decode_json`, `portable_name`, `safe_path` | Preserve exact-byte versus object digests. Add byte count/role/format/required status. Keep duplicate-key, nonfinite, alias, traversal and resource checks. |
| Native acquisition/provenance | `hatch.py::prepare`, `claim`, `ingest`, `fail`, `repair`, `reconcile`; `production_workflow.py::bind_generation_run`, `claim_generation`, `ingest_generation`, `fail_generation`, `repair_generation`; `source_interface.py::import_source` | Preserve claims/tokens/model-call history and origin classes. Registration cannot trigger duplicate generation or invent provider/license evidence. Current production bridge is raster-specific. |
| Review authority | `production_workflow.py::record_review`, `review_status`; `rig_review.py::apply_review`; `decomposition_review.py::apply_review`; `hatch.py::review`, `require_review` | Preserve evidence-bound review scope. Packaging/validation/licenses do not grant art approval. Rig review returns `production_artwork_approved=False`; publication cannot bypass native review. |
| Locks and lifecycle | `hatch.py::ownership`; `rig_errors.py::job_lock`; `rig_jobs.py::run_step`; `hatch.py::atomic`; `rig_errors.py::atomic_bytes` | Reuse OS owner locks, histories and bounded retries. Library-wide metadata revisions, journals, GC and cross-store promotion remain #141/#142. |
| Dependencies and impact | `production_workflow.py::shot_dependencies`, `dependency_snapshot`, `impact_report`, `coverage_report`; `rig_models.py::rig_signature` | Preserve selective 2D consumers and exact rig signatures. General transitive/reverse asset dependency queries, project lockfiles, compatibility ranges and replacement plans remain #143; no mutable 'latest' binding may change an existing project. |
| Legacy/project archives | `portable_runs.py::archive_run`, `verify_archive`, `restore_run`; `production_workflow.py::archive_project`, `verify_project_archive`, `restore_project`; `decomposition_package.py::export_decomposition`, `verify_package`, `import_decomposition` | Adapt existing ZIP/inventory and directory contracts. Production archive is schema 2 with project schema 1/workflow schema 2. Preserve active-claim checks, exact inventories, bounds and staged restoration. New collection/library packages need explicit versioned closure, not a weaker parallel extractor. |
| Source and multipart transport | `production_sources.py::create_source_bundle`, `verify_source_bundle`, `restore_source_bundle`; `production_bundle.py::create_bundle`, `verify_bundle`, `restore_bundle`; `production_delivery.py::verify_delivery`, `restore_pilot` | Source format `hatch-production-sources` v1 verifies complete logical-file hashes and fragment bytes. `hatch-production-bundle` v1 reconstructs a ZIP then delegates to the production archive verifier. Valid indexes alone never establish payload readiness. |
| 3D and consumer exports | `rig_gltf.py::export_gltf`; `rig_blender.py::export_blender`; `rig_package.py::package_rig`, `restore_rig`; `export_assets.py::export_assets`; `hatch.py::package`, `verify_package`, `rollback` | Preserve glTF skin/morph/material/clip data, actual optional Blender reopening, rig-package v1 and legacy package receipts. Native pet installation rollback is not a generic library-version rollback. New format losses, closure, license and verification receipts belong in explicit adapters. |

### API and integration mapping

These are future #128 §15/§21 boundaries, not existing `AssetLibrary` methods.

| Required interface | Current anchor and needed adapter |
| --- | --- |
| `open`, `get`, version resolution, asset loading | Native production loader and `load_rig`; add one library namespace/resolver recording source library, exact version/hash and supported legacy kind. #138 starts real-file registration/retrieval. |
| `import_asset`, procedural/generated registration | Reuse `load_character_model`, preserved source files and native acquisition receipts; quarantine/verify conversion outputs before registering. Do not relabel imported bytes as generated. #139. |
| `search`, discovery, asset picker | Existing state/style search is limited to definitions. Add rebuildable offline metadata/FTS indexes over canonical records; genuine embedding inference is a separate optional provider, not keyword matching. #144. |
| `validate`, compatibility, inspector | Reuse geometry, skeleton, weights, animation and source validators; add kind-specific files/dependencies, licenses, extension and renderer diagnostics. Independent glTF check: `rig_interop.py::validate_gltf`. #140. |
| `resolve_dependencies`, change notifications, replacement | Reuse snapshots/impact reports; add direct/transitive/reverse closure and exact project locks. Plan replacement before versioned binding updates; retain originals and unrelated projects. #143. |
| `bind_project`, instantiation, scene/material/rig/animation binding | Use canonical production/rig references. Persistent Scene3D/editor APIs are absent; add explicit adapters. Instances share immutable assets, not local transforms/motion. |
| `generate_preview`, preview acquisition | `rig_render.py::render_rig_preview`, `render_pose_sheet`; `rig_blender.py::render_blender_preview`; `rig_viewer.py::create_review_ui`. Real geometry previews are not an asset browser. Bind outputs to version, camera/settings/backend and hashes. |
| `export_package`, `restore_package`, `verify` | Dispatch native verifiers by kind. Add complete closure/lockfiles and verify all relocated payloads. Missing/corrupt required files remain incomplete regardless of metadata/reviews. |
| Local HTTP/jobs | `rig_http.py::RigServer`, `RigHandler`, `serve` provide a loopback/token/origin-checked pattern. No library service exists. New routes require bounded inputs, scoped streaming, write authorization, typed progress/cancellation and native job ownership. |


## Canonical integration decisions

The repository already has several scoped registries and asset formats. The new library must offer one resolution interface over those authorities, rather than rewrite every existing format into a second source of truth.

1. **Preserve identity and exact versions.** Existing production references select `id@version`, relative file paths and SHA-256. Rig manifests bind source bytes, geometry, weights, clips and a rig signature. A library adapter should reference those existing owners and independently verified bytes. It must not turn an imported file into a generated asset, a catalog definition into a finished motion, or a 2D drawing into a 3D model.
2. **Separate immutable content from mutable indexing.** New `AssetIdentity`, `AssetVersion`, `AssetFile`, dependency, compatibility, preview, provenance and publication contracts belong to #138 and later tasks. Any SQLite/search index is rebuildable from canonical records; it is not another authoritative version registry. Tags/favorites can change without rewriting published content. Project snapshots must pin resolved versions and hashes, not follow a mutable shared-library alias.
3. **Reuse the native acquisition lifecycle.** `hatch.claim/ingest/fail/repair/reconcile`, under `hatch.ownership`, remain the raster generation authority. Production's binding/claim/ingest/fail/repair bridge delegates to it. Asset resolution, import, metadata registration or index reconstruction must not issue hidden generation calls or reset an uncertain claim. Future 3D providers need their actual outputs inspected, authorized operation context and genuine provenance; no provider is established by this audit.
4. **Keep scoped reviews authoritative.** Legacy, production, decomposition and rig review records retain their own contracts and exact evidence. Adapt their status; do not copy them into a parallel ledger that can diverge. Integrity, technical readiness, licensing, distribution permission, fixture classification, assistant review and human signoff remain independent facts. A hash match or successful import does not confer artistic approval.
5. **Resolve required bytes before readiness.** A valid index is insufficient. Recursively bind required buffers, textures, rig/clip/material versions and required provenance/license evidence; independently inspect compatible payloads. Unknown formats/extensions, missing sources, incompatible rigs and incomplete transport remain explicit. New archive closure/lockfiles and licensing gates are downstream #143/#148 work, not existing capabilities of a metadata catalog.
6. **Make conversion a versioned derivative.** Use existing real mesh/rig import/export and basis adapters where supported. Preserve source bytes and record source/output hashes, tool/backend identity, units, feature loss and independent reload/reopen. Unsupported operations or formats, such as OBJ export, FBX, USD, Alembic or additional renderer features, must remain unsupported until an adapter is implemented and exercised. Existing OBJ import remains supported; a filename extension alone is not evidence of another operation's support.

## Protected contracts and compatibility

### Existing document families

`asset_contracts.versions()` reports Hatch tool version 2.1.0, run schema 3, profile schemas 1/2 and source schema 1. Production schema 1 and workflow/review schema 2 remain independent. Existing 3D rig schemas are version 1. `portable_runs.migrate` specifically supports legacy run schema 2 → 3; it is not a general library migration engine. `production_workflow.migrate_project` has its own production workflow migration. Unknown versions must continue to fail explicitly.

Library adapters should inspect and reference original files under those contracts. New schema families may add library metadata, but cannot require extra fields in old strict objects, invalidate old packages, silently bump versions, or manufacture empty 3D records for legacy 2D assets. Preserve source receipts, state selections, frozen style snapshots, cast/clip identities, original review chains and archive inventories.

### Atlas, states, styles and media

The fixed Codex atlas remains 8×9 cells of 192×208, producing 1536×1872 pixels. Row/state order, counts, millisecond durations, transparent unused cells, exact package files, mirroring restrictions, installation backups and rollback stay authoritative in the existing profile/controller pipeline. `tests/test_rig_compatibility.py` already protects these byte identities and proves 2D discovery without optional 3D imports:

| Frozen file | Baseline SHA-256 |
|---|---|
| `profiles/codex-v1.json` | `f4e0279f8634ea53ef544ecb49b9a71ec2565c61ec5b8e63163ecc5ead478a6b` |
| `profiles/profile.schema.json` | `afba01bc16c4f6c297d1b95b62803c7a5b989e0fa9b967c33e5d50471091163c` |
| `assets/playback.js` | `9aa7d5228de0a57cd443b70c14b160cb22238d21a861a0fb06f6b4bcc6ccbc79` |
| `state-library/catalog.json` | `970139db7291c4233ef75e37ffd6abe0385c8f165dd37b339326a4e8647f3de9` |

The 416 state definitions and 205 selectable style records remain their existing catalogs. State compilation does not generate a 3D clip; the `3d-toy` style does not supply geometry; a style record does not establish a working PBR shader. Rendered 3D frames may enter an explicit existing 2D import workflow with 3D provenance retained, then pass that workflow's validation and review gates.

Legacy production renders layered PNG/PCM. `production_render.mux_video` explicitly maps audio and validates one audio stream, so its audiovisual contract and original speech cannot be changed to satisfy a different subsystem's silent-video requirement. Director/3D silent exports need an explicit separate adapter with zero-audio verification. Current rig previews are real geometry previews, not a general cinematic/PBR renderer or a completed two-scene Asset Library acceptance demonstration.

### Spatial and temporal contracts

| Domain | Existing convention | Asset Library integration boundary |
|---|---|---|
| Legacy profiles | Millisecond raster frame durations | Preserve source timing and label any new explicit conversion. |
| 2D production | Pixels, X right/Y down, clockwise degrees, integer frames and rational FPS, half-open intervals with terminal state at N | Keep `production_performance`/`production_render` authoritative; never reinterpret pixels as meters or frame N as displayed N−1. |
| Rig geometry/transforms | Right handed, X right/Y up/Z forward, meters, radians, XYZW quaternions, column-vector matrices; world = parent-world × local | Reuse `rig_contracts` and `rig_math`; retain bounds, hierarchy, binds and explicit basis. |
| Rig animation | Continuous seconds and integer clip FPS | Declare adapters for exact rational scene timestamps; do not silently rewrite existing clips. |
| Blender | Explicit `rig_math.BLENDER_FROM_CANONICAL` +90° X conversion: Y-up → Z-up, forward Z → −Y | Convert consistently and roundtrip-test geometry, skeletons and animation. |

Asset Library #128 prefers the implemented glTF-compatible Y-up convention. Physics #153 proposes Z-up; that requires an explicit adapter, not a global reinterpretation. Likewise, matching bone names or SemVer alone cannot prove compatible hierarchy, rest transforms, skins, morphs or motion. Reuse actual skeleton/retarget/evaluation validation and retain uncertainty.

### Persistence, paths and dependencies

Existing helpers reject unsafe paths, duplicate keys, nonfinite data and excessive allocations within their documented formats. Preserve exact inventories and limits. There is **no single existing cross-library transaction manager**. Native controller locks, content-addressed rig derivatives, immutable component imports and archive staging are useful foundations; they do not already provide shared-library locking, crash-recoverable filesystem/database commits, safe garbage collection, project dependency lockfiles or deterministic multi-root resolution.

Do not equate atomic replacement with exclusive publication. Production source/project delivery uses `production_sources._rename_no_replace` through its publication helpers. Other owners, including `portable_runs.restore_run`, `rig_package.restore_rig` and `production_bundle.create_bundle`, use an initial destination check followed by `os.replace`. Their existing payload checks are valuable, but they cannot simply be cited as a uniform concurrent-destination guarantee for a new shared library. #141 must establish and test the library's immutable/exclusive publication, race handling, journals, quotas and recovery explicitly, and reuse the strongest compatible primitive without weakening existing formats.

Keep the existing archive families distinct: legacy run ZIP, production project ZIP, multipart project transport, content-addressed source transport, decomposition package and rig package have different inventories and validation. A library wrapper must declare which adapter verified each input and include the new required dependency closure; it must not rename a package and assume equivalence.

Optional NumPy, pygltflib, Blender, Three.js and future provider SDKs stay outside ordinary 2D imports. Use lazy adapters and capability discovery. Runtime enumeration is separate from a real operation probe. Preserve CPU/offline operation, no hidden network calls, explicitly bounded subprocesses and fixture-only automated demonstrations.

## Migration and rollback boundaries

This contribution adds only documentation and actual test/delivery evidence. It does not modify runtime modules, schemas, catalogs, sources, licenses, review history or existing tests. Reverting the audit commit removes its additions without a data migration.

Future library migrations must preview the detected format and proposed adapter/index changes, preserve a verified original/backup and its hashes, write new metadata alongside the old authority, validate the result, and leave rollback possible. Do not rewrite a production `id@version` binding merely because a shared-library asset was updated. Replacement must name explicit consumers, compute impact, preserve the previous binding and publish a new revision. Mutable annotations must not change immutable content digests.

Use the artifact owner's restore routine into a fresh owned destination, then validate source bytes, inventory, code/backend dependency identity and review freshness. Restoring a historical receipt does not approve changed rendering. An incomplete legacy package remains incomplete until the exact legitimate missing bytes are restored and reverified; no fixture, substitute art, invented license or synthesized review repairs that evidence gap.

Deletion/garbage collection requires reference-closure analysis and a recoverable, bounded plan; no current helper supplies a general permission to remove shared blobs or unrelated files. Preserve uncertain generation claims and completed output while canceling only the owning operation's workers. Do not terminate shared WSL instances or unrelated sessions.

## Follow-on implementation and acceptance gates

The next Asset Library task is #138: canonical schemas/resolver and actual-file registration. Import and technical inspection are #139/#140; transactional storage and version lifecycle #141/#142; dependency closure/search #143/#144; previews/browser #145/#146; verified exports/packages #147/#148; production bindings/jobs #149/#150; real demonstration/security/regression acceptance #151/#152. No downstream task is completed by this audit.

Before claiming readiness, those tasks must test missing/corrupt payload and dependency rejection; strict schema/runtime parity; immutable version and annotation separation; actual mesh/skin/morph/material compatibility; unsafe import and archive inputs; concurrent publication and crash recovery; version-pinned shared reuse; bounded reindex/GC; independent export/reload and Blender reopen; truthful preview provenance; complete restored packages with required license/source evidence; and two actual rendered scenes reusing the same real animated asset. The negative demonstration must remove a required payload and reject readiness until its exact bytes return. Numerical or fixture success stays separate from production-art approval, live provider integration and human signoff.
