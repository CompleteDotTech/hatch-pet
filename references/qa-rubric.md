# Acceptance and visual review

Read the selected profile and the exact source assets. Default Codex geometry is 1536×1872, eight columns, nine rows, 192×208 cells; custom profiles use their own contract. Acceptance requires both deterministic validation and a persisted visual review of the exact hashed artifacts. Automated measurements are evidence, not an artistic verdict.

## Deterministic evidence

- `frames/frames-manifest.json` has schema 3, supported extraction algorithm, exact state/frame indices and order, source/frame/request/profile/calibration hashes, and valid segmentation/viewport/masking evidence. Missing or stale provenance blocks acceptance.
- Each state contains exactly `00.png` through its last index. Extra images, missing poses, cross-slot components, multiple major cores, and suspicious thin connections are rejected. A count of N components alone is not proof of N valid animation frames.
- Occupied cells fit the profile, unused cells are transparent, and fully transparent pixels have zero RGB.
- Inspect `qa/review.json` measurements: exact/near duplicates, adjacent and loop differences, area ratios, baseline displacement, palette change, and possible ordering outliers. Thresholds are state-aware and printed with the measurements.
- Confirm extraction preserved source movement. `slot` alignment shares the source viewport; `center`/`baseline` can intentionally remove displacement. A wider pose must not cause the body to shrink.
- Inspect chroma collision and edge warnings. Alpha preserves holes and antialiased edges. For chroma, enclosed matching pixels are retained unless `holes=key` was explicitly chosen; neither default can guess whether an enclosed key-colored region is a detail or a hole.

All deterministic checks must pass. Warnings need visual assessment and specific notes, not blanket dismissal.

## Required visual evidence

View the canonical reference, labeled contact sheet, and timed playback of every state. Set each corresponding evidence field in the review template only after viewing it. Review actual final-cell size as well as enlarged views.

- Same character, face, proportions, markings, palette, materials, lighting, and approved props throughout.
- Full poses within cells; no cropped neighbors, guide marks, checkerboards, key residue, fringing, disappearing details, or accidental opaque rectangles.
- Motion and loop transitions read correctly. Intentional holds may duplicate frames; static profiles may be still. Quiet idle permits low-amplitude breathing/blinking; directional states need a readable facing and gait; jumping needs retained rise/peak/land displacement.
- State semantics match the profile purpose. In Codex, `running` means active task work, distinct from directional locomotion. `waiting`, `review`, and `failed` must be distinguishable.
- The selected still frame works for reduced motion. The default uses idle frame zero.
- Detached effects obey the profile. The Codex profile excludes detached decorations, shadows, text, scenery, dust, glows and trails. Small attached details should survive extraction.
- A mirrored row preserves identity, asymmetric details, prop side, marks and lighting, and retains temporal order. Only a declared, explicitly approved derivation is valid.

Record `pass` or `fail` and specific notes per row in `qa/visual-review.json` through `hatch.py review`. A failing row blocks packaging and installation. Repair the smallest affected row; a wrong canonical identity requires base repair. Changed artifacts invalidate the review. Preserve prior evidence in history; never edit a receipt to pretend an old review covered new files.

## Reporting boundaries

Fixture reviews test gate behavior only. A fixture receipt cannot establish production artwork quality. Package verification establishes file integrity, not app integration. Do not claim Codex selection, OBS Program output, engine import, device playback, or delivery to a messaging platform unless that integration was actually exercised and separately recorded. Local exports and example event mappings are useful without such a claim.
