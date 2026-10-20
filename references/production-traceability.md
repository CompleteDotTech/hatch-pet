# Production requirement traceability

This document maps the user's fifteen production requirements to the current source, tests, documentation, and demonstration evidence. P01–P15 are stable references to the numbered sections of that request. **An implemented interface, a passing synthetic regression, a current production artwork review, and a completed repository delivery are separate outcomes.**

An earlier pre-v3 workspace was lost during development. That separate loss remains disclosed in the acquisition audit. The October 20 public-delivery repair recovered the retained v3 originals, review ledger and hash-bound evidence from authorized preservation objects; see [recovery proof](public-asset-recovery.json). No invented record is used to fill earlier losses. The retained acquisition audit is [`lost-prior-artifacts.json`](../examples/production-pilot/acquisition/lost-prior-artifacts.json). Current original model outputs and new acquisition records belong to the current pilot attempt.

The current delivery report is [`production-public-validation.md`](production-public-validation.md), with [publication and merge state](../DELIVERY_STATUS.md). The original [`production-validation.md`](production-validation.md) remains unchanged historical evidence. This map separates original implementation checkpoints, authentic historical reviews and newly executed public delivery checks.

## Current evidence that can be checked independently

| Evidence | Observed result | Scope |
| --- | --- | --- |
| [`production-baseline-123.log`](../tests/results/production-baseline-123.log) | 123 tests passed, no skips, 140.326 seconds | Fresh baseline regression in the current environment |
| [`production-contracts-regression.log`](../tests/results/production-contracts-regression.log) | 26 tests passed, 1.096 seconds | Current portable contracts, source validation, construction, ownership, continuity, and resource guards |
| [`production-performance-regression.log`](../tests/results/production-performance-regression.log) | 28 tests passed, 1.106 seconds | 22 performance tests and six actual geometry, raster, cue audio, and synthetic demo tests |
| [`production-preview.log`](../tests/results/production-preview.log) | Four tests passed, 4.765 seconds; actual browser 155.0.8059.84 | Real browser controls, pixel changes, timing stall recovery, audio seeking, and reduced motion |
| Complete public production suite | [Current gate and exact reports](production-public-validation.md) | 790 tests passed on each of Linux, macOS and Windows, with zero failures/errors; both complete films and editor handoffs also passed |
| Production pilot evidence | [Original 20-record ledger](../examples/production-pilot/reviews-source-bundle/sources-index.json), [new media provenance](../examples/production-pilot/media/provenance.json) | Authentic assistant decisions and exact supporting images are restored; new sampled visual inspection has its own scope, with no human signoff |
| Merge and default branch | [PR #8](https://github.com/CompleteDotTech/hatch-pet/pull/8) and its linked checks | The PR records the actual review, merge result and resulting default-branch commit; see P15 |

## P01 — Establish the current baseline

**Implementation and retained scope.** The original skill, profile/schema/source contracts, orchestration, extraction, playback/export code, reference documentation, and test inventory remain available in the repository. [`SKILL.md`](../SKILL.md), [`profiles/codex-v1.json`](../profiles/codex-v1.json), [`asset_contracts.py`](../scripts/asset_contracts.py), [`source_interface.py`](../scripts/source_interface.py), and [`prepare_pet_run.py`](../scripts/prepare_pet_run.py) identify the legacy behavior the extension must preserve.

**Evidence.** The fresh baseline run is saved as [`production-baseline-123.log`](../tests/results/production-baseline-123.log): 123 passing tests, no skips. Existing [`tests/baseline.md`](../tests/baseline.md) and [`references/validation-results.md`](validation-results.md) remain historical repository documents; they do not replace the current run.

**Acceptance boundary.** Baseline success establishes the pre-extension reference. The final combined regression must also pass after all production changes; that result belongs to P13.

## P02 — Preserve existing guarantees

**Implementation.** Production uses a separate [`production.py`](../scripts/production.py) CLI, separate schema version, and new cast/clip/scene manifests. The fixed Codex state layout and legacy examples still use the existing profile and hatch commands. Production acquisition bindings in [`production_workflow.py`](../scripts/production_workflow.py) call the existing claim, ingestion, failure, repair, and receipt lifecycle rather than creating an alternate model backend. The imagegen acquisition helper is [`prepare_production_art.py`](../scripts/prepare_production_art.py).

**Evidence.** Legacy coverage includes [`test_profiles.py`](../tests/test_profiles.py), [`test_schemas_and_compatibility.py`](../tests/test_schemas_and_compatibility.py), [`test_raster.py`](../tests/test_raster.py), [`test_raster_strict.py`](../tests/test_raster_strict.py), [`test_workflow.py`](../tests/test_workflow.py), [`test_exports.py`](../tests/test_exports.py), and [`test_playback_extended.py`](../tests/test_playback_extended.py). Production workflow tests `test_claim_retry_preserves_context_original_inputs_and_exact_token`, `test_project_call_budget_counts_failed_claims_after_explicit_repair`, and `test_ingest_uses_native_receipt_contract_and_preserves_unknown_model_metadata` verify that current production bindings preserve acquisition context and failed-call history.

**Limits.** Synthetic imports and fixture receipts retain their fixture flag. Generation is performed through the installed imagegen workflow. Source import, evaluation output, production artwork approval, installation, and live integration remain distinct. No production command implicitly installs a pet or third-party application.

## P03 — Add a versioned cast and project model

**Implementation.** [`production_contracts.py`](../scripts/production_contracts.py) exports `load_project`, `validate_cast`, `validate_clip`, `validate_scene`, `validate_shot`, and the canonical schema definitions. Five [`production-*.schema.json`](../profiles/production-project.schema.json) documents cover project, cast, clip, scene, and shot. File references are portable relative paths with exact SHA-256 hashes; character/prop/clip references select stable semantic versions. The returned bundle shares one cast across all scenes.

**Evidence.** `test_schema_documents_match_the_runtime_contract_and_validate_the_fixture`, `test_two_scenes_reuse_exact_character_versions_and_asset_inventory`, `test_versioned_assets_reject_duplicate_identity_but_allow_a_new_version`, `test_unknown_fields_unsupported_versions_and_boolean_frames_fail_closed`, and the missing/hash/path tests in [`test_production_contracts.py`](../tests/test_production_contracts.py) exercise actual files and failure paths. Workflow archive and import tests verify relocation and retaining older selected character versions.

**Documentation.** [`production-contracts.md`](production-contracts.md) defines the fields, file layout, public bundle API, versions, paths, and diagnostic behavior. Missing leaf sources are reported in explicit diagnostic mode; missing manifest structure, unsafe paths, and conflicting hashes fail in every mode.

## P04 — Add layered character construction

**Implementation.** Cast characters contain named component hierarchies with explicit pivots, parent anchors, offsets, local anchors, drawing variants, masks, z-order, visibility, and role. Identity retains proportions, palette, materials, markings, asymmetries, allowed facings, and mirror prohibition. Costume and viewpoint selection uses compatible authored drawings. [`production_render.py`](../scripts/production_render.py) evaluates the hierarchy and exposes actual world matrices/anchors used to rasterize the frame.

**Evidence.** Contract tests reject cycles, missing grandparents, broken anchors, mismatched replacement viewports, invalid masks, undeclared views, and forbidden root facings. Renderer tests `test_parent_pivot_anchor_camera_and_cast_scale`, `test_mask_alpha_and_filter_edges_with_a_one_image_cache`, and `test_inherited_visibility_and_explicit_hidden_tracks_change_pixels` inspect geometry and actual pixels. The synthetic regression project has two versioned characters and nine independently controllable components per character.

**Production scope and limits.** Current pilot construction uses actual generated part artwork retained under `art/originals/` after [verified source restoration](../examples/production-pilot/source-bundle/sources-index.json) and explicit derived components under `art/components/` after [exact project restoration](../examples/production-pilot/project-source-bundle/sources-index.json). The pilot's final joint placement is being repaired and must receive its own final artifact review. The renderer does not invent a back view, mirror an asymmetric drawing, or automatically prove visual identity from metadata.

## P05 — Add practical coverage planning

**Implementation.** `planned_requirements` and `incompatible_requirements` in [`production_performance.py`](../scripts/production_performance.py) preserve independent dimensions and exact temporal intervals. `coverage_report` in [`production_workflow.py`](../scripts/production_workflow.py) separates reusable, missing, incompatible, and unreviewed work, deduplicates shared requirements, and reports bounded generation work. Character reviews bind advertised capability/restriction declarations.

**Evidence.** `test_planned_coverage_is_independent_and_binds_intervals_character_versions_and_sources` limits the minimal example's requirements without multiplying states. `test_restriction_requires_temporal_overlap_of_independent_dimensions` distinguishes simultaneous from sequential incompatible choices. Workflow tests `test_missing_coverage_deduplicates_across_scenes_and_bounds_retries`, `test_coverage_reports_when_missing_work_exceeds_project_call_bound`, `test_new_declared_coverage_needs_review_without_invalidating_unused_shots`, and `test_missing_unused_drawing_does_not_invalidate_shot_dependencies` exercise planning and selective reuse.

**Limits.** Capability metadata is a planning claim until supported by current sources and scoped review. Coverage does not silently synthesize every action/view/expression/mouth combination or treat numerical geometry checks as artwork approval. See [`production-operations.md`](production-operations.md).

## P06 — Add reusable motion and transitions

**Implementation.** Clips support loop, once, and hold behavior; entry and exit points; start/end poses; root displacement; component tracks; contact intervals; exact event markers; bounded numeric transitions; explicit full-frame artwork; and interruption policies. The shared evaluator accumulates completed root motion and overlays shot properties independently.

**Evidence.** [`test_production_performance.py`](../tests/test_production_performance.py) tests idle/walk/stop displacement, hold entry events, once completion modes, early one-shot and midcycle loop interruption, compatible exits, pose mismatch admission, step jump rates, and moving-target interpolation at every adjacent blended frame. The synthetic `locomotion`, `sit-stand`, and `reach-grasp-release` shots exercise actual rendered sequences. Four planted stance intervals are measured at zero world-anchor drift by `inspect_regression_behaviour`; `test_planted_foot_check_catches_a_real_stance_compensation_error` deliberately breaks the compensation and requires failure.

**Limits.** Drawing changes need authored transition artwork when numerical blending is unsuitable. Contact locking uses explicit authored compensation; there is no automatic motion synthesis or inverse kinematics. The production pilot advertises only clips and views actually present in its cast and clip manifests.

## P07 — Add facial performance and dialogue

**Implementation.** Independent `body`, `face`, `gaze`, and `mouth` tracks control different component properties. Shot overrides preserve unrelated clip channels. Audio cues retain exact source hashes, text, speaker IDs, frame intervals, gain, provenance, and compatible mouth shapes. Offline PCM mixing maps rational FPS to exact sample boundaries, preserves editable timing, and records clipping.

**Evidence.** Performance tests `test_body_face_gaze_and_mouth_channels_remain_independent`, `test_shot_mouth_override_preserves_clip_body_and_cast_scale`, `test_dialogue_preserves_editable_cues_and_explicit_mouth_overrides`, and `test_offline_pcm_matches_cue_start_end_samples_and_exact_total_duration` validate independent behavior and actual PCM. The synthetic `facial-dialogue` shot returns brows from neutral to reaction to neutral while gaze, head acting, and alternating speaker mouth tracks remain separate. Browser `test_audio_seek_is_stable_and_reduced_motion_does_not_autoplay` runs against actual browser media.

**Production scope and limits.** Current pilot audio sources and original text are retained in [`audio/`](../examples/production-pilot/audio/) and [`audio/original/`](../examples/production-pilot/audio/original/). The synthetic demo uses square-wave cues and claims no speech. The production pilot uses authored mouth timing rather than automatic phoneme recognition; final convincing dialogue and AV review remain separate from sample counts. No human or auditory review is inferred from PCM tests.

## P08 — Add coordinated interactions

**Implementation.** Props have one explicit owner and attachment. Ownership changes bind previous/new owner, the exact frame, and a shared interaction with named participants, component anchors, clip markers, target position, and tolerance. Clip target names bind to actual shot prop instances. Runtime frame evaluation checks reachability and rejects ownership position jumps beyond two world pixels.

**Evidence.** Contract tests require matching ownership chains, attachments, both handoff participants, and actual markers on the shared frame. `test_shared_handoff_positions_ownership_and_prop_scale` in [`test_production_render.py`](../tests/test_production_render.py) checks rendered attachment geometry. Synthetic pickup/release at frames 24/42 has zero-distance contacts; `test_grasp_render_fails_when_the_hand_does_not_reach_the_owned_prop` changes the reaching offset and requires a discontinuity error. The minimal two-scene fixture passes the cup between characters and preserves the final owner across the scene link.

**Production scope and limits.** [`contact-frame-84.json`](../examples/production-pilot/evidence/contact-frame-84.json) records current authored pilot contact geometry. The final visible hand/object overlap still requires inspection of the exact completed render. Open-paw or limited hand art must not be described as a fully articulated grasp merely because its anchor reaches the object.

## P09 — Add scenes, shots, cameras, and continuity

**Implementation.** Scenes order shots; shots place shared character versions, reusable clips, props, foreground/background layers, audio, and bounded camera pan/zoom. Parallax is explicit per scenery layer. Continuity links can require costume, scale, world position, and prop ownership across shots or scenes. Lighting direction and color treatment are authored declarations carried with the shot.

**Evidence.** Contract tests check camera rate/zoom limits, cross-scene scale and position, and prop ownership separately. Renderer tests check camera/parent transforms and exact scene-cut assembly. `test_scene_cut_and_hardlink_fallback_are_exact_and_atomic` verifies identical scene/shot pixels and safe copy fallback. Current synthetic scenes share one cast, and the new performance reel contains five editable shots.

**Production scope and limits.** Current pilot scene manifests are [`seed-exchange.json`](../examples/production-pilot/scenes/seed-exchange.json) and [`garden-promise.json`](../examples/production-pilot/scenes/garden-promise.json): 432 and 264 frames at 12 fps, respectively, using the same two character versions. Lighting metadata does not perform automatic relighting of painted assets. Final continuity approval depends on the exact repaired films.

## P10 — Add deterministic rendering and a usable local review workflow

**Implementation.** [`production_render.py`](../scripts/production_render.py) renders bounded RGBA PNG frames, per-track layer images, exact frame provenance, PCM audio, scene manifests, contact sheets, and optional inspected MP4 review copies. Checkpoints bind renderer identity, sources, frame state, output hashes, and dependencies. Partial runs resume; unaffected frames can reuse matching pixels. [`production-preview.html`](../assets/production-preview.html) and [`production-preview.js`](../assets/production-preview.js) provide scrub/step/playback, source inspection, track visibility, pinned comparison, audio seeking, and reduced-motion handling.

**Evidence.** Renderer tests cover interrupted checkpoints, tampered-frame recovery, source edits affecting only used drawings, FPS-only pixel reuse, bounded caches, corrupt/foreign output destinations, exact scene cuts, real audio bytes, and actual movie stream timing. Four current real-browser tests are saved in [`production-preview.log`](../tests/results/production-preview.log); they include real pixel changes and a stalled main thread. The complete synthetic render was freshly exercised through validation and an all-frame reuse pass.

**Editable handoff.** [`production_adapter.py`](../scripts/production_adapter.py) exports lossless image/audio sequences and layered OpenRaster snapshots with timing/provenance. [`test_production_adapter.py`](../tests/test_production_adapter.py) verifies archive structure, layer order, exact pixel roundtrip, edited-layer roundtrip, relocation, timing/metadata consistency, and malicious archive rejection. Live Krita exercise is separately capability-gated; an exported handoff and local archive roundtrip do not establish that an unavailable external application was run. The offline PNG/WAV masters remain authoritative for timing and alpha.

## P11 — Extend review and change tracking to production scope

**Implementation.** [`production_workflow.py`](../scripts/production_workflow.py) provides scoped character/component/clip/shot reviews, independent review dimensions, append-only hash-chained receipts, dependency snapshots, impact reports, versioned component import, generation binding, migration, and verified archive/restore. Exact render identity, output pixels, audio counts, timing, and selected sources bind final artifact review. Unrelated drawings or unused character versions do not invalidate a shot.

**Evidence.** Workflow tests include `test_camera_change_invalidates_only_its_shot_and_review_dimensions`, `test_component_review_tracks_ancestor_construction_but_not_siblings`, `test_final_artifact_review_binds_exact_rendered_bytes`, `test_old_render_cannot_support_review_after_camera_change`, `test_human_or_assistant_identity_cannot_promote_automated_checks`, `test_review_history_is_append_only_and_detects_receipt_tampering`, and `test_restore_reports_stale_cached_shots_and_scenes_even_with_same_renderer`. Import and archive tests preserve old selections and reject unsafe or active acquisition archives.

**Transport.** [`production_bundle.py`](../scripts/production_bundle.py) verifies ordered bounded parts and the complete archive hash before delegating to the existing guarded restore. [`test_production_bundle.py`](../tests/test_production_bundle.py) exercises identity/review/dependency roundtrips, tampered or missing parts, duplicate JSON keys, noncanonical archive names, oversized members, traversal, symlinks, and destination preservation. A bundle transports complete assets and masters; an acceptance receipt inside it remains valid only for the exact restored artifacts and current dependency identity.

## P12 — Produce two kinds of demonstrations

### A. Deterministic regression demonstrations

**Implementation.** [`production_fixture.py`](../scripts/production_fixture.py) builds the minimal two-character, two-scene cup handoff. [`production_regression_demo.py`](../scripts/production_regression_demo.py) extends it into a three-scene, 300-frame fixture project with a 276-frame/23-second main reel: idle/walk/stop, stand/sit/stand, reach/grasp/hold/release, independent facial/body/gaze/mouth acting and alternating cue audio, plus an explicit full-frame override. Rebuild with `python scripts/production_regression_demo.py --output-dir examples/production-fixture --movie`.

**Evidence.** The six `ProductionRegressionDemoTests` in [`test_production_performance.py`](../tests/test_production_performance.py) compare real raster changes, exact layered override boundaries, deterministic source inventories, world-space planted feet, failed grasp geometry, and PCM start/end sample values. The full generator has also freshly rendered all 300 frames, validated each scene, resumed with zero newly rendered frames, and recorded synthetic scoped reviews producing ready coverage.

**Delivery boundary.** The final fixture directory should retain editable source, performance evidence, coverage/dependency/acceptance reports, storyboards, and review movies. If complete master frames/layers/reviews are delivered in `complete-project/production-bundle.json` and numbered parts, restore that bundle before following master preview paths or requesting current artifact review status. Every fixture receipt identifies synthetic automated evidence; none is production art acceptance.

### B. Production-art pilot

**Current implementation.** [`production_demo.py`](../scripts/production_demo.py) builds the current two-character pilot from retained actual imagegen originals, explicit crop/placement provenance, versioned cast construction, reusable clips, scenery, camera/shot timing, interactions, and original dialogue sources. The current attempt acquired four model outputs: Milo and Luma identity images and component boards. The original files remain under `art/originals/` after [verified source restoration](../examples/production-pilot/source-bundle/sources-index.json); prompts, handoffs, native acquisition state, provider metadata or explicit unavailability, and failed prior-attempt audit remain under [`acquisition/`](../examples/production-pilot/acquisition/).

**Authored duration and reuse.** The first scene is 36 seconds/432 frames; the second is 22 seconds/264 frames, at 12 fps. Both select the same `milo@3.0.0` and `luma@3.0.0` cast entries. The retained model contains twenty reusable clips and five shots. Both public films are reproduced from these exact shared selections. Counts describe the authored project; review status remains scoped to its actual records.

**Current acceptance boundary.** All five original-source transports, the original assistant ledger and its supporting evidence are public and hash-verified. Both [public films, storyboards and drawings](../examples/production-pilot/README.md#completed-films-and-inspectable-outputs) are actual complete CI outputs; all 696 Linux frame hashes match the historical shot-review dependencies. Current sampled inspection is recorded separately in media provenance. Limited frontal cutouts, hand/mouth variants, absent auditory listening and absent human signoff remain explicit. The original ledger is never rewritten to approve a changed renderer.

## P13 — Validate comprehensively

**Implementation and test inventory.** Validation spans the legacy baseline; JSON Schema/runtime contracts; malformed paths/hashes/resources; hierarchy and pivots; independent coverage; modes, transitions, interruptions, and actual stance geometry; independent acting and cues; contact synchronization; scene/camera/continuity; renderer caching/resume/tampering; real browser controls; offline PCM and movie stream timing; editable handoff; scoped review and selective invalidation; import/acquisition binding; archive/bundle restoration; and CLI failure paths.

**Current owned evidence.** The fresh saved contract and performance logs cover 54 tests. The fresh baseline covers 123 tests, and the preview log covers four actual browser tests. Workflow, renderer, adapter, bundle, CLI, and any newly added source-transport or pilot-specific tests belong in the complete final regression run. Test discovery totals must come from that final saved run, with every skip and unavailable optional consumer stated explicitly.

**Delivery gate.** The [automated public verifier](../scripts/verify_public_delivery.py) validates every fragment and public media hash, the complete regression suite, exact project restoration, both full layered films, PCM counts, repeat reuse, FFmpeg streams and complete editor handoffs. [Current validation](production-public-validation.md) binds results to actual commits and reports. Numerical checks do not supply auditory review, human approval or native editor integration.

## P14 — Update the skill and documentation

**Documentation implemented.** [`production-contracts.md`](production-contracts.md) covers schema, paths, public APIs, coordinate/scale conventions, layered construction, viewpoint/costume identity, independent coverage, clips/interruption, ownership contacts, dialogue, overrides, and bounds. [`production-operations.md`](production-operations.md) covers CLI usage, coverage/generation budgets, scoped review, change tracking, source import, recovery, migration, archives, and bundles. Renderer/adapter/preview instructions belong in [`production-rendering.md`](production-rendering.md). This file maps all fifteen requirements to implementation and evidence; [`production-public-validation.md`](production-public-validation.md) reports the current public delivery, while the original report remains historical.

**Public instructions.** The repository README, [pilot recipe](production-pilot.md) and [demonstration index](../examples/production-pilot/README.md) document ordinary-Git distribution, exact restoration, both renders, original acquisition and speech metadata, historical review inspection, portable exports and optional editor integration. Source paths materialized by restoration are identified as outputs; public movies and evidence use actual repository links.

## P15 — Commit, push, merge, and synchronize

**Delivery record.** [PR #8](https://github.com/CompleteDotTech/hatch-pet/pull/8) is the authoritative review and merge record for the public delivery. [Delivery status](../DELIVERY_STATUS.md) identifies recovery, publication and validation evidence; the PR's checks and merge commit establish the exact reviewed/default revision. Publication uses complete Git trees only after all payload hashes and automatic approvals succeed. The original historical report is not edited to fabricate a later merge.

The public repository retains original source transports, acquisitions, audio attribution, the authentic review chain, cast/clip/scene JSON and actual review movies. Complete master frames, PCM, browser previews and editor handoffs are reproducible from a fresh checkout. The final default-branch verification is recorded on the PR after its merge; no implementation-only checkpoint substitutes for that verification.
