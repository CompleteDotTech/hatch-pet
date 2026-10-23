# Model3D #43 implementation audit and acceptance map

Starting default revision: `6943607c4e678a447536384566ea6230cc1a1d27`, after independently
reviewed PR #200 merged and #51 passed post-merge verification. The full roadmap
snapshot includes 180 issues, 168 native parent edges, 200 native dependency edges
and all 35 comments at capture time. Parent #10 and its complete continuation,
#43's checklist and the other subsystem integration requirements remain authoritative.
See the execution ledger on `agent/roadmap-capture-20261023` and #43's ownership comment.

## Reuse and boundaries

| Existing authority | Use in this slice |
|---|---|
| `rig_contracts` | Canonical Y-up/meters/XYZW basis and existing schema construction idioms. Independently named Model3D contracts; no replacement of rig contracts. |
| `rig_errors` / decomposition path policy | Existing structured errors, strict duplicate-key/nonfinite JSON, portable spelling, hashing and contained paths. |
| `rig_import`, `rig_gltf`, `rig_obj`, `rig_models`, `rig_geometry` | Decode real geometry, inspect hierarchy/skins/clips, enforce existing format/resource limits and measure bounds/counts. No parallel mesh or importer implementation. |
| `rig_jobs.code_signature` | Existing implementation fingerprint for the inspection authority; no duplicate job store. |
| Existing production acquisition, versioning, reviews and archives | Left authoritative and unchanged. Model3D job/export/review fields describe records; this slice does not instantiate a new lifecycle or grant approval. |
| Existing schema generator / test collectors | Generate the additive schema and isolate only the new 3D test namespace from dependency-free legacy execution. |
| Existing robotic GLB and source payload | Referenced unchanged by the executable example, with exact hashes and fixture status. No fabricated artwork, generation receipt or license. |

No AGENTS.md, CONTRIBUTING or CODEOWNERS was present in the captured full repository
tree. README, SKILL, DELIVERY_STATUS and the existing contract/import/persistence
boundaries were inspected. The implemented Y-up basis takes precedence over earlier
unimplemented Z-up suggestions in related issue prompts; an explicit basis adapter
is required at any boundary, never a silent reinterpretation of legacy pixels.

## #43 checklist and evidence

| Required work | Implemented behavior / executable evidence |
|---|---|
| Record baseline and preserve existing contracts | Full clean baseline at `7995804`: 853 tests, zero failures/errors, nine local environmental/optional skips. Initial host-startup NumPy isolation failure retained separately. Current source-delivery verification passes actual restored v3 payloads. Older unavailable historical/private media remains unavailable. |
| Strict request/source/asset/part/material/uncertainty/job/export schemas | `model3d_contracts.py` generates all eight definitions and runtime uses the same generated definitions. `generate_schemas.py --check` verifies parity. No legacy generated-schema bytes change. |
| Hashes, units, bounds, versions, graph references and unknown fields | Unit tests cover malformed values, unsafe paths, declared/actual geometry mismatch, missing and same-size corrupt payloads, cycles, conflicting immutable versions, graph depth, source modality, calibration, fixture provenance and unsupported fields. |
| Capability detection and isolated dependencies | `model3d.py capabilities` reports installed packages without importing the numeric backend or making network/provider calls. Existing rig dependency files are reused. `doctor.py` advertises the bounded read-only feature and explicitly says generation/provider execution/approval are false. |
| Real affected workflows | `model3d.py validate` decodes the retained robotic GLB: 706 vertices, 1,368 triangles, 11 skin bindings and three actual clips. GLB SHA-256 `38c95ce549f58bdef2f06ce4652ac2026ca99c744f9593f348d0d1696131296e`; original fixture source SHA-256 `0a1c4fe3927c93588964f3cea225c4b78abe0ce096fd3d6fae6159e4277274ad`. |
| Persistence/failure safety | Read-only source root, private staged snapshot, post-read identity checks, complete dependency validation, bounded copies and cleanup. Tests restore all declared payloads into a fresh directory, compare results, delete required content and require rejection. Concurrent readers return the same result without changing inputs. |
| Legacy regressions | Existing schema/math gate passes all 20 tests and still discovers all 790 2D tests with 3D imports blocked. Full changed-tree results and remote checks must be recorded against the actual published head before merge. |
| Documentation and honest capability limits | `model3d-contracts.md`, README/SKILL additions and executable example document semantics and exclusions. Structural, payload, geometry, visual and licensing evidence remain separate. |

The test that edits an original model after snapshot creation still runs the real
existing decoder against the verified copy. It tests snapshot isolation; it is not
a mocked model-generation or rendering success. Likewise, deliberately malformed
model fixtures are negative inputs, not substitute production artifacts.

## Unmet gates and scope

Independent review and current-head CI are required before merging this slice.
No self-review is independent approval. #43 stays open until its complete checklist,
review, checks, merge and post-merge verification succeed. Parent #10 and #44–#50
remain open. Actual model generation/reconstruction, optimization, full export
roundtrips and production-art approval are not supplied by this contract slice.
The existing #201 rig-correction branch remains owned by its earlier worker.

This slice creates no alternate registry, renderer, persistence database, paid
provider, review authority or scheduler. Future producers must emit these contracts
and pass real payload inspection; merely selecting a method in a request is not
an implementation of that method.

## Executed changed-tree results

The local source-hash-bound run completed **893 tests, zero failures/errors, ten
explicit environmental/optional skips** in 245.662 seconds. All **31 new Model3D
tests passed without skips** in 5.714 seconds, including actual OBJ and an independent
pygltflib read. No source/test file changed during the full run. The targeted log, full-suite summary/checksum, source hashes,
capability discovery and actual GLB inspection are retained in
`tests/results/model3d-contracts-20261023/`. Remote CI and independent review remain
separate gates; these local results do not claim that either has completed.
