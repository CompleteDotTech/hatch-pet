# 3D rigging implementation audit

## Starting point

Audit date: 2026-10-20. Starting commit:
`19649be829a9badcd789d381a3a22ebe2b3f3a54` (main).
The fresh clone was clean; the remote advertised only main and GitHub returned
no open PRs. No repository or parent `AGENTS.md`, `.entire` instruction, or CI
workflow was present. Work uses the isolated `feat/3d-character-rigging` worktree.
A separate local animation branch contained an uncommitted math module; it is
not part of the audited base and is not modified or treated as an integration.

Read the complete supplied 38-section specification, README, SKILL, delivery
status, profile and production contracts, catalog loader, source and identity
interfaces, decomposition corrections/packages, operational/archive references,
doctor, schema generator, CLI dispatch and relevant regression tests.

## Confirmed architecture and decisions

| Surface | Confirmed behavior | Integration decision |
| --- | --- | --- |
| `hatch.py` | Resumable raster lifecycle and early catalog dispatch | Add an early, lazy `rig` dispatch; preserve existing parsers |
| `asset_contracts.py` | Pixel limits, source hashing, identity and evidence | Reuse hashing conventions, keep mesh budgets and coordinates separate |
| `state_catalog.py` | 416 real definitions, aliases, anatomy and bounded selections | Resolve actual IDs and anatomy; never imply 416 finished 3D clips |
| `production_*` | Pixel-space layered casts, integer scene frames, scoped review | Separate schema/time base; explicit rendered-frame handoff only |
| `character_decomposition.py` | Exact 2D masks, uncertain semantics and source lineage | Hash-bound advisory handoff; no inference of 3D topology from masks |
| `decomposition_review.py` | Immutable revisions and stale-receipt rejection | Apply equivalent revision and artifact binding to native rigs |
| `decomposition_package.py` | Portable names, bounded ZIP inventory, traversal rejection | Reuse portable-name validation; independent 3D package receipt |
| 3D acquisition | No generated-mesh provider in main | Genuine local GLB/glTF/OBJ imports and explicit provider-result validation |
| Rigging/animation | No mesh skeleton, weights, FK, IK, morph or export engine in main | Add optional NumPy-based core and Blender 4.5 adapter |
| Browser | Existing Playwright raster tests | Add actual Three.js/WebGL asset inspection with local pinned modules |

Use right-handed +X right, +Y up, +Z forward, meters, seconds, radians and
XYZW quaternions. Matrices act on column vectors; world = parent-world × local.
glTF stores matrices column-major. Blender conversion is a proper +90-degree
X rotation, mapping canonical forward to Blender -Y and canonical up to +Z.

## Baseline evidence

With isolated Python dependencies and actual Chromium 140.0.7339.16, the
unchanged source ran **764 tests in 265.135 seconds**: **one error, two skips**.
The error is `ProductionPilotTests.setUpClass`, where the incomplete original
production source transport prevents reconstruction. Skips are native Krita
and the opt-in decomposition browser edit case. Production browser playback
and the other Chromium suites executed. The full log is retained as
`tests/results/rig-baseline.log`.

Initial attempts were environmentally invalid: a full shared filesystem and
missing test dependencies. Those interrupted attempts are not counted as
regression results. No existing test is deleted, weakened, relabeled or skipped
to accommodate this feature. The missing art/audio/review-history boundary was
recorded at the starting commit. Upstream PR #8 subsequently restored the exact
original payload and merged as `594177b865b3401d1b9748860931ee0d63b859cb`; that
repair was integrated before the final frozen-source regression. Consult the
acceptance report and current `DELIVERY_STATUS.md` for the resulting status.

| Frozen compatibility file | Starting SHA-256 |
| --- | --- |
| `profiles/codex-v1.json` | `f4e0279f8634ea53ef544ecb49b9a71ec2565c61ec5b8e63163ecc5ead478a6b` |
| `profiles/profile.schema.json` | `afba01bc16c4f6c297d1b95b62803c7a5b989e0fa9b967c33e5d50471091163c` |
| `assets/playback.js` | `9aa7d5228de0a57cd443b70c14b160cb22238d21a861a0fb06f6b4bcc6ccbc79` |
| `state-library/catalog.json` | `970139db7291c4233ef75e37ffd6abe0385c8f165dd37b339326a4e8647f3de9` |

## Risks and acceptance boundaries

Template fitting is an anatomical suggestion unless supplied landmarks or
existing compatible rig data support it. Skinning must numerically move actual
mesh vertices; a hierarchy is insufficient. Rich control rigs remain native or
in Blender; glTF receives evaluated standard channels. Independent Blender and
browser loading must validate geometry as well as animation names. Procedural
demonstrations are labeled synthetic fixtures and cannot approve production art.
Optional-tool absence is a blocker for its release gate, not a passing result.

Authoritative interchange reference:
[Khronos glTF 2.0](https://registry.khronos.org/glTF/specs/2.0/glTF-2.0.html).
