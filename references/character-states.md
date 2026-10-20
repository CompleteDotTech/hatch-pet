# Character states, packs and selective generation

## Contents

- [What the library contains](#what-the-library-contains)
- [Discover definitions and artwork](#discover-definitions-and-artwork)
- [Compile a bounded selection](#compile-a-bounded-selection)
- [Anatomy, identity and approved props](#anatomy-identity-and-approved-props)
- [Worked selections](#worked-selections)
- [Generate or import selected artwork](#generate-or-import-selected-artwork)
- [Animation and transition recipes](#animation-and-transition-recipes)
- [Custom libraries and packs](#custom-libraries-and-packs)
- [Compatibility, migration and limits](#compatibility-migration-and-limits)
- [Demonstrations and verification](#demonstrations-and-verification)

## What the library contains

`state-library/catalog.json` is the canonical, versioned authoring catalog: **416 canonical states, 408 aliases, 16 categories, 16 packs, 15 archetypes, nine animation recipes and nine transition recipes** in catalog version 1.0.0. The CLI lists every definition and resolves aliases to canonical IDs. A definition describes a visual behavior; it is not a raster asset or a claim of model generation.

The catalog spans neutral and ambient behavior, positive and difficult emotions, cognition, locomotion, social gestures, pet needs, software workflows, hobbies, games and combat, communication and streaming, environmental reactions, narrative performance, microexpressions, lifecycle changes and accessible feedback. Packs select reusable subsets across these categories. Combat belongs in opt-in game/RPG packs.

Each canonical record contains a portable lowercase ID, display name, category, family, tags, aliases, meaning, applicable archetypes and anatomy, generation-ready animation data, timing, key poses, expression, direction, event and transition rules, completion and recovery, priority and interruption policy, a reduced-motion pose, prop requirements, negative constraints, semantic review criteria, compatibility metadata and examples. Runtime animation fields are nested under `animation`; catalog-only fields never leak into the strict profile schema.

The supporting data files are:

| File | Purpose |
| --- | --- |
| `catalog.json` | Canonical state definitions, categories and aliases |
| `packs.json` | Sixteen named packs, composition and selection restrictions |
| `archetypes.json` | Character presets and explicitly named anatomy capabilities |
| `animation-recipes.json` | Reusable frame/timing and action-phase recipes |
| `recipes.json` | Finite event/completion workflows with legal transitions |

Run `python scripts/hatch.py states validate` or `python scripts/doctor.py` for actual counts, versions, integrity checks and capability summaries. Machine-readable definitions are the source of truth; profile compilation also invokes the existing `profile_spec.load_profile()` and resource checks.

| Category ID | Canonical states | Distinguishing coverage |
| --- | ---: | --- |
| `neutral-idle` | 34 | Resting posture, attention, gaze and personality idles |
| `positive-emotions` | 26 | Different expressions of happiness, interest, confidence and affection |
| `difficult-emotions` | 30 | Sadness, frustration, fear, uncertainty and recovery needs |
| `cognition` | 29 | Investigation, understanding, reasoning and communication |
| `locomotion` | 40 | Explicit directions, gaits, jumps, flight and balance |
| `social-gestures` | 32 | Greetings, agreements, acknowledgment and interpersonal gestures |
| `pet-daily-life` | 49 | Needs, rest, care and creature anatomy |
| `agent-workflows` | 43 | Task progress, waits, failures and connectivity |
| `activities-hobbies` | 19 | Performance, creative work and approved object interactions |
| `game-rpg` | 29 | NPC interactions, unarmed combat and non-graphic reactions |
| `streaming-communication` | 17 | Stream status, audience reactions and connection changes |
| `environmental-reactions` | 14 | Weather, lighting, sound and spatial reactions |
| `narrative-cinematic` | 13 | Scene entrances, emphasis, resolution and exits |
| `transitions-microexpressions` | 14 | Brief expression changes and pose transitions |
| `lifecycle-progression` | 14 | Emergence, approved variants and achievement |
| `accessibility` | 13 | Low-stimulation and static communicative feedback |

Canonical states belong to one category but can serve several packs. For example, `listening` serves idle, tutor and streaming workflows. Synonyms such as `working` and `processing` resolve to `running`; directional `running-left` and `running-right` remain distinct. The catalog does not count aliases as additional animations.

### Recommended packs

| Pack ID | Selection purpose |
| --- | --- |
| `core-essentials` | A small general character foundation |
| `emotions-and-expressions` | Positive and difficult emotions plus expressions |
| `movement-and-locomotion` | Directional travel, gaits and recovery |
| `social-and-gestures` | Social communication and gestures |
| `virtual-pet-and-daily-life` | Needs, care, play and rest |
| `ai-assistant-and-coding-agent` | Comprehensive software and task statuses |
| `game-npc` | Locomotion and social game interactions |
| `rpg-and-combat` | Opt-in game action and combat responses |
| `streaming-and-obs` | Stream presentation and audience feedback |
| `educational-and-tutor` | Learning, explaining and encouragement |
| `customer-support-and-kiosk` | Attentive service and nonverbal responses |
| `storytelling-and-cinematic` | Narrative gestures, arrivals and exits |
| `environmental-reactions` | Character-only reactions to surroundings |
| `creature-specific-behaviors` | Capability-gated paws, wings, tails and other anatomy |
| `accessibility-and-low-motion` | Clear, low-stimulation feedback |
| `complete-character-studio` | Discovery of all states and explicit bounded chapters |

Packs include core essentials where appropriate. Their listed sizes are not generation orders: inspect them, select useful subsets, and apply the character's actual anatomy/prop constraints. Large combinations require the same deliberate ceiling and resource checks as individual selections.

## Discover definitions and artwork

```bash
python scripts/hatch.py states list
python scripts/hatch.py states list --json
python scripts/hatch.py states search curious
python scripts/hatch.py states search waiting --archetype cat
python scripts/hatch.py states show running
python scripts/hatch.py states packs
python scripts/hatch.py states archetypes
python scripts/hatch.py states recipes
python scripts/hatch.py states recipes --animation
```

Search includes names, aliases, descriptions, families, categories, tags and generation semantics. Use `--category`, `--family`, repeated `--tag`, `--archetype`, repeated `--capability`, and `--compatibility` filters where useful. `states show ID` exposes the full generation and review contract rather than only a name. Use `--help` on each subcommand for its accepted flags.

Artwork discovery is separate:

```bash
python scripts/hatch.py states preview curious
python scripts/hatch.py states preview idle curious --run-dir output/cat-run
python scripts/hatch.py states preview idle curious --export-dir output/cat-export
```

Without artwork, the result says `not-generated`. With a run/export, it reports actual indexed frames, available preview HTML, fixture and review status, and profile/catalog binding information. Missing or invalid frames are reported; no generated-looking placeholders are substituted. Open the existing export's `preview.html` for manual selection, timed playback, stepping and static alternatives. The run's review desk is created explicitly through `hatch.py review-ui`.

## Compile a bounded selection

```bash
python scripts/hatch.py states compile --state idle --state curious --state investigating --archetype cat --output output/curious-cat.json
python scripts/hatch.py states compile --selection examples/state-selections/expressive-cat.json --output output/cat-profile.json
```

The command writes the normalized profile plus `cat-profile.selection.json`. It refuses to overwrite either output. Omitting `--output` prints the complete compilation result for inspection without creating a run or making a model call.

Compilation resolves aliases, deduplicates in first-selection order, composes packs deterministically, checks anatomy and props, adds mandatory recovery/completion/directional dependencies, and applies the existing geometry and memory limits. It records why each state was selected, substitutions, omissions, recipe adaptations, exact source hashes and the resulting profile hash. Conflicting event names, aliases, recipes, missing dependencies and invalid transitions fail explicitly.

The default operational ceiling is **32 states including dependencies**. To deliberately choose a larger bounded profile, supply both `--allow-large` and a finite `--max-states`, while remaining within all runtime resource limits. `--limit` selects a deterministic subset of pack members; mandatory dependencies may add states and are still checked against `--max-states`. Check the final count rather than assuming the requested list is the complete dependency closure.

The Complete Character Studio pack is for discovery and explicit subsets. It cannot be compiled unrestricted into a giant atlas. Give it selected `--state` entries or an explicit `--limit`; incompatible anatomy still requires the chosen policy. Build multiple modest profiles for a large cast or reuse existing generated rows through explicit imports.

The selection manifest estimates state count, total frames, atlas pixels/RGBA bytes, largest source strip, raster working memory, and a baseline of **one canonical base plus one model call per selected state**. Retries increase this count; importing approved art can reduce it to zero. No price or completion-time estimate is invented. Set the existing run attempt/concurrency/call/budget limits before production acquisition.

## Anatomy, identity and approved props

Archetypes are convenient starting assumptions, not image recognition. Compare the preset with the supplied reference. A stylized cat may lack a visible mouth; a robot may have no hands; an object mascot may have no face. Repeated `--capability` flags replace the entire preset capability set rather than adding anatomy silently.

Choose an explicit policy:

| Policy | Behavior |
| --- | --- |
| `error` | Reject an incompatible selection; this is the default |
| `substitute` | Follow declared, validated fallback definitions and record every substitution |
| `filter` | Omit incompatible pack members with reasons; explicitly requested states still fail |

Fallbacks preserve the communicative intent where feasible: a greeting can become a body acknowledgment instead of inventing a waving hand. They are distinct selected definitions, not automatic edits to the original action. Mandatory recipe/dependency states cannot be silently substituted. Tail, wing, ear, paw, hand and expressive-face actions require their declared capabilities.

`--approve-prop keyboard` records an explicit compilation choice. It does not independently modify the production identity. If selected states require `keyboard`, preparation requires a structured identity whose `approved_props` includes `keyboard`. It fails before creating a run when approval is missing or an explicit identity direction contradicts the state. Optional props are allowed only when already approved in that identity.

Keep the approved silhouette, proportions, facial structure, markings, colors, textures, materials, clothing, accessories, lighting, style and scale consistent. The compiler includes these requirements in every state's generation contract. Left/right/back/front orientations are explicit; selecting a directional state never authorizes mirroring. Catalog profiles declare no inferred mirror derivations. Environmental reactions describe character poses while keeping rain, snow, lightning and other scenery/effects outside the character artwork.

## Worked selections

The files under `examples/state-selections/` are saved compiler inputs, not runtime profiles. They use `schema_version: 1`, a `profile_id`, selected `states` and/or `packs`/`recipe`, an `archetype`, optional exact `capabilities`/`approved_props`, an `anatomy_policy`, and optional bounded layout/recipe choices. Compile them before passing them to `prepare`.

| Selection | Intended use |
| --- | --- |
| `expressive-cat.json` | Exactly 25 expressive, prop-free cat states, including pet needs and anatomical behavior |
| `coding-assistant.json` | Comprehensive workflow/status coverage; literal keyboard actions require approved keyboard identity |
| `game-npc.json` | Locomotion, social behavior and non-graphic game actions for a humanoid |
| `obs-mascot.json` | Speaking, listening, celebration, interruptions and connection/stream status |
| `reference-studio.json` | A bounded cross-family starting selection for a supplied character reference |
| `accessible-feedback.json` | One static expressive pose per selected accessible feedback state |
| `stream-conversation.json` | A five-state recipe with declared speech, listening and resumable interruption events |

```bash
python scripts/hatch.py states compile --selection examples/state-selections/coding-assistant.json --output output/agent-profile.json
python scripts/hatch.py states compile --selection examples/state-selections/game-npc.json --output output/npc-profile.json
python scripts/hatch.py states compile --selection examples/state-selections/obs-mascot.json --output output/obs-profile.json
python scripts/hatch.py states compile --selection examples/state-selections/reference-studio.json --output output/studio-profile.json
python scripts/hatch.py states compile --selection examples/state-selections/expressive-cat.json --reduced-motion --output output/cat-stills.json
```

At the default cell size, the cat selection has 100 frames and 26 baseline generation jobs; the coding selection has 196 frames and 50 jobs. The game and OBS examples contain 29 and 25 states; the reference chapter contains 32. The accessible selection contains 14 static states and 14 frames. These are workload estimates, not completed image generation. The coding example deliberately opts into a 64-state ceiling. Its keyboard and the game's `usable-item` must also be approved in the preparation identity.

For a user-supplied image, select the closest archetype and accurate capability overrides first, then prepare with `--reference art/character.png` and the compiled profile. Preserve multiple viewpoints using the existing reference-role contract. This workflow does not infer missing anatomy or reconstruct unseen views automatically. Produce additional bounded chapters from the Complete Character Studio pack as useful; importing existing approved rows avoids regenerating common states.

## Generate or import selected artwork

```bash
python scripts/hatch.py prepare --run-dir output/cat-run --profile output/cat-profile.json --pet-name Miso --reference art/cat.png
python scripts/hatch.py limits --run-dir output/cat-run --max-attempts 3 --concurrency 1 --max-calls 40
python scripts/hatch.py claim --run-dir output/cat-run --job base
```

Preparation automatically loads an adjacent `.selection.json` when present; `--state-selection PATH` supplies a separately stored manifest. The bound copy is saved in the run and pinned by the immutable request. Changing or removing it blocks lifecycle operations. A standalone custom runtime profile still works through the historical profile workflow without a catalog claim.

Read the installed imagegen skill for actual production calls. For a base claim, attach all required supplied references. Ingest the selected source with the existing token/receipt, inspect it, and record `base-review`. Claim selected state jobs only after their dependencies are ready. Every row handoff retains canonical identity, original references, the layout guide, exact timing, key poses, action progression, expression, motion limits, orientation, negative constraints and semantic review criteria. Retry prompts preserve that contract.

Alternatively use `import-source` with attributed image/strip/ordered-frame descriptors. Imported art retains import origin and never becomes imagegen output. See [sources and identity](sources-and-identity.md) for exact acquisition and review commands.

```bash
python scripts/hatch.py validate --run-dir output/cat-run
python scripts/hatch.py review-ui --run-dir output/cat-run --destination output/cat-review
```

Inspect actual artwork and timed playback. The review desk displays each state's meaning and generation requirements next to the six existing review dimensions. Download the completed receipt, submit it through `review`, then export/package. Numerical checks cannot determine whether joy differs from relief, a gait faces left, or a subtle idle preserves identity. No metadata compiler can supply those verdicts.

## Animation and transition recipes

Animation recipes reuse authored frame counts, durations and ordered phases. Use `--animation-recipe state-id=recipe-id` only after inspecting `states recipes --animation`. The compiler preserves the state-specific meaning and constraints, reports the adaptation and rejects invalid static/hold frame indices or excessive allocations.

Transition recipes compile into the existing browser playback v2 event/completion model. Inspect one with `states recipes RECIPE_ID` and compile with `states compile --recipe RECIPE_ID --archetype humanoid --output output/recipe.json`. A recipe declares its complete legal event graph, initial/cancel state, completion chain and queue bound. Recipe profiles expose their declared event names; generic catalog event aliases do not bypass recipe restrictions. The manual state selector remains an explicit inspection tool.

Examples cover discovery and celebration; working, reviewing and success; failure, frustration and recovery; and a tired/yawn/sleep/wake routine. Loops persist until an event, one-shots complete deterministically, and holds show their configured frame. Cancellation returns to the declared recovery state. See [playback and extensions](playback-and-extensions.md) for priorities, fairness, interruption/resume, coalescing and reduced-motion behavior.

Per-state `playback.reduced_motion_frame` selects an expressive existing frame for static display. A compiled `--reduced-motion` alternative emits one deliberately static pose per state, avoiding fabricated duplicate frames. No interpolation, blending, skeletal rigging or speech synchronization is implemented by this library.

When compiling a recipe as static poses, automatic completion edges become explicit `next:<source-state>` events. This makes every step accessible without adding hidden timers. Automatic interruption return is disabled as well: the static streaming recipe uses explicit `resume-speech` to select speaking or cancellation to return to idle; it does not restore a previously active listening pose automatically. The manifest records these adaptations. A browser preference for reduced motion instead freezes the selected expressive frame in the animated profile until an explicit event or selection changes it.

## Custom libraries and packs

Use `--library path/to/state-library` for an explicitly selected complete library directory. It must contain the same five versioned data files and pass strict validation. `--catalog-file path/to/extension.json` adds compatible canonical definitions/categories; `--pack-file path/to/packs.json` adds composable local packs. Extensions are JSON data, never executable plugins. Existing canonical IDs cannot be replaced accidentally; conflicting aliases and definitions fail.

A pack file has `schema_version: 1` and a `packs` list. Each pack follows the same exact fields as the bundled `packs.json`; copy a small existing record, give it a unique portable ID, and select declared states or include other packs. Pack inclusion cycles, missing members and incompatible rules are rejected. A custom state follows the catalog's exact record schema, including a valid nested animation, anatomy fallback and recovery. Inspect a similar canonical entry instead of inventing unsupported runtime fields.

Try the supplied custom pack:

```bash
python scripts/hatch.py states --pack-file examples/state-packs/quiet-companion.json compile --pack quiet-companion --archetype cat --output output/quiet-companion.json
```

An additive catalog extension can declare `entry_transitions`, mapping an existing source ID to newly defined destinations. For example, a file defining the complete record for `custom-bow` can include `"entry_transitions": {"idle": ["custom-bow"]}` alongside `schema_version`, `catalog_version`, `categories` and `states`. This explicitly authorizes entry from the existing hub. Sources must exist; every destination must be a non-builtin state defined in that extension. Existing canonical meanings cannot be replaced. Unknown endpoints and an unreachable new state fail validation. This field is accepted only for `--catalog-file` extensions; the base catalog format remains unchanged.

For reproducibility retain the source files, normalized saved selection, compiled profile and sidecar. The sidecar records library version/hash, source hashes, the exact final state order, recipe adaptations and profile hash. The same definitions and selection produce identical compilation output; it contains no timestamps or random identifiers. Production run IDs and source acquisition receipts remain independently recorded by the existing controller.

## Compatibility, migration and limits

`profiles/codex-v1.json` is unchanged: nine rows, eight columns, 192×208 cells, the exact original state order and millisecond timings. The catalog retains `running` for task processing, with directional running separately identified. Catalog profiles set `codex_compatible: false`. Additional states do not become available in the fixed Codex consumer.

Profile schema versions 1 and 2 remain accepted; compiled character profiles use version 1 to retain the established character/style prompt workflow. Playback remains consumer v2 with additive optional fields. Existing examples and presets continue through their original commands. Moving an existing run to another state set/order requires a newly prepared run. A permitted `revise-profile` keeps the original selection as historical provenance; exports explicitly state whether the current profile still exactly matches it. Revalidate and visually review affected artifacts.

The existing hard limits remain in force: at most 256 states, 64 frames per state, 1,024 total frames, 64 million atlas pixels, a 768 MiB estimated raster working set, and 2 million pixels/64 MiB per imported source. These limits interact, so a nominally valid state count can still exceed memory or geometry. The compiler checks the largest selected source strip before preparation. Reducing cell size or selecting a smaller subset preserves the same architecture; no validator is disabled to fit the catalog.

PNG frames, atlas metadata and static alternatives retain exact pixels and integer millisecond timings. GIF uses palette/binary alpha and 10 ms timing units. GIF one-shots omit looping metadata; animated WebP one-shots use one play. Hold exports contain the held frame. Cross-state completion/event transitions execute in the browser runtime, not inside separate GIF/WebP files. OBS can display the existing local `preview.html?overlay=1&state=idle`; OBS setup, live Program output, remote events, game-engine import and external integrations remain separate work.

## Demonstrations and verification

```bash
python scripts/doctor.py
python scripts/hatch.py states validate
python scripts/demonstrate_states.py --all --output-dir output/state-demos
python scripts/demonstrate.py --all --output-dir output/capability-demos
python -m unittest discover -s tests -v
```

The five state demonstrations compile saved selections, import ordered synthetic shapes, enforce strict extraction/atlas checks, exercise fixture review gates, package/export, and build offline review workspaces. Each `acceptance.json` records counts, hash checks, zero model calls and explicit fixture/production/integration boundaries. Original purpose-specific demonstrations remain included in `demonstrate.py --all`.

Tests validate every canonical definition and individual bounded compilation, pack integrity and deduplication, alias conflicts, anatomy/props, dependencies, schema and resource limits, prompts, serialization, actual event playback, encoded outputs, sidecar provenance, review gates and the unchanged Codex bytes. The synthetic art verifies plumbing, not emotion or action quality. See [character state validation](character-state-validation.md) for acceptance mapping and measured results.
