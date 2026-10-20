# Character state library

Version **1.0.0** contains **416 canonical animation definitions**, **408 semantic aliases**, **16 composable packs**, **15 archetype presets**, **9 animation recipes**, and **9 transition recipes**. The [complete state index](CATALOG.md) lists every definition and alias. These are production instructions and validated metadata; this directory contains no generated or reviewed production artwork.

Use the existing Hatch entry point:

```sh
python scripts/hatch.py states list
python scripts/hatch.py states search "tail" --archetype cat
python scripts/hatch.py states list --category agent-workflows
python scripts/hatch.py states show double-blinking
python scripts/hatch.py states packs streaming-and-obs
python scripts/hatch.py states recipes stream-conversation
python scripts/hatch.py states validate
```

`python scripts/state_catalog.py` provides the same standalone catalog commands. `show` includes exact pose progression, timings, anatomy, dependencies, static alternative, generation requirements and semantic review criteria. Discovery never starts image generation.

## Authoritative files and boundaries

| File | Purpose |
| --- | --- |
| `catalog.json` | Versioned canonical definitions, aliases, category registry and generation/review requirements |
| `packs.json` | Explicit state memberships, pack composition, exclusions, recommendations and selection-only studio policy |
| `archetypes.json` | Named anatomy capabilities and conservative preset capability sets |
| `animation-recipes.json` | Reusable timing/phase recipes; every state also retains its fully materialized animation contract |
| `recipes.json` | Executable playback event rules, completion chains, legal sources, initial/cancel states and queue bounds |
| `schema.json` | Strict JSON Schema for the files and extension documents; runtime animation reuses the existing profile schema |

Catalog metadata stays outside the strict runtime profile. The compiler produces a validated ordinary profile and a hash-bound selection record. The existing preparation, installed imagegen handoffs, source imports, extraction, validation, review desk, playback, export and packaging pipeline consumes that profile.

The catalog targets custom profiles. **The fixed Codex consumer still has exactly nine rows, eight columns and 192×208 cells, in its original order and timings.** `profiles/codex-v1.json` remains the authority. Catalog records with familiar IDs are custom-profile definitions, not edits to that consumer contract. In particular, `running` means active task processing; `running-left`, `running-right`, `running-forward` and `running-away` are physical locomotion.

## Selection and operational limits

```sh
python scripts/hatch.py states compile --state idle,curious,excited --profile-id curious-mascot --output work/curious-profile.json
python scripts/hatch.py states compile --pack virtual-pet-and-daily-life --archetype cat --anatomy-policy filter --limit 25 --output work/pet-profile.json
python scripts/hatch.py states compile --recipe agent-success --output work/agent-profile.json
python scripts/hatch.py states compile --recipe stream-conversation --archetype humanoid --output work/stream-profile.json
```

Inspect the compile report before acquisition. It reports the selected states, dependency closure, generation-call estimate, frame count, atlas dimensions, memory estimate and all filtering or substitutions. These are explicit work estimates, not image-provider prices. No command above creates artwork.

The default selection limit is bounded. An explicitly approved larger selection still passes the existing hard state, frame, atlas geometry and memory limits. Pack membership is a discovery pool; it is not a promise that every member belongs in one production atlas. `complete-character-studio` is selection-only and requires an explicit subset or limit. Do not turn its 416 definitions into a monolithic sheet.

The compiler deduplicates resolved canonical IDs in deterministic selection order. Aliases add discoverability without manufacturing new animation rows. If an explicitly selected state is incompatible, the default is a clear failure. `filter` omits incompatible pack members and reports them. `substitute` follows the declared fallback graph and records each changed selection. A missing keyboard never quietly appears merely because a coding state was requested.

The canonical extraction policy is the existing row policy. Generation and review require a common viewport and character scale. For an actual art set needing a stronger shared-scale calibration, use the existing extraction calibration workflow; catalog selection does not infer a trustworthy scale from metadata.

## Anatomy and approved dependencies

An archetype is a starting assumption, not a visual analysis of a supplied image. `generic` declares only a body. `cat` assumes a usual cat with paws, ears, mouth, eyes and tail; it does not grant human hands. `bird` grants wings and feet, without adding human hands or mammal ears. `object`, `blob` and `robot` are deliberately conservative about expressive faces.

Compare the selected capabilities with the approved reference. Explicit capability lists replace the preset rather than silently augmenting it. A character lacking a mouth can still convey anatomy-neutral emotion through its existing posture. Actions that actually require a mouth, hand, fin, wing, shell, ear or tail are gated. Their declared fallback can preserve intent through a suitable body gesture when substitution was selected. Fallbacks are different canonical states and are always disclosed.

`props.required` contains explicit dependency labels. Ordinary labels such as `keyboard`, `food`, `paintbrush` or `musical-instrument` require an approved source identity containing the relevant prop. Tokens such as `approved-growth-variant`, `approved-evolved-variant`, `approved-transformed-variant` and `approved-dirty-variant` instead identify a required **approved appearance variant**. They do not name physical objects to draw. Reconcile both source and destination appearance, all supplied identity views, and every intermediate pose before acquiring these states. The compiler's approval token is an attestation of a prerequisite; it neither creates the variant nor proves visual continuity.

The same principle applies to equipping, handing over items and hatching. The approved before-and-after prop states must exist in the reference specification. Detached thrown, caught or juggled objects require explicit component approval and the existing exact extraction annotations. The default detached-detail gate stays enabled. No state grants automatic permission to paint detached effects, text, shadows, backgrounds or new props.

Directional states carry facing and travel requirements separately. Every catalog animation has an empty derivation list. Left-facing and right-facing performances are independent acquisitions; no mirror permission is implied. Rear-view travel and a full rotation require reconciled approved rear/side identity information before generation.

## Timing, transitions and static alternatives

Each canonical record materializes a usable `animation` object. Four-beat recipes handle many small sprite performances; `double-blinking` uses five explicit open/closed/open/closed/open frames so two closures are actually representable. Intentionally static definitions contain one frame. They do not repeat a bitmap to imitate animation.

Animation recipes describe phases and cadence. A state may choose deliberate different durations from its named general recipe, such as slower meditation or faster sprinting; its materialized animation timings and generated instructions agree. An explicit animation-recipe override is a new selection decision and is retained in the selection record.

Canonical `legal_transitions` list allowed outgoing destinations. The compiler inverts the selected edges into the existing playback event `from` rules. Idle is the neutral entry/recovery hub, related family states allow direct movement within their family, and useful cross-family transitions are explicit. Direction dependencies, completion destinations and recovery states must all resolve. A completion is a real state change at the end of a one-shot; it does not promise frame blending or interpolation.

Transition recipes are executable bounded configurations. `curiosity-discovery`, `sleep-cycle`, `social-welcome`, `setback-resilience`, `cinematic-arrival` and `low-motion-feedback` provide finite illustrated phrases. They deliberately adapt interior loop states to one cycle where needed. `agent-success` and `agent-recovery` retain host-controlled active work until the host reports a result. `stream-conversation` alternates speech/listening and marks its one-shot interruption with `resume: true`; playback restores the interrupted loop after that temporary event finishes. A separate explicit `resume-speech` event can return to speech immediately when legal.

Every state supplies a static alternative by frame index. Expression apex frames are used where a neutral starting frame would lose the meaning. True static and calm ambient definitions select their stable first pose. Reduced-motion behavior displays the chosen pose without flashing, forced looping or fabricated tweening.

## Meaningful distinctions and aliases

A canonical definition needs a distinguishable performance, not merely another adjective. This library uses four practical discriminants: the event being represented, the direction of attention, the ordered body/face poses, and their timing.

| Neighbors | Deliberate distinction |
| --- | --- |
| Happy / smiling / laughing / giggling | Overall positive posture; localized gradual mouth expression; broad body laugh pulses; small contained laugh pulses |
| Curious / investigating / inspecting / fascinated | Interest begins; successive clue tests; one close detail check; sustained absorbed attention |
| Realization / having-an-idea / understanding | Sudden connection; proposal of a new possibility; gradual comprehension |
| Disappointed / discouraged / defeated | One unmet expectation; diminished willingness after effort; release of active resistance |
| Grateful / thanking | Inward felt appreciation versus a directed social acknowledgment |
| Ready / ready-stance | Available software-task attention versus physical game-action guard |
| Failed / error / blocked / cancelled | Unsuccessful outcome; unexpected fault occurrence; inability to proceed; intentional abandonment |
| Completed / successful / partially-successful | Work ended; confirmed favorable result; useful progress with an unresolved limitation |
| Floating / hovering / gliding | Passive drift; powered stationary wing action; extended-wing travel without active flapping |
| Waving / beckoning / inviting | Side-to-side greeting; inward motion asking someone closer; open body invitation to participate |
| Recovering / balance-recovery / emotional-recovery / healing | Restored task organization; regained physical balance; emotional composure; gradual physical comfort |
| Greeting / audience-greeting / introduction / introducing | One-person welcome; inclusive group sweep; character reveal; social self-introduction |

Synonyms resolve to an existing canonical record when these discriminants do not justify a second animation. Examples include `joyful` and `cheerful` → `happy`, `irritated` → `annoyed`, `frightened` → `afraid`, `reviewing` → `review`, and `working`/`processing` → `running`. Category overlaps are represented through tags, pack membership and aliases rather than cloned definitions.

## Extending and migrating

A custom pack file contains `schema_version: 1` and a `packs` list using the same record schema. Pass it with `--pack-file path/to/my-packs.json`. It may combine existing packs and IDs and exclude a deliberate subset. Identical repeated definitions are idempotent; conflicting definitions, unknown targets, alias collisions and inclusion cycles fail.

A custom catalog file contains the matching `catalog_version`, `schema_version: 1`, `categories` and complete `states` records. Use the nearest existing state as an authoring reference, then give the new action a unique ID, independent semantics, full requirements and a new unique event name. Pass the file through `--catalog-file`. An optional `entry_transitions` map, such as `{"idle":["custom-slow-bow"]}`, explicitly connects existing source states to new definitions introduced by that extension. It cannot mutate built-in meanings or grant unrelated new transitions to built-in targets. For a complete alternative library, supply the entire five-file set with `--library`.

Keep published IDs and aliases stable. Additions normally warrant a minor catalog version; meaning-changing edits, removed states or changed alias resolution require deliberate migration. Existing production runs retain their selected profile and the source/version/hash evidence. Recompile deliberately and use the existing profile-revision and review workflow when changing a run's contract; do not silently reinterpret saved frames under a different catalog definition.

## Evidence and review status

`states validate` checks structural and semantic references. The automated suite compiles every canonical state into a bounded valid profile and exercises representative profiles with deterministic labeled synthetic assets. Fixture workflows demonstrate integration and gate behavior. They do not demonstrate that a model drew 416 faithful animations.

Use `states preview --run-dir <run>` to inspect availability and bound review status for actual frames. Missing artwork is reported as not generated. An available fixture remains a fixture. Reviewed production artwork requires the real installed-imagegen or explicit-import provenance path and current visual review. Browser export and local playback tests establish local consumer behavior; they do not establish a live OBS account, game engine, stream service or expanded fixed Codex integration.
