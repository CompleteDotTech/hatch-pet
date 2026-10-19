# Capability revision acceptance map

The starting checkout was clean at `3d226b1`. A fresh run of `python -m unittest discover -s tests -v` passed all 67 tests, including Chromium playback (64.506 s). Historical `tests/baseline.md` describes earlier revisions, not this baseline.

| Limitation / improvement | Classification and implementation | Documentation | Acceptance evidence |
| --- | --- | --- | --- |
| L01 / I01 source interface | Engineering gap: [source_interface.py](../scripts/source_interface.py), [hatch.py](../scripts/hatch.py) import receipts and image/strip/frame normalization | [Sources](sources-and-identity.md) | `test_import_origin_is_distinct_and_source_still_gets_reviewed`, import rejection and all fixture-import demos |
| L02 / I02 identity | Metadata gap: [asset_contracts.py](../scripts/asset_contracts.py), [prepare_pet_run.py](../scripts/prepare_pet_run.py); visual identity remains a human judgment | [Identity](sources-and-identity.md) | `test_structured_identity_roles_and_constraints_survive_retries`, conflicts and role tampering tests |
| L03 / I03 extraction | Conservative default intentional: [extraction_annotations.py](../scripts/extraction_annotations.py), [extract_strip_frames.py](../scripts/extract_strip_frames.py), [inspect_frames.py](../scripts/inspect_frames.py) | [Extraction](extraction-and-review.md) | exact component/invalid override and diagnostic tests; every use imports annotated fixtures |
| L04 / I04 scaling | Engineering gap: [profile_spec.py](../scripts/profile_spec.py), [extract_strip_frames.py](../scripts/extract_strip_frames.py), `hatch.calibrate` | [Calibration](extraction-and-review.md) | nearest palette, shared body scale, retained jump displacement and viewport bounds tests |
| L05 / I05 review | Semantic assurance inherently visual: [review_ui.py](../scripts/review_ui.py), [review.html](../assets/review.html), `hatch.review` | [Review](extraction-and-review.md) | `test_review_ui_steps_frames_and_binds_downloaded_evidence`, review freshness and dimensions tests |
| L06 / I06 invalidation | Confirmed coupling defect: `hatch.inputs`, `descendants`, `configure`, `revise_profile`; extraction projections in [asset_contracts.py](../scripts/asset_contracts.py) | [Dependencies](portability-and-operations.md) | independent/actual mirrors, calibration-only and playback/export revision tests |
| L07 / I07 portability | Engineering gap: [portable_runs.py](../scripts/portable_runs.py), relative extraction references | [Migration](portability-and-operations.md) | full archive exact-review roundtrip, version change, tampering/traversal and schema-2 migration tests |
| L08 / I08 playback | Engineering gap; physical browser precision inherent limit: [playback.js](../assets/playback.js), [export_assets.py](../scripts/export_assets.py) | [Playback](playback-and-extensions.md) | [test_playback_extended.py](../tests/test_playback_extended.py), existing exported browser test |
| L09 / I09 operations | Engineering gap: [doctor.py](../scripts/doctor.py), [asset_contracts.py](../scripts/asset_contracts.py), `hatch.configure_limits` | [Operations](portability-and-operations.md) | doctor, resource, limit, active token and original crash/rollback tests |
| L10 / I10 extension | Intentional bounded registry: [asset_exporters.py](../scripts/asset_exporters.py), [generate_presets.py](../scripts/generate_presets.py), [demonstrate.py](../scripts/demonstrate.py) | [Extensions](playback-and-extensions.md) | all [demonstration tests](../tests/test_demonstrations.py), schemas and local consumer browser tests |

| Use | Preset / demonstration | Shared output | Automated acceptance |
| --- | --- | --- | --- |
| U01 assembly | presets/assembly.json | print cards + step metadata | order, labels, PDF pages |
| U02 science | presets/process.json | annotated process cards + browser | stage order, content-review declaration |
| U03 configurator | presets/configurator.json | selectable browser variants | stable viewpoint geometry, approved palette differences |
| U04 flipbook | presets/flipbook.json | flipbook PDF + zoetrope strip | frame order, dimensions, print geometry |
| U05 communication | presets/communication.json | selectable board + stills | accessible labels and static alternatives |
| U06 perception | presets/perception.json | stimulus CSV + browser | conditions, hashes, intended timings and limitations |
| U07 regression | presets/regression.json | alpha/holes/detail/encoding fixtures | pixel and codec reconstruction |
| U08 cursor | presets/cursor.json | animated cursor + local consumer | binary structure, hotspots, timing, pixels |
| U09 protocol | presets/protocol.json | legal-event browser state machine | legal/illegal transitions and completion |
| U10 craft | presets/craft.json | grid PDF/PNG + palette legend | palette membership, grid dimensions and counts |

`python scripts/demonstrate.py --all --output-dir output/capability-demos` runs all deterministic uses and writes per-use acceptance evidence. Final execution evidence is recorded in `references/validation-results.md`. No fixture result certifies production artwork, expert content review, installation, or external integration.
