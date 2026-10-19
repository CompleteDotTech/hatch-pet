# Production rendering, local review, and editor handoff

The reference renderer turns a validated production project into indexed RGBA PNG frames and a sample-counted PCM WAV master. Those files, their exact dependency manifest, and the authored integer-frame edit are the timing authority. The browser preview and optional movie support review; the editor handoff supplies editable raster drawings and an animation sequence. None of these operations submits a visual approval. Implementation: [`production_render.py`](../scripts/production_render.py), [`production_adapter.py`](../scripts/production_adapter.py), and [`production-preview.js`](../assets/production-preview.js).

## Contents

- [Render a shot or scene](#render-a-shot-or-scene)
- [Coordinate, layer, and color contract](#coordinate-layer-and-color-contract)
- [Exact timing, audio, and optional movies](#exact-timing-audio-and-optional-movies)
- [Resume, dependency reuse, and resource bounds](#resume-dependency-reuse-and-resource-bounds)
- [Review actual output locally](#review-actual-output-locally)
- [Portable editor handoff](#portable-editor-handoff)
- [Reproduce focused checks](#reproduce-focused-checks)

## Render a shot or scene

Run commands from the repository root with the Python environment described in [`requirements.txt`](../requirements.txt). Pillow is required. FFmpeg and ffprobe are optional local executables for movie creation; rendering PNG/WAV masters does not require them or a network service.

```bash
python scripts/production.py validate --project examples/production-pilot/project.json

python scripts/production.py render \
  --project examples/production-pilot/project.json \
  --scene seed-exchange \
  --destination work/seed-exchange

python scripts/production.py render \
  --project examples/production-pilot/project.json \
  --scene garden-promise \
  --destination work/garden-promise --video

python scripts/production.py render \
  --project examples/production-pilot/project.json \
  --shot exchange \
  --destination work/exchange --max-frames 24
```

The last command limits newly rendered shot frames per invocation. Repeat it to continue; omit `--max-frames` to finish. A cache hit does not consume this work allowance. Partial output is explicitly marked, and a partial shot cannot be accepted as a complete audiovisual master. Scene rendering proceeds shot by shot; interruption leaves owned shot checkpoints that the same command can resume.

The default retains separate screen-space raster layers for visibility review and OpenRaster export. `--no-layers` reduces output storage and supplies flattened frames only. Choose the default when a layered editor handoff is needed. It is safe to rerun the same destination with layers enabled; entries missing required layers are regenerated.

| Output | Meaning |
| --- | --- |
| `render-manifest.json` | Project/scene/shot identity, renderer identity, exact dependencies, frame indices, hashes, layer records, timing, events, interactions, dialogue, audio, and completion status |
| `frames/000000.png`, etc. | One actual RGBA PNG for each rendered integer frame |
| `layers/<hash>.png` | Content-addressed transparent layers with transforms, masks, opacity, and camera already applied |
| `audio.wav` | Exact-duration signed 16-bit PCM master; silent intervals are represented explicitly |
| `preview.html` | Local review page containing the manifest and script; it references the retained PNG/WAV files |
| `shots/<shot-id>/` | A scene's independently resumable shot render caches |
| `review.mp4` and its receipt | Optional encoded movie and actual FFmpeg/ffprobe verification evidence |

For a compact or archived example, first restore its complete project using the commands in [`production-operations.md`](production-operations.md). Restored paths and hashes are checked before the same render commands are used.

## Coordinate, layer, and color contract

All authored coordinates are pixels with X increasing right and Y increasing down. A character's fixed world scale is `shot.cast_scale * character.relative_scale`. Component drawing variants share their declared canvas and pivot; the renderer does not independently fit or resize performance frames. This preserves proportions during drawing changes, acting, and locomotion. The public construction and timing schema is documented in [`production-contracts.md`](production-contracts.md).

An actor's world position combines its shot position, accumulated completed clip displacement, the current clip's root motion, and an additive shot root offset. A root component attaches its pivot at its authored offset from that position. A child attaches its own pivot to its parent's named source-space anchor plus its authored and animated offsets. Parent rotation and scale therefore affect the child through the hierarchy. Positive rotation is clockwise in this Y-down coordinate system. Visibility is inherited: hiding a parent also hides its descendants.

The four independent performance channels are `body`, `face`, `gaze`, and `mouth`. Shot overrides replace only the properties they author; an independently keyed mouth can change while the body loop and head rotation continue. Selected costume drawings and explicit drawing overrides are resolved before rasterization. A full-frame replacement suppresses that actor's component raster layers only over its half-open interval. It retains actor position and scale and leaves the underlying rig's world anchors available for contact inspection. Its picture still needs to be authored and reviewed against those anchors.

Each source is hash-checked before use. An image-local mask multiplies alpha before transformation. Bilinear and bicubic affine filtering operates on premultiplied color to avoid transparent-edge color fringes, then returns straight RGBA. Nearest-neighbor preserves exact nearest sampling. Compositing uses 8-bit encoded-sRGB source-over; it is not a linear-light or ICC color-management pipeline. Lighting direction and unchanged color-treatment declarations are planning metadata; the renderer does not synthesize new lighting or paint.

Layers draw in ascending Z, using declaration order to break ties. Character layers use instance Z plus component Z, so authored components may interleave with props or other actors. The camera maps a world point to `zoom * (point - camera_position)`. Scenery's parallax value multiplies camera translation, while its zoom remains the camera zoom. Camera pan and zoom are evaluated at exact frames and checked against declared bounds.

An attached prop follows its owner's evaluated world anchor. Its own source pivot is placed there, with its explicit prop rotation track. The prop keeps its own world scale and orientation; a hand's rotation does not automatically rotate the prop. This is intentional and requires authored rotation when a turning prop is desired. Ownership changes check both attachments at the change frame and reject a jump over two world pixels. A shared interaction additionally checks the prop and all participants against its explicit target and tolerance.

Contact metadata does not solve inverse kinematics or automatically pin feet. Author stance compensation, then measure actual world-space sole drift through the composed clip root, shot root, hierarchy, and scale. The synthetic regression reel and pilot tests use that geometry. A visually convincing contact or grasp still needs inspection of the actual artwork.

```python
from production_contracts import load_project
from production_render import evaluate_frame, render_frame

bundle = load_project("examples/production-pilot/project.json")
state = evaluate_frame(bundle, "exchange", 84)
print(state["instances"]["milo"]["components"]["hand-right"]["anchors"]["grip"])
print(state["props"]["seed-packet"]["owner"])
image, state = render_frame(bundle, "exchange", 84)
image.save("work/shared-contact.png")
image.close()
```

Use `PYTHONPATH=scripts` for Python API examples. Callers normally pass a bundle returned by `load_project`, or a project path; mutating a loaded dictionary is a test/authoring operation and does not replace schema validation when saving it.

## Exact timing, audio, and optional movies

A duration of N frames displays indices 0 through N−1. Frame n occupies `[n / fps, (n + 1) / fps)`. Scene assembly preserves shot order and exact cut boundaries. Frame rates are stored as integer numerator/denominator pairs, so a rate such as `30000/1001` does not accumulate decimal timing error.

Audio accepts hash-bound uncompressed signed 16-bit PCM WAV, mono or stereo, at one common rate from 8–192 kHz. Convert an incompatible source explicitly before import; the mixer does not secretly resample it. Each frame boundary maps to the nearest integer sample at `frame * sample_rate * fps_denominator / fps_numerator`, with ties rounded upward using integer arithmetic. At 12 fps and 48 kHz, one frame is exactly 4,000 sample frames.

Mixing uses blocks of at most 4,096 sample frames. It honors source intervals, track placement, gains from 0 to 4, and silence padding; it records source hashes, source/start/end sample indices, rational gains, and clipped channel samples. Mono sources are copied to both output channels; stereo-to-mono explicitly averages channels. Gains use deterministic nearest-integer rounding. The WAV header, actual terminal PCM payload, rate, channel count, hash, and exact duration are checked offline. Mouth cues are authored timing data, not an automatic phoneme analysis or a lip-sync verdict.

The renderer rejects a planned WAV larger than the reader's 512 MiB bound before creating output or changing an existing/partial WAV. This is a tighter limit than the independent maximum sample-count bound for some rate/channel/duration combinations.

```bash
PYTHONPATH=scripts python -c \
  "from production_render import validate_render; print(validate_render('work/seed-exchange'))"

PYTHONPATH=scripts python -c \
  "from production_render import mux_video; print(mux_video('work/seed-exchange'))"
```

Movie creation runs the available FFmpeg with one encoder thread, explicit H.264/AAC settings, and the manifest's rational frame rate. ffprobe then verifies the actual decoded frame count, frame rate, and audio duration. AAC duration is allowed one 1,024-sample packet of codec tolerance; exact PCM timing remains in the WAV. The receipt records the source manifest, resulting file hash, tools, and observed measurements. Identical PNG/WAV inputs and renderer identity are deterministic; encoded movie bytes are not promised identical across different FFmpeg builds.

## Resume, dependency reuse, and resource bounds

Every completed frame updates an atomic checkpoint. A process lock protects a shot or scene destination. Both new and resumed scene rendering check retained ownership before any writes, including a first-shot interruption that has only a nested shot checkpoint. A different project, scene, render kind, corrupt checkpoint, or unowned scene output produces an error; disabling cache reuse does not bypass ownership. Preserve the earlier output and use a new destination for a different render. The OS releases a process lock after a terminated process; there is no force-unlock workflow that ignores a live owner.

Reuse verifies every retained frame and required layer by hash. Visual signatures include renderer identity, source raster hashes, transform/mask/opacity/drawing state, camera effects, dimensions, filtering, and background. A changed drawing invalidates frames that use it. An FPS-only change can reuse identical PNG pixels while rewriting frame timing, audio, and the source manifest. Exact source dependencies still change when a semantic or timing input changes, so old reviews do not remain valid merely because some pixels were reused.

Scene PNGs are atomically hardlinked to their own identical shot frame where supported, with an atomic-copy fallback across filesystems or where linking is unavailable. Different frame indices are never hardlinked together. A scene and its corresponding shot file share storage on a supporting filesystem: editing either copy in place changes that same frame in both views and is detected by hashes. Treat completed renders as immutable evidence; import edited artwork as a new source version. Interrupted copy publication preserves the preceding complete destination.

Raster buffers and the decoded-image cache are bounded independently of duration. Metadata necessarily grows with the frame/layer count and is estimated separately. Scene preflight accounts for the assembled scene manifest, the largest current shot manifest, and raster work before writing; it rejects a scene that exceeds `limits.max_work_bytes` even if each shot is individually affordable. These are conservative work estimates, not a measured operating-system RSS guarantee.

| Bound | Effective rule |
| --- | --- |
| Accepted project raster | At most **2,000,000 pixels**, with each dimension at most 4,096; the loader's lower pixel bound applies |
| Accepted project FPS | Rational **1–60 fps**; internal helpers' 120 fps ceiling is defensive and does not enlarge the public contract |
| Internal raster ceiling | `4096 * 2160` pixels is an additional defensive limit for rendering/adapter helpers, not the accepted project maximum |
| Layers / frames | At most 256 composited layers per shot; at most 18,000 rendered frames, also subject to lower project limits |
| Source raster | At most the configured source-pixel budget; 64 MiB encoded file cap; source dimensions and hashes checked before decoding |
| Decoded source cache | LRU, at most 64 MiB and at most half the configured working budget |
| Shot raster output cache | At most 4 GiB, including retained frame/layer PNGs from earlier revisions; preserve/archive it and use a fresh destination when full |
| Audio | At most 32 mixed tracks, 8–192 kHz, signed 16-bit, one or two channels, 512 MiB WAV cap and independent sample-count cap |
| Storyboard | At most 64 selected frames, 1–8 columns, 64–640-pixel cell width, and 16 million output pixels |
| Editor handoff | At most 32 selected layered snapshots and 2 GiB total files; complete numbered animation sequence included |

The public project also bounds JSON size, asset inventory, shots, scenes, and total work; see [`production-contracts.md`](production-contracts.md). Retained old cache files are counted, not silently deleted. Generation, extraction, review, archive and render budgets are separate operations.

## Review actual output locally

Open `work/seed-exchange/preview.html` with its adjacent frames/layers/audio retained. The page is self-contained except for those local files, makes no model calls, and records no approval. A local server is an alternative if the browser's local-file policy restricts playback:

```bash
python -m http.server --bind 127.0.0.1 --directory work/seed-exchange 8000
```

Then open `http://127.0.0.1:8000/preview.html`. The controls scrub to an integer frame, step with buttons or arrow keys, show the exact interval and shot-local index, and expose current source hashes, event markers, shared contacts, and dialogue. Track checkboxes composite actual retained layer PNGs. Pin a frame for side-by-side comparison or an onion overlay. Hidden tracks affect both comparison views. A flattened render cannot provide separated layer visibility.

Playback follows elapsed time and catches up after a stalled browser thread; it does not add one frame per callback. Audio is explicitly opted into. The preview preloads opted-in local WAV data and waits for a seekable range before seeking; an obsolete seek cannot rewind a later scrub. With audio playing, media time drives the preview frame. Playback stops at the final frame or when the page becomes hidden. There is no autoplay, including with reduced motion enabled. Image caching is bounded to 64 images and a nominal 32 MiB of decoded pixels; browser/runtime overhead is additional.

```bash
python scripts/production.py storyboard \
  --render-dir work/seed-exchange --destination work/seed-storyboard.png \
  --frames 0,48,96,144,228,300,360,431 --columns 4
```

A storyboard samples actual output frames and labels their indices. It is useful for identity, composition, and contact inspection, but cannot establish the quality of every intervening motion or replace timed review. Record an approval only through the dependency-bound review workflow after inspecting the relevant actual files.

## Portable editor handoff

```bash
python scripts/production.py export-editor \
  --render-dir work/seed-exchange \
  --destination work/seed-editor \
  --frames 0,144,228,431
```

The export contains the complete flattened numbered PNG sequence, `audio.wav`, an exact retained source render manifest, selected layered `.ora` drawings, `EDITING.md`, and `handoff.json`. Every file is listed and hash-bound. Validation compares handoff identity, dimensions, frame rate/count, numbered frame hashes, source manifest hash, actual PCM length, and snapshot source hashes; updating only an inventory hash cannot conceal a changed retained source or different timing.

Only the designated root `consumer-integration.json` and root `consumer-evidence/` hold auxiliary consumer results outside that core export inventory. Similarly named nested files do not evade the inventory. All encountered paths, including auxiliary evidence, reject symlinks, and consumer output paths are checked before an external application is called.

OpenRaster snapshots preserve raster layers and draw order after transforms, masks and camera have been baked into pixels. Their deterministic ZIP contains the mandatory first uncompressed mimetype, layer-stack XML, PNG layers, merged image, and thumbnail, following the official [file layout](https://www.openraster.org/baseline/file-layout-spec.html). The uppermost layer comes first in the XML, as defined by the official [layer-stack specification](https://www.openraster.org/baseline/layer-stack-spec.html). The supported reader handles source-over layers, offsets, opacity, visibility, and isolated groups; unsupported blending, nonisolated groups, unsafe paths, links, duplicate members, XML entities, and excessive allocations fail explicitly.

In Krita, open a selected `.ora`, edit its paint layers, and save a working `.kra`. For animation, create a document at the manifest's resolution and frame rate, set the end frame to N−1, then use **File → Import Animation Frames** with ascending numerical order, start 0, and step 1. Krita documents these [frame import controls](https://docs.krita.org/en/reference_manual/import_animation.html). Add `audio.wav` through the Timeline Docker's audio menu. Krita retains the audio path, so keep that WAV with the working document or reload it after relocation; see [Audio for Animation](https://docs.krita.org/en/reference_manual/audio_for_animation.html). If an editor cannot represent a particular rational rate, preserve the exact masters and use an editor that can conform it.

The numbered sequence provides editable animation pixels. The ORA files provide selected layered drawing edits. Neither reconstructs the source rig, parameterized component transforms, reusable clips, contacts, or an editable camera timeline inside Krita. Source project JSON and component artwork remain the editable production model. Bring edited drawings back through import as new versions and obtain current review before using them as approved assets.

### Separate three claims

| Evidence | What was exercised |
| --- | --- |
| `exported_assets: true` | Complete files were exported with manifests and hashes |
| `adapter_roundtrip_tested: true` | This adapter reopened the ORA and reconstructed pixels equal to the retained source PNG; sequence and actual audio contract also passed |
| `application_integration: verified` | An available real Krita imported the ORA and exported both PNG and ORA, preserving dimensions, pixels within one channel value, and layer count |

The optional `--exercise-krita` runs the available executable through its documented [export command](https://docs.krita.org/en/reference_manual/linux_command_line.html), with temporary configuration/cache/data directories and offscreen Qt. It installs no application. It records version, commands, diagnostics, exported evidence, and results in `consumer-integration.json`. If the executable is unavailable, the report says `not-performed`; adapter success does not become an integration result. Even successful drawing import/export leaves `timeline_integration: not-performed` until the actual animation timeline import is separately exercised. Visual acceptance remains a separate review in every case.

## Reproduce focused checks

```bash
python -m unittest discover -s tests -p 'test_production_render.py' -v
python -m unittest discover -s tests -p 'test_production_adapter.py' -v
python -m unittest discover -s tests -p 'test_production_preview.py' -v
python -m unittest discover -s tests -p 'test_production_pilot.py' -v
```

The preview suite uses Playwright against a local server and checks actual canvas pixels, frame stepping, stalled-thread catch-up, layer visibility, pinned comparison, audio seeking, and reduced-motion behavior. Configure `PLAYWRIGHT_BROWSERS_PATH` or `HATCH_BROWSER_EXECUTABLE` to an installed supported browser. A missing optional browser can be reported as unavailable; once a binary is found, launch or behavior failures are test failures. Current focused logs are in [`tests/results`](../tests/results). The adapter's optional real Krita exercise is reported separately from its format tests; synthetic fixtures exercise software behavior and do not substitute for production-art acceptance.

Set `HATCH_PRODUCTION_PILOT` to an already materialized pilot root to test it directly. Without that override, the pilot suite restores the checked source bundle and separate original-audio bundle into a temporary project, including the original speech WAVs, text, receipts, and Flite copyright. It then rebuilds components, cues and scenes while forbidding all subprocesses and reporting external executables unavailable. This proves that rebuilding retained speech needs no new TTS or FFmpeg invocation; optional movie encoding remains separate. A missing or corrupt retained source/audio bundle is a build failure when the bundle is expected, rather than permission to invent replacement evidence. The older `HATCH_PRODUCTION_PILOT_ROOT` alias and complete-project bundle remain supported.
