# Continuity foundation validation

The frozen execution at b7e0b13 (before the shared decoder integration) used
Python 3.12.15 and pinned public-delivery
dependencies. `regression.log` records 76 passing tests in 25.656 seconds with no
failures, errors or skips: 28 new contract/lifecycle cases plus existing
production-v1, optional-dependency/atlas/catalog compatibility and retained
production-pilot cases. The compatibility suite discovered 830 ordinary 2D tests;
it did not execute all 830. Public pilot cases exercised actual source/project
loading and existing provenance, timing, review and continuity protections.

`verification.json` hashes every script, all new generated schemas and focused
test/helper files before and after the frozen run, and checks protected original
inputs against base `a08569c`. It binds the raw log and records limitations. These
results describe those input hashes, not a future modified head. Generated-schema
parity, actual structured CLI validation, and exact native fixture byte
verification also passed. Retained fixture files are a 71-byte OBJ and 14-byte
PPM: this establishes exact bytes, not geometry inspection or rendered-reference
approval. Uninspected geometry statistics and bounds remain explicitly null.

The original reviewed commit 63f5810 had 69 passing tests, but independent Astra
reviewers exposed five security/numerical and three acceptance/representability
findings. Their correction adds real two-connection admission/CAS races,
project-source freshness, receipt-to-FIFO replacement, all-23-model integral-float
coverage, native asset/dependency migration closure, unavailable measurements and
cross-identity/index-integrity regressions. Those 76-test results are fresh after the continuity fixes, before the separately
reviewed shared decoder integration. `history-63f5810` preserves the exact old log/receipt; its internal paths
refer to that historical commit, not today's sibling files. Earlier uncommitted
development logs remain session-local under `/tmp/continuity113-*`.

Tests simulate explicitly labelled supplied review decisions only to exercise
promotion/rejection. They do not establish actual assistant/human visual
inspection, production approval, changed-asset compatibility, or full continuity
acceptance. Real asset inspection, event replay, rendered comparisons, native
review-adapter execution, scene integration and final production demonstrations
remain separate work. Windows/macOS execution, published-head CI and fresh
independent review remain gates; no cross-platform execution or new PASS is
claimed by this report.

After normal-merging independently reviewed shared decoder ffe872d, clean
committed source a5c6b24 ran all 28 focused continuity tests again in 4.228s,
zero skips/errors/failures. `post-helper-focused.log` and
`post-helper-verification.json` bind that exact committed code and confirm an
actual 5000-digit integer CLI input returns structured exit 2 without traceback.
The current standalone schema parity check passes. This targeted rerun is not
a claim that all 76 legacy-inclusive cases reran after the helper change. The
shared-helper's own retained tests and independent Astra report are separate
evidence. Any further source head needs fresh independent review/current-headCI.
