# Production workflow delivery status

## Current repair audit (2026-10-20 UTC)

The current request authorizes PR repair and merge. The outstanding production payload is not available in this checkout or its fetched Git history: the source transport lacks 113 parts (5,910,402 bytes, affecting 30 original files), and the audio transport lacks all 39 parts (1,715,251 bytes, affecting 16 original files). The review-history index is also absent. The prior author's private-environment validation below does not establish fresh-checkout reproducibility.

The integration repair preserves the merged style catalog and character-state library. UTF-8 test reads now preserve the exact Unicode metadata on Windows. The synthetic scene demo now writes portable forward-slash review references; an explicit Windows/POSIX regression covers the original failure. Its three scenes can be reproduced without the missing production payload.

The retained-pilot test remains enabled and fails at exact source-inventory verification. Restore the original complete source/audio bundles, verify them with `production_sources.py verify`, and rerun the complete suite before merging. No replacement artwork, synthetic substitute, fabricated review, or skipped pilot check has been introduced.

After integration with main `66b759039a4ce4685d1265750e3ad28f02fd4ee0`, the complete combined Linux suite ran **764 tests in 331.379 seconds**, with **zero test failures, one retained-pilot setup error and two optional capability skips**. Thirteen retained-pilot cases could not start because their original source bundle is incomplete. The skipped capabilities were native Krita and FFmpeg/ffprobe; a separate Windows run passed all five selected movie/PCM/path tests, including actual FFmpeg encoding. Node, actual Chromium playback and decomposition editing ran in the combined suite. Its source copy was byte-verified and unchanged throughout.

The standalone synthetic demonstration successfully rendered and validated all three scenes (300 frames), recorded explicitly synthetic review evidence, and verified reuse. Its performance storyboard was inspected. The archive repair also rejects original ZIP/OpenRaster names that Python would otherwise normalize before validation; targeted Windows and POSIX path checks pass. Generated schemas, compilation and the installed skill metadata validator pass. No native Krita integration or production-art acceptance is claimed.

## Earlier author validation

The feature branch implements versioned casts, layered components, reusable motion and facial tracks, dialogue and coordinated props, scene/camera contracts, deterministic rendering, local previews, scoped review, dependency tracking, portable archives and an OpenRaster handoff. Existing Codex asset contracts remain unchanged.

The [final local regression](references/production-public-validation.md) ran 299 tests: 298 passed and one optional external-application check was skipped. Its public test output is distinct from the production media/evidence held pending authorization.

## Public branch boundary

**This branch is not ready to merge.** Automatic approval review has blocked additional production media and derived review/evidence publication. Some previously accepted source parts and manifests are present, but the public production source transports are incomplete. Their presence must not be interpreted as a self-contained pilot distribution.

Implementation, procedural references, synthetic fixtures and regression tests can be reviewed independently. Production films, complete source/evidence records and verified archives have been retained locally; completed review outputs have been made available privately to the user. Media publication needs explicit payload authorization accepted by the automatic approval review before the remaining public delivery and merge can proceed.

The detailed local production traceability and validation reports are not fully published while that gate is unresolved. Links into pending production evidence may therefore be unavailable on the public feature branch. This is a delivery limitation, not an approval of missing evidence.

## Reproduce the independent synthetic workflow

```bash
python -m pip install -r requirements-test.txt
python scripts/production_regression_demo.py --output-dir /tmp/hatch-production-fixture --movie
python scripts/production.py --help
```

Use a new output directory. Optional movie creation requires FFmpeg/ffprobe; model calls and production-pilot media are not required. The synthetic acceptance files identify themselves as fixtures and do not establish production-art or external-editor acceptance.

## Repository delivery

The user authorized the repository workflow. The implementation and safe validation output are committed to `feat/cast-scene-production`. Complete retained production assets and evidence are preserved on a separate local branch pending publication authorization. The pull request must remain open while publication is blocked; no checks or branch protections may be bypassed. A completed merge and synchronized default branch will be reported only after they actually succeed.
