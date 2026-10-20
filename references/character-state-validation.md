# Character state library: validation and acceptance

## Verified implementation

Hatch Pet 2.1.0 adds catalog version 1.0.0 with **416 canonical states, 408 aliases, 16 categories, 16 composable packs, 15 archetypes, 19 anatomy capabilities, nine animation recipes and nine transition recipes**. Every canonical state compiles into a bounded custom profile with usable generation instructions. The ordinary preparation, acquisition/import, extraction, validation, review, playback, export and packaging systems consume the result.

This record was measured on **2026-10-19**. [Machine-readable evidence](character-state-validation.json) records the code and consumer hashes, catalog hash, exact test results and demonstration acceptance summaries. The catalog hash is `5de72dedb3262ee0e350d1c5b45fa1cd4455d763b4760fa69ff20914f1895795`.

## Required validation results

| Check | Measured result |
| --- | --- |
| Pristine main baseline at `857791b9503f9ff54b118751eea640866688000a` | 123 tests passed with browsers enabled |
| `python scripts/doctor.py` | Passed; no errors or warnings; catalog and codecs available |
| `python scripts/hatch.py states validate` | Passed, including catalog references and recovery reachability |
| `python scripts/generate_schemas.py --check` | Passed; generated runtime schemas match checked-in schemas |
| `python -m unittest discover -s tests -v` | **206 tests passed in 166.237 seconds; zero failures, errors or skips** |
| `python scripts/demonstrate.py --all --output-dir output/capability-demos` | **15 of 15 workflows passed**, comprising all ten historical presets and five new state selections |
| Skill validation | Updated `SKILL.md` and `agents/openai.yaml` passed the skill validator |
| Independent documented-workflow test | Discovery, cat25 compilation/preparation, base dependency rejection, custom-pack deduplication, animated/static streaming recipes and missing-art previews passed |
| Local visual inspection | Cat fixture playback and all 25 review-state fieldsets rendered in Chromium with no page errors; expanded state guidance was readable |

The project test runtime was Python 3.12.14, Pillow 13.0.0, Node 24.19.0 and Playwright 1.64.0. Real Chromium tests were enabled; the final visual inspection used Chromium 155.0.8059.84. Use the repository's test requirements and install the matching Playwright Chromium browser when reproducing browser checks. A run that skips browser tests supplies less evidence than the result above.

## Acceptance coverage

| Requirement | Implementation and exercised evidence |
| --- | --- |
| At least 200 useful distinct states | 416 canonical records across all 16 requested categories; semantic tests check independent purposes/poses, aliases, expression guidance and the complete human-readable index |
| Every state usable in a valid profile | Every canonical state compiles twice, animated and static: **832 validated profiles**, using only its minimum declared anatomy and its own required props |
| Data validation and schema boundaries | Catalog schema reuses the strict runtime animation schema; compiler validates fields, types, unique IDs, aliases, durations, pose/static consistency and cross-file references; catalog-only fields remain in the sidecar |
| Safe pack composition | All 16 packs compile as bounded subsets; deduplication, deterministic order, nested composition, exclusions, inclusion cycles, missing targets and conflicting definitions are tested |
| Extensibility | Complete custom libraries, additive catalog files and custom pack files work; explicit extension `entry_transitions` make new states reachable without silently granting transitions or replacing canonical meanings |
| Applicability and dependencies | Minimum-anatomy compilation, explicit filter/substitute policies, fallback cycles, mandatory dependencies, approved props, identity direction conflicts and preparation failure before mutation are tested |
| Bounded resource use | Default 32-state operational ceiling; larger finite selections require explicit opt-in; existing frame, source, geometry, atlas and working-memory limits remain enforced |
| Meaningful production instructions | Every state specifies ordered poses, expression, exact durations, action limits, direction, anatomy alternatives, canonical identity constraints, negative constraints and semantic review criteria |
| Source and review integrity | Existing imagegen handoffs and original references remain required; imported art stays imported; sidecar tampering blocks lifecycle operations; wrong profile/prop bindings fail; review/package gates remain active |
| Portable provenance | Preparation pins original selection evidence; archives restore it; deliberate profile revisions preserve the original selection and export whether it still matches the current profile |
| Event-driven playback | The shipped JavaScript executes all nine authored recipes in both animated and static form; tests cover legal sources, once completion, idle recovery, loop/hold dispatch, priorities, repeat events and bounded queues |
| Interruption and fairness | Tests exercise finite interruption restoration, pause/resume, cancellation, hidden-tab timing, suspended-history bounds, coalescing, interruption budgets and an aged event's protected performance turn |
| Reduced motion | Every state has an expressive static alternative; static compilations use one frame per state; runtime preference changes create no hidden animation timers; static recipe completion edges become explicit events |
| Export correctness | Actual frame order, integer durations, static-frame pixels, once/hold GIF/WebP encoding, export file hashes, selection evidence, offline browser preview and review UI are exercised |
| Honest availability | Missing-art previews report `not-generated`; same-name state IDs do not prove catalog binding; export previews require a complete valid receipt and retain fixture/review distinctions |
| Fixed Codex compatibility | Exact original profile bytes, row order, frame counts, durations and 8 × 192 × 208 geometry are regression-tested; additional states stay in custom profiles |
| Existing integrations/examples | All historical preset demonstrations and seven legacy example workflows remain covered; no existing exporter is replaced |
| Reproducible workflows | All seven saved selection files satisfy the actual profile JSON Schema and reproduce normalized compilation output; custom Quiet Companion pack composition is exercised |

The focused test files are `test_state_catalog.py`, `test_state_catalog_cli.py`, `test_state_catalog_data.py`, `test_state_integration.py` and `test_state_playback.py`, with real browser additions in `test_playback_extended.py`. The full suite includes all historical tests; none were removed or relaxed to admit new definitions.

## Demonstrated state selections

The new demonstrations execute the real local pipeline with an explicitly synthetic, asymmetric calibration shape. Animated fixture frames are distinct; static profiles use one intentional frame. The calibration shape does not depict the selected emotions, species, props or actions. It verifies data flow, extraction, timing, source receipts, gate handling, packaging and export behavior.

| Demonstration | States | Frames | Model calls | Result |
| --- | ---: | ---: | ---: | --- |
| Expressive cat | 25 | 100 | 0 | Passed |
| Coding assistant | 49 | 196 | 0 | Passed |
| Game NPC | 29 | 116 | 0 | Passed |
| OBS mascot | 25 | 100 | 0 | Passed |
| Accessible feedback | 14 | 14 | 0 | Passed |
| **Total** | **142** | **526** | **0** | **All passed** |

The historical assembly, process, configurator, flipbook, communication, perception, regression, cursor, protocol and craft demonstrations also passed. Each demonstration writes an `acceptance.json`, exported consumer files and a review workspace. Run the documented command to reproduce these files locally; generated output is intentionally not versioned as production artwork.

The separate `reference-studio.json` selection compiles a 32-state chapter from the Complete Character Studio pool. `stream-conversation.json` compiles a five-state interruption recipe. The independent forward test also verified that a newly prepared cat run retains 26 pending jobs, zero attempts, and a mandatory base dependency before any state acquisition.

## Compatibility and evidence boundaries

The fixed `profiles/codex-v1.json` remains byte-for-byte unchanged, with SHA-256 `f4e0279f8634ea53ef544ecb49b9a71ec2565c61ec5b8e63163ecc5ead478a6b`. It still defines exactly nine rows in this order: `idle`, `running-right`, `running-left`, `waving`, `jumping`, `failed`, `waiting`, `running`, `review`. Its original eight columns, 192×208 cells and frame timings are preserved. Catalog compilation always marks its custom profiles as not Codex-compatible.

| Evidence level | What this implementation establishes |
| --- | --- |
| Available definitions | All 416 states are discoverable, selectable and structurally/semantically validated as production instructions |
| Fixture workflows | Five new state selections and ten existing purpose-specific presets pass the actual deterministic local pipeline |
| Reviewed production animations | **No new production artwork was generated or accepted in this implementation**; real production acquisitions still require provenance and current visual review |
| Locally tested consumers | Existing browser playback/review, frame and atlas export, GIF/WebP, static assets and historical purpose-specific consumers pass their automated checks |
| External integrations | No new live OBS, game-engine, stream-service or expanded fixed Codex integration is claimed |

For production use, supply the approved character references, confirm actual anatomy and props, acquire only the selected rows through the installed imagegen workflow or explicit imports, and complete the normal visual review. A dependency token for an appearance variant is a prerequisite to supply approved references; it is not a generated form or an animation morphing system.

External applications must map their real events to the exported local event interface and test their own host behavior. OBS can present the local browser export; live stream output and remote event transport remain host integration work. The player implements discrete frame changes, completion transitions and bounded local state restoration. It does not implement interpolation, blending, rigging, physics, phoneme synchronization or remote orchestration.
