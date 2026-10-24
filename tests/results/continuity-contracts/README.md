# Continuity foundation validation

Frozen local execution used Python 3.12.15 and pinned public-delivery dependencies.
`regression.log` records 69 passing tests in 26.635 seconds with no failures,
errors or skips: 21 new contract/lifecycle cases plus existing production-v1,
optional-dependency/atlas/catalog compatibility and retained production-pilot
cases. The compatibility suite discovered 823 ordinary 2D tests; it did not execute
all 823. The public pilot cases exercised actual source/project loading and
existing provenance, timing, review and continuity protections.

`verification.json` hashes every script, all new generated schemas and focused
test/helper files before and after the frozen run, and checks protected original
inputs against base `a08569c`. It binds the raw log and records limitations. These
results describe those input hashes, not a future modified head. Generated-schema
parity, actual CLI validation of the retained synthetic revision, and exact native
fixture byte verification also passed. The retained fixture reference payloads
are 71-byte OBJ and 14-byte PPM files; this is byte verification, not a geometry
inspection or reference-render approval.

Earlier development runs passed 64 tests before schema/regex hardening and 67
before the last provenance/CLI cases. They are superseded for the final tree;
their source snapshots/logs remain session-local under `/tmp/continuity113-*`.
No earlier passing output is presented as validation of later source bytes.

Tests simulate explicitly labelled supplied review decisions only to exercise
promotion/rejection. They do not constitute actual assistant/human visual
inspection, production approval, changed-asset compatibility or full continuity
acceptance. Real native geometry inspection, event replay, continuity comparison,
reference rendering, evidence lifecycle, scene integration and final production
demonstrations remain separate open work. Windows/macOS execution and current-head
CI require the published PR; no cross-platform execution is claimed here.
