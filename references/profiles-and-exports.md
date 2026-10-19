# Profiles, exports, and local adaptations

`profiles/codex-v1.json` is the versioned source of the Codex contract. Every deterministic stage reads the profile saved as `run/profile.json`; `--profile path.json` explicitly selects another profile. The default remains nine rows, eight columns, 192×208 cells, and 1536×1872 pixels. Generate its documentation table with `python scripts/profile_spec.py --table`.

## Custom profile schema

The structural schema is `profiles/profile.schema.json`. `profile_spec.load_profile()` also enforces relationships that JSON Schema alone does not express: unique portable state identifiers (including reserved filename/job names), one duration per frame, frames fitting columns, valid event targets, valid static-frame index, bounded atlas size, and compatible source counts/timing for explicitly approved mirrors. It rejects cycles, stale derived dimensions, unknown keys, nonfinite numbers, and unsupported combinations before preparation. Profile schemas 1 and 2 are supported; other versions are rejected. Version 2 supports non-character assets. See [playback and extensions](playback-and-extensions.md) for the extended state machine and exporter options.

A profile contains `id`, `schema_version`, `layout` (`columns`, `cell_width`, `cell_height`), and ordered `states`. Each state has `id`, `purpose`, `frames`, and integer millisecond `durations`. List order defines atlas row order. Optional `motion` is `quiet`, `vertical`, `directional`, `gesture`, or `static`. `alignment` selects coordinates (`slot`, `center`, `baseline`), scale (`row`, `shared`, `none`), pixel `padding`, and normalized `[x,y]` `anchor`/`pivot`.

- `slot` preserves each full source slot, including vertical displacement. All frames in a row share one viewport and scale; a taller or wider pose never triggers per-frame fitting.
- `center` explicitly recenters each pose within that viewport; `baseline` explicitly bottom-aligns each pose. These policies remove intended displacement and should not be used for jumping.
- `row` fits the full row viewport inside the padded destination cell. `none` uses source pixels at 1:1 and rejects clipping. `shared` uses a single positive finite scale from calibration (`configure --shared-scale`) or a common profile `alignment.scale`. Conflicting explicit shared scales are rejected. Source resolutions must be comparable for a pixel multiplier to represent a common character scale.
- `alignment.resampling` explicitly selects nearest, bilinear, bicubic or lanczos. If omitted, new runs use the frozen style's recorded fallback; historical runs without one retain lanczos. No profile dimensions or timing change to accommodate a style. `anchor` positions the scaled viewport in the destination's available space. `pivot` is exported metadata for consumers; it does not change raster pixels. Both remain in `animation.json` and do not imply an engine integration.

Generated production states use `generation.skill: imagegen` and `requires_identity_reference: true`. Top-level and state `generation.instructions` and `generation.requirements` provide semantic guidance to base/row/retry prompts. Allowed derivations contain at most one `horizontal-mirror` record with a source state and `requires_explicit_approval: true`; declaring it never grants approval. The default permits only `running-right` to `running-left`.

Top-level `validation.require_provenance` must be true; weaker acceptance is unsupported. `allow_detached_details` permits small intentional details, while extra major poses remain ambiguous. State thresholds use these exact keys (unknown keys are errors):

| Key | Unit / interpretation |
| --- | --- |
| `min_motion` | Minimum mean RGBA difference, 0–1; lower defaults for quiet motion |
| `near_duplicate_delta` | Pairwise RGBA difference below this value is near-identical |
| `max_size_ratio` | Maximum occupied-alpha area ratio before a warning |
| `max_baseline_shift` | Maximum occupied-bottom displacement as a fraction of cell height |
| `loop_warning_ratio` | Last-to-first change compared with median adjacent change |
| `palette_distance_warning` | Euclidean RGB distance between alpha-weighted mean colors |
| `min_used_pixels` | Integer occupied-pixel minimum for a frame |

Reports include measured values, thresholds, pairwise comparisons, cross-row area measurements, and uncertainty. These are review signals; changed visible surfaces can affect area and color without identity drift. Suspicious ordering uses an adjacent-transition outlier heuristic. None can prove action semantics, direction, identity, or good animation.

`export.formats` supports `frames`, `atlas`, `gif`, `webp` (animated), `browser`, `cards`, `flipbook`, `board`, `stimuli`, `cursor`, and `craft`; `static_state` and `static_frame` select the overall still alternative. Other states use their first frame as their still. `events` maps application event names to stable state IDs.

## Export and preview

After extraction and validation:

```powershell
python scripts/hatch.py export --run-dir C:/work/run --destination C:/work/web-status-export
```

Export writes `animation.json`, `profile.json`, a hashed `export-receipt.json`, per-state static PNGs, and selected formats. Controller exports add generation provenance, structured metrics, and any recorded visual review. Browser export includes actual ordered PNG frames. Open `preview.html` locally or serve the export folder. The manual selector and **Send local event** button use the metadata's event mapping. Playback schedules each exported frame's `duration_ms`, respects the operating system reduced-motion preference, and offers a still toggle. GIF has binary transparency, palette limits, and 10 ms timing resolution; use the PNG/browser or WebP outputs for antialiased alpha and integer-millisecond timing. Browsers can throttle timers in background tabs; this preview is not a real-time synchronization engine.

The local event interface is:

```javascript
window.hatchPet.dispatchLocalEvent('request'); // web-status.json event -> working state
window.hatchPet.selectState('working'); // direct state selection
window.dispatchEvent(new CustomEvent('hatch-pet-event', {detail: 'request'}));
```

For OBS, use `examples/obs-mascot.json` and point a browser source at the exported local HTML, with `?overlay=1&state=idle` to hide controls and select that state. This implements a local transparent page, not OBS scene setup or verified Program output. Controls still work when opened normally. There is no network event listener, authentication layer, hardware driver, or external service connection.

## Representative examples

All profile versions use the same [style registry](style-catalog.md). Their own subject and generation requirements remain authoritative. Controller exports retain the complete frozen style under `provenance.json.resolved_style`; reviewed packages add hashed `style-provenance.json` without changing `pet.json` or atlas dimensions. These are requested artistic specifications, with separate actual source origins and review evidence.

Every JSON in `examples/` is a complete supported profile usable by the same preparation/extraction/export pipeline. These are example adaptations; they do not establish production integration.

| Profile | Local capability | Remaining integration |
| --- | --- | --- |
| `game-npc.json` | Rest/walk/interact frames, atlas, pivots | Engine import and event adapter |
| `web-status.json` | Ready/working/error browser playback | Product event wiring |
| `obs-mascot.json` | Transparent welcome/celebrate browser source | OBS source setup and live Program check |
| `tutor-avatar.json` | Listening/explaining/encouraging states | Lesson and speech coordination |
| `support-kiosk.json` | Ready/listening/answering visuals | Support backend and kiosk lifecycle |
| `iot-display.json` | Online/busy/alert assets | Device renderer and transport |
| `stickers-emoji.json` | PNG, GIF and animated WebP exports | Platform format/size adaptation and upload |
| `storyboard.json` | Ordered establish/react/resolve rows | Editorial timeline and audio |
| `model-evaluation.json` | Controlled states and metrics/provenance without installation | Model experiment harness and human scoring |
| `ui-animation.json` | Available/loading/complete states | Application state binding |

For controlled evaluation retain extraction and validation JSON together with the export receipt. Measurements quantify differences, not semantic identity or action quality; record visual review separately.

See [the ten additional-use presets](additional-uses.md) for assembly cards, educational processes, product variants, flipbooks, communication boards, stimuli, regression fixtures, cursors, protocols and craft grids. [Sources and identity](sources-and-identity.md) covers explicit artwork imports.

## Extension interfaces

The stable bounded interfaces are documented in [playback and extensions](playback-and-extensions.md). Exporters consume a validated profile plus exact indexed PNG cells using `export_assets(frames_root, output_dir, profile)`. Add a format to `profile_spec.FORMATS` and dispatch it in `export_assets.py` only with format-specific tests. Validators consume the same ordered state records; `inspect_frames.py` produces row metrics and uncertainty warnings, and `validate_atlas.py` enforces geometry/transparency. Adding a state needs profile data, not a separate pipeline. New coordinate policies or derivation types need an explicit implementation and validator update; unsupported policies are rejected.

`write_export_receipt(output_dir, profile)` finalizes hashes after a caller adds metrics or provenance. A validator extension should return measurements plus named warnings/errors, document units and uncertainty, and add its accepted configuration keys to runtime/schema validation. No plugin loader or external service is required for profile extensions.
