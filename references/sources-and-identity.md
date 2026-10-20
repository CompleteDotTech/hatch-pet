# Sources, identity and import review

Source interface version 1 supports installed-imagegen generation and explicit imports. Imports accept single-frame PNG, WebP and JPEG: an image for the canonical base, a horizontal strip for a state, or an ordered list of equal-sized frames for a state. SVG, PDF, video and animated-image imports are rejected; convert deliberately before import. Frame lists are concatenated without per-pose scaling. Arbitrary layouts can use [rectangular extraction annotations](extraction-and-review.md).

Descriptors contain `schema_version: 1`, `kind: "import"`, `layout: "image" | "strip" | "frames"`, `files: [...]`, and nonempty `origin` attribution. File paths resolve relative to the descriptor. `fixture: true` can only enter fixture-mode runs. Originals must be outside managed run outputs and are preserved. Import receipts retain original hashes, descriptor hash, normalized source hash, origin and inspection note. They are distinct from generation receipts.

## Complete import-and-review recipe

Assume `work/art/front.png` and `rest-00.png` through `rest-03.png`, `walk-00.png` through `walk-03.png`, and `interact-00.png` through `interact-03.png` are existing approved artwork for `examples/game-npc.json`. Write `work/base-source.json`:

```json
{"schema_version":1,"kind":"import","layout":"image","files":["art/front.png"],"origin":"User-supplied artwork; creator and permission recorded by the user"}
```

Write one descriptor per state; `work/rest-source.json` is:

```json
{"schema_version":1,"kind":"import","layout":"frames","files":["art/rest-00.png","art/rest-01.png","art/rest-02.png","art/rest-03.png"],"origin":"User-supplied rest animation, original frame order"}
```

Use the same four-path pattern for `walk-source.json` and `interact-source.json`. Then:

```powershell
python scripts/hatch.py prepare --run-dir work/import-run --profile examples/game-npc.json --pet-name Imported-NPC --reference work/art/front.png
python scripts/hatch.py import-source --run-dir work/import-run --job base --receipt work/base-source.json --note "Inspected supplied canonical art and alpha."
python scripts/hatch.py base-review --run-dir work/import-run --note "Canonical proportions and transparency are suitable."
python scripts/hatch.py import-source --run-dir work/import-run --job rest --receipt work/rest-source.json --note "Original rest order inspected."
python scripts/hatch.py import-source --run-dir work/import-run --job walk --receipt work/walk-source.json --note "Original walk direction inspected."
python scripts/hatch.py import-source --run-dir work/import-run --job interact --receipt work/interact-source.json --note "Original interaction inspected."
python scripts/hatch.py validate --run-dir work/import-run
python scripts/hatch.py review-ui --run-dir work/import-run --destination work/import-review
```

Open `work/import-review/review.html`, complete actual visual inspection and download the receipt to `work/import-review.json`:

```powershell
python scripts/hatch.py review --run-dir work/import-run --receipt work/import-review.json
python scripts/hatch.py package --run-dir work/import-run --destination work/import-package
```

If validation fails, inspect diagnostics, supply constrained annotations or `repair` and import a corrected source. Never relabel imports as generated. A self-contained deterministic version is `python scripts/demonstrate.py --preset assembly --output-dir output/import-review-demo`. Its `run`, `review`, `export`, `package` and `acceptance.json` exercise the full import/review gate using labeled fixtures; its synthetic review makes no art-quality claim.

## Structured identity

Pass `--identity identity.json` to preparation:

```json
{
  "schema_version": 1,
  "markings": ["white tip on the anatomical left ear only"],
  "proportions": {"head_to_body_height": 0.6},
  "palette": {"coat": "#B43C28", "ear_tip": "#FFFFFF"},
  "materials": ["matte stitched felt"],
  "approved_props": ["plain ceramic cup"],
  "asymmetries": ["left ear tip differs from right"],
  "directions": {"running-left": "left", "running-right": "right"},
  "forbid_mirror": true,
  "unresolved_conflicts": []
}
```

Only version is required. Proportions are positive finite ratios; palette values are hex RGB; directions name states and `left/right/front/back/any`. Unknown fields fail. Explicit unresolved conflicts, contradictory Codex directions and exact marking/prop versus avoidance conflicts stop preparation. Natural-language contradictions and reference disagreements still require human resolution; detection is not complete. Structured identity describes requirements, not proof of visual identity.

`--reference-roles roles.json` assigns a required role/note to each repeated `--reference`, in order:

```json
[
  {"role":"front","note":"Approved front proportions"},
  {"role":"side","note":"Left anatomical side; preserve white tip"},
  {"role":"detail","note":"Cup handle and felt seam"}
]
```

Roles are `identity`, `front`, `side`, `back`, `detail`, `style`, and `edit-target`. All supplied references remain required; roles do not make them optional. Identity is carried in base/state/retry prompts and handoffs, and repair notes preserve it. The review desk displays roles and structured identity alongside actual artwork.

## Imagegen handoff and provenance

Handoffs and attempt history also retain the complete resolved style snapshot. The approved rendering of an imported canonical base remains authoritative in generated states; a requested preset never authorizes silent restyling. Imported pixels keep their origin and never acquire an imagegen receipt from style selection. Package/export style metadata records requested guidance separately from actual source origin and visual review.

`claim` returns the prompt, image roles/paths/hashes, identity, token, failure history and output rules. Read the installed imagegen skill, inspect local inputs, then attach all required images. Use `referenced_image_paths` when all inputs have local paths; otherwise the recent-image mechanism must include every target within its supported limit. Never pass both. A brand-new unreferenced base omits both mechanisms. If all required references cannot be attached, resolve that constraint before calling.

Hatch receipts are attestations, not independent proof of a provider call. Optional `model_call` records genuine `id`, `model`, `parameters`, or nulls with `unavailable_reason`. Hatch tokens are never substituted for provider IDs. The installed skill's image-display and project-save requirements remain in force.
