# 3D rigging acceptance and limitations

## Result and evidence boundary

The repository now contains an optional, reusable 3D mesh rigging and skeletal animation engine, with real skin weights, FK/IK, facial and appendage controls, executable animation channels, retargeting, editable Blender files and an offline Three.js review application. The retained humanoid, quadruped and six-legged winged character each execute six distinct named motions. A mechanical arm/gripper and two proportionally different retarget targets provide additional coverage.

**Automated engineering fixture acceptance has passed. Production visual acceptance remains pending.** These characters are explicitly procedural engineering fixtures. No production-art approval, human signoff, deployment or merge is implied. The implementation's unsupported cases and authoring limitations are listed below rather than hidden behind the fixture result.

The primary machine-readable evidence is [demo acceptance](../examples/rig-3d/acceptance.json). Each fixture retains the original source GLB, source-bound landmarks, exact geometry and weight arrays, immutable rig revisions, executable clips, animated GLB/glTF, independent reports, pose sheet, transparent animation frames and a verified archive. The four principal fixtures also retain editable `.blend` files and offline viewers. See the [artifact index](../examples/rig-3d/README.md) and [workflow guide](3d-rigging.md).

## Measured demonstration results

All positions below are measured in meters. A contact error and a vertex displacement measure different things: planted endpoints should remain fixed while the rest of the character moves. A near-zero contact result does not mean the mesh is static.

| Fixture | Bones | Vertices / triangles | Named clips | Distinct sampled poses | Largest animated vertex displacement |
| --- | ---: | ---: | ---: | ---: | ---: |
| Humanoid | 57 | 3,830 / 7,536 | 6 | 24 | 1.032052 m |
| Quadruped | 27 | 2,284 / 4,488 | 6 | 27 | 0.825947 m |
| Six-legged winged creature | 37 | 3,276 / 6,440 | 6 | 27 | 0.890912 m |
| Robot arm and gripper | 7 | 706 / 1,368 | 3 | 10 | 1.051430 m |
| Taller humanoid retarget | 57 | 3,830 / 7,536 | 1 | 6 | 0.524727 m |
| Smaller quadruped retarget | 27 | 2,284 / 4,488 | 1 | 6 | 0.399510 m |

All six have zero hierarchy cycles, invalid joint references and nonfinite evaluated vertices. The worst weight-sum error is `2.220446049250313e-16`; the worst bind-pose reconstruction error is `4.440892098500626e-16 m`. The largest planted-foot drift across the six fixtures is `9.171947447016606e-16 m`, below each fixture's explicit contact tolerance (at most 1 cm). These are measurements on known authored geometry and constraints, not a prediction of arbitrary imported-model quality.

The humanoid is retargeted to proportions `(0.82, 1.18, 1.0)` relative to the original, and the quadruped to `(0.82, 0.72, 0.88)`. Both retain source/target skeleton identities, calibrated role maps, explicit scale factors, target contact correction and executable `walk-retargeted` channels. Their independent standards validation passes. Independent Blender/Three.js sampling is performed on the four principal fixtures; the two retarget variants additionally use native round-trip and archive evaluation.

### Independent consumers

| Fixture | Blender maximum sampled vertex difference | Three.js maximum sampled vertex difference | Three.js vertices compared |
| --- | ---: | ---: | ---: |
| Humanoid | 0.000974066 m | 0.000523490 m | 8,928 |
| Quadruped | 0.000480533 m | 0.000238187 m | 5,760 |
| Winged creature | 0.000091438 m | 0.000088368 m | 8,064 |
| Robot | 0.000016416 m | 0.000000053 m | 1,584 |

Blender 4.5.3 LTS imports the real GLB, preserves editable armatures, vertex groups, armature modifiers, actions and shape keys, saves the project, reopens it in a new process, evaluates representative times from every clip and exports another animated GLB. The largest measured difference is less than 1 mm; the declared acceptance threshold is 1 cm. Continuous native contact/constraint evaluation and sampled portable animation explain bounded differences. Reports retain the exact sample coordinates, file hashes and tool version.

Three.js 0.180.0 runs in Chromium 140.0.7339.16 and evaluates three nonuniform times per clip, sampling up to 16 vertices per mesh. Browser automation also operates play/pause, frame step, skeleton and weight overlays, IK editing, reduced motion, and available facial expressions including neutral release. These are actual WebGL asset loads and deformed-vertex comparisons.

All four retained `.blend` projects also produce real transparent Cycles CPU PNG previews at 0.00 and 0.65 seconds. They use a shared camera across both samples, 16 samples per pixel and the saved materials. `validation/blender-preview.json` binds the frames to the exact saved Blender bytes. A separate automated test verifies nonempty alpha, transparent background and different pixels between two animated poses.

Khronos glTF Validator `2.0.0-dev.3.10` reports **zero errors and zero warnings for all six native animated GLBs**. Blender's four re-exports have zero errors and respectively 31, 20, 28 and 11 `NODE_SKINNED_MESH_NON_ROOT` warnings. Those warnings concern Blender's armature-parented mesh nodes and glTF's treatment of parent transforms for skinning. The warnings remain in the reports; they are not rewritten to zero. Independently evaluated baked deformation still meets the numerical threshold. Consumers should evaluate skins rather than applying mesh-parent transforms a second time.

### Range and visual checks

| Fixture | Constraint-range poses evaluated | Maximum edge stretch ratio | Nonfinite poses |
| --- | ---: | ---: | ---: |
| Humanoid | 88 | 1.577679 | 0 |
| Quadruped | 28 | 1.500148 | 0 |
| Winged creature | 48 | 1.564649 | 0 |
| Robot | 6 | 1.000000 | 0 |

The robot's constant edge lengths verify rigid-part articulation. Organic range sweeps intentionally include extreme joint poses; stretch ratios are reported for review rather than interpreted as artistic approval. Surface intersection detection is unavailable in this implementation and is explicitly marked unavailable in diagnostics. Volume checks on open/disconnected components are not a watertight-volume guarantee.

The implementation agent inspected the final native pose sheets, actual browser screenshots and Cycles frames from the four saved Blender projects. The humanoid's crouch, arm reach, raised-hand wave and morph blink are visibly distinct. The quadruped has a different seated silhouette, independently articulated legs, head rotation and tail motion. The custom creature has six legs, a segmented tail and articulated membrane wings; its hierarchy is not a renamed humanoid. The mechanical fixture shows arm rotation and gripper translation. Geometry and colors remain recognizable across the displayed poses. These observations support engineering inspection only: the fixtures remain visually pending, with no fabricated approval receipt or assertion that every extreme pose is artistically acceptable.

## Tests, baseline and upstream integration

The initial untouched baseline was commit `19649be829a9badcd789d381a3a22ebe2b3f3a54`: **764 tests**, one original production-pilot setup error and two optional skips. The [baseline log](../tests/results/rig-baseline.log) records the missing exact original source transport. No test was deleted or weakened to hide that failure.

During implementation, upstream PR [#8](https://github.com/CompleteDotTech/hatch-pet/pull/8) restored the original production assets and merged as `594177b865b3401d1b9748860931ee0d63b859cb`. This branch includes that commit. The original missing-payload problem is therefore historical; final compatibility must be judged against the integrated run, not the earlier incomplete checkout.

A pre-integration run executed 838 tests with the inherited pilot error plus two stale-validation errors because source files changed during the run. The validation guards correctly invalidated source-bound receipts. That run is retained as [pre-integration evidence](../tests/results/rig-pre-integration-regression.log) and is not used as a passing release result. Final regression runs freeze implementation files. The current counts, errors, skips and source hashes are retained in [release results](../tests/results/rig-release-results.json) and [the integrated regression log](../tests/results/rig-integrated-regression.log). The focused [3D test log](../tests/results/rig-3d-tests.log) includes actual Blender, browser and Khronos execution.

The integrated suite passed **865 tests in 321.471 seconds**, with zero failures/errors and one optional native-Krita skip. All 13 original production-pilot tests now pass. After that run, the additive Blender CPU preview path and its extra test were finalized; the focused 3D suite passed **76 tests in 14.844 seconds**, with no skips. The logs have separate source snapshots in the machine report; no single combined run including later additions is asserted.

The first remote run exposed an integration issue: the public 2D delivery runner discovered optional 3D tests without installing their dependencies. Its explicit `--test-scope 2d` now retains all **790 existing 2D cases**, filtering only `test_rig_*.py` before import. All existing test bodies and strict unexpected-skip rejection remain unchanged. `--test-scope all` opts into the additional dependency/tool requirements. Nine separate 3D/compatibility jobs exercise the new subsystem. A new isolation regression blocks NumPy, pygltflib and bpy imports and verifies successful discovery of all 790 cases, including every production-pilot test and the actual browser suites. The [four compatibility tests passed in 0.504 seconds](../tests/results/rig-delivery-scope-tests.log); there are now 77 available focused 3D cases. This final follow-up changes the delivery runner, not 2D rendering, profile, playback or test behavior. Updated remote execution is reported on [PR #9](https://github.com/CompleteDotTech/hatch-pet/pull/9).

The four frozen compatibility files retain their starting hashes: `profiles/codex-v1.json`, `profiles/profile.schema.json`, `assets/playback.js` and `state-library/catalog.json`. Tests execute ordinary capabilities with NumPy, jsonschema, bpy and Playwright imports explicitly blocked. Existing Codex atlas dimensions, nine-state timing, package names, profiles V1/V2, playback behavior and all 416 catalog identifiers remain unchanged.

## Requirement traceability

The section numbers refer to the supplied 38-section implementation specification. A code path or automated test proves its stated technical scope; it does not automatically satisfy subjective visual acceptance.

| Specification | Implementation / retained evidence | Status and scope |
| --- | --- | --- |
| 1 — Primary objective | Native engine and three full import → rig → skin → animate → export demonstrations | Working engineering fixtures |
| 2 — Audit and compatibility | `3d-rigging-audit.md`, frozen-byte tests, baseline and integrated logs | Existing tests retained; upstream repair integrated |
| 3 — Engineering principles | Real arrays/channels, source hashes, uncertainty, transactional revisions | Implemented and tested |
| 4 — Architecture | Focused `rig_*` modules; optional imports; Python facade and CLI dispatch | Implemented |
| 5 — Coordinates | `rig_math.py`, `rig_skeleton.py`, analytic expectation tests | RH Y-up, XYZW, meters and seconds verified |
| 6 — Contracts and packages | Eight strict generated schemas; content-addressed mesh/weights/clips; inventory ZIP | Versioned, unknown-field and traversal tests |
| 7 — Import | `rig_gltf.py`, `rig_import.py`, `rig_obj.py`, Blender adapter | Real geometry/material/morph/skin import; unsupported transforms/extensions rejected |
| 8 — Templates | Five JSON templates and inheritance validation | Humanoid, quadruped, winged, robotic and custom |
| 9 — Automatic fitting | Existing rigs, source-bound landmarks, region/bounds fitting and uncertainty | Geometric fitting implemented; anatomy is not universally inferred |
| 10 — Correction | Hash-bound bone, controller, morph and weight edits; CLI and viewer | Versions and dependent invalidation tested |
| 11 — Skinning | Real LBS, diffusion/distance/segmented/rigid weights, locks and editing | Four/eight native influences; deformation demonstrated |
| 12 — FK | Hierarchy evaluation, world/local rotations, parent transforms | Analytical and independent checks |
| 13 — IK and constraints | Two-bone/FABRIK, poles, bounded iterations, joint limits, dependency checks | Reachable/unreachable targets and constraints tested |
| 14 — Face | Actual morph authoring, qualified expressions, mixing, gaze and viseme availability | Existing geometry only; missing expressions explicit |
| 15 — Specializations | Finger curl/spread, tails, wing controls, sockets | Real appendages and ownership tests |
| 16 — Contacts | World foot targets, object-relative grasps, attach/detach/handoff | Endpoint errors and ownership verified |
| 17 — Animation | SLERP/Hermite/STEP, masks/additive layers, crossfades, root motion and baking | Actual channels, interpolation and layering tests |
| 18 — Retargeting | Semantic role maps, calibration, proportions and target contact solving | Two different-proportion targets retained |
| 19 — Catalog and 2D bridge | Actual catalog resolver, selective recipes, transparent rendered frames | Explicit unsupported/review statuses; no 416-motion claim |
| 20 — Decomposition/generation | Source-bound 3D semantic annotations and provider-result import origin | No automatic 2D-mask-to-3D conversion or configured generation provider |
| 21 — Blender | Editable controls/actions/shape keys, fixed headless worker, reopen sampling and Cycles CPU previews | Actual application exercised; some native authoring constraints remain manifest data |
| 22 — Interchange | Animated GLB/glTF, Khronos reports, native/Blender/Three.js checks | Native exports zero errors/warnings; Blender warnings disclosed |
| 23 — Preview/review | Offline Three.js, pose/FK/IK/morph/weights, comparison and bound receipts | Interactive behavior tested; production visual verdict pending |
| 24 — APIs | `rig_api.py`, authenticated loopback `rig_http.py` | Real HTTP requests and failure cases tested |
| 25 — CLI | `rig.py` and lazy `hatch.py rig` dispatch | Actionable errors and documented workflows |
| 26 — Jobs | Single-writer lock, step journal, hash caches, retry limits and resume | Interrupted/stale/failure paths tested |
| 27 — Budgets | Geometry/key/frame/archive limits, estimated memory and subprocess deadlines | No OS-level memory isolation claim |
| 28 — Validation | Bind/weights/finite/range/contact/deformation metrics | General surface intersection detection unavailable |
| 29 — Tests | Math, controls, skinning, animation, workflow, HTTP, import/export, specialization, render and compatibility suites | Executed results retained |
| 30 — Demonstrations | Three six-motion characters, mechanical fixture, two retarget targets | Genuine geometry and independently sampled movement |
| 31 — Visual identity | Exact original sources, topology/material correspondence, retained images and independent vertex sampling | Engineering inspection; production approval pending |
| 32 — Failure/status | Structured `RigError`, explicit lifecycle, stale evidence rejection | Tested; status survives restored packages |
| 33 — Documentation | Workflow/API/toolchain guide, example index and this report | Delivered |
| 34 — Execution | Audit → contracts → mesh controls → integration → demos → independent checks | Evidence retained for the implemented path |
| 35 — CI | Nine named 3D/compatibility jobs plus inherited delivery workflow | Pinned runtime tools; remote execution reported separately |
| 36 — Final checklist | Working core/capabilities/interchange; review and environmental boundaries above | No unqualified production-readiness assertion |
| 37 — Deliverables | Source, schemas, templates, demos, documentation, logs and archives | Repository branch; PR/commit reported at delivery |
| 38 — Definition of done | Real source meshes fitted, skinned, corrected, animated, retargeted and exported | Demonstrated for all three required anatomies |

## Known limitations and unverified scope

**Implemented, requiring visual acceptance:** uncertain auto-fitted anatomy, skin quality on a user's actual model, subjective identity, facial semantics and suitability of mapped catalog motions. The review workflow is functional, but no user production model was provided for this implementation's acceptance.

**Known interoperability limits:** sheared/reflected skeletal rest transforms, inconsistent bind shapes, compressed required glTF extensions and advanced MTL shading need explicit source conversion. Native LBS supports eight influences, while the shipped Three.js shader profile requires four. The native constraint engine is authoritative; the browser implements a useful ball/hinge IK editing subset, and Blender retains some native constraint/socket semantics in the manifest rather than converting every authoring rule. Baked motion is the portable interchange guarantee. Browser looping restarts the trajectory; native evaluation can accumulate root motion.

**Known rendering and diagnostics limits:** the portable CPU renderer shades material base colors; the Three.js application and Blender retain full material/texture data. Surface intersections, general bone-to-surface separation and general velocity-discontinuity classification are not certified by this release. No physical collision or dynamics engine is implemented. Numerical range sweeps cannot establish production-quality deformation on arbitrary meshes.

**Not implemented/configured:** automatic creation of missing facial geometry, a remote mesh-generation provider, a learned anatomical landmark model, automatic conversion of 2D decomposition masks into 3D geometry, and all 416 finished 3D state motions. These features are not simulated with metadata. Authored morphs, external genuine meshes, explicit landmarks and selected real clips are the supported paths.

**Environmentally unverified:** native Krita remains an unrelated optional legacy integration; full cross-platform 3D application testing and live external game-engine imports are not established by local Linux evidence. CI availability and results are reported using the actual branch checks. Hard OS memory caps are not applied to Blender; geometry estimates and deadlines do not make arbitrary `.blend` input safe to treat as a trusted sandbox.

## Reproduce and inspect

Install the pinned optional dependencies as described in [the tools guide](../tools/rig/README.md), then run:

```bash
python scripts/generate_schemas.py --check
python scripts/generate_rig_templates.py --check
HATCH_RIG_INTEROP_TEST=1 HATCH_RIG_BLENDER_TEST=1 HATCH_RIG_BROWSER_TEST=1 \
  python -m unittest discover -s tests -p 'test_rig_*.py' -v
python scripts/verify_rig_demos.py --generate --destination output/rig-acceptance \
  --blender --browser --validator --render --archives
python -m http.server 8765 --bind 127.0.0.1 \
  --directory examples/rig-3d/humanoid/review-ui
```

Use a new generation destination. Open `http://127.0.0.1:8765/` for the local reviewer. Archives are under `examples/rig-3d/packages`; `rig restore` verifies their contents before promotion. Keep implementation files unchanged during a regression run because acceptance receipts are deliberately bound to implementation hashes.
