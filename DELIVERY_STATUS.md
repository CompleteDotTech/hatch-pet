# Production workflow delivery status

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
