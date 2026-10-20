# Style catalog validation

Validated on **2026-10-19 UTC** against the implementation branched from main commit `857791b9503f9ff54b118751eea640866688000a`.

## Result

The final style-expansion suite passed **403 tests in 164.292 seconds, with zero failures and zero skips**. The original baseline passed all 123 tests before implementation. The expansion adds 280 regression cases, including a separate preparation case for each of the 205 registered entries. [Complete unittest output](../tests/results/style-catalog-unittest.txt) is retained as automated test evidence. See [combined state and style validation](state-style-integration.md) for the subsequent integration check.

| Check | Result |
| --- | --- |
| `python scripts/doctor.py` | Pass; no errors or warnings |
| `python scripts/generate_presets.py --check` | Pass |
| `python scripts/generate_schemas.py --check` | Pass |
| `python scripts/generate_style_reference.py --check` | Pass |
| `python -m unittest discover -s tests -v` | 403 passed, no skips |
| `python -m compileall -q scripts tests` | Pass |
| `git diff --check` | Pass |
| Skill frontmatter validation | Pass |
| Existing profile, purpose-preset and dependency files versus baseline | Unchanged |

The execution environment used Python 3.12.14, Pillow 13.0.0, jsonschema 4.26.0 and Playwright 1.64.0. Browser tests used real headless Chromium 155.0.8059.84 through the existing local installation; a launcher supplied its path to Playwright. Native browser process privileges were required in this sandbox. No browser tests were skipped or replaced with mocks. Dependencies were already available; this change adds no runtime or test dependency.

## Catalog and coverage

Catalog version **1.0.0** contains **205 selectable entries: 195 techniques, 8 treatments and 2 adaptive selectors**, across 14 categories. The 70 aliases and 14 thematic modifiers are separate from those counts. All 195 named coverage targets in the expansion request resolve to an ID or declared alias in their intended category. The [style reference](style-catalog.md) contains every ID and the category counts.

Catalog content SHA-256: `be2cc5f8e194a61f28b0828edbb2baef295865757d099fdf1ab25c801bfcf747`.

Every style has unique materials, forms, linework, shading, palette, texture and rendering instructions. The composed style contract is 1,610–2,424 characters before optional user notes and themes; only the selected record enters generation prompts. The complete catalog is never added to a model prompt.

Tests exercise:

- Actual preparation and layout-guide creation for every entry, with all defining instructions and negative constraints present in base, state and retry prompts.
- The original nine styles, every alias and theme, all 20 existing example/purpose profiles, and extension by adding a declarative record without central generation changes.
- Schema validation, duplicate IDs/aliases/JSON keys, invalid categories and reserved filenames, unsafe text, missing instructions, unknown fields, contradictory restrictions, modifier conflicts and bounded regular-file loading.
- Human and JSON discovery, category and keyword search, accurate adaptive-style inspection, automatic selection and explicit style avoidances.
- Alpha/chroma warnings, nearest-neighbor recommendations, explicit per-state filter precedence, invalid filter types, and historical Lanczos behavior.
- Frozen specifications through claims, retries, repairs, configuration, profile revisions, resume and archive restoration, including a fresh process with catalog access disabled before importing preparation helpers.
- Original imported pixels, receipt-derived origins, fixture-label consistency, immutable snapshot/hash checks, export/package provenance and mandatory warning-specific visual review evidence.
- Existing extraction, provenance, package, browser playback, review UI and export regression coverage.

## Independent review

An independent read-only code and catalog-content review found and resolved six implementation issues: a fresh-import catalog dependency, mismatched `auto` discovery warnings, ignored exact style avoidances, missing-snapshot fallback, editable origin labels, and cross-stitch component guidance. A related existing fixture-label consistency gap was also closed. Each behavior has a regression test, and the final review reported no remaining concrete blockers.

The reviewer inspected the historical schema-2 controller implementation as well as current code. Its generation receipts already carry the required generation-skill field; missing historical convenience origin labels remain supported.

## Compatibility and limits

The Codex contract remains nine states, eight columns, 192×208 cells, the original frame counts and timings, and the existing 1536×1872 atlas and `pet.json`/`spritesheet.webp` consumer package. Profile and run schema versions are unchanged; package receipt schema 2 remains valid. Packages add a hashed style-provenance sidecar. Historical requests without a style snapshot retain their saved contract, and old extraction settings without a filter retain Lanczos. No new migration is required.

New preparations save a recommended extraction fallback. Explicit per-state profile filters continue to win. Existing provenance rules can require fresh deterministic validation and visual review when pipeline code changes; they do not authorize automatic regeneration or a different saved style.

This evidence proves configuration and lifecycle behavior. **No new production imagegen artwork was generated or visually certified for this expansion.** Raster inputs used by regression tests are labeled fixtures, and the retained README artwork is historical. Glass, translucent media, sparse glyphs, separate stitches and other difficult techniques still require actual-source inspection, supported extraction settings or source-bound annotations, and the existing visual review gates. Natural-language artistic contradictions beyond exact selectors remain a canonical-review responsibility.
