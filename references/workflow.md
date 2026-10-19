# Local workflow and recovery

Use Python 3.10+ and Pillow (`python -m pip install Pillow`). Run commands from the skill directory. All paths below work in PowerShell; Python accepts the same commands on macOS/Linux. Bash and jq are unnecessary. `hatch.py` delegates image generation through human/agent handoffs to the installed imagegen skill; it contains no generation client. Never substitute fixture drawings for requested production artwork.

## Prepare and generate

Choose a new run directory outside the skill source and outside installed pets:

```powershell
python scripts/hatch.py prepare --run-dir C:/work/otter-run --pet-name Otter --pet-notes "sleepy otter barista" --style-preset plush --avoid "readable text"
python scripts/hatch.py status --run-dir C:/work/otter-run
python scripts/hatch.py claim --run-dir C:/work/otter-run --job base --out C:/work/base-handoff.json
```

Optional preparation fields: `--reference path` (repeatable), `--description`, `--display-name`, `--pet-id`, `--style-notes`, `--require`, `--constraints constraints.json`, `--brand-name`, `--brand-brief`, `--brand-source`, `--brand-discovery-file`, `--profile examples/web-status.json`, `--background auto|alpha|chroma`, and `--chroma-key '#FF00FF'`. Quote hex colors in PowerShell. `auto` initially requests actual transparency and decides from the selected image; it does not equate incidental partial alpha with a cutout.

Read the handoff's exact prompt, attached-image paths/roles, prior failures, job ID, token, and receipt template. The worker must follow the installed imagegen skill, including viewing local references and attaching every required image. The base is the only job that can have no image inputs. Select and inspect the generated source, then ingest it:

```powershell
python scripts/hatch.py ingest --run-dir C:/work/otter-run --job base --token TOKEN_FROM_HANDOFF --source C:/work/selected-base.png --receipt C:/work/base-handoff.json --note "Full body, required markings and style checked."
python scripts/hatch.py base-review --run-dir C:/work/otter-run --note "Viewed canonical base and color analysis; alpha and identity are suitable."
python scripts/hatch.py claim --run-dir C:/work/otter-run --job idle --out C:/work/idle-handoff.json
```

The complete handoff JSON or its `receipt_template` may be supplied as `--receipt`. This is the worker's attestation that the listed prompt and image hashes were actually used. Do not submit it if they were omitted. Receipts establish recorded provenance, not independent proof of a remote model call. Worker output rules never override imagegen's required image display or final-output behavior. Ingest the original selected source from outside managed run outputs; the controller preserves it and owns only its decoded copy.

Ingest each row with its own active token and receipt. Rows depend on the canonical base; configured mirror targets also depend on their source row. An attempt is reserved before generation, so a lost tool result remains `running`. Reconcile that token using the recovered image or record failure; do not start a duplicate call:

```powershell
python scripts/hatch.py fail --run-dir C:/work/otter-run --job idle --token TOKEN_FROM_HANDOFF --note "Tool failed before producing a usable output."
python scripts/hatch.py claim --run-dir C:/work/otter-run --job idle --out C:/work/idle-retry.json
```

Three claims per job are allowed before explicit repair. Failure history and every repair reason are retained. Subsequent claims select the retry prompt, which preserves style, constraints, and required references.

## Extraction policy and calibration

`extraction-settings.json` records the selected base hash, actual background policy, key/color-collision measurements, warnings, and extraction settings. It is separate from the original request. Inspect it before `base-review`. A chroma collision blocks that checkpoint unless a specific reviewed exception uses `--accept-color-warning`; prefer a safer key or preserved alpha instead.

```powershell
python scripts/hatch.py configure --run-dir C:/work/otter-run --background chroma --chroma-key '#00FFFF' --key-threshold 36 --holes preserve
python scripts/hatch.py base-review --run-dir C:/work/otter-run --note "Viewed base with the revised key; checked cyan against the character palette."
```

Configuration changes invalidate row generation, extraction, validation, and approval. They rebuild row/retry prompts without rewriting the base's original generation receipt. `--shared-scale 0.5` records a common pixels-to-cell multiplier for states using `scale_policy: shared`. The multiplier must fit every source viewport; the extractor rejects clipping instead of resizing an individual pose to fit. It does not infer physical character height from arbitrary generated resolutions.

Alpha is preserved and fully transparent RGB is normalized. Chroma uses edge-connected background masking with constrained edge unmixing. Enclosed matching colors are preserved by default. `--holes key` explicitly classifies enclosed key-colored regions as holes; inspect this decision because they could be foreground colors. Neither color distance nor components can reliably resolve every foreground/background ambiguity.

## Validate, review, repair

```powershell
python scripts/hatch.py validate --run-dir C:/work/otter-run
python scripts/hatch.py review-template --run-dir C:/work/otter-run --out C:/work/visual-review.json
```

Validation extracts only missing/stale rows, merges frame provenance by state, checks exact indices and files, composes PNG/WebP, and renders `qa/contact-sheet.png` and timed `qa/previews/*.gif`. It rejects missing or unsupported schema-3 extraction evidence, changed sources/settings, and ambiguous segmentation. It reports temporal measurements and thresholds in `qa/review.json`; geometric success does not prove identity or action quality.

View the canonical base, contact sheet, and every timed row. Complete the template's reviewer, `evidence` fields, and each row's `verdict` (`pass` or `fail`) and specific `notes`. Leave its exact `artifact_hashes` and fixture label intact. Then record it:

```powershell
python scripts/hatch.py review --run-dir C:/work/otter-run --receipt C:/work/visual-review.json
python scripts/hatch.py repair --run-dir C:/work/otter-run --job jumping --note "Peak never leaves the ground; keep the approved face and palette."
```

A failing row prevents packaging/installation. Repair regenerates the smallest row, preserving untouched rows and their evidence. A base repair invalidates its dependent rows. Run validation and record a fresh complete review afterward; old receipts remain in history. Changing a reviewed frame, source, prompt, calibration, profile, canonical reference, or review file invalidates the relevant gate. Never restore approval by manually changing the manifest.

Only a profile-declared, explicitly approved mirror is allowed:

```powershell
python scripts/hatch.py derive --run-dir C:/work/otter-run --job running-left --approve-mirror --note "Viewed rightward gait: symmetric markings, no readable marks or sided props; mirroring preserves identity."
```

This mirrors each frame in place, preserving time order, and records source hashes and approval. `derive_running_left_from_running_right.py` is a compatibility wrapper for the same controller gate. `--force` is not a bypass. All other default states require generation.

## Export, package, install

```powershell
python scripts/hatch.py export --run-dir C:/work/otter-run --destination C:/work/otter-export
python scripts/hatch.py package --run-dir C:/work/otter-run --destination C:/work/otter-package-v1
```

Choose new destination paths. Export requires deterministic validation and includes review status and metrics for evaluation use. Package requires current passing visual review, stages the exported files, verifies their hashes, then promotes the package. Default Codex packages include `pet.json` and `spritesheet.webp`; custom profiles produce generic asset packages. A package is not an installed pet.

Only if the user requested installation, use `install --package-path ... --destination ...`. The destination must be an isolated package directory outside the run and source package. Existing verified packages or recognizable legacy Codex packages are backed up to a sibling `.previous-...` directory. Unrecognized contents block replacement. A failed installation restores the previous version, retaining a failed new version for inspection. `rollback --run-dir ...` restores the recorded previous package and keeps the displaced new one. The app is not automatically selected or exercised; `app_integration_verified` stays false.

`--test-destination` permits fixture/custom-profile installation only for isolated test directories and rejects the installed Codex pets directory. It is not a production override. Never use it to install fixtures as real pets.

## Resume and retention

```powershell
python scripts/hatch.py resume --run-dir C:/work/otter-run
python scripts/hatch.py cleanup --run-dir C:/work/otter-run
python scripts/hatch.py cleanup --run-dir C:/work/otter-run --apply
```

`status` derives pending/running/failed/generated/validated/reviewed/packaged from live hashes and receipts, writing `run-summary.json`. `resume` preserves the same run identity and generation tokens, reconciles interrupted local transactions, and explains the next action. It never invokes generation. A short OS lock protects manifest mutations; it releases on process exit. Atomic JSON replacement preserves the previous complete manifest if interrupted. Low-level extraction has its own OS lock.

`prepare --replace-inputs` deliberately creates a new run revision and preserves the entire previous directory as a sibling; it refuses to replace a run with active generation claims. `resume` does not reinterpret its original request. The preserved revision is historical evidence at its prior paths; do not claim its old absolute-path receipts validate a relocated directory without re-extraction.

Cleanup is preview-only unless `--apply`. Default `repair` writes and verifies a compact ZIP containing canonical identity, source strips, request/profile, constraints, prompts, hashes, generation/extraction records, metrics, and visual-review receipts. It removes only exact owned frame files, generated GIF previews, and the redundant PNG atlas. Raw row sources remain available; `resume`, then `validate` reconstructs those intermediates without generation. Keep the package/export separately.

`cleanup --mode minimal-delivery --apply` additionally removes the run-owned decoded row-strip copies and excludes them from the archive. Identity and receipts remain, but those rows require generation (or the original matching source supplied again) before extraction. It never deletes external imagegen outputs, user references, shared assets, installed packages, or unrelated files. Archive contents are explicitly listed in the preview. Deleting local generated files cannot remove image payloads embedded in earlier tool results or rollouts.

## Offline validation

```powershell
python -m unittest discover -s tests -v
python tests/fixture_workflow.py --output-dir C:/work/hatch-fixture-demo --profile examples/web-status.json
```

The second command creates clearly labeled synthetic sources, a complete run, export/preview, and package. Its review receipt exercises gates only; it is not a semantic judgment of production art. It never installs anything or calls a model. Browser tests use optional locally installed Playwright/Chromium; core tests need only Pillow. All test installations use temporary isolated destinations.
