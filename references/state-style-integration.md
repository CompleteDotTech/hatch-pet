# Combined character state and style validation

Validated on **2026-10-20 UTC**, integrating the character state library with main commit `55d4c829bc8ec81c3cf52095937f25cade4d2874` (style catalog PR #5). This is the current combined validation record. The [state expansion record](character-state-validation.md) and [style expansion record](style-validation.md) retain their separate pre-integration results.

## Result

**All 487 tests passed in 197.498 seconds, with zero failures, errors or skips. All 15 demonstration workflows passed.** [Complete unittest output](../tests/results/state-style-unittest.txt) and [machine-readable evidence](state-style-integration.json) retain the measured results and provenance hashes.

| Check | Measured result |
| --- | --- |
| `python scripts/doctor.py` | Passed; no errors or warnings; both catalogs and required codecs available |
| `python scripts/generate_schemas.py --check` | Passed |
| `python scripts/generate_presets.py --check` | Passed |
| `python scripts/generate_style_reference.py --check` | Passed |
| `python -m unittest discover -s tests -v` | 487 passed, no skips; real browser tests enabled |
| `python scripts/demonstrate.py --all --output-dir output/capability-demos` | 15 of 15 passed: ten historical presets and five state selections |
| Skill frontmatter validation | Passed after the state and style documentation merge |
| Independent integration review | CLI routing, preparation, frozen provenance, review and fixture correction reviewed; no remaining findings |

The runtime used Python 3.12.14, Pillow 13.0.0, jsonschema 4.26.0 and Playwright 1.64.0. Browser tests ran with real headless Chromium. Test temporary files and demonstration output used a memory-backed directory because the shared workspace had limited free disk space; this does not change the pipeline or its validation.

The combined implementation contains **416 canonical states, 408 aliases, 16 packs and 205 styles with 14 optional style modifiers**. Both catalog versions remain 1.0.0. Script content SHA-256 is `b9b76c94a3fecaa8af6d394b6090fe8186d469371845279cd43514831daed925`; consumer and catalog hashes are recorded in the JSON evidence. No runtime or test dependency was added during integration.

## Integration behavior and correction

The preparation flow retains both the selected state requirements and the frozen style specification. The `hatch.py states` discovery/compiler interface and the style discovery commands coexist. Doctor reports both catalogs. Review presents both state-specific semantic checks and style-specific visual requirements. Catalog metadata remains separate from the strict runtime profile schema, and existing source, export and package provenance gates stay active.

The first combined test suite passed 486 tests. The subsequent full demonstration run found that the pixel style's nearest-neighbor extraction could collapse two adjacent synthetic calibration poses: a one-pixel source extension became indistinguishable when a 96-pixel viewport was fitted into 86 pixels of padded destination space. The fixture now changes that extension by three source pixels per frame. Its connected asymmetric shape remains inside the source viewport. Exact-byte distinct-frame checks, extraction thresholds, source hashes and review gates were not relaxed.

A new regression executes the actual 25-state, 100-frame cat demonstration, checks nearest-neighbor extraction, and retains the existing assertion that every animated fixture frame is distinct. The final 487-test and 15-demo runs above include this correction.

## Demonstrations and compatibility

| New state demonstration | States | Frames | Model calls | Result |
| --- | ---: | ---: | ---: | --- |
| Expressive cat | 25 | 100 | 0 | Passed |
| Coding assistant | 49 | 196 | 0 | Passed |
| Game NPC | 29 | 116 | 0 | Passed |
| OBS mascot | 25 | 100 | 0 | Passed |
| Accessible feedback | 14 | 14 | 0 | Passed |

The ten historical assembly, process, configurator, flipbook, communication, perception, regression, cursor, protocol and craft workflows also passed. New state demonstrations cover 142 selected states and 526 frames through the actual import, extraction, validation, export and review workspace paths. Their calibration shapes test the pipeline; they do not depict the named character actions or constitute reviewed character artwork.

`profiles/codex-v1.json` is byte-for-byte unchanged from both implementation baselines, with SHA-256 `f4e0279f8634ea53ef544ecb49b9a71ec2565c61ec5b8e63163ecc5ead478a6b`. Its nine rows, eight columns, 192×208 cells, state order and original timings remain the fixed Codex contract. Expanded states compile into custom profiles; the fixed consumer does not acquire additional states.

**No production model calls were made, no new production animation was accepted, and no external OBS, game-engine or remote event integration was certified.** Available definitions, successful synthetic workflows and locally tested consumers remain distinct from reviewed production artwork. The saved state examples still require approved identity references, anatomy and props, selective installed imagegen generation or explicit imports, and normal visual review for production use.
