# Physics stage 0: repository audit and compatibility baseline

## Scope and source snapshot

This audit addresses [#166](https://github.com/CompleteTech-Skills/hatch-pet/issues/166),
the implementation task for [stage 0, #154](https://github.com/CompleteTech-Skills/hatch-pet/issues/154).
It applies the inspection and legacy-regression requirements in
[#153, section 2](https://github.com/CompleteTech-Skills/hatch-pet/issues/153) and
[its continuation, section 18.6](https://github.com/CompleteTech-Skills/hatch-pet/issues/153#issuecomment-6333974000).
It records integration decisions for subsequent tasks; it adds no physics solver,
simulation command, backend capability, or production-art approval.

The starting default-branch commit is
[`7b966a639bcaf23bd3a0d037f46f29e2edfcc273`](https://github.com/CompleteTech-Skills/hatch-pet/commit/7b966a639bcaf23bd3a0d037f46f29e2edfcc273),
inspected on 2026-10-22. At initial reconnaissance there were 180 open issues and
no open PRs, including drafts. The two non-default branches were the already
merged `feat/3d-character-rigging` and `fix/public-production-delivery` branches.
These observations describe that snapshot, not a permanent ownership lock.
The audit work uses `agent/issue-166-physics-baseline-36752e25`; concurrent work
must be checked again before implementation, push, review, or merge.

[README](../README.md) and [SKILL](../SKILL.md) establish the existing workflow
and evidence boundaries. No `AGENTS.md` or `CONTRIBUTING.md` exists in the audited
tree. The current [3D rigging guide](3d-rigging.md),
[rigging acceptance report](3d-rigging-acceptance.md),
[production contracts](production-contracts.md),
[rendering reference](production-rendering.md),
[operations reference](production-operations.md), and
[delivery status](../DELIVERY_STATUS.md) were checked against implementation.

## What currently exists

Main contains the established raster-production system and an optional, working
mesh/rig/animation subsystem. There is no physics package, physical-world schema,
rigid-body simulation adapter, cloth/fluid worker, or solver-cache lifecycle in
this source snapshot. Authored motion, inverse kinematics, skinning, and Blender
rendering are useful integration points; none establishes physical state evolution.

| Responsibility | Current source authority and observed behavior | Physics integration boundary |
| --- | --- | --- |
| Public commands | [`hatch.py`](../scripts/hatch.py) dispatches `rig` lazily; [`production.py`](../scripts/production.py) owns raster production commands | Follow opt-in dispatch. Ordinary 2D imports and commands must not require or launch Blender, NumPy, PyBullet, or a physics worker. |
| Legacy schemas and identities | [`production_contracts.py`](../scripts/production_contracts.py) defines strict project/cast/clip/scene/shot version-1 contracts, versioned asset references, source hashes, contacts and ownership checks | Keep these schemas and their pixel-space semantics unchanged. Define separately versioned physics contracts with explicit references to authoritative assets and future 3D scenes. |
| 2D performance and timing | [`production_performance.py`](../scripts/production_performance.py) evaluates bounded integer-frame tracks, clips, contacts, events and prop ownership; [`production_render.py`](../scripts/production_render.py) supplies exact rational frame/sample conversion | Preserve existing frame boundaries, loop displacement and audio sampling. Introduce solver-step and cache-sample clocks separately. |
| Raster rendering and reuse | [`production_render.py`](../scripts/production_render.py) owns renderer identity, visual signatures, output locks, checkpoints, PNG/PCM masters and verified video muxing | Reuse the integrity/ownership approach, not the raster renderer as a substitute for 3D simulation rendering. Physics caches need their own physical-input identity. |
| Acquisition, dependencies and review | [`production_workflow.py`](../scripts/production_workflow.py) binds generation claims, computes scoped `shot_dependencies`, projects continuity, and validates hash-bound reviews of exact completed artifacts | Preserve the existing claim owner, fixture provenance and review history. Add explicit physics dependencies without invalidating unaffected visual or audio work. |
| Asset contracts and exports | [`asset_contracts.py`](../scripts/asset_contracts.py), [`asset_exporters.py`](../scripts/asset_exporters.py), [`source_interface.py`](../scripts/source_interface.py) preserve identity, source origin, hashes and export contracts | A rendered physics frame is a derived asset with simulation provenance. It still needs the existing raster import, validation and review gates before 2D packaging. |
| Portability and editor handoff | [`portable_runs.py`](../scripts/portable_runs.py), [`production_bundle.py`](../scripts/production_bundle.py), [`production_sources.py`](../scripts/production_sources.py), and [`production_adapter.py`](../scripts/production_adapter.py) provide bounded archives, source verification and PNG/WAV/OpenRaster handoff | Reuse portable-path and integrity conventions. Native simulation files require independent inventories and backend/version restrictions; an archive alone proves neither replay nor editor integration. |
| Real mesh and skin data | [`rig_models.py`](../scripts/rig_models.py), [`rig_import.py`](../scripts/rig_import.py), [`rig_gltf.py`](../scripts/rig_gltf.py) represent finite triangle geometry, materials, textures, morphs, skins and original source bytes | Reuse stable mesh/rig identities and validated geometry. A collision proxy is a separately identified derivative, not an automatic substitute for its visual mesh. |
| Rig transforms and animation | [`rig_contracts.py`](../scripts/rig_contracts.py), [`rig_math.py`](../scripts/rig_math.py), [`rig_skeleton.py`](../scripts/rig_skeleton.py), [`rig_animation.py`](../scripts/rig_animation.py) define coordinates, FK, quaternion interpolation, morph channels and authored clips | Keep the established coordinate convention and skeleton versions. Dynamic simulation needs an explicit transform owner and an adapter into evaluated animation. |
| Contacts and props | [`rig_ik.py`](../scripts/rig_ik.py), [`rig_constraints.py`](../scripts/rig_constraints.py), [`rig_attachments.py`](../scripts/rig_attachments.py) provide spatial IK, authored constraints, sockets and single-owner handoffs that preserve world pose | These are kinematic operations. Physical collisions, impulses, release velocities, inertia, solver joints and force feedback remain unimplemented. |
| Persistent rig work | [`rig_jobs.py`](../scripts/rig_jobs.py) writes immutable geometry/animation blobs and revision snapshots before promoting `rig.json`; `run_step` binds operations to inputs/code and records failure/staleness | Reuse the immutable-output and bounded-job conventions. Existing step reuse is not an arbitrary mid-solver checkpoint mechanism. |
| Worker safety and diagnostics | [`rig_errors.py`](../scripts/rig_errors.py) supplies bounded strict JSON, finite-value checks, portable paths, atomic writes and locks; [`rig_blender.py`](../scripts/rig_blender.py) supplies a trusted, bounded subprocess wrapper | Physics needs category-specific validated job data, resource admission, output verification and recovery semantics. Existing checks are a foundation, not proof that every future solver is isolated. |
| Actual 3D previews | [`rig_render.py`](../scripts/rig_render.py) renders skinned triangles with a CPU z-buffer; [`rig_blender_worker.py`](../scripts/rig_blender_worker.py) supports actual Blender import/export, inspection and Cycles rendering; [`rig_viewer.py`](../scripts/rig_viewer.py) builds the local review UI | Reuse actual geometry inspection and rendering. Label authored playback, cached simulation replay, live solver state and final rendering separately. |

The browser-facing legacy authorities remain
[`production-preview.js`](../assets/production-preview.js),
[`production-preview.html`](../assets/production-preview.html), and
[`playback.js`](../assets/playback.js). Their playback timing does not supersede
offline PNG/PCM timing. The fixture and production demonstrations remain distinct:
[`production_regression_demo.py`](../scripts/production_regression_demo.py)
exercises synthetic data; [`production_demo.py`](../scripts/production_demo.py)
reconstructs the retained production project.

## Coordinate, unit and timing decisions

### Preserve the established 3D basis

The rig contract already specifies right-handed **+X right, +Y up, +Z forward**,
meters, seconds, radians, XYZW quaternions, and matrices acting on column vectors.
World transforms compose as `parent_world @ local`. The parent physics request's
Z-up preference must be reconciled with this implemented contract; it must not
silently redefine existing mesh, rig, animation or glTF data.

Future physics contracts should retain this canonical basis. Add kilograms,
Newtons, Newton-meters, meters/second and radians/second explicitly. The default
gravity vector is consequently `[0, -9.81, 0]` in canonical coordinates. This is
an integration decision for [#167](https://github.com/CompleteTech-Skills/hatch-pet/issues/167),
not a claim that gravity simulation currently runs.

The existing Blender worker converts a canonical point `(x, y, z)` to
`(x, -z, y)` and converts back with `(x, z, -y)`. This is a proper +90-degree
rotation around X. Let `C` be its 3×3 rotation and `H = diag(C, 1)` its 4×4
homogeneous extension. A future physics adapter must consistently map positions,
linear/angular velocities, forces and torques with `C`, transforms with
`H M H^-1`, and inertia tensors with `C I C^T`. Rotations require quaternion
basis conversion, retaining XYZW order; swapping position axes alone is
insufficient. Blender gravity becomes `[0, 0, -9.81]`. Roundtrip and known-axis
tests must verify those conversions before declaring a backend supported.

Geometry import scale, collision dimensions, center of mass and inertia must
use the same physical units. Nonuniform or animated visual scale must be handled
explicitly or rejected for the chosen solver. No pixel-to-meter conversion can
be inferred from an existing 2D drawing or camera.

### Keep the time domains explicit

| Domain | Current representation | Required adapter behavior |
| --- | --- | --- |
| Legacy atlas and custom profiles | Integer frame durations in milliseconds, with fixed Codex state order/counts and geometry | Preserve the 8×9 atlas of 192×208 cells and original per-state timing. Extended catalog definitions and 3D clips do not change this consumer contract. |
| Legacy 2D production | Integer frame indices; rational FPS through `fps_fraction`; PNG frames and PCM sample counts are authoritative | Preserve existing exclusive render boundaries, exact event frames and sample rounding. Do not change the audio-capable pipeline to make new 3D output silent. |
| Existing 3D rig clips | Finite float-second key times; integer FPS from 1 to 60 in `AnimationClip`; continuous-time interpolation | Preserve rig schema/version compatibility. Convert exact requested timestamps at the evaluation boundary and record any precision or resampling limitation. |
| Future physics | No current contract or implementation | Distinguish solver step, internal substep, cache sample, animation evaluation and output/render rate. Retain rational timestamps and record requested versus effective backend rates. |

[#169](https://github.com/CompleteTech-Skills/hatch-pet/issues/169) must test
fractional rates such as `30000/1001`, arbitrary output sampling and frame-boundary
events. Interpolation may sample computed states; it cannot replace solver steps.
Hash-verified replay, pinned-environment numerical reproduction, approximate
reruns and nonguaranteed reruns need separate classifications.

## Ownership, cache and execution hazards

1. **Transform authority:** authored animation controls kinematic objects,
   physics controls dynamic bodies, and static bodies retain declared transforms.
   A transition needs a validated world pose and velocity transfer. Existing
   `attach_prop`/`detach_prop` preserve pose but do not calculate physical release
   momentum. A valid 2D handoff within two world pixels does not establish a
   physical 3D contact tolerance.
2. **Identity and dependency scope:** retain exact character, rig, skeleton,
   source-geometry and asset versions. Physics cache identity must bind physical
   settings, geometry/collider hashes, solver/application/adapter versions,
   effective stepping, forces, events and upstream caches. Camera, exposure,
   visual material color and output resolution should not invalidate an otherwise
   independent bake. A physical-material change must invalidate affected motion.
3. **Immutable publication and recovery:** retain the prior valid result while
   producing a new version. Verify every expected output's existence, size, hash
   and state/sample coverage before atomic promotion. A successful process exit
   or an existing cache directory is insufficient. Resume only when complete
   internal solver state can be restored; otherwise report and perform a clean
   restart from the required boundary.
4. **Worker safety:** the existing Blender wrapper uses explicit argv,
   `--background`, `--factory-startup`, `--disable-autoexec`, a trusted worker,
   timeout and structured report checks. Physics jobs must additionally validate
   category-specific objects/settings and bounds before launching. Solver support
   requires an actual smoke run, not merely finding an executable or importing a
   module. GPU rendering support does not imply GPU physics.
5. **Review and provenance:** preserve source origin, fixture labels, actual
   backend/version and the exact inspected artifacts. Existing
   [`rig_review.py`](../scripts/rig_review.py) and production review gates
   distinguish numerical validation from visual decisions. Neither synthetic
   receipts nor successful authored-animation renders approve physics or
   production artwork.
6. **Exports and continuing shots:** glTF transform animation can represent baked
   rigid motion only after a tested conversion; it does not preserve arbitrary
   cloth, liquid or gas solvers. Native/deformation caches need their own verified
   import/export path. A camera cut must not reset a continuous physics world.
   New silent video exports need measured frame/duration and stream inventory,
   while existing 2D audio remains available.

## Environment and baseline evidence

The supported installation boundary is documented by
[`requirements-test.txt`](../requirements-test.txt),
[`requirements-delivery.txt`](../requirements-delivery.txt), and the separate
[`requirements-rig.txt`](../requirements-rig.txt) /
[`requirements-rig-test.txt`](../requirements-rig-test.txt).
The [public-delivery workflow](../.github/workflows/public-delivery.yml) exercises
Linux, macOS and Windows; the [rig workflow](../.github/workflows/rig-3d.yml)
uses Ubuntu, Python 3.12, and a checksum-pinned Blender 4.5.3 LTS integration gate.
These workflow definitions and historical results do not prove that this audit
session executed every platform or optional backend.

The new local baseline uses Linux x86_64 and Python 3.12.14. Two isolated virtual
environments retain the repository's distinct pins: delivery uses Pillow 13.0.0,
jsonschema 4.26.0 and Playwright 1.64.0; rig checks use NumPy 2.3.5,
jsonschema 4.25.1, Pillow 12.3.0, Playwright 1.55.0 and pygltflib 1.16.5.
The delivery environment contains no NumPy, pygltflib, Blender or physics package.
Full versions and unavailable/unexecuted capabilities are recorded in
[`environment.json`](../tests/results/physics-baseline-20261022/environment.json).

Real Chromium **140.0.7339.16** was launched using the existing
`HATCH_BROWSER_EXECUTABLE` override. The Playwright 1.64.0 Chromium 156 download
returned an invalid ZIP; the repository's rig-test Playwright version obtained
Chromium 140 through its Microsoft mirror. Its later optional headless-shell
installation failed on a stale directory lock, so the successfully installed
full browser was explicitly selected and probed before tests. The local browser
result is not a claim that Chromium 156 executed. No repository dependency pin
or test was changed to accommodate the environment.

All checks below ran against the unmodified runtime at the starting commit.
The audit changes documentation, retained engineering evidence and its byte
preservation attributes only; no runtime, schema, dependency pin or test changed.

| Executed command | Environment | Observed result | Retained output |
| --- | --- | --- | --- |
| `python scripts/test_rig_gate.py compatibility` | Delivery; `HATCH_DECOMPOSITION_BROWSER_TEST=1`; explicit Chromium executable | **790 tests: 789 passed, 0 failures, 0 errors, 1 skip** in 282.918 seconds. Native Krita was unavailable; actual production-preview, export and decomposition browser tests executed. | [Full 2D log](../tests/results/physics-baseline-20261022/compatibility-2d.log) |
| `python scripts/test_rig_gate.py schema-math` | Rig | **12 tests passed**, no failures/errors/skips; 1.148 seconds. The isolation check discovered all 790 2D tests with optional 3D imports blocked. | [Schema/math log](../tests/results/physics-baseline-20261022/schema-math.log) |
| `python scripts/generate_schemas.py --check` | Rig | Exit 0; all generated schemas match; no output or file writes. | [Execution record](../tests/results/physics-baseline-20261022/schemas.json) |
| `python scripts/generate_rig_templates.py --check` | Rig | Exit 0; generated templates match; no output or file writes. | [Execution record](../tests/results/physics-baseline-20261022/rig-templates.json) |
| `python scripts/production_sources.py verify-delivery` | Rig | Exit 0; all five source transports, 129 logical files, 462 parts, 7 public files, 20 historical assistant reviews and 13 evidence files verify. No new visual review, human approval, image generation or TTS occurred. | [Source verification](../tests/results/physics-baseline-20261022/source-delivery.log) |
| `python scripts/hatch.py doctor` | Delivery | Exit 0; raster/runtime capability and filesystem diagnostics retained. | [Hatch diagnostics](../tests/results/physics-baseline-20261022/hatch-doctor.log) |
| `python scripts/rig.py doctor` | Rig | Exit 0; installed dependencies reported. Blender and the Khronos validator are unavailable, not passed integrations. | [Rig diagnostics](../tests/results/physics-baseline-20261022/rig-doctor.log) |
| Explicit Playwright launch and page probe | Delivery | Exit 0; actual Chromium 140.0.7339.16 created a page and returned its title. Exact Python probe is in the execution record. | [Browser probe](../tests/results/physics-baseline-20261022/browser-probe.json) |

Reproduce the gate using the declared requirements and an installed real browser:

```bash
python -m venv /tmp/hatch-physics-delivery
/tmp/hatch-physics-delivery/bin/python -m pip install -r requirements-delivery.txt
/tmp/hatch-physics-delivery/bin/python -m playwright install chromium
HATCH_DECOMPOSITION_BROWSER_TEST=1 /tmp/hatch-physics-delivery/bin/python scripts/test_rig_gate.py compatibility
```

When selecting an already installed browser, set `HATCH_BROWSER_EXECUTABLE` to
its actual binary and retain the observed version as this run did. Do not claim
an absent browser executed. Use a separate environment for
`requirements-rig-test.txt` because its Pillow/jsonschema/Playwright pins differ
from the delivery environment. Platform-specific environment activation may
replace these Unix paths; only Linux was newly executed here.

Every command has an adjacent JSON execution record with the original argv,
working directory, explicit test environment, source commit, start/end time,
wall duration, exit code and SHA-256 of its unmodified combined output.
The [retained evidence directory](../tests/results/physics-baseline-20261022)
contains those records and logs; it records engineering checks only.

[`protected-inputs.json`](../tests/results/physics-baseline-20261022/protected-inputs.json)
records SHA-256 and byte length for **36 unchanged legacy contracts and source
authorities**: all non-rig profile/schema JSON, the state and style catalogs,
browser playback sources, and the audited production/identity/lifecycle modules.
Each was compared byte-for-byte with `git show 7b966a6:<path>` before recording.
This is an audit identity check; it does not prohibit reviewed future changes.

The baseline must retain command exit status, test count, failures/errors/skips,
dependency versions and unavailable prerequisites. The existing compatibility
gate is `python scripts/test_rig_gate.py compatibility`; it discovers every
`test_*.py` except `test_rig_*`. The `schema-math` gate includes
[`test_rig_compatibility.py`](../tests/test_rig_compatibility.py), whose current
guards freeze the Codex profile, profile schema, playback source and state
catalog, and exercise ordinary capabilities/test discovery with optional 3D
imports blocked. Generated schema parity is checked by
`python scripts/generate_schemas.py --check`.

Those byte checks supplement behavioral coverage; they do not replace production
rendering, source-integrity, archive, review, audio, and browser tests. The audit
manifest also pins unchanged legacy production schemas and source authorities.
A missing optional tool is an explicit unavailable/skip
result, never a passing external integration.

### Historical missing-media limitations

The older [rigging audit](3d-rigging-audit.md) began at `19649be` and recorded a
missing production-source failure. [PR #8](https://github.com/CompleteTech-Skills/hatch-pet/pull/8)
restored the original source transports and merged at `594177b` before this
audit's starting commit. Current [delivery status](../DELIVERY_STATUS.md) and
[public validation](production-public-validation.md) retain separate evidence
for recovery, public checkout, complete rendering and platform verification.
Do not carry the older missing-source failure forward as an unresolved current
defect, or reuse its old test counts as this audit's results.

Historical private master-ZIP names and past inspection receipts retain their
original provenance. Their existence does not establish a current solver, new
visual approval, or a newly executed integration. Verify current retained source
bytes with `python scripts/production_sources.py verify-delivery` and report the
actual result above. Reconstruction must not silently replace missing originals
with generated artwork or new synthetic speech.

### Limits of this evidence

Native Krita accounts for the single skipped 2D integration test; adapter and
archive tests passed independently. Blender, PyBullet, the Khronos validator,
native 3D browser playback, and fresh Windows/macOS runs were not executed by
this audit. The starting commit already has successful
[rig CI](https://github.com/CompleteTech-Skills/hatch-pet/actions/runs/39421253425)
and [three-platform delivery CI](https://github.com/CompleteTech-Skills/hatch-pet/actions/runs/39421253433);
those are separate historical GitHub results, not local runs or physics evidence.

No solver ran. Actual physics backend/version, physical settings, effective
solver timestep, cache contents, solver output hashes, numerical tolerances and
peak solver resource measurements are therefore **not applicable**. The proposed
gravity and unit conventions above are future contract decisions. This baseline
does not approve production artwork, certify an external application, or satisfy
any physical simulation category. Later tasks must supply their own real
execution, numerical, cache, recovery and inspected-artifact evidence.

## Downstream owners and implementation gates

The scene, asset, animation, rendering, editor, Director and continuity missions
remain separate authorities: [#10](https://github.com/CompleteTech-Skills/hatch-pet/issues/10),
[#11](https://github.com/CompleteTech-Skills/hatch-pet/issues/11),
[#12](https://github.com/CompleteTech-Skills/hatch-pet/issues/12),
[#13](https://github.com/CompleteTech-Skills/hatch-pet/issues/13),
[#14](https://github.com/CompleteTech-Skills/hatch-pet/issues/14),
[#15](https://github.com/CompleteTech-Skills/hatch-pet/issues/15),
[#16](https://github.com/CompleteTech-Skills/hatch-pet/issues/16),
[#17](https://github.com/CompleteTech-Skills/hatch-pet/issues/17),
[#18](https://github.com/CompleteTech-Skills/hatch-pet/issues/18),
[#107](https://github.com/CompleteTech-Skills/hatch-pet/issues/107), and
[#128](https://github.com/CompleteTech-Skills/hatch-pet/issues/128).
Their existence as issues does not imply their requested interfaces are already
implemented. Recheck current code and active claims before defining a shared
scene/asset adapter; preserve already implemented rig identities and conventions.

| Physics work | Exit evidence still required after this audit |
| --- | --- |
| [#167](https://github.com/CompleteTech-Skills/hatch-pet/issues/167)–[#169](https://github.com/CompleteTech-Skills/hatch-pet/issues/169): contracts, workers, time | Strict schema/runtime parity, unit/basis roundtrips, bounded genuine backend smoke run, rejected unsupported parameters, exact requested/effective stepping and unchanged 2D operation. |
| [#170](https://github.com/CompleteTech-Skills/hatch-pet/issues/170)–[#172](https://github.com/CompleteTech-Skills/hatch-pet/issues/172): bodies, collision, joints | Real free-fall/force/impulse/contact response, measured friction/restitution/penetration, and actual constrained assemblies within declared tolerances. |
| [#173](https://github.com/CompleteTech-Skills/hatch-pet/issues/173)–[#174](https://github.com/CompleteTech-Skills/hatch-pet/issues/174): character and prop physics | Geometry-aware traversal, exclusive transform/prop ownership, pose/velocity continuity, and genuine post-release dynamics. |
| [#175](https://github.com/CompleteTech-Skills/hatch-pet/issues/175)–[#182](https://github.com/CompleteTech-Skills/hatch-pet/issues/182): deformable/environmental categories | Executed cloth, soft-body, secondary-motion, particle, smoke/fire, liquid, force and fracture demonstrations; actual changing state/caches, bounded resources and category-specific numerical/render evidence. |
| [#183](https://github.com/CompleteTech-Skills/hatch-pet/issues/183)–[#185](https://github.com/CompleteTech-Skills/hatch-pet/issues/185): coupling and production bridge | Tested state/force exchange per claimed coupling mode, hash-bound replay/invalidation, crash-safe restart, verified derived animation and rendering without unnecessary resimulation. |
| [#186](https://github.com/CompleteTech-Skills/hatch-pet/issues/186)–[#187](https://github.com/CompleteTech-Skills/hatch-pet/issues/187): operations | Real CLI/preview job control, resource admission, process isolation, useful diagnostics and safe cancellation. |
| [#188](https://github.com/CompleteTech-Skills/hatch-pet/issues/188)–[#189](https://github.com/CompleteTech-Skills/hatch-pet/issues/189): acceptance | Every required category and the combined laboratory, genuine cache/numerical/visual evidence, verified silent media when produced, supported-platform results and existing 2D regressions. |

Follow the native blocked-by relationships within these groups. Minimal cache,
safety and evidence handling accompanies each introduced solver; later lifecycle
tasks do not justify omitting those protections from early real execution.
Completion of this audit establishes an inspected compatibility boundary only.
All physical simulation categories remain unimplemented at the recorded source
snapshot and need their own executed acceptance evidence.
