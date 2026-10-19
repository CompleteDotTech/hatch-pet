# Production contracts and performance coordinates

The production workflow stores a portable project, a shared cast, reusable clips, and scene manifests. The deterministic evaluator and raster renderer consume those files directly. Production schema version **1** is independent of the existing hatch run and profile schema versions. Existing Codex pet manifests continue through the legacy commands.

The executable definitions live in [`production_contracts.py`](../scripts/production_contracts.py). The five checked-in JSON Schema documents are generated from those same definitions. [`test_production_contracts.py`](../tests/test_production_contracts.py) verifies schema equality and validates a real fixture against both JSON Schema and the runtime loader. Semantic checks supplement JSON Schema: a structurally valid file can still have a broken hierarchy, incompatible drawing, discontinuous ownership change, or illegal interruption.

## Files, identity, and portability

| Artifact | Required identity and relationship | Checked-in schema |
| --- | --- | --- |
| Project | `schema_version: 1`, `kind: project`, stable `id`, semantic `version`, `fixture`; hash-bound cast, clip, and scene references | [`production-project.schema.json`](../profiles/production-project.schema.json) |
| Cast | `kind: cast`; character and prop versions shared by any number of project scenes | [`production-cast.schema.json`](../profiles/production-cast.schema.json) |
| Clip | `kind: clip`; stable clip `id@version` and one exact character `id@version` | [`production-clip.schema.json`](../profiles/production-clip.schema.json) |
| Scene | `kind: scene`; ordered shots and explicit continuity links, including links across scenes | [`production-scene.schema.json`](../profiles/production-scene.schema.json) |
| Shot | Stable project-wide `id`; integer duration, instances, props, interactions, layers, camera, and audio | [`production-shot.schema.json`](../profiles/production-shot.schema.json) |

IDs start with a lowercase letter and contain at most 64 lowercase letters, digits, underscores, or hyphens. Versions use three nonnegative integers, such as `1.0.0`, without leading zeros. A character reference such as `milo@3.0.0` selects that exact version. Multiple versions may coexist in a cast; duplicate `id@version` entries fail validation. All shot IDs and scene IDs are unique within a project.

File references contain `path` and lowercase hexadecimal `sha256`. Image references also contain `size: [width, height]` and `provenance`. Every referenced path is relative to the project directory, including paths found inside the cast, clips, scene files, source provenance, and acquisition receipts. Paths cannot be absolute, contain a drive prefix or backslash, traverse `.` or `..`, contain empty segments, or traverse a symlink. Moving the complete directory preserves those references.

A project can therefore have the following layout without copying character assets between scenes:

| Path | Contents |
| --- | --- |
| `project.json` | Project identity, cast/clip/scene references, render settings, resource limits |
| `cast.json` | Shared versioned characters, costume maps, component drawings, prop assets |
| `clips/idle-milo.json` | Reusable authored motion for one character version |
| `scenes/first-scene.json` | Instances, shot-specific acting, camera, audio, and interaction placements |
| `scenes/second-scene.json` | New performance using the same cast versions and clip assets |
| `art/`, `audio/`, `provenance/` | Exact referenced sources and acquisition/import evidence |

The default `load_project(path)` fails on missing files, changed hashes, unsafe paths, invalid image headers, unsupported fields, nonfinite numbers, duplicate JSON keys, broken references, and excessive resource requests. A missing original image cannot be replaced with unrelated bytes while retaining its hash or acquisition history.

Read-only diagnostics can call `load_project(path, verify_hashes=False, allow_missing_assets=True)`. Missing leaf assets appear in `missing`, `stale`, and `inventory`; a missing cast, clip, or scene manifest still fails because the loader cannot determine the project structure. Contradictory expected hashes for one path, unsafe paths, and semantic errors fail in every mode. Diagnostic loading does not make stale work renderable or approvable.

## Public Python interfaces

| Function | Result and purpose |
| --- | --- |
| `load_project(path, verify_hashes=True, *, allow_missing_assets=False)` | Validated bundle with `root`, `project`, `cast`, version-indexed `characters`, `props`, `clips`, ordered `scenes`, indexed `shots`, portable `paths`, actual `inventory`, `stale`, `missing`, and `resources` |
| `validate_cast(cast, fixture=None)` | Structural and character construction validation |
| `validate_clip(clip, characters)` | Track types, root motion, poses, viewpoints, events, contacts, and interruption bounds |
| `validate_shot(shot, characters, clips, props, fixture=False)` | Placements, bindings, independent overrides, synchronized event metadata, camera, and audio cue intervals |
| `validate_scene(scene, characters, clips, props, fixture=False)` | Shot validation and explicit continuity declarations |
| `evaluate_track(track, frame, default=None)` | Exact step value or linear interpolation at an integer frame |
| `evaluate_clip(clip, frame)` | Separate root, body, face, gaze, and mouth state; active full frame, contact intervals, and exact markers |
| `evaluate_instance_performance(bundle, shot, instance, frame)` | Cumulative clip displacement, shot overrides, component modifiers, uniform scale, facing, and visibility |
| `planned_requirements(bundle, shot_id)` | Stable independent requirement records with character version, dimension, value, interval, and source |
| `prop_owner(prop, frame)` | Owner and copied attachment metadata after all ownership changes through that frame |
| `interruption_plan(clip, frame, target_pose, blend_frames=0)` | Explicit admission or actionable rejection of a cancellation request |
| `dialogue_timing(bundle, shot_id)` | Editable audio/cue declarations alongside independent shot mouth overrides |

Evaluation functions live in [`production_performance.py`](../scripts/production_performance.py). They return copied state without modifying source tracks. The compositor uses `evaluate_instance_performance` directly, so geometry diagnostics and rendered frame placement use the same performance state.

## Coordinate system and layered construction

Coordinates are pixels, with X increasing right and Y increasing down. Positive rotation is clockwise in that coordinate system. Component pivots and anchors are measured in the component image's local viewport. Offsets are additive translations; rotations are degrees. Component transforms do not contain independently animated scale.

A character declares its canonical full-frame `dimensions`, one positive `relative_scale`, visual identity, allowed views/facings, replaceable components, costumes, independent capabilities, optional restrictions, and provenance. Identity records proportions, palette, materials, markings, asymmetries, and `forbid_mirror`. These declarations make constraints inspectable; numerical equality cannot establish that a drawing preserves the intended personality or silhouette.

Each component has a stable `id`, `role`, parent and parent anchor, local `pivot`, rest `offset`, named local `anchors`, local `z`, visible flag, default drawing, replaceable drawings, and optional mask. A character must have exactly one root. The root has `parent: null` and `parent_anchor: null`. Every child names an existing parent's anchor; cycles and missing ancestors fail with a construction error.

The hierarchy evaluates these operations in order:

1. Translate the actor to its evaluated world position and apply its uniform cast scale.
2. For a root component, add its rest offset and animated offset.
3. For a child, start from its parent's component transform, translate to the named parent anchor, and add rest and animated offsets.
4. Rotate about the component's pivot by translating by the negative pivot after the rotation.
5. Apply the shot camera transform for raster placement.

For example, a hand's local `grip` anchor remains attached to its parent arm or torso as those parts rotate. A prop attached to that grip obtains its position from the evaluated world anchor. The renderer exposes each component's matrix, visibility, and world anchors for inspection.

All replacement drawings of a component use exactly the same declared image viewport. Its pivot and anchors must lie inside that viewport. A mask has the same size. This lets an animator switch mouth shapes, expressions, or hand drawings without introducing a new crop origin. The loader checks actual encoded image dimensions against the manifest and requires alpha-capable component and prop sources. It does not attempt to recover premultiplied sources or guess hidden alignment.

The effective actor scale is:

`character.relative_scale × shot.cast_scale`

That product applies to the character's local construction uniformly. The actor's base world position, clip root displacement, and shot root path are world-pixel translations; they are not multiplied by character scale. Camera zoom transforms the completed shot composition. Animating a head offset or root path therefore does not silently resize the character.

Draw order is ascending instance `z` plus component `z`, with declaration order resolving ties. Background and prop layers participate in the same ordering. Visibility is inherited through component parents. Named components can represent torso, head, limbs, eyes, brows, mouth, hands, hair, clothing, accessories, or other authored parts; the software does not require every role for every design.

## Viewpoints, facing, materials, and costumes

Supported viewpoint names are `front`, `side-left`, `side-right`, `back`, `three-quarter-left`, `three-quarter-right`, `three-quarter-back-left`, and `three-quarter-back-right`. Supported facing names are `front`, `left`, `right`, and `back`. A drawing carries both an explicit viewpoint and a costume ID. A character declares which views exist and which facings identity permits.

Drawing selection tries a compatible costume mapping, then the compatible default drawing, then a deterministically ordered compatible drawing. A missing view/costume combination fails. The renderer has no implicit mirroring or view synthesis. A facing change requires compatible authored clips and views; root facing keys cannot bypass identity or switch away from the instance's selected facing.

Costumes name differences and optional per-component drawing mappings. Creating a new component or costume import produces a new character version through the workflow import command; previous shots can continue selecting the previous version. Shared unchanged references remain shared. Components retain acquisition/import provenance, exact source hashes, and explicit crop metadata where applicable.

View reviews identify status, reviewer kind, reviewer, exact evidence, and notes. An approved declaration requires evidence and an identified reviewer. The production workflow additionally binds the relevant construction, capability declarations, current source files, and scoped reviews. A synthetic viewpoint receipt cannot approve production artwork.

## Independent coverage dimensions

Coverage dimensions are `action`, `pose`, `viewpoint`, `facing`, `expression`, `intensity`, `gaze`, `mouth`, `hand`, `costume`, `prop_state`, and `contact`. A capability is a list within one dimension, rather than an asset for every combination of values.

An instance supplies explicit requirements; clips add their requirements and start/end poses over each placement interval. Viewpoint, facing, and costume are explicit requirements for the shot interval. Audio mouth cues add exact mouth requirements during their authored cue intervals. Each output requirement has a stable ID and identifies its shot, instance, exact character version, dimension, value, interval, and whether its source is `explicit` or `clip`.

Restrictions declare `when` conditions across dimensions and a reason. The compatibility checker finds actual overlap between requirement intervals. A back view used before a mouth cue does not create a simultaneous back-view/open-mouth incompatibility. Coverage planning reports reusable, missing, incompatible, and unreviewed work separately and deduplicates requests shared by scenes. It does not generate a Cartesian list of action × view × expression × mouth assets.

Capability declarations are planning claims until the appropriate current reviews and references support them. See [`production-operations.md`](production-operations.md) for coverage, acquisition binding, budgets, import, review, and selective invalidation.

## Integer-frame clips and tracks

A clip declares its character version, viewpoint, facing, start/end poses, duration, playback mode, completion behavior, displacement, independent tracks, entry/exit points, interpolation limits, interruption policy, contact intervals, event markers, requirements, and optional full-frame overrides.

Frame numbers are integers; booleans and fractional frames are rejected. A rendered duration of N frames displays indices `0` through `N - 1`. Placements, audio cues, contacts, and full-frame overrides use half-open intervals `[start_frame, end_frame)`. A track may declare a terminal value at frame N; root displacement specifically uses that terminal endpoint.

Tracks have `interpolation: step | linear` and ordered keys containing `frame` and `value`. Every track declares frame zero. Scalar and two-coordinate tracks can interpolate linearly or use steps. Drawing, facing, and visibility changes use steps. Keys are distinct, ordered, and bounded by the relevant duration. Numeric step changes are checked as a one-frame jump, even if the keys are widely separated.

The four independent channels are `body`, `face`, `gaze`, and `mouth`. Each channel maps component IDs to any authored `offset`, `rotation`, `drawing`, or `visible` tracks. Two channels cannot write the same component property in the same clip or shot. Different properties of the same component can be independent: gaze may move an eye component while a face track blinks it. A shot-level property override replaces that property's clip result while preserving other properties and channels.

For example, the following is a **track fragment**, not a complete clip:

```json
{
  "body": {
    "head": {
      "rotation": {
        "interpolation": "linear",
        "keys": [{"frame": 0, "value": 0}, {"frame": 12, "value": -6}]
      }
    }
  },
  "mouth": {
    "mouth": {
      "drawing": {
        "interpolation": "step",
        "keys": [{"frame": 0, "value": "default"}, {"frame": 4, "value": "open"}]
      }
    }
  }
}
```

Clip root tracks live in `clip.root`, separately from component channels. Shot root tracks live in `instance.tracks.root`. Every clip root begins at `[0, 0]`. Its declared displacement equals the root value evaluated at frame N. This requirement prevents initial offsets being accumulated repeatedly as clips are placed.

| Playback mode | Evaluation behavior |
| --- | --- |
| `loop` | Local frame wraps modulo N. Each completed cycle adds declared root displacement. Start/end poses match and completion is `loop`. |
| `once` | Displays through local frame N−1. Root motion reaches its frame-N endpoint. Completion can hold the final pose, return component tracks to their start, or make the actor exit. Root displacement remains accumulated. |
| `hold` | Repeats one fixed local pose with zero displacement. Tracks cannot change; events are entry events at frame zero. |

Placements reference exact clip versions and use ordered, nonoverlapping shot intervals. Completed placement displacement accumulates before the next placement, so an idle/walk/stop sequence does not return to its original position. Numeric blending can join poses; explicit component replacement drawings or full-frame artwork can express more complex transitions.

## Transitions and interruption

A transition is `cut` with zero frames or `interpolate` with a positive bounded frame count. A cut joins compatible declared poses. Numeric interpolation blends component offsets and rotations from the preceding placement's evaluated state toward the incoming moving target. Drawing identities are not crossfaded by that numeric interpolation; an incompatible replacement requires explicit transition artwork.

The validation uses the actual evaluated adjacent frames across the blend, including its endpoint. Dividing only the initial pose gap by the number of blend frames is insufficient when the target itself keeps moving. Maximum offset and rotation change per frame must satisfy both outgoing and incoming clip limits. The blend must fit inside the incoming placement and each clip's maximum transition duration.

Natural loop exits use authored local exit points; an arbitrary midcycle cut is not a natural completion. Early one-shot or loop interruption must satisfy the declared `never`, `at-markers`, or `any` policy. Marker admission uses the local cancellation frame, including loop phase. An incompatible cancellation pose needs an explicit bounded transition. Holds can be left at their fixed compatible pose. Entry/exit points and cancellation metadata remain inspectable instead of being guessed from artwork.

Regression tests include forbidden early one-shot and loop exits, permitted authored exits, mismatched pose cuts, changing hold tracks, oversized numeric jumps, incompatible drawing interpolation, and a moving target whose first blended step exceeds the rate limit despite an apparently acceptable initial gap.

## Contacts, props, and synchronization

Clips declare named foot/hand contact intervals and exact event markers. Contact targets are local logical names such as `cup`; an instance binds those names to actual shot prop IDs. `ground` is the reserved unbound ground target. Authored clip contacts are available to geometry inspection. Ground locking is achieved by authored stance compensation, not automatic inverse kinematics; the synthetic regression reel measures world-space sole drift on its declared planted intervals.

A prop instance declares one initial owner and attachment, or neither. Each ownership change records integer frame, previous owner, new owner, new attachment, and an exact shared interaction ID. Its `from` value must match the current ownership chain; unchanged ownership is not an ownership event. A nonnull owner and attachment must identify the same existing character instance and valid component anchor.

A shared interaction declares its frame, prop, target world position, tolerance, and participating character/component/anchor/marker records. An ownership transfer includes both the releasing and receiving participants. Each participant's clip must emit its named marker at that exact frame, with a matching contact anchor and bound target when those are declared.

During frame evaluation, the renderer checks the prop and every participant against the shared target. Ownership changes additionally compare the previous and new prop attachment positions at the change frame and reject a jump greater than two world pixels. This fixed ownership guard applies independently of the interaction's declared tolerance. These checks catch a grasp that occurs before a hand actually reaches an object.

## Audio, facial performance, and full-frame overrides

Audio records contain a hash-bound WAV reference, integer start frame and duration, optional explicit speaker, text, provenance, gain, and mouth cues. Mouth cues carry shot-frame start/end and a compatible mouth drawing name. Cues must lie inside their audio interval, be ordered, and not overlap another cue for that speaker. Different speakers retain independent timelines. Unidentified sound effects can have `speaker: null` and no mouth cues.

Body acting, head rotation, blinking, brows, gaze, expression intensity requirements, and mouth drawings remain separate editable tracks. The audio cue metadata does not claim automatic phoneme recognition, inferred gaze, generated acting, or verified lip sync. A production author supplies or repairs those tracks against the actual line. The synthetic demo uses labeled square-wave cues, so its audio checks establish sample placement rather than spoken performance quality.

Offline mixing accepts signed 16-bit PCM WAV at a common supported rate and one or two channels. It computes each boundary as the nearest integer sample at `frame × sample_rate × fps_denominator / fps_numerator`, mixes in bounded blocks, records exact source sample intervals, counts clipping, and pads the master to the exact frame count. The browser preview follows the same frame/audio map; the offline PNG/WAV master remains the timing authority. See [`production-rendering.md`](production-rendering.md).

Complex poses may replace the actor's component raster layers over an explicit `full_frames` interval. Each override has a hash-bound image, local pivot, viewpoint, and the character's exact canonical full-frame dimensions. The actor retains world position, uniform scale, facing, and underlying rig diagnostics. Other actors, props, scenery, and camera remain independent. Since underlying rig anchors remain the contact geometry, an override used during a contact must still be authored to align with that geometry and visually reviewed.

## Resource bounds

Project limits can tighten these ceilings but cannot enlarge them:

| Resource | Bound |
| --- | --- |
| JSON manifest | 16 MiB; maximum nesting 64 levels; duplicate keys/nonfinite numbers rejected |
| Encoded referenced source | 64 MiB per file; 1 GiB total inventory |
| Referenced assets | 2,048 |
| Total rendered project frames | 18,000 |
| Scenes / total shots | 128 / 256 |
| Character versions / components per character | 128 / 128 |
| Actors / props / scenery layers per shot | 64 / 128 / 64, subject to renderer's 256-layer bound |
| Source raster / rendered raster | 2,000,000 pixels each |
| Output frame rate | Rational 1–60 fps |
| Estimated raster working set | At most the project's configured bound, no more than 768 MiB |
| Interpolation duration | 120 frames maximum, with lower per-clip limits |
| Project generation calls | Explicit nonnegative bound, at most 256; fixture default is zero |

The loader estimates raster work before rendering and checks image headers before decoding. Rendering, audio, metadata, caching, export, and archive transport have additional local bounds documented in their modules. A source image's byte count and pixel dimensions are both checked; a small compressed file is not assumed to be cheap to decode.

## Reproduce the checked examples

```bash
python scripts/production_contracts.py --write-schemas
python scripts/production_regression_demo.py --output-dir examples/production-fixture --build-only
python scripts/production_regression_demo.py --output-dir examples/production-fixture --movie
python -m unittest discover -s tests -p 'test_production_contracts.py' -v
python -m unittest discover -s tests -p 'test_production_performance.py' -v
```

The minimal public factory remains `production_fixture.build_fixture_project(root)`. The expanded regression generator adds five performance shots while preserving its two short original scenes. The actual production-art pilot uses separately acquired artwork and original dialogue, with its own source provenance and review records. Current evidence and limitations are tracked in [`production-validation.md`](production-validation.md) and [`production-traceability.md`](production-traceability.md); synthetic evidence cannot satisfy the pilot's production artwork gate.
