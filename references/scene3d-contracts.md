# Scene3D v1 contracts and static transform foundation

This additive foundation addresses [#59](https://github.com/CompleteTech-Skills/hatch-pet/issues/59)
under [Scene Builder #12](https://github.com/CompleteTech-Skills/hatch-pet/issues/12).
It defines documents, hash-verified dependencies and static hierarchical transforms.
It does not implement the remaining scene-builder packages #60–#66: editable
geometry, import/export, procedural environments, spatial queries, constraint or
animation evaluation, an interactive editor, rendering and production acceptance.
The example's render backend is explicitly `unavailable`.

## Baseline and existing owners

The implementation starts at `a5dc729ebb2c31c4be0357afc3dd08e6fe15677e`.
README, SKILL, DELIVERY_STATUS, both workflows, production contracts/evaluation,
rig contracts/math, acquisition/delivery and the retained audit references were
inspected. No repository `AGENTS.md` exists in that snapshot. Production v1
remains closed and pixel-based; no existing project, scene, shot, cast, clip,
atlas, catalog or playback field changes meaning or bytes.

The historical missing-media warning in the original issue is no longer the
current baseline: `production_sources.py verify-delivery` verifies the retained
original artwork, speech, review records and supporting transports in this
checkout. Existing pilot tests remain required; no replacement artwork or
approval is introduced. Current production capabilities and limitations remain
in [DELIVERY_STATUS](../DELIVERY_STATUS.md). Numerical test success and restored
historical evidence do not supply new human approval.

| Authority | Reuse and boundary |
| --- | --- |
| `production_contracts.py`, `production_performance.py` | Preserve v1 formats and pixel/frame semantics; a linked 2D project is an explicit hash-bound external reference using its actual `project` kind, never automatically interpreted as 3D. |
| `rig_errors.py` | Reuse strict duplicate-key/nonfinite/depth-bounded JSON and structured `RigError` diagnostics. |
| `rig_math.py` | Reuse TRS, quaternion interpolation/decomposition and the existing canonical-to-Blender basis. Scene math adds only pivot/coordinate adapters and static hierarchy evaluation. |
| `rig_*`, forthcoming asset-library/model contracts | Own actual mesh/skin/animation import and technical validation. This loader verifies content bytes and manifest contracts; it does not count mesh vertices or certify geometry. |
| Render/camera/material/animation subsystems | Own full optics, shaders, temporal evaluation and execution. Minimal typed camera/light node fields admit declarations; they do not create a second renderer or optical evaluator. |
| `production_workflow.py` review/acquisition | Remains the existing evidence/claim authority. New review fields retain hash-bound evidence references and never manufacture approval receipts. |

## Documents and APIs

`scene3d_contracts.definitions()` is the authoritative structural definition;
`generate_schemas.py` generates eight checked-in schemas: project, scene, shot,
node, asset, prefab, animation and render. All objects are closed. Unknown
versions, fields and kinds fail. IDs use the existing lowercase portable ID
policy; versions use exact `major.minor.patch` with no leading zeros.

`validate_document(value, kind=None)` checks structure plus semantic paths,
quaternions, bounds, reference inventories, graph/constraint/attachment cycles,
unique identities, timestamp ordering, fixture declarations and exact timing.
Schema-only validation is explicitly insufficient for these relational rules.
`canonical_bytes` produces deterministic UTF-8 JSON; `document_hash` hashes that
canonical serialization. Referenced **files** are always hashed as their actual
bytes, including original whitespace, not canonical reserializations.

`load_project(root, name='project.json')` validates a real, bounded closure before
returning `{project, documents, inventory, bytes, status}`. `documents` maps
project-relative paths to validated manifests. `inventory` maps actual paths to
`{sha256, bytes}`; status is `hash-and-contract-verified`. Manifest identities must
match their references; every typed reference must be in the dependency lock.
Conflicting hashes, duplicate version identities, portable aliases, dangling
shot/camera/node references, dependency cycles and missing/corrupt files fail.
Asset byte estimates are checked against actual content; vertex/triangle counts
remain estimates for the geometry owner to verify. All input files stay intact.

An immutable manifest reference has this shared shape:

```json
{"id":"example-scene","version":"1.0.0","path":"example-scene.json","sha256":"<64 lowercase hex characters>","kind":"scene3d-scene"}
```

A raw file reference is `{path, sha256}`. Manifest references load and validate
Scene3D documents; external owner references (`hatch-3d-rig`,
mesh/material/texture/catalog/evidence/collision resources) verify bytes without
claiming the other subsystem's semantic validation. An external integration must
call its owner's validator before execution. The linked 2D project's existing
`project` kind, ID, version and v1 structure are checked by the production owner;
loading its cast/media closure still belongs to that owner's loader. Paths are relative to the project
root, even inside nested manifests. They are NFC POSIX paths without absolute
paths, traversal, backslashes, drive/URI prefixes, device names, control characters
or trailing-dot/space aliases. Filesystem symlinks and nonregular inputs fail.

The loader is a **read-only admission operation on stable input files**, not a
transaction or sandbox against a malicious concurrent filesystem writer. It
checks hashes during loading and returns no promise that files remain unchanged
afterward. A worker must revalidate the actual bytes it consumes at its own job
admission boundary and operate on a protected input snapshot. This foundation
adds no extraction, publication, shared-file mutation or arbitrary execution.
Budgets cap files (4096), bytes (1 GiB), nodes per graph (10000), nesting (128),
manifest bytes (16 MiB), frames and track keys. Project budgets may only tighten
these caps. Over-budget input fails; no truncation or fake success is returned.

## Coordinates, transforms and timing

Coordinates reuse the existing rig convention: right-handed +X right, +Y up,
+Z character forward, meters/radians/seconds, XYZW normalized quaternions,
column-vector mathematics, local `T × R × S`, world `parent_world × local`.
The XZ plane is ground; camera-local view direction is **−Z**. Quaternion rotations
are authoritative; Euler angles/matrices are not accepted as competing persisted
orientations. This follows the [glTF 2.0 coordinate and node transform convention](https://registry.khronos.org/glTF/specs/2.0/glTF-2.0.html#coordinate-system-and-units).

Node transforms use the existing rig fields:
`{translation:[x,y,z], rotation:[x,y,z,w], scale:[x,y,z], pivot?:[x,y,z]}`.
Quaternions must already be unit length. Scale must be positive, nonsingular and
bounded; mirrored/negative scales are explicitly unsupported in v1. They are
rejected rather than silently changing normals, winding or character identity.

The optional pivot is a separate **rotate/scale about point** adapter:
`T(t) × T(p) × R × S × T(−p)`. Translation retains the original rig TRS meaning;
the effective matrix translation is `t + p − R*S*p`, not a second world pivot
position. No-pivot transforms exactly preserve rig behavior. A glTF consumer must
use this evaluated matrix or deliberately bake that effective translation; glTF
has no independent pivot field.

`scene3d_math.evaluate_transforms(scene)` returns static local/world matrices,
world position, orientation and scale, decomposability and inherited visibility.
World orientation/scale are `None` when nonuniform ancestor scale induces shear;
the exact matrix remains available. The evaluator rejects unexpanded prefabs,
constraints, attachments and animation bindings, whose owning evaluators are not
implemented by this foundation. It does not silently ignore those declarations.

`to_blender` maps `(x,y,z)` to `(x,−z,y)` via the existing rig basis and conjugates
matrices once. `from_blender` is its inverse. Canonical glTF coordinates need no
basis conversion; `to_gltf`/`from_gltf` only transpose column-major serialization.
Independent numeric tests cover nonzero pivot hierarchies and both conversions.
Future render/export adapters must not apply these conversions twice.

For an explicitly requested 2D overlay, `overlay_point` requires pixel origin,
pixels-per-meter and depth, mapping to the canonical XY plane with Y inverted.
`overlay_rotation` maps clockwise 2D radians to negative rotation about Z. A
billboard node must be marked `billboard_2d` with `billboard: true`. These helpers
do not change the v1 camera or raster alpha. Future overlay rendering must retain
source straight alpha and define an orthographic camera matching the chosen
pixel origin/scale; perspective projection requires an explicitly authored camera.
No overlay rasterization or camera bridge is claimed here.

Frame rates are positive reduced `{numerator, denominator}` rationals, limited to
240 fps. Frame keys and interval boundaries require JSON integer components;
floating timestamps are not an alternate clock. Display intervals are half-open
`[0, duration_frames)`; a terminal key at `duration_frames` is allowed for boundary
state. Thus frame 720 at 24 fps is exactly 30 seconds. Clip/constraint/render
intervals must be nonempty and fit their authoritative duration. Track value
dimensions, quaternion norms and interpolation policies are checked. Rotation
interpolation reuses rig shortest-path `slerp`; no scene animation engine is
claimed. The tiny `frame_time(frame, fps)` adapter returns a `Fraction`; the
shared Animation3D exact-time owner can replace its implementation on integration
without changing this public shape.

## Reproducible example and validation

The checked-in [example](../examples/scene3d-contracts) contains seven actual
manifests and an original 3-vertex/1-triangle OBJ. Its fixture provenance and
unreviewed asset status are explicit. It demonstrates serialization and secure
hash/dependency admission, not a rendered environment.

```bash
python -m pip install -r requirements-delivery.txt
python scripts/generate_schemas.py --check
python scripts/scene3d_contracts.py examples/scene3d-contracts
python scripts/scene3d_example.py NEW_DESTINATION
PYTHONPATH=scripts:tests python -m unittest discover -s tests -p 'test_scene3d_contracts.py' -v
# Optional numeric transform tests require the separate 3D dependencies:
python -m pip install -r requirements-rig-test.txt
PYTHONPATH=scripts:tests python -m unittest discover -s tests -p 'test_rig_scene3d_math.py' -v
```

On Windows, set `PYTHONPATH` with `;` between `scripts` and `tests`. The existing
`python scripts/test_rig_gate.py schema-math` runs the numeric tests in 3D CI;
contract/file-loading tests also run in the existing 2D gate with NumPy blocked.
The example refuses an existing destination. Its direct file creation is for a
new, caller-owned fixture directory only; it is not a package publisher.

The implementation's focused execution passed **48 tests**, including real
fresh-process reopening and actual geometry-byte/hash tampering. Source delivery
inventory and generated schema/template checks passed. Exact source revision,
full legacy regression results, CI and independent Astra review are recorded in
the PR; this document does not substitute pending checks with an approval claim.

| #59 requirement | Executable evidence |
| --- | --- |
| Current production baseline and historical missing-media distinction | Original source inventory verification; unchanged legacy contracts; complete existing 2D suite and pilot cases remain required in CI. |
| Strict project/scene/shot/node/asset/prefab/render plus animation schemas | All eight generated schemas validated; valid document roundtrips; nested unknown-field/version/type negative tests. |
| Real hash-bound references and dependency graph | New-process load of actual seven-document+OBJ package; tampering/missing bytes, wrong identity despite correct hash, raw-first reference bypass, lock coverage, alias/conflicting hash and budget regressions. |
| Y-up SI TRS/quaternion and Blender/glTF conversions | Existing rig math reused; independent hand-computed hierarchy/pivot, shear, basis/column-major roundtrip and overlay direction tests. |
| Preserve v1 and reject inconsistent transforms/versions/graphs | Frozen legacy assets and v1 unchanged; negative quaternions/scales/NaN, duplicate/missing parents, root inventories, cycles, constraints/attachments, camera/node references and half-open exact timing tests. |
| Truthful capability boundary | Backend `unavailable`; dynamic evaluator declarations fail; no fabricated renderer/provider/approval receipts; geometry inspection stays with its owner. |
