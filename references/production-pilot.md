# Produce, review and reuse the Milo/Luma cast

The production pilot contains original imagegen artwork for Milo, an amber bear with an asymmetric coral scarf, and Luma, a taller teal rabbit in an ochre waistcoat. A shared v3.0.0 cast drives a 36-second seed exchange and a distinct 22-second garden scene. The recipe authors layered performances, retains original speech, and makes no image-provider calls when reconstructing the retained sources.

## Contents

- [Reconstruct the retained production project](#reconstruct-the-retained-production-project)
- [Render and inspect both scenes](#render-and-inspect-both-scenes)
- [Shot and dialogue plan](#shot-and-dialogue-plan)
- [Author another project or acquire new artwork](#author-another-project-or-acquire-new-artwork)
- [Edit construction, clips, dialogue and interactions](#edit-construction-clips-dialogue-and-interactions)
- [Review, reuse and diagnose changed work](#review-reuse-and-diagnose-changed-work)
- [Export and restore](#export-and-restore)
- [Reproduce the synthetic demonstration](#reproduce-the-synthetic-demonstration)
- [Compatibility, migration and limits](#compatibility-migration-and-limits)

## Reconstruct the retained production project

Run commands from the repository root. Install Python dependencies with `python -m pip install -r requirements-test.txt`. The recorded production renders use Python 3.12.14 and Pillow 13.0.0; use the recorded environment to compare exact raster and renderer hashes. PNG/PCM reconstruction needs no TTS or image provider when the retained source bundles are restored. FFmpeg and ffprobe are optional dependencies for MP4 review copies. A missing dependency must be reported, not replaced with invented evidence.

The repository retains original artwork and acquisition records in `examples/production-pilot/source-bundle`, and original speech, text and local TTS records in `audio-source-bundle`. Content-addressed parts allow exact transfer without altering source bytes; their JSON indexes list every restored path, size and hash. These are source transports, not production-art approval receipts.

Choose new directories. These commands fail instead of replacing an existing restore destination:

```bash
python scripts/production_sources.py verify --bundle examples/production-pilot/source-bundle
python scripts/production_sources.py verify --bundle examples/production-pilot/audio-source-bundle
python scripts/production_sources.py restore --bundle examples/production-pilot/source-bundle --destination /tmp/hatch-pilot
python scripts/production_sources.py restore --bundle examples/production-pilot/audio-source-bundle --destination /tmp/hatch-pilot-audio
python -c "import shutil; shutil.copytree('/tmp/hatch-pilot-audio/audio', '/tmp/hatch-pilot/audio')"
python scripts/production_demo.py --project /tmp/hatch-pilot
python scripts/production.py validate --project /tmp/hatch-pilot
python scripts/production.py coverage --project /tmp/hatch-pilot --output /tmp/hatch-pilot-coverage.json
```

`production_demo.py` verifies the original PNG hashes against actual generated jobs and handoff receipts. It writes measured crop/registration provenance, both character constructions, 20 clips, editable dialogue cues, two scenes and three construction inspection images. It never fabricates a provider call, source receipt, review or approval. `--without-audio` is a construction diagnostic only; it is not the complete demonstration.

The retained speech build checks each original WAV, text and voice against its original local TTS receipt. It pads PCM to integer frame boundaries and does not resynthesize an existing recording. If original speech is deliberately absent, the recipe can use local FFmpeg Flite; the resulting new source and engine version are recorded, and its hashes and reviews must be assessed as new work. Retain the original source bundle when reproducing this delivery.

The four current model outputs, their native hatch claim/attempt histories and unavailable provider metadata are retained unchanged. Earlier workspace losses are disclosed in the acquisition audit; lost prior claims, artwork and approvals are not reconstructed as current evidence. The pilot's current acquisition cap is four calls. The separate audit counts eight earlier observed calls whose source files were lost. No new model call is needed for either reconstruction or the second scene.

## Render and inspect both scenes

```bash
python scripts/production.py render --project /tmp/hatch-pilot --scene seed-exchange --destination /tmp/hatch-pilot/renders/seed-exchange --video --output /tmp/seed-render.json
python scripts/production.py render --project /tmp/hatch-pilot --scene garden-promise --destination /tmp/hatch-pilot/renders/garden-promise --video --output /tmp/garden-render.json
python scripts/production.py storyboard --render-dir /tmp/hatch-pilot/renders/seed-exchange --destination /tmp/seed-storyboard.png --frames 0,24,72,96,143,154,204,227,228,229,311,326,400,431
python scripts/production.py storyboard --render-dir /tmp/hatch-pilot/renders/garden-promise --destination /tmp/garden-storyboard.png --frames 0,12,36,65,143,144,168,183,236,263
python -m http.server 8765 --bind 127.0.0.1 --directory /tmp/hatch-pilot
```

Open `http://localhost:8765/renders/seed-exchange/preview.html` or `http://localhost:8765/renders/garden-promise/preview.html`. Scrub by integer frame, use arrow keys or the previous/next buttons, inspect the frame interval and source manifest, toggle tracks, and pin a frame for comparison. Audio playback requires explicit opt-in. Serve the directory locally because browser file-URL fetch restrictions vary.

The offline masters are `frames/000000.png` onward and `audio.wav`, with their exact inventory in `render-manifest.json`. Scene frames retain their shot/frame mapping. Optional `review.mp4` is a flattened H.264/AAC review copy; it is not the RGBA master. The compositor checks exact PNG count and PCM duration, then ffprobe checks the actual muxed streams within the declared AAC packet tolerance. Browser wall-clock playback does not establish final timing.

Inspect construction at actual size, a complete locomotion cycle, stopping, the authored departure entry, mouth changes, listener blinks/brows/head movement, the camera cut, handoff frames 83/84/85 of the exchange shot, and final exits. Check visual hand/object overlap in addition to exact anchor agreement. Record assistant or human inspection as that actual reviewer; audio sample checks do not constitute auditory review.

## Shot and dialogue plan

The project uses 640×360 sRGB RGBA masters at exactly 12/1 frames per second. Character coordinates are pixels; X points right, Y down. Each shot applies cast scale 0.56, multiplied by Milo's declared relative scale 1.1 or Luma's 1.0. One measured construction calibration is used across all frames. Painted upper-left light and a warm color treatment are declared; the renderer does not relight the artwork.

| Scene / shot | Frames | Performance |
| --- | ---: | --- |
| Seed exchange / arrival | 144 | Both enter, reuse three walk cycles, stop, and begin dialogue/listening |
| Seed exchange / exchange | 168 | Closer camera cut; Luma speaks, Milo reacts, both reach and share the packet, ownership transfers at shot frame 84, arms return |
| Seed exchange / departure | 120 | Luma invites Milo along; explicit planted entry steps lead into reusable walking and complete exits |
| Garden promise / garden | 144 | New location and foreground planter, same cast/costume/prop owner, reaction and Milo's dialogue |
| Garden promise / tomorrow | 120 | Second camera framing, Luma's response, listening and a shared final reaction |

The departure entry is an authored `walk-start` clip, not a generic pose blend: the right foot remains planted while the left swings into the walk stance. Separate `walk-right`, `walk-left`, `stop`, `idle`, `reaction`, `reach`, `hold`, `release` and `exchange` clips remain versioned and reusable. The synthetic performance reel separately demonstrates stand/sit/stand and individually drawn full-frame overrides.

| Line | Speaker / local voice | Shot start frame | Duration in frames | Original text |
| --- | --- | ---: | ---: | --- |
| 01 | Milo / rms | arrival 86 | 47 | Luma, I found a seed. Can you help me plant it? |
| 02 | Luma / slt | exchange 10 | 46 | Of course. A little care can grow into something wonderful. |
| 03 | Luma / slt | departure 1 | 31 | Come on. Let's give it a sunny home. |
| 04 | Milo / rms | garden 27 | 50 | This looks like the perfect spot. Our little seed has a home. |
| 05 | Luma / slt | tomorrow 12 | 41 | And tomorrow, we will come back and see how it grows. |

The scripts are original demonstration dialogue. Actual Flite engine/voice, source WAV/text hashes and original receipts are retained under `audio/original`. The installed engine's copyright information is retained there as supplied attribution. Each padded recording and all supporting provenance references are bound by the scene audio record. Mouth cues use an editable amplitude-gated rhythmic approximation; they are not automatic phoneme recognition or proof of persuasive acting.

## Author another project or acquire new artwork

Use the production JSON contracts to author a new project and cast from explicitly imported or generated original sources. The production recipe is a concrete complete authoring example. Its Milo/Luma image coordinates are specific to its retained artwork and must not be applied blindly to another character. `create --fixture` is a labeled geometric development starter; changing its fixture flag does not turn it into production art. `create --from-project` is a verified portable copy that preserves the existing project identity.

To prepare a fresh bounded acquisition of this character design, use a new run directory:

```bash
python scripts/prepare_production_art.py --destination /tmp/new-acquisition/milo --character milo
python scripts/hatch.py claim --run-dir /tmp/new-acquisition/milo --job base
```

Read the installed imagegen skill. Invoke it with the exact claimed prompt and every required attachment, preserve genuine output metadata or its honest unavailability, then ingest with the same token. Inspect and review the canonical base before claiming `parts`. Do not run these generation steps when merely reconstructing retained sources. For arbitrary new designs use the legacy `prepare` profile, identity and source commands in [sources and identity](sources-and-identity.md); keep project requirement bindings and bounded generation limits as described in [production operations](production-operations.md#bound-acquisition-claims-and-recovery).

After extraction, use `import-component` or `adopt-generated-component` with a new character version to bring an explicitly described drawing into an existing construction. Their complete descriptor, attachment and provenance contracts are in [production operations](production-operations.md#import-with-immutable-construction-and-provenance). A new asset version does not silently switch older shots to it.

## Edit construction, clips, dialogue and interactions

Edit ordinary JSON in a text editor; edit paint layers in the supported editor handoff. Recalculate the relevant containing file reference hashes deliberately after an edit. The helper `file_ref(root, path)` in the recipe shows the exact hash-bound reference form. `validate` rejects forgotten or conflicting hashes. Run `snapshot` before editing and `impact` afterward to see which selected shots need work.

- **Construction:** change the appropriate pivot, parent anchor, offset, drawing, mask or costume in a new version. Keep all replacement drawings for a component registered to its common viewport; author separate viewpoint components where required.
- **Clips:** edit integer keys in independent channels, root displacement, contact ranges, events and entry/exit poses. An unsupported transition needs a named missing pose/clip or explicit bounded interpolation. The validator checks interruption points and actual adjacent interpolation rates.
- **Dialogue:** edit an audio record's `start_frame`, `duration_frames`, text and `mouth_cues`, then edit the speaker's `tracks.mouth.mouth.drawing` keys. Cues remain inspectable even when explicit mouth drawing keys override them. Keep cues inside the declared recording interval and shot boundary.
- **Listening and gaze:** edit `tracks.face` and `tracks.gaze` without replacing body motion. The pilot uses partner and packet gaze targets, brows, head rotation and blinking. Literal gaze offsets remain authored artistic choices; target names alone do not solve eye tracking.
- **Interaction:** edit the two arm performances, their shared contact target and clip events together. The prop ownership record must agree on `from`, `to`, frame, target attachment and synchronized event. The packet and both hand anchors must coincide at transfer; reauthor reach or positioning if they do not.

The production model is a bounded reference compositor. It does not contain an automatic rigging service, physics engine, lip-sync recognizer or general animation timeline editor.

## Review, reuse and diagnose changed work

```bash
python scripts/production.py snapshot --project /tmp/hatch-pilot --output /tmp/pilot-before.json
python scripts/production.py review-template --project /tmp/hatch-pilot --character milo --version 3.0.0 --output /tmp/milo-review.json
python scripts/production.py review-template --project /tmp/hatch-pilot --clip milo-walk-right --version 3.0.0 --output /tmp/walk-review.json
python scripts/production.py review-template --project /tmp/hatch-pilot --scene seed-exchange --shot exchange --render-manifest renders/seed-exchange/shots/exchange/render-manifest.json --output /tmp/exchange-review.json
# Inspect, identify the actual reviewer, and fill exact evidence/verdicts before submitting:
python scripts/production.py review --project /tmp/hatch-pilot --receipt /tmp/exchange-review.json
python scripts/production.py reviews --project /tmp/hatch-pilot --scene seed-exchange --shot exchange
python scripts/production.py coverage --project /tmp/hatch-pilot --scene garden-promise --output /tmp/garden-coverage.json
python scripts/production.py impact --project /tmp/hatch-pilot --receipt /tmp/pilot-before.json --output /tmp/pilot-impact.json
```

Templates are intentionally unreviewed. The submission command fails until the reviewer supplies actual evidence and explicit decisions. Final shot acceptance binds the persisted completed shot render and inspected frame/layer artifacts. Historical delivery reviews are separate from a fresh source reconstruction; the recipe never recreates approvals. Use archived projects to preserve a complete review history, and recheck freshness in the restored environment.

To add another scene, write another scene document selecting the same `milo@3.0.0`, `luma@3.0.0` and existing clip versions, then add its hash-bound file reference to `project.scenes`. Declare cross-scene continuity deliberately. `garden-promise` demonstrates this: it reuses the cast and idle/reaction clips, changes scenery and dialogue, and retains Luma as packet owner. There is no copied second cast identity and no second-scene image generation.

Coverage readiness requires current construction and used-clip reviews. It remains separate from the eight final shot review dimensions. The delivery acceptance report records actual assistant visual inspection, automated frame/audio checks and external integration status separately. The review chain is local hash-linked evidence, not an external identity-signature service.

## Export and restore

```bash
python scripts/production.py export-editor --render-dir /tmp/hatch-pilot/renders/seed-exchange --destination /tmp/hatch-editor --frames 96,228,326 --exercise-krita
python scripts/production.py archive --project /tmp/hatch-pilot --destination /tmp/hatch-pilot.zip
python scripts/production.py restore --source /tmp/hatch-pilot.zip --destination /tmp/hatch-pilot-restored
python scripts/production.py validate --project /tmp/hatch-pilot-restored
python scripts/production.py reviews --project /tmp/hatch-pilot-restored --scene seed-exchange --shot exchange
```

The handoff exports PNG frames, WAV, timing/provenance and selected layered OpenRaster snapshots. Its own roundtrip validation reopens the ORA files and checks exact pixels and structure. `--exercise-krita` only exercises an already available executable and records an unavailable result otherwise. It neither installs Krita nor changes live settings. See [rendering](production-rendering.md#portable-editor-handoff) for actual editing instructions and the distinction between drawing import/export and timeline integration.

Archive and restoration preserve sources, versions, acquisition history, reviews and actual rendered outputs. A fresh destination is mandatory. Restoration verifies bytes, paths and cached render freshness before reporting what can be reused. Renderer/environment changes require fresh render evidence. Split transport and its exact limits are documented in [operations](production-operations.md).

## Reproduce the synthetic demonstration

```bash
python scripts/production_regression_demo.py --output-dir /tmp/hatch-production-fixture --movie
python -m unittest discover -s tests -p 'test_production_*.py' -v
```

This produces three explicitly synthetic scenes, 300 frames total: a two-scene shared-cast example and a 276-frame performance reel with locomotion, stand/sit/stand, reach/grasp/hold/release, independent facial dialogue and individually drawn full-frame pose overrides. Acceptance records automated geometry, audio timing, render validation and an all-frame reuse pass. Synthetic receipts remain synthetic even when every regression passes.

## Compatibility, migration and limits

The default Codex profile and existing examples are unchanged. Legacy state order, frame counts, millisecond durations, 192×208 cells, eight columns, alpha rules and package compatibility still belong to `hatch.py`. No production project is implicitly converted into or installed as a Codex pet.

Production manifests use schema 1; workflow review history uses schema 2. `python scripts/production.py migrate --project PROJECT` explicitly backs up schema-1 workflow bytes and migrates their history, without upgrading old approvals into current decisions. Unknown schemas fail. See [contracts](production-contracts.md) for supported fields and bounds.

The current production artwork supports a frontal cutout rig and four-view design references. Milo's rear design remains rejected: the source places the scarf knot on viewer-right in both front and back views, so its physical asymmetry needs reconciliation before a back-facing performance. The original is retained unchanged, and the frontal scenes do not use that drawing. Side/back/three-quarter animation rigs are not authored or approved by the design turnaround. Hand art supports a readable open-paw packet exchange, not articulated finger wrapping. Mouth art is a limited registered set; timing and acting remain editable. Transitions needing different silhouettes should use supplied full-frame drawings. Numerical contact coincidence cannot certify visual anatomy, gaze intent or persuasive speech.

The exact verified outcomes and remaining review/integration limits are in [production validation](production-validation.md); P01–P15 mapping is in [production traceability](production-traceability.md). The [demonstration index](../examples/production-pilot/README.md) links inspectable source, render and acceptance locations.
