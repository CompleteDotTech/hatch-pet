# Baseline evidence

The pre-change implementation was inspected from `git show HEAD:scripts/<name>.py`, so concurrent implementation edits did not affect these probes. Probes used Pillow-created deterministic rectangles in a temporary directory; no generated artwork, production installation, or paid service was used.

## Confirmed by execution

| Probe | Observed old behavior | Defect |
| --- | --- | --- |
| Two otherwise identical 41×51 red sprites at y=100 and y=50 passed separately through `fit_to_cell` | Byte-identical output (`True`) | Intentional jump displacement disappears. |
| Five separate complete equal-sized poses passed to `component_frame_groups(strip, 4)` | Four groups with component counts `[1, 1, 1, 2]` | An extra complete pose is silently merged into a selected frame. |
| Six valid idle frames without `frames-manifest.json`, `inspect_state(... require_components=True)` | `ok=True`, no errors | Missing provenance bypasses the requested extraction gate. |
| Extract `idle`, then separately extract `waving` into the same frames directory | Manifest contains only `['waving']` | Partial repair discards untouched-row provenance. |
| Put one extra frame in each state directory and call `compose_from_frames` | Successful `(1536, 1872)` atlas | Composition silently takes the first N files. |

## Confirmed by code inspection; not independent execution

- Default extraction selects component crops and individually centers/fits them; larger silhouettes can trigger per-frame rescaling. The explicit `stable-slots` option existed but was a recovery instruction rather than the default.
- Chroma removal clears every sufficiently similar RGB pixel regardless of whether it is foreground, including enclosed character detail. Component extraction uses four-neighbor connectivity and discards components below its area floor.
- Preparation writes request and jobs separately without a transaction or owner lock; `--force` can reuse an existing directory without invalidating decoded files.
- Frame provenance records method and paths but no source/settings/version hashes. Inspection checks an extraction method only when the method is present.
- Documentation packages directly into the installed pet directory before visual acceptance and writes an unconditional `ok: true` summary.
- Cleanup instructions discard prompts, canonical references, generated strips, frame provenance and the job manifest, removing the inputs needed for a precise row repair.
- The discovery handoff requests `avoid`, but preparation has no original `--avoid` argument. Retry prompts omit style notes. Instructions both require workers by default and ask permission if worker authorization is vague; worker final-output restrictions may conflict with the installed imagegen skill.
- State counts, cell dimensions and timings are duplicated across scripts; custom-profile support is absent.

These findings establish mechanism and reproducible failures, not a claim that every historical generated pet exhibited each failure. Final regression tests exercise the replacement behavior separately.

## Starting working-tree audit

The checkout already contained uncommitted profile/controller work. Its 12 existing raster tests passed before editing. Independent temporary probes confirmed additional defects in that working tree:

- One edge pixel at alpha 254 caused `auto` masking to retain an otherwise opaque green background.
- A one-alpha connector between two full poses made slot analysis accept them as one component.
- `min_motion`, `max_size_ratio`, and `max_baseline_shift` profile keys did not match the metric implementation's keys.
- Hashed empty extraction settings and `slots: [null, null]` passed provenance inspection.
- Different padding/anchor settings produced identical extracted pixels.
- After replacing the visual-review file, status still reported reviewed/packaged; deleting the package receipt also left packaged true.
- Preparation and legacy-install recovery could not advance after a crash between writing a journal and renaming the original directory.
- Switching between generated and mirrored rows retained contradictory active origin records.

The implementation now includes regressions for these cases. The original HEAD jump, extra-pose, enclosed-color and missing-manifest defects were independently rerun from `git show` modules in a temporary directory during this work. No image-model call or live pet installation was used.
