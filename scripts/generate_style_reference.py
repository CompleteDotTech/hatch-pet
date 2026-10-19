"""Render the human style reference from the validated catalog; --check detects drift."""
import argparse
from pathlib import Path

from style_registry import digest, load_catalog

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / 'references/style-catalog.md'

INTRO = '''## Discovery and selection

```bash
python scripts/hatch.py styles
python scripts/hatch.py styles --search "woven"
python scripts/hatch.py styles --category painting-drawing --json
python scripts/hatch.py style --style-preset watercolor
python scripts/hatch.py style --style-preset watercolor --profile profiles/codex-v1.json --background chroma --json
python scripts/hatch.py style-modifiers --json
```

`styles` lists every entry, grouped by category. Search is case- and accent-insensitive and matches IDs, names, aliases, tags, descriptions and categories; multiple words must all match. A category filter uses its stable ID. `--json` returns complete records, counts and the canonical catalog hash. `style` describes the seven generation dimensions, negatives, use cases, limitations, compatibility and aliases. Supplying a profile and background also previews compatibility warnings. Discovery does not need a run directory or make a model call.

Select any stable ID through the existing `--style-preset` option on either preparation entry point. Declared aliases resolve to the same specification and are never counted as additional styles. Original IDs remain supported: `auto`, `pixel`, `plush`, `clay`, `sticker`, `flat-vector`, `3d-toy`, `painterly`, `brand-inspired`.

```bash
python scripts/hatch.py prepare --run-dir output/otter-watercolor --pet-name Otter --pet-notes "small otter barista" --style-preset watercolor --style-modifier cozy --style-modifier botanical --style-notes "Keep the approved white ear tip; broaden the watercolor marks." --avoid "new props"
python scripts/hatch.py claim --run-dir output/otter-watercolor --job base --out output/otter-base-handoff.json
```

Follow the installed `$imagegen` skill for production generation. Only the chosen entry and modifiers enter the prompt, not the full catalog. The handoff retains the snapshot, identity, attachments, token and warnings. [The lifecycle workflow](workflow.md) covers ingestion, base approval, animation rows, extraction, validation, review and packaging.

## Composition and precedence

Use one visual style plus zero to four thematic modifiers. Modifiers are separate, composable art-direction cues; they do not authorize added props, backgrounds or changes to approved identity. `--style-notes` accepts up to 4,000 characters and can refine the technique. Keep direct requirements in `--require`, avoidances in `--avoid`, and detailed palette/material/marking invariants in `--identity`.

Explicit user requirements and avoidances, approved identity and references, and the selected profile contract govern preset guidance. For example, a prescribed blue coat stays blue when selecting a traditionally monochrome technique; the generation prompt must adapt the technique to that constraint. Exact contradictory user require/avoid statements fail preparation. An explicit style whose ID, name or alias exactly matches an avoidance also fails with a correction message. Arbitrary natural-language contradictions cannot be completely detected, so inspect unresolved material or reference conflicts at the canonical-base review.

`auto` resolves an explicit artistic term in the concept, requirements, material identity or notes when possible, excluding exactly avoided style IDs, names and aliases. Without one, it uses reference-guided `auto` when references exist, `brand-inspired` when brand guidance exists, and `flat-vector` otherwise. If that fallback is explicitly avoided, it tries another supported compact direction and records its selection; if no suitable direction remains, preparation reports the conflict. Reference-guided selection preserves the existing technique and requires canonical visual review; Python does not inspect source pixels or claim a specific inferred medium. Use an explicit style ID when that choice is already known. No full catalog is inserted into a generation prompt.

## Compatibility, rasterization and review

All entries are adapted to an isolated compact subject. For a Codex pet, the contract remains nine states, eight columns, 192×208 cells, the existing frame counts and millisecond timings, a 1536×1872 atlas, and the existing `pet.json`/`spritesheet.webp` package. Materials, decoration and effects must remain readable within that silhouette. Texture landmarks, colors, lighting, facial features, markings and props remain stable across frames. A craft, icon or process profile still determines its own subject and semantic requirements; selecting a style never turns a non-character asset into a mascot.

Compatibility metadata describes **source extraction**, not permission to deliver an opaque atlas. Alpha is supported, preferred or required. Chroma is supported, cautionary or unsupported. Glass, translucency, soft textile edges and internal light effects often need alpha or a carefully simplified opaque core. Chroma warnings explain the risk and recommend alpha; they do not silently change user settings or guarantee a usable result. Inspect the actual canonical source and resolve an unsupported combination before proceeding with generation. Neither edge cleanup nor a style selection relaxes provenance, segmentation, clipping or visual review checks.

New runs record a recommended extraction fallback: `nearest` for hard grids, usually `lanczos` for continuous edges. A profile's explicit per-state `alignment.resampling` takes precedence. No layout, counts, timings, anchor, scale policy or dimensions are changed. Historical runs without a saved fallback retain the previous `lanczos` behavior. `configure --resampling` deliberately changes the fallback and reuses generation; it does not override explicit per-state filters. Use `revise-profile` to revise those. Review after either change.

```bash
python scripts/hatch.py configure --run-dir output/pixel-otter --resampling nearest
python scripts/hatch.py base-review --run-dir output/pixel-otter --note "Inspected the actual edges and extraction configuration."
```

Use integer source-grid scales for crisp pixels where practical; nearest-neighbor filtering alone cannot repair irregular source pixel grids. Soft and painted edges need antialiasing. GIF uses binary transparency and a limited palette; use PNG, WebP or browser output when partial alpha matters. Fixed craft palettes may discard gradients and material texture. Small cells require broad strokes and fewer marks. Warnings are surfaced during preparation, handoffs, status/resume, calibration, discovery and visual review; each current review warning requires an evidence note.

Imported art retains its pixels and import origin. When an imported canonical base grounds generated states, its approved existing rendering takes precedence over the requested preset. Export/package metadata labels the style as requested guidance, not proof that the style was applied. A generated status, preset name, screenshot or deterministic fixture never proves imagegen origin or artistic quality.

## Reproducibility and historical runs

Preparation stores `pet_request.json.resolved_style`: schema version, catalog version/hash, requested ID or alias, resolved ID, selection reason, complete style and modifier records, user notes, exact composed contract and its SHA-256. Hashes use canonical UTF-8 JSON with sorted keys, no insignificant whitespace and no nonfinite values. The snapshot hash excludes its own `sha256` field. The catalog hash covers the combined validated category/style/modifier data rather than filesystem indentation.

The immutable request is already part of generation, extraction and review provenance. Controller manifests also retain its style hash. Claims retain the full snapshot in their history. Retry, repair, configure, profile revisions, resume and archive restoration use the saved contract rather than the current catalog. Existing historical requests without a snapshot remain readable: their saved contract is retained, with their original version-2 generic profile framing when applicable. No new run/profile/package schema migration is required. Old package receipt schema 2 stays accepted.

Controller exports include the resolved snapshot in `provenance.json`. Packages add hashed `style-provenance.json` alongside the unchanged consumer files. Origin labels are derived from generation, import or derivation receipts; a conflicting display label is rejected. Full archives retain exact request and prompt bytes. Catalog changes affect new preparations only. Saved-run prompt reconstruction does not load the live catalog, even in a fresh process. A restored run can still require deterministic revalidation after pipeline versions change, under the existing archive rules; this does not authorize a different style or a new model call.

## Catalog schema and contributor workflow

The source index is `styles/catalog.json` (schema 1, semantic catalog version). It names categories; each has one `styles/CATEGORY.json` file. Themes are declared separately in `styles/modifiers.json`. The structural schema is generated at `profiles/style-catalog.schema.json`, and `scripts/style_registry.py` enforces cross-record relationships and hashes without additional dependencies or executable plugin loading.

To add a style:

1. Add a new entry to the appropriate category file. Assign a unique lowercase kebab-case ID and keep existing IDs stable. A genuinely new category also needs an `{id, name}` index record and a matching JSON file.
2. Supply name, category, kind, description, tags and aliases. Use `kind: technique` only for a materially distinct construction or rendering method; use `treatment` for palette/finish variations and `adaptive` for selection policies. Themes belong in the separate modifier file.
3. Write seven specific instruction fields: `materials`, `forms`, `linework`, `shading`, `palette`, `texture`, `rendering`. Each is 20–800 characters; describe visible construction choices and how they survive reduction. Do not substitute a name into repeated generic instructions.
4. Add at least two `negative_constraints`, use cases and limitations. Rate `character`, `sequence`, `icon`, `print` and `grid` applicability as `recommended`, `adapted` or `unsuitable`. These are art-direction recommendations, not external-consumer certification.
5. Declare `compatibility.alpha`, `chroma`, `edge_mode`, `resampling`, `scaling` and explanatory `notes`. Hard edges require nearest. Required alpha pairs with unsupported chroma. Use only nearest, bilinear, bicubic or lanczos. Optional `recommended_modifiers` must name existing theme IDs.
6. Add only non-colliding aliases. Modifier conflicts, if necessary, must name existing modifiers symmetrically; a modifier cannot conflict with itself. All metadata is inert data. Unknown fields, unsafe IDs/control characters, duplicate JSON fields, duplicate IDs/aliases, missing dimensions and conflicting restrictions fail validation.
7. Bump the catalog version for content changes; never rewrite existing run snapshots. Run the checks below and review the artistic distinction and limitations manually. Exhaustive preparation tests discover new entries automatically.

```bash
python scripts/generate_style_reference.py
python scripts/generate_schemas.py
python scripts/doctor.py
python scripts/generate_style_reference.py --check
python scripts/generate_presets.py --check
python scripts/generate_schemas.py --check
python -m unittest discover -s tests -v
python -m compileall -q scripts tests
git diff --check
```

The ten purpose/profile presets in `presets/` remain a separate interface managed by `generate_presets.py`. New visual entries need no central generation-logic changes. A process caches its installed catalog for that invocation; start a new CLI invocation after editing catalog data.

Automated tests establish configuration, hashing, discovery and lifecycle behavior. They do not certify subjective rendering quality. This catalog expansion includes no newly generated imagegen preview gallery, and its synthetic regression inputs are not production artwork samples.
'''


def cell(value):
    return str(value).replace('|', '\\|').replace('\n', ' ')


def build():
    catalog = load_catalog()
    styles = catalog['styles']
    counts = {kind: sum(s['kind'] == kind for s in styles) for kind in ('technique', 'treatment', 'adaptive')}
    lines = ['# Visual style catalog', '',
             f"Catalog **{catalog['catalog_version']}** provides **{len(styles)} selectable entries**: **{counts['technique']} distinct techniques**, "
             f"{counts['treatment']} treatments and {counts['adaptive']} adaptive selectors across {len(catalog['categories'])} categories. "
             f"The {len(catalog['modifiers'])} optional themes and all aliases are counted separately.", '',
             'Generated by `python scripts/generate_style_reference.py`; check drift with `--check`.', '',
             '## Contents', '', '- [Discovery and selection](#discovery-and-selection)',
             '- [Composition and precedence](#composition-and-precedence)',
             '- [Compatibility, rasterization and review](#compatibility-rasterization-and-review)',
             '- [Reproducibility and historical runs](#reproducibility-and-historical-runs)',
             '- [Catalog schema and contributor workflow](#catalog-schema-and-contributor-workflow)',
             '- [Category inventory and quick starts](#category-inventory-and-quick-starts)',
             '- [Thematic modifiers](#thematic-modifiers)', '', INTRO, '',
             '## Category inventory and quick starts', '',
             'All examples prepare a new run; they do not generate artwork or waive review. '
             'The description and rendering cue below summarize each entry; `hatch.py style --style-preset ID` exposes every instruction and applicability rating.', '',
             '| Category ID | Category | Entries | Techniques |', '| --- | --- | ---: | ---: |']
    for category in catalog['categories']:
        entries = [s for s in styles if s['category'] == category['id']]
        lines.append(f"| `{category['id']}` | {cell(category['name'])} | {len(entries)} | {sum(s['kind'] == 'technique' for s in entries)} |")
    for category in catalog['categories']:
        entries = [s for s in styles if s['category'] == category['id']]
        representative = next((s for s in entries if s['kind'] == 'technique'), entries[0])
        lines += ['', '### ' + category['name'], '',
                  '```bash', f"python scripts/hatch.py prepare --run-dir output/{category['id']}-otter --pet-name Otter --pet-notes \"compact otter\" --style-preset {representative['id']}",
                  '```', '', '| Stable ID / aliases | Description and rendering cue | Extraction | Limitations |', '| --- | --- | --- | --- |']
        for style in entries:
            c = style['compatibility']
            names = '`' + style['id'] + '`' + (f" ({style['kind']})" if style['kind'] != 'technique' else '')
            if style['aliases']:
                names += '; aliases: ' + ', '.join('`' + a + '`' for a in style['aliases'])
            direction = style['description'] + ' ' + style['instructions']['rendering']
            extraction = f"Alpha {c['alpha']}; chroma {c['chroma']}; {c['edge_mode']}; `{c['resampling']}`"
            lines.append('| ' + ' | '.join(cell(v) for v in (names, direction, extraction, ' '.join(style['limitations']))) + ' |')
    lines += ['', '## Thematic modifiers', '',
              'Use repeated `--style-modifier ID` options (maximum four); duplicate aliases and declared conflicts are rejected. '
              'Every current theme is composable with the others; requests still need a coherent approved identity.', '',
              '| Modifier | Direction | Limits |', '| --- | --- | --- |']
    for modifier in catalog['modifiers']:
        lines.append('| ' + ' | '.join(cell(v) for v in ('`' + modifier['id'] + '`', modifier['instructions'], ' '.join(modifier['negative_constraints']))) + ' |')
    lines += ['', 'Catalog content SHA-256: `' + digest(catalog) + '`.', '']
    return '\n'.join(lines)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    content = build()
    if args.check:
        if not TARGET.is_file() or TARGET.read_text(encoding='utf-8') != content:
            raise SystemExit('generated style reference drift: ' + str(TARGET))
    else:
        TARGET.write_text(content, encoding='utf-8')
