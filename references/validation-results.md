# Local delivery validation

Recorded 2026-10-19T03:47:45.903033+00:00. The checkout started clean at `3d226b1`; these implementation checks were completed locally before repository publication. No live application installation, deployment or production model call was performed. Temporary installation/rollback tests are isolated fixtures. WSL was used only for native cursor decoding; it was not shut down or terminated.

## Baseline and final regression

- Fresh baseline: **67 passed** in 64.506 seconds, including the exported-browser test.
- Final frozen-code regression: **123 passed**, zero failures/skips, in 222.049 seconds: `python -m unittest discover -s tests -v`.
- [Full final log](../output/delivery-regression.log). An earlier test process was stopped after a source-version change invalidated its in-flight fixture evidence; its log is preserved separately and is not final acceptance evidence.
- `python scripts/generate_presets.py --check`, `python scripts/generate_schemas.py --check`, `python -m compileall -q scripts tests`, installed skill-creator `quick_validate.py`, and `git diff --check` passed.
- All ten original example profiles completed fixture preparation, acquisition, validation, review and export. The default nine-state Codex fixture completed the same core pipeline.
- Default `profiles/codex-v1.json` is byte-identical to baseline `3d226b1`, SHA-256 `f4e0279f8634ea53ef544ecb49b9a71ec2565c61ec5b8e63163ecc5ead478a6b`. Its generated state table matches the reference. The historical bundled atlas also passes geometry/transparency validation at 1536×1872, with zero transparent-RGB residue.

## New demonstrations

`python scripts/demonstrate.py --all --output-dir output/delivery-examples` completed with all ten use-specific acceptance checks passing. Each folder contains actual source fixtures, run/provenance/history, indexed frames, a review desk, export, package and acceptance JSON. Fixture reviews exercise gates; they do not certify production artwork.

[Open the local demonstration index](../output/delivery-examples/index.html).

| Use | Preset | Result | Evidence |
| --- | --- | --- | --- |
| U01 | assembly | pass | [outputs](../output/delivery-examples/assembly/export/) / [receipt](../output/delivery-examples/assembly/acceptance.json) |
| U05 | communication | pass | [outputs](../output/delivery-examples/communication/export/) / [receipt](../output/delivery-examples/communication/acceptance.json) |
| U03 | configurator | pass | [outputs](../output/delivery-examples/configurator/export/) / [receipt](../output/delivery-examples/configurator/acceptance.json) |
| U10 | craft | pass | [outputs](../output/delivery-examples/craft/export/) / [receipt](../output/delivery-examples/craft/acceptance.json) |
| U08 | cursor | pass | [outputs](../output/delivery-examples/cursor/export/) / [receipt](../output/delivery-examples/cursor/acceptance.json) |
| U04 | flipbook | pass | [outputs](../output/delivery-examples/flipbook/export/) / [receipt](../output/delivery-examples/flipbook/acceptance.json) |
| U06 | perception | pass | [outputs](../output/delivery-examples/perception/export/) / [receipt](../output/delivery-examples/perception/acceptance.json) |
| U02 | process | pass | [outputs](../output/delivery-examples/process/export/) / [receipt](../output/delivery-examples/process/acceptance.json) |
| U09 | protocol | pass | [outputs](../output/delivery-examples/protocol/export/) / [receipt](../output/delivery-examples/protocol/acceptance.json) |
| U07 | regression | pass | [outputs](../output/delivery-examples/regression/export/) / [receipt](../output/delivery-examples/regression/acceptance.json) |

## Additional observed checks

- Real Chromium 145.0.7632.6 exercised actual exported playback, one-shots, held frames, completion, legal transitions, priority/interruption, queue bounds, cancellation, late timers, hidden-page pause/resume and reduced motion. Review downloads bind exact artifacts. Board, configurator and cursor adapters were exercised locally.
- Representative PDF pages and browser surfaces were rendered and visually inspected. Print source cells scale to their common declared print viewport, labels/legends are readable, and inspected desktop pages have no horizontal overflow. [Inspection records](../output/delivery-evidence/inspection.json), images in that folder.
- Native `libXcursor.so.1` loaded all six cursor frames; hotspots `(4,4)`, 80 ms timings and every premultiplied pixel hash match the independent export decoder. No display was opened. [Native evidence](../output/delivery-evidence/native-xcursor.json).
- Full archive/restore was exercised through the CLI into another directory; run identity and current validation/review survived with no revalidation required. [Restoration evidence](../output/delivery-evidence/restoration.json). Version-change, tamper, traversal and migration failure paths are covered by tests.
- A vertically stacked source fails conservative horizontal segmentation, then passes exact rectangular annotation extraction with complete provenance. [Grid/diagnostic evidence](../output/delivery-evidence/grid/acceptance.json).
- A supported 16-state/1,024-frame profile passed resource preflight. One representative maximum-count row (64 frames, 262,144 source pixels) was processed in 0.7709 seconds with 4735376 Python-traced peak bytes. This is one-row measurement, not a whole-profile or native-memory benchmark. [Performance evidence](../output/delivery-evidence/performance.json).
- Environment: Python 3.14.3, Pillow 12.2.0; WebP, PNG/zlib, JPEG and FreeType are available. [Version/code hashes](../output/delivery-evidence/versions.json).

## Compatibility and specific remaining limits

Default Codex dimensions, state order, frame counts, exact timings, transparency and package manifest remain unchanged. Profile schema 1 remains supported. Controller schema-2 runs use explicit `migrate`; old extraction evidence is revalidated under schema 4. Animation metadata is schema 2; strict external v1 consumers must update their schema check. Historical diagnostic paths remain verbatim while operational references are portable.

Identity, direction, action meaning and scientific/technical content still require genuine visual or subject-matter review. Structured metadata and metrics assist but do not prove semantics. Ambiguous occlusion, complex opaque backgrounds or connected overlapping poses may require source repair; annotations cannot reconstruct missing content. Shared scaling requires comparable source units and reviewed landmarks. Browser timings are best effort, not laboratory onset measurements. Physical assembly, printing calibration, clinical suitability and live application integrations remain external acceptance work. Model-call identifiers are unavailable unless the generation provider exposes them; none were invented.

There are no remaining blockers for the requested local implementation and deterministic demonstrations. These limits are documented operating boundaries, not claims of production-art or external-integration acceptance. See [traceability](traceability.md) for L01–L10, I01–I10 and U01–U10 mappings.
