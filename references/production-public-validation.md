# Public production validation

## Current delivery contract

The October 20 recovery restored every missing artwork/audio fragment and the original review index from preservation commit `ebdb5d64a0d36e6a2fd6fbf5cb574fc6968f4404`. The [recovery audit](public-asset-recovery.json) records exact object identities and bytes. [Delivery status](../DELIVERY_STATUS.md) records publication and merge state independently of local implementation.

`production_sources.py verify-delivery` verifies all 63 logical transported files, 370 unique transport parts, four original imagegen acquisitions, five original speech recordings, 20 historical assistant decisions and all 13 distinct referenced supporting artifacts. The four bundle index hashes are pinned in [delivery-manifest.json](../examples/production-pilot/delivery-manifest.json). Ten historical inspection PNGs match their pre-existing hashes; no new artistic decision is inferred.

## Reproduce the complete gate

Use a fresh clone, Python 3.12, Git, Node, FFmpeg/ffprobe, and the pinned dependencies:

```bash
python -m pip install -r requirements-delivery.txt
python -m playwright install --with-deps chromium
python scripts/verify_public_delivery.py --destination delivery-verification --tests --render --video
```

The destination must not exist. Unset `HATCH_PRODUCTION_PILOT` and `HATCH_PRODUCTION_PILOT_ROOT`; the runner refuses private-source overrides. `HATCH_BROWSER_EXECUTABLE` may identify an already installed compatible Chromium executable. Browser launch failures remain failures. Native Krita may be supplied through `HATCH_KRITA_EXECUTABLE`; it is the only optional application integration. Windows additionally reports its unavailable POSIX named-pipe test as platform-inapplicable.

The command checks:

1. Every fragment, assembled source, pinned project file, acquisition receipt and historical evidence hash.
2. The complete regression suite, including legacy Codex atlas, styles, character states, decomposition, actual Chromium playback, retained production art, malicious transports and FFmpeg.
3. Full two-character/20-clip reconstruction with original speech and the unmodified review ledger.
4. Portable project archive/restore, preserving every review record and explicitly appending the restore event.
5. Both complete 640×360 RGBA films at 12 fps: 432 frames/36 seconds and 264 frames/22 seconds, with 1,728,000 and 1,056,000 audio sample frames at 48 kHz.
6. Repeated rendering that reuses every verified frame and preserves the complete manifest and frame hashes.
7. Actual H.264/AAC stream/frame/timing validation when `--video` is requested, and complete PNG/WAV/OpenRaster editor handoffs with pixel-exact drawing roundtrips.
8. An unchanged checkout throughout the run, recorded by per-file SHA-256 rather than an uncommitted tree being represented solely by its base commit.

`report.json` contains structured results, exact input hashes, scene frame hashes, audio hashes, test counts and any errors. `tests.log` preserves the actual regression output. `portable-project.zip`, `evidence/`, `project/renders/` and `editor-handoffs/` contain inspectable artifacts. An interrupted or failed run retains its partial report and exits unsuccessfully.

`--compact` validates every frame and PCM sample duration, saves reports/storyboards/movies and one real layered production drawing per scene, then removes completed frame trees. It reports `complete_delivery_gate: false` because the complete editor handoffs belong to normal mode. CI always uses normal mode on Linux, Windows and macOS.

## Current execution evidence

The frozen local regression ran **786 tests in 267.596 seconds**, with **zero failures, zero errors and one native Krita skip**. Its [actual log](../tests/results/public-delivery-local-tests.log) and [input hashes/report](../tests/results/public-delivery-local.json) are retained. After that run, the added checkpoint-preservation regression passed with all six delivery tests, and all 17 transport cases passed, including all four bundles and pinned metadata under forced Git newline conversion. These targeted logs are also retained in `tests/results/`.

The earlier sandbox-only integration exposed Chromium kernel restrictions and one legacy review invalidated by concurrent source edits. Those issues were resolved for the frozen 786-test pass above; required browser checks were not skipped. The following render attempt exhausted the shared workstation disk while writing scene audio. A later full-gate attempt was also interrupted by shared disk exhaustion. Atomic report replacement now preserves the previous checkpoint on a failed write. The final complete **787-test**, layered-render and editor-handoff gate remains required on fresh CI runners before merge; no disk failure is classified as an optional skip.

## Historical records remain historical

The original author-environment result was **299 tests: 298 passed and one native Krita skip**, with its exact log at [production-final-public.log](../tests/results/production-final-public.log). The earlier integration repair ran 764 tests with one missing-pilot setup error. These records describe their own checkouts and do not establish the current public branch's readiness.

[Original production validation](production-validation.md), [P01–P15 traceability](production-traceability.md), and the recovered `examples/production-pilot/evidence/` records preserve original inspection outcomes, repair notes and limits. They are not rewritten to confer current acceptance. The 20 retained reviews identify `assistant:/root`; human review remains false. New renderer evidence, assistant artistic inspection, auditory listening and external editor execution are separate claims.

The default Codex profile, state order, frame counts, millisecond timings, dimensions, transparency, package/install behavior and state/style catalogs remain under their existing regression contracts. No live pet installation or application settings change is part of this delivery.
