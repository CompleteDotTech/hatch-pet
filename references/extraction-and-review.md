# Extraction, calibration and visual review

The default is conservative, eight-connected component/core/bridge analysis in equal source slots. A slot must contain one identifiable pose. Missing poses, extra major components, boundary crossings and suspicious bridges fail. Alpha is preserved, including antialiasing and intentional holes. Chroma uses edge-connected masking; enclosed key colors are preserved unless `holes=key` explicitly classifies them as holes.

For semantic parts within a single character, use the separate [character decomposition workflow](character-decomposition.md). Its binary ownership masks may split one connected silhouette or join disconnected details under an explicit semantic label. These masks and their review receipts do not change the conservative frame-slot annotation contract below.

Failure diagnostics are `qa/extraction-diagnostics/STATE.png` and `.json`: red component boxes, blue default boundaries, exact error, component areas and source dimensions. Clipping is rejected before output. Diagnostics are evidence, not automatic permission to waive a failure.

The diagnostic preview scales large sources to a bounded canvas and wraps the full error above the image. Its JSON retains original coordinates and the preview scale; use the original source for pixel-level decisions.

## Annotated extraction interface v1

Pass `annotate --job STATE --receipt annotation.json`. Coordinates are integer source pixels with exclusive right/bottom bounds; `source_sha256` binds the current `decoded/STATE.png`, not an earlier compressed input. Example for two 60×50 slots:

```json
{
  "schema_version": 1,
  "source_sha256": "REPLACE_WITH_CURRENT_DECODED_SOURCE_SHA256",
  "author": "Reviewer name",
  "note": "The two major pieces in the first frame are the approved disassembled object.",
  "frames": [
    {"rect":[0,0,60,50],"allow_components":[
      {"bounds":[35,10,55,36],"permit":"disconnected","reason":"Approved separate component"}
    ]},
    {"rect":[60,0,120,50]}
  ]
}
```

Obtain the hash with `(Get-FileHash work/run/decoded/STATE.png -Algorithm SHA256).Hash.ToLower()` in PowerShell. Each permission names an actual complete alpha component and allows only `disconnected` or `bridge`. There is no “ignore all errors” setting. Rectangles cannot overlap, omit any visible component or clip a connected component. Arbitrary rectangular layouts are normalized into one common maximum-size viewport without resizing individual poses. All non-permitted checks remain active. If a bridge really joins unrelated poses, repair the source instead of permitting it.

Annotations retain author, rationale and hashes. Source/annotation changes invalidate extraction and review; they do not trigger generation. The extraction manifest records both original and normalized viewport sizes, filter, scale, source/output bounds, anchors, baselines and annotation hash. Review must still establish that the permitted parts belong together.

## Resampling and common scale

`alignment.resampling` accepts `nearest`, `bilinear`, `bicubic`, `lanczos`. An explicit per-state setting takes precedence. New preparations save the selected style's recommended fallback in `pet_request.json.extraction.resampling`; historical runs without one retain `lanczos`. `configure --resampling nearest` deliberately revises that fallback without changing geometry or generating new artwork. Use `revise-profile` to change an explicit per-state filter. Use nearest for grid/pixel art and filtered methods for continuous-tone artwork. Warnings identify mismatches with the frozen style; review the actual pixels before accepting them. `slot` preserves displacement, `center` recenters and `baseline` aligns bottoms. Do not use the latter two for jumps whose vertical displacement matters.

Every row uses one viewport and multiplier. `row` fits the shared viewport, `none` uses 1:1 pixels, and `shared` uses a single calibration value across states. No pose independently expands to fill its cell. Poses may legitimately occupy different areas. Choose anchors and padding deliberately; extraction rejects a multiplier that clips the padded viewport.

For body-based calibration, create measurements tied to decoded sources:

```json
[{"state":"idle","source_sha256":"CURRENT_HASH","body_rect":[30,20,70,80],"target_height":30}]
```

```powershell
python scripts/hatch.py calibrate --run-dir work/run --receipt work/body-measurements.json
python scripts/hatch.py calibrate --run-dir work/run --receipt work/body-measurements.json --apply
```

The common multiplier is the median measured target/source ratio; measurements disagreeing by over 5% fail for inspection. Set relevant profile states to `scale_policy: "shared"` using `revise-profile`. Ratios require comparable source resolution and a consistent definition of body height. Neither silhouette area nor a numeric scale proves physical identity. A later extraction still checks all viewport bounds.

## Review desk and receipts

`review-ui --destination NEW_DIRECTORY` exports an offline snapshot with canonical/reference roles, source strips, contact sheet, indexed frames and the actual exported playback consumer. Use previous/next, pause/play, state selection, timing display, reduced-motion still and checker/light/dark/green backgrounds. Images play at declared cell size; enlarged source links support detail inspection.

For every state record six separate verdicts and evidence notes: identity, action, direction, loop, extraction, reduced motion. A non-looping sequence may pass the loop dimension with an explicit “intentional one-shot/hold” note. Every numerical or style-compatibility warning needs its own note, including cross-state warnings. The review desk includes the frozen requested style and source origins. The receipt binds exact source, frames, profile, settings, canonical/reference images, prompts and pipeline version. It is checked again on submission, export and packaging.

The UI cannot know whether a person truly inspected an image. Checkboxes and reviewer notes are attestations. It never computes a semantic “pass.” Downloading JSON does not approve a run; submit it through `hatch.py review`. Changed artifacts require a fresh applicable review. Fixture receipts test this process only.
