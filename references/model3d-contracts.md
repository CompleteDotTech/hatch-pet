# Model3D contract and payload foundation

This is the bounded #43 foundation under #10, not a completed model-generation
system. It adds eight strict, independently versioned document types and a working
read-only verifier. It reuses actual rig geometry/import inspection rather than
creating another mesh representation, registry, renderer, job store or review store.

## Public operations

Install the existing isolated 3D dependencies:

```sh
python -m pip install 'Pillow>=10.1' -r requirements-rig.txt
python scripts/model3d.py capabilities
python scripts/model3d.py validate --file examples/model3d-contracts/robotic.json --root .
python scripts/model3d.py validate --file examples/model3d-contracts/robotic.json --structural-only
```

The first validation checks both original source bytes and the actual animated
GLB. The second checks only the document: it reports `payloads_verified: false`
and `geometry_inspected: false`, even when all structural checks pass. Neither
operation generates a model, calls a provider, grants approval, or publishes files.
All output is JSON on stdout; expected failures use a JSON error on stderr and
exit status 2. Argument errors use argparse's ordinary exit status 2 and help text.
Commands never overwrite the selected project. Redirect stdout explicitly to
retain a report outside a protected source directory.

Python callers import `validate_contract` from `model3d_contracts` and
`validate_document` / `validate_file` from `model3d_validation` (add `scripts` to the
module path, following the existing repository convention). The first performs no
file I/O. The latter two verify the declared closure by default, raising the shared
`RigError` for invalid contracts/payloads and ordinary `OSError` for OS failures.
A successful observation refers to the copied, hash-verified snapshot, not a lock
on mutable source files. Later source edits require a new verification.

## Versioned contracts

Canonical definitions live in `scripts/model3d_contracts.py`; generated JSON Schema
Draft 2020-12 is `profiles/model3d.schema.json`. Regenerate with
`python scripts/generate_schemas.py`; CI checks `--check`. Every document requires
`schema_version: 1` and an explicit `model3d-*` kind. No legacy document is migrated
or accepted as a 3D document.

| Kind | Meaning and important validation |
|---|---|
| `model3d-request` | Target identity, source roles, method intent, description/negative constraints, exact source/identity/style references, dimensions and scale evidence, desired formats/semantic parts, assumptions, provider selection, seed and resource ceilings. Source modalities and calibration must match the selected intent. This is not a generation receipt. |
| `model3d-source` | Exact original file, stable source version/role, fixture/origin distinction, supplied provenance and license claims, and explicitly unknown/supplied/estimated camera data. Unknown calibration cannot contain invented matrices. |
| `model3d-asset` | Exact source/runtime inventories, canonical geometry reference, measured counts/bounds, part/material annotations, version-pinned dependency manifests, uncertainties, review claims and budgets. Actual geometry, counts, bounds, mesh IDs and referenced file closure are verified. |
| `model3d-part` | Stable semantic ID, parent, local TRS, whole-mesh identities, material/source/uncertainty references. Duplicate IDs, cycles, missing parents, nonunit rotations, singular scales and multiple whole-mesh ownership are rejected. |
| `model3d-material` | Versioned glTF-compatible PBR parameter/slot annotation, texture references and color interpretation. Color textures use sRGB; normal/roughness/metallic/occlusion use linear data. This foundation does not assert equivalence between annotated material parameters and renderer output. |
| `model3d-uncertainty` | Target, observed/inferred/unknown classification, source evidence, explanation, optional measured confidence and its method. Missing confidence remains null; a number without evidence/method is rejected. |
| `model3d-job` | Request hash, target, explicit state, bounded attempts, outputs, failure details and dependencies. A complete declaration needs outputs and no active error; the request must resolve to a matching request contract. No scheduler or provider execution is implemented here. |
| `model3d-export` | Exact asset revision, requested format, declared state, actual output references, tool identities, declared losses and optional independent-inspection evidence. A complete claim cannot have an empty inventory. Output hashes and the source asset's geometry are checked; format-specific export roundtrip/Blender/archive verification is not implied. |

Unknown fields, versions, duplicate JSON keys, NaN/Infinity, oversized values,
unsafe relative paths and conflicting records are rejected. Schema validation
establishes structure; runtime semantic checks additionally enforce referential
integrity, geometry measurements and payload evidence. A JSON Schema-only consumer
must not claim to have run those semantic or filesystem checks.

### Coordinates, timing and annotations

Reuse `rig_contracts.COORDINATES`: right-handed, +X right, +Y up, +Z character
forward, meters, radians, XYZW unit quaternions, column-vector mathematics and
seconds. Local TRS is composed as T × R × S. Positive nonsingular scale is the
initial Model3D part contract; mirrored/negative transforms need an explicit future
version rather than an undocumented reinterpretation. Existing imported glTF
geometry remains subject to the existing importer's documented reflection rules.

Source camera matrices are serialized as 16 **row-major** values and applied to
column vectors. Their rotation must be a proper orthonormal basis, with affine
last row `[0,0,0,1]`. Perspective intrinsics are a row-major 3×3 matrix; orthographic
size is in meters. Supplied/estimated calibration needs image dimensions and a
hash-bound evidence file. Validation does not establish that a calibration was
physically measured; the source classification remains a claim requiring review.

The asset inspector measures geometry after the existing importer's canonical
world-space normalization. Part transforms are validated authoring annotations;
this foundation does not apply them as another hidden import transform or offer
an editing/rendering command. Binding names come from the actual importer, not
assumed anatomical segmentation. Material annotations, job/export state and review
claims are never promoted to observed visual, licensing or provider approval.

## Exact paths, versions and dependency closure

All references, including those inside child asset manifests, are relative to one
explicit common project root. They are **not** relative to each child manifest's
directory. Use `--root` for manifests nested below that root. Each file reference
includes portable path, exact SHA-256, positive byte count and media type.

Each asset dependency pins an ID, semantic version and hash-bound JSON manifest.
Conflicting hashes for the same immutable ID/version fail. Cycles, unknown target
versions, path aliases, case collisions and non-NFC spellings fail. Global and
per-document transitive file/byte/depth ceilings are enforced, including cached
shared dependencies reached through a deeper path.

The verifier copies all declared files into a unique temporary directory while
checking actual sizes, SHA-256 and file identity. It decodes models **only from
that snapshot**. Actual buffers, materials' image resources and other importer
resources must be present in the asset's runtime inventory, even when another
provenance record happens to provide identical bytes. Missing/corrupt required
content fails; a valid manifest alone cannot pass payload verification.

Files are streamed in bounded chunks. Links and nonregular files are rejected.
On openat/O_NOFOLLOW platforms, held directory descriptors prevent parent renames
from redirecting individual file reads. The portable fallback rechecks path and
file identities, but is not a sandbox against a hostile process concurrently
replacing directories; isolate untrusted writers at OS level. Neither variant
claims to make a mutable project a transactional multi-file source. SHA-bound
snapshot consistency and source-directory locking are different guarantees.

Default maximums are 256 MiB per file, 1 GiB aggregate payload, 4,096 files/parts,
1,000,000 vertices, 2,000,000 triangles, dependency depth 16, and 2 GiB estimated
geometry memory. Project limits may lower these hard ceilings. Static image inputs
are decoded and limited to 16,777,216 pixels and the snapshot's memory budget.
Multiframe images are rejected in this initial contract. Native geometry budgets
are delegated to the existing bounded importer, not disabled.

Bounds tolerance is `abs(actual-declared) <= 1e-6 * max(1, abs(actual), abs(declared))`
in meters. Quaternion norm tolerance is 1e-6. These are structural/numerical checks,
not artistic tolerances or measurements of reconstruction accuracy.

## Capability and compatibility boundaries

Implemented and executed: strict validation, exact dependency/file verification,
real GLB and external-resource glTF decoding, existing rig/animation preservation
inspection, CLI JSON failures, read-only concurrent verification, independent
restoration of the declared closure, and negative missing/corrupt/fake mesh tests.
The OBJ route reuses the existing importer; its limitations remain unchanged.

Supported only through other existing rig commands: skeletal generation, skinning,
animation, native previews, Blender authoring and rig archives. This foundation
neither reimplements nor falsely upgrades them. Current verification reports bind
to the actual existing rig implementation hash and installed software versions.

Not implemented here: text/image/multiview generation, arbitrary model-provider
adapters, topology repair/LOD, material editing/render equivalence, model job
execution, general asset-library management or a Model3D editor. No paid service,
model download, GPU probe or network request occurs. Blender-native model inputs
are deliberately excluded from this read-only canonical inspection path; use the
existing explicit trusted Blender workflow and its separate acceptance evidence.

GLB/glTF/OBJ retain the existing importer's supported primitive, attribute,
extension and local-resource policies. This is not a claim of unrestricted glTF
extension support. Sources requiring unsupported adapters fail explicitly rather
than being flattened or silently converted. Output/approval state remains distinct
from contract validity, file integrity and actual geometry inspection.

The fixed Codex atlas, 2D schemas, pixel-space transforms, audio-capable production,
state/style IDs, existing provenance and historical reviews are unchanged. The
legacy test collectors explicitly classify the **new** `test_model3d_` namespace
as optional 3D; no existing 2D test is removed, skipped or reclassified. The new
cross-platform workflow runs those new tests separately with 3D dependencies.
