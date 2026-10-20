# Public production validation summary

**Current repair audit:** the historical passing result below used the author's retained assets. A fresh checkout is missing 113 source parts and 39 audio parts, so the retained-pilot setup currently fails. The test has not been disabled. See [current delivery status](../DELIVERY_STATUS.md) for the exact outstanding condition and portability fixes.

The current combined regression against merged main `66b7590` ran 764 tests in 331.379 seconds: zero test failures, one retained-pilot setup error and two optional capability skips. The missing bundle prevented 13 additional pilot tests from starting. Separate Windows checks passed five movie/PCM/path cases, including actual encoding. These results supersede the historical result below for the public branch's present readiness.

## Historical author-environment result

The final local suite ran **299 tests: 298 passed, one skipped, zero failures or errors**. The [exact public test output](../tests/results/production-final-public.log) records the command, UTC interval, test results and the 91 implementation/test/configuration hashes that remained unchanged throughout the run. It contains no production source payload or render/review dependency inventory.

## What was verified

The fresh original baseline passed all 123 cases. The final full run, after the acquisition-input preservation and Git transport portability fixes, retained all 123 passes and completed all 11 actual-browser tests, all 13 retained-pilot tests, and all 11 new preparation-preservation tests. The complete suite took 160.239 seconds under unittest and exited successfully. The actual browser was Chrome 155.0.8059.84; Python was 3.12.14 and Pillow 13.0.0.

The only skip was the unavailable Krita application. Structural and pixel-roundtrip tests of the OpenRaster handoff passed independently. Neither those tests nor browser playback constitute a verified native editor timeline integration or human production-art acceptance.

The preservation fix rejects existing acquisition destinations, sibling input collisions, symlinks and recovery journals before writes; exclusive creation and ownership-aware cleanup preserve other writers' data. Its eleven regressions exercise both failures and real model-free preparation for new characters.

The final Git transport regression exercises all three content-addressed bundle paths with `core.autocrlf=true`. It checks exact index blobs, actual checkout bytes, part hashes and complete bundle verification, while an unprotected text control proves conversion is active. The repository marks only those immutable `.bin` fragments as binary. A separate isolated negative control without the copied attributes failed as expected; no original payload was reformatted.

## Compatibility and migration

The default Codex profile, state order, frames, millisecond timing, dimensions, transparency and package compatibility remain unchanged. Production projects use a separate versioned project/cast/clip/scene contract with integer-frame or rational timing. Existing pet runs remain pet runs; migration and archive restoration retain identities and history and report stale dependencies. No live installation, settings change or WSL shutdown was performed.

## Public delivery boundary

See [delivery status](../DELIVERY_STATUS.md). Automatic approval review has blocked further production media and derived evidence publication. The complete local project, demonstrations, reviews and detailed reports are retained, but the public source transports remain incomplete. Consequently this local passing result is not a claim that a fresh public clone can restore the pilot or pass its retained-source tests yet. The pull request must remain unmerged until the publication blocker is resolved and the complete public snapshot is verified.

A [synthetic demonstration](../examples/production-fixture/README.md) remains reproducible without model calls or pilot media. The detailed local production validation and traceability reports distinguish fixture metrics, actual assistant visual decisions, offline timing, adapter roundtrips and unavailable external integration. Those detailed records are held with the blocked evidence rather than republished through this summary.
