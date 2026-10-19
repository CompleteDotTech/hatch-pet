# Local workflow

Use Python 3.10+ and Pillow 10.1+. Commands work in PowerShell and POSIX shells. Paths below are local examples. `python scripts/doctor.py` diagnoses missing Pillow before importing the pipeline. Production generation is a handoff to the installed imagegen skill, not an API client.

## Prepare and acquire sources

```powershell
python scripts/hatch.py doctor --destination output/otter-run
python scripts/hatch.py prepare --run-dir output/otter-run --pet-name Otter --pet-notes "sleepy otter barista" --style-preset plush --avoid "readable text"
python scripts/hatch.py limits --run-dir output/otter-run --max-attempts 3 --concurrency 1 --max-calls 30
python scripts/hatch.py claim --run-dir output/otter-run --job base --out output/base-handoff.json
```

Preparation accepts repeated `--reference`, `--reference-roles roles.json`, `--identity identity.json`, `--constraints`, `--require`, `--avoid`, style/brand fields, and `--profile`. The default is the exact Codex contract. Preserve required references and constraints through every call. Brand discovery has separate attribution and uncertainty.

Read the handoff's prompt, attachments/roles, identity, token and failure history. Follow the installed imagegen skill, inspect the original selected result and save project-bound output as it requires. Receipts attest actual inputs used; never submit one if attachments were omitted. Record genuine provider IDs/model/parameters in optional `model_call` when exposed; otherwise retain unavailable fields. A hatch token is not a model-call ID.

```powershell
python scripts/hatch.py ingest --run-dir output/otter-run --job base --token ACTIVE_TOKEN --source output/selected-base.png --receipt output/base-handoff.json --note "Viewed full body, markings, style and alpha."
python scripts/hatch.py base-review --run-dir output/otter-run --note "Canonical identity and transparency inspected."
python scripts/hatch.py claim --run-dir output/otter-run --job idle --out output/idle-handoff.json
```

Ingest each row with its own active token/receipt. `fail --job idle --token ACTIVE_TOKEN --note "..."` records a failed call. Retry preserves references and constraints. `repair --job jumping --note "Preserve markings; raise peak."` starts a deliberate attempt series without erasing history. `status` and `resume` reconcile existing work without model calls.

For existing artwork, use [the complete import recipe](sources-and-identity.md). Imports have import receipts and never count as imagegen output. Fixture imports require both a fixture-mode run and fixture descriptor.

## Extract, inspect and review

```powershell
python scripts/hatch.py validate --run-dir output/otter-run
python scripts/hatch.py review-ui --run-dir output/otter-run --destination output/otter-review-v1
```

Open `output/otter-review-v1/review.html`. Inspect references, sources, extracted frames, timings, static alternatives and backgrounds. Record six review dimensions and each numerical warning. Download the bound JSON outside the run, then submit it:

```powershell
python scripts/hatch.py review --run-dir output/otter-run --receipt output/visual-review.json
python scripts/hatch.py export --run-dir output/otter-run --destination output/otter-export-v1
python scripts/hatch.py package --run-dir output/otter-run --destination output/otter-package-v1
```

`review-template --out output/visual-review.json` provides the same receipt for another review method. Missing evidence/dimensions/warning notes, changed artifacts or failing verdicts block acceptance. Rebuild the review UI after changes: it is a snapshot. An evaluation export may be unreviewed and says so. A package requires current passing review. Default packages contain Codex-compatible `pet.json` and `spritesheet.webp`; custom profiles create asset packages.

## Calibration and profile revision

```powershell
python scripts/hatch.py configure --run-dir output/otter-run --holes preserve --key-threshold 36
python scripts/hatch.py configure --run-dir output/otter-run --shared-scale 0.5
python scripts/hatch.py base-review --run-dir output/otter-run --note "Rechecked settings against canonical artwork."
python scripts/hatch.py annotate --run-dir output/otter-run --job jumping --receipt output/jump-annotation.json
python scripts/hatch.py revise-profile --run-dir output/otter-run --profile output/revised-profile.json
```

Thresholds, hole handling and shared scale affect deterministic extraction and reuse model output. Generation background/key changes rebuild prompts and mark generated rows stale; imported pixels need no new model call. `revise-profile` distinguishes generation, extraction and playback/export dependencies. State set/order changes require a separate run. See [extraction](extraction-and-review.md).

## Optional installation and retention

Only if requested: `install --run-dir ... --package-path ... --destination ...` installs a verified reviewed package into an isolated destination outside run/package trees. Recognized existing packages are backed up; unrecognized files block replacement. `rollback --run-dir ...` restores the bound previous package. Neither selects a pet nor proves app behavior. `--test-destination` permits temporary fixture installations and refuses the live Codex pets directory.

`cleanup --run-dir ...` previews exact run-owned removals. `--apply` writes/verifies a compact repair archive first. `--mode minimal-delivery` also discards decoded rows, losing re-extraction unless matching originals are restored or generation is repeated. It never removes external inputs, imagegen originals, installations or unrelated files. [Portable full archives](portability-and-operations.md) work independently of cleanup.

## Deterministic checks

```powershell
python scripts/demonstrate.py --all --output-dir output/capability-demos
python tests/fixture_workflow.py --output-dir output/legacy-fixture-demo --profile examples/web-status.json
python -m unittest discover -s tests -v
```

These produce labeled synthetic fixtures and exercise gates/exporters/local consumers without model calls or production-art acceptance. Browser tests exercise actual exported HTML with controlled clocks. Physical display timing remains unmeasured.

Use a new output directory for a rerun; existing demonstrations are preserved. Fixture pixels and layouts are deterministic. Run identities, timestamps and document metadata may differ between executions.
