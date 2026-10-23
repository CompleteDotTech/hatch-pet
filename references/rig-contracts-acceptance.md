# Rig contract and compatibility acceptance

This audit covers [issue #51](https://github.com/CompleteTech-Skills/hatch-pet/issues/51), work package 1 of the [3D rigging mission](https://github.com/CompleteTech-Skills/hatch-pet/issues/11). The audited base is `7b966a639bcaf23bd3a0d037f46f29e2edfcc273`. Evidence was collected on 2026-10-22. The implementation/test file hashes, commands, environment, test results and exported artifact hashes are retained in [results.json](../tests/results/rig-contracts-20261022/results.json).

The base already contains the mesh rigging engine and most required contracts. This contribution repairs two observable contract defects: unused IK declarations could pass structural validation, and `RigExportReceipt` was an alias for a validation report that rejected the actual exporter output. The new regressions reproduce these boundaries using real mesh fixtures and export bytes.

Independent review of the initial PR head `287b25c8257302f1ee620ca422a53996caeb1a72` found a further unused-chain boundary: distinct valid bones could have coincident evaluated rest origins and pass declaration validation while failing the solver's existing length guard. [The finding](https://github.com/CompleteTech-Skills/hatch-pet/pull/200#pullrequestreview-5619512428) and [independent corroboration](https://github.com/CompleteTech-Skills/hatch-pet/pull/200#pullrequestreview-5619567130) are addressed by sharing the evaluated segment-length guard between rest declaration validation and runtime IK. The original [83-test source/evidence record](../tests/results/rig-contracts-20261022/results-before-ik-length-review.json) is retained as historical evidence for that pre-fix head; it is superseded by the current 86-test record linked above.

## Current compatibility baseline

The actual catalog loader validates **416 states, 408 aliases, 16 packs and nine animation recipes** at catalog version `1.0.0`. These are definitions and recipes, not 416 completed 3D animations. The Codex atlas remains eight columns by nine rows, with 192 by 208 pixel cells: **1536 by 1872 pixels**, the same nine state IDs and all original frame durations. The `running` state continues to mean task processing. Existing 2D pixel coordinates and timing remain separate from the meter/second 3D contracts.

[compatibility.json](../tests/results/rig-contracts-20261022/compatibility.json) records byte equality against the base commit for all 11 existing non-rig profile/schema JSON files, the catalog and `assets/playback.js`. The following established anchors retain their hashes:

| File | SHA-256 |
| --- | --- |
| `profiles/codex-v1.json` | `f4e0279f8634ea53ef544ecb49b9a71ec2565c61ec5b8e63163ecc5ead478a6b` |
| `profiles/profile.schema.json` | `afba01bc16c4f6c297d1b95b62803c7a5b989e0fa9b967c33e5d50471091163c` |
| `assets/playback.js` | `9aa7d5228de0a57cd443b70c14b160cb22238d21a861a0fb06f6b4bcc6ccbc79` |
| `state-library/catalog.json` | `970139db7291c4233ef75e37ffd6abe0385c8f165dd37b339326a4e8647f3de9` |

The fresh `python scripts/production_sources.py verify-delivery` run succeeds. [Its complete report](../tests/results/rig-contracts-20261022/source-delivery.json) verifies the original Milo/Luma payload, seven public files, five original audio recordings, and the 20-record historical review chain. It records `fixture: false`, `provider_called: false`, `tts_called: false`, `new_approval_recorded: false` and `visual_review_performed: false`. This verifies byte integrity and retained provenance. It does not add a current visual verdict or human signoff. The missing production-media error in the historical [initial rig audit](3d-rigging-audit.md) was repaired before the current base and is not a current blocker.

The independent physics-baseline workstream ran the complete unchanged-base 2D gate: **790 tests, zero failures/errors and one optional native-Krita skip**, in 282.918 seconds, using actual Chromium 140. Its [immutable log](https://github.com/CompleteTech-Skills/hatch-pet/blob/6951b198f6bab4c89fd9bf0ce848b336d6ae0308/tests/results/physics-baseline-20261022/compatibility-2d.log) and [execution record](https://github.com/CompleteTech-Skills/hatch-pet/blob/6951b198f6bab4c89fd9bf0ce848b336d6ae0308/tests/results/physics-baseline-20261022/compatibility-2d.json) identify base `7b966a6`. That is an inherited baseline, not a claim that this contribution reran all 790 tests. The changed-source rig suite below reruns the four legacy isolation/byte-preservation tests and discovers all 790 2D cases without optional 3D dependencies. No 2D implementation or contract file changes in this contribution.

## Contracts and transform rules

`scripts/rig_contracts.py` defines strict version-1 `Rig`, `Character3D`, `GeometryAsset`, `Skeleton`, `Bone`, `SkinBinding`, `VertexInfluence`, `RigController`, `IKChain`, `JointConstraint`, `Pose`, `AnimationClip`, `RigValidationReport`, `RigCorrection`, `RigReviewReceipt`, `RigJob` and export types. Related attachment, facial, morph, event, contact, retarget and provenance definitions remain available. Generated schema entry points are `rig`, `rig-template`, `rig-animation`, `rig-correction`, `rig-job`, `rig-review`, `rig-pose`, `rig-retarget` and the new `rig-export`.

`RigExportReceipt` now selects exactly one real adapter shape: `RigGltfExportReceipt` or `RigBlenderExportReceipt`. Native receipts preserve all existing fields and normalize the accepted filename suffix to `glb` or `gltf`. They keep `independently_verified: false`. Blender receipts preserve all existing successful return fields and add the version and `blend` format discriminator. The reopen case requires comparison distances, sample count, tolerance and round-trip path/hash; the creation-only case cannot carry those reopen fields. Both producers validate the completed receipt before returning it. A numerical validation report cannot be used as an export receipt, and a native receipt cannot claim an independent review by toggling its flag.

The native `joints` field retains its established meaning: the count of all exported skeleton bone/nodes, including a nondeforming root. It is not the count of unique indices in glTF `skins[].joints`. In the robotic workflow below, seven skeleton nodes include six deform joints; Blender reports the six bones in its actual imported armature. These are different, documented observations of the same export.

The coordinate contract is unchanged:

| Property | Contract and implementation |
| --- | --- |
| Axes and units | Right-handed, +X right, +Y up, +Z forward; meters, radians and seconds |
| Quaternion | Unit XYZW; malformed/nonfinite/zero rotations rejected |
| Rest and pose | Local TRS; pose fields are absolute local overrides, omitted fields use rest |
| Composition | Column vectors; `world = parent_world @ local` |
| Bind transforms | Skinning applies joint world transforms and inverse binds to actual mesh vertices; bind-pose reconstruction is checked |
| Matrix storage | Python row-indexed arrays; glTF MAT4 buffers are column-major |
| Blender adapter | Proper +90-degree X rotation: `(x, y, z)` maps to `(x, -z, y)` |
| Invalid skeletal transforms | Singular scales, nonfinite numbers, shear/reflection in skeletal rest transforms, duplicate bones, bad parents and hierarchy cycles fail |
| Resource boundary | Source/dependency hashes and identity are checked; traversal, symbolic links, unsupported required extensions and resource-budget violations fail |

JSON Schema validates structural shape. Runtime validators add graph, quaternion, transform, bind, identity and filesystem semantics. Every declared IK chain now receives those semantic checks during `validate_rig`, including chains unused by all animations. IDs must be unique, bone references must be valid and distinct, the chain must follow direct parents, two-bone solvers require three bones, and optional orientation must be a unit quaternion. Evaluated rest-pose distances between consecutive joint origins must each be strictly greater than `1e-8` meters. The same helper preserves that existing guard for the supplied runtime pose in `solve_ik`; it does not replace or weaken runtime checking. The GLB/glTF export boundary applies controller validation before replacing the destination. Blender receives the same validation through its native intermediate export.

## Requirement-to-test traceability

| Issue #51 task | Implementation and evidence | Executed coverage |
| --- | --- | --- |
| 1. Actual baseline; fixed atlas and 2D schemas | Catalog loader, source-delivery verifier, protected-byte snapshot; inherited full 2D baseline above | `test_rig_compatibility.py` checks fixed bytes, optional-dependency isolation, structured CLI errors and discovery of all 790 2D cases; source-delivery command succeeds |
| 2. Rig/skeleton/bone/binding/controller/pose/clip/review/job/export contracts | `rig_contracts.py`, generated `profiles/rig*.schema.json`; native and Blender producers | `test_rig_contracts.py`, strict unknown/nonfinite workflow cases, job/review/HTTP tests, schema regeneration check |
| 3. Quaternion/rest/local/world/inverse-bind/unit/basis rules | `rig_math.py`, `rig_skeleton.py`, `rig_skinning.py`, glTF and Blender adapters | Literal matrix and pivot expectations; parent rotation without mutation; antiparallel/SLERP cases; bind reconstruction; actual Blender and Three.js vertex comparisons |
| 4. Reject cycles, invalid references, singular transforms and unsafe resources | Skeleton/controller validators, safe-path/import/package boundaries | Duplicate/cycle/missing-parent tests; new unused-IK and preserved-output negatives; singular/NaN/shear cases; wrong joint/inverse bind; traversal, symlink, truncated container and archive tampering cases |

The new contract tests check five invalid declaration classes: a missing bone, duplicate chain ID, disconnected chain, repeated bone and zero orientation. They prove `validate_rig` fails at the structural check even when clips have no contacts, and that export leaves an existing destination byte-for-byte intact. Actual native GLB and glTF receipts pass the published schema, match the written bytes and load with independent `pygltflib` skins, joints and animation channels. Malformed hashes, formats, versions, counts, unknown fields and unearned verification claims fail. Retained Blender evidence tests the required reopen fields; fresh opt-in Blender tests execute both verification modes.

Three additional tests cover the reviewed length boundary using generated, rebound, saved and reloaded rigs with no clips. Both two-bone and FABRIK reject rest segments of `0`, `1e-9` and exactly `1e-8` meters, report `RIG_IK_LENGTH`, and preserve existing GLB and glTF output bytes. Segments of `1.01e-8` and `1` meter remain valid, solvable and exportable. Runtime pose overrides that collapse either segment are still rejected for both solvers. On the previous implementation, the expanded eight-test contract suite produced [six failing boundary subcases](../tests/results/rig-contracts-20261022/ik-length-review/before.log); after the fix [all eight tests pass](../tests/results/rig-contracts-20261022/ik-length-review/contracts.log).

## Executed validation and real workflows

The complete changed-source rig suite passed **86 tests in 14.907 seconds, zero failures/errors/skips**. [The current full log](../tests/results/rig-contracts-20261022/ik-length-review/rig-suite.log) records all cases. It includes actual loopback HTTP requests, Blender 4.5.3 LTS save/reopen and CPU rendering, creation-only Blender receipts, Chromium 140.0.7339.16 playback/skinned vertices, Khronos `2.0.0-dev.3.10` and pygltflib `1.16.5`. The schema and template `--check` commands and `git diff --check` also pass. The schema-math CI group now includes `test_rig_contracts.py`.

The initial restricted-environment run had four HTTP setup errors because the sandbox prohibited `socket.socket`; Blender tests passed, and two browser/validator opt-in tests were disabled. That [failed attempt](../tests/results/rig-contracts-20261022/rig-suite-sandbox-blocked.log) is retained separately and is not passing evidence. The successful run used authorized loopback access and enabled all optional integrations. The Playwright installer recovered from a truncated primary-CDN response using its fallback CDN; the tested runtime is the matching 1187 headless shell, without source or test monkeypatching.

A fresh CLI robotic demonstration then exercised genuine geometry generation/import, skeleton fitting, binding, authored clips, numerical validation, native GLB/glTF export and actual Blender export/reopen. It contains 706 vertices, 1,368 triangles, seven native joints and three executable clips. Numerical validation reports zero hierarchy/reference/nonfinite errors and ten distinct sampled poses. The native GLB has zero Khronos errors/warnings and one informational unused-material message. Blender reopened 11 skinned meshes and compared **2,376 vertex samples**: maximum vertex error `0.000016416032056674572 m`, maximum joint error `0.00001339864477991747 m`, both below `0.01 m`. Its intermediate GLB hash equals the separately exported native CLI GLB hash below.

After the IK review fix, the saved fixture was loaded again and all three export formats were freshly written to a separate destination. The current native files retain the same hashes, the new Blender save/reopen reproduces the same measured errors and sample count, and its new file hash is recorded below. The original demonstration and export receipts remain in the parent evidence directory as pre-fix evidence; current receipts are under `ik-length-review/`. The new exports reuse the exact source fixture, not the previously exported output bytes.

| Artifact | Exact SHA-256 | Receipt |
| --- | --- | --- |
| Native animated GLB | `88e715465fa22d7a0c4aa177310696af45813e620d632bcdee906ce3676a268c` | [GLB](../tests/results/rig-contracts-20261022/ik-length-review/glb-export.json) |
| Embedded-buffer glTF | `fb37f137013ce739745044b315867e8aeec2384867b64eac67ae10f38ed23029` | [glTF](../tests/results/rig-contracts-20261022/ik-length-review/gltf-export.json) |
| Reopened Blender project | `4511758f8e9aaf122a4eb8f1a996b1e5a3dd788710ab79ac2c75253cce106ead` | [Blender](../tests/results/rig-contracts-20261022/ik-length-review/blender-export.json) |
| Blender round-trip GLB | `f45bcf21854434255f3264f2dd780e59937aa400a2166446ea5612c64bb1bdaf` | [Blender](../tests/results/rig-contracts-20261022/ik-length-review/blender-export.json) |

Each receipt was schema-validated and its hash recomputed from the actual file. Generated binary artifacts remain at the recorded local paths; the full JSON evidence and logs are committed. New runs create new timestamped fixture provenance and Blender metadata, so their byte hashes may differ. No binary from the earlier baseline was substituted for the new workflow.

## Reproduction and scope

Install the [pinned optional tools](../tools/rig/README.md), set `HATCH_BLENDER` to the verified Blender executable and use the matching Playwright browser cache. From the repository root:

```bash
python scripts/generate_schemas.py --check
python scripts/generate_rig_templates.py --check
HATCH_RIG_INTEROP_TEST=1 HATCH_RIG_BLENDER_TEST=1 HATCH_RIG_BROWSER_TEST=1 \
  python -m unittest discover -s tests -p 'test_rig_*.py' -v
python scripts/production_sources.py verify-delivery
python scripts/rig.py demo --archetype robotic --destination output/rig-contract-check
python scripts/rig.py export --run-dir output/rig-contract-check --format glb \
  --destination output/rig-contract-check/exports/character-cli.glb
python scripts/rig.py export --run-dir output/rig-contract-check --format gltf \
  --destination output/rig-contract-check/exports/character.gltf
python scripts/rig.py export --run-dir output/rig-contract-check --format blender \
  --destination output/rig-contract-check/exports/character.blend
python scripts/rig.py export-validate --file output/rig-contract-check/exports/character-cli.glb
```

Use a fresh demonstration destination. The original generation commands used `/workspace/scratch/36752e25b9f2/hatch-rig51-evidence`. The post-review export commands loaded that saved fixture and wrote new outputs under `/workspace/scratch/36752e25b9f2/hatch-rig51-ik-review`; exact commands and the pinned environment are listed in `results.json`.

The numerical and export evidence uses explicitly synthetic engineering geometry. Production anatomical/visual acceptance, all downstream work packages #52–#58, live external game-engine integrations and the overall parent mission remain separately scoped. The existing [interoperability and diagnostic limitations](3d-rigging-acceptance.md#known-limitations-and-unverified-scope) still apply. Independent PR review, required remote CI and merge verification are evaluated on the submitted commit; this local report does not assert those future gates passed.
