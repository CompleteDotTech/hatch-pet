# Playback contract and bounded extensions

The profile is the extension surface, not arbitrary executable plugins. `hatch.py capabilities` reports interface version 1, supported source layouts, extraction policies, filters, exporters and consumers. Unknown keys/formats and incompatible combinations fail during profile validation. `profiles/profile.schema.json` and `profiles/asset-inputs.schema.json` describe structural types; runtime validation also checks relationships and resource bounds.

## Playback contract v2

Existing v1 profiles keep their state order, exact durations, infinite loops and immediate event-to-state selection. The static alternative remains the configured frame (Codex idle frame zero). The export records all intended per-frame integer milliseconds. New profiles can add:

```json
{
  "playback": {
    "initial": "idle",
    "cancel_state": "idle",
    "queue_limit": 4,
    "events": {
      "send": {"target":"request","from":["idle"],"priority":1,"restart":false},
      "receive-ack": {"target":"ack","from":["request"],"priority":2,"interrupt":"never"}
    }
  }
}
```

Each state may have `playback: {mode, completion, hold_frame, interruptible}`. `mode` is `loop` (default), `once`, or `hold`. `once` holds its last frame after completion unless `completion` names another state. `hold` displays `hold_frame` (default zero) without a timer. Completion transitions require `once` and another existing state.

Event rules must agree with the ordinary `events` mapping. `from` lists legal current states, `priority` is 0–100, and `interrupt` is `always`, `higher` than current priority, or `never`. `interruptible: false` on the active state queues legal incoming events until completion. New event rules default `restart: false`; repeated same-state events do not restart playback unless requested. Legacy event mappings retain restart behavior. Pending events are bounded, coalesced by event name, ordered by descending priority and stable arrival order. Legality is checked again at completion; stale illegal events are discarded. Rejected events return false.

```javascript
hatchPet.dispatchLocalEvent('send'); // boolean acceptance/queue result
hatchPet.selectState('request');     // explicit local selection, clears queue
hatchPet.pause(true);
hatchPet.step(1);                    // pause and advance one frame
hatchPet.cancel();                   // clear queue, return to cancel/static state
hatchPet.playback;                   // state, index, priority, queued, deadline, etc.
```

Cancellation and direct selection clear queued events. Hidden pages pause at the remaining frame duration; becoming visible resumes without racing through a hidden backlog. Reduced-motion preference selects a static frame, clears pending events and stops animation. Explicit event selection while reduced still updates the chosen state's still. Controls honor user preference changes.

Scheduling uses `performance.now()` and accumulated deadlines instead of adding callback lateness to every frame. A late callback advances to the current intended frame; catch-up is bounded at 256 transitions before resynchronizing. Browsers, refresh rate, image decode, background throttling and system load still affect physical presentation. This is not laboratory timing, audiovisual synchronization or a hard real-time renderer. The perception exporter records intended timings and this limitation.

## Stable extension interfaces

| Interface | Input → output | Required validation |
| --- | --- | --- |
| Source v1 | claimed imagegen output or explicit import descriptor → normalized owned PNG + origin receipt | type, size, order, required input hashes, active claim or import intent |
| Extraction v1 | source PNG + profile + optional annotation → indexed PNGs and extraction-v4 manifest | component/viewport bounds, scoped permissions, source/configuration/annotation/frame hashes |
| Exporter v1 | validated profile + exact indexed PNG cells → portable files, `animation.json`, export receipt | cell dimensions, exact frame set, format-specific constraints and reconstruction tests |
| Consumer v2 | animation metadata and relative PNG paths → local selection/playback | state/event targets, bounded queues, timings, reduced motion and actual browser tests |

Implement new built-in exporters in `asset_exporters.export_extensions` and declare their formats in runtime/schema/capability discovery together. Add a focused compatibility and reconstruction test. Do not load user-supplied Python modules. A new extraction/source strategy must produce full provenance and preserve existing gates; merely naming a policy in a profile never enables it.

## Reusable outputs

- `frames`, `atlas`, `gif`, `webp`, `browser`: ordered PNGs, atlas, encoded animations and local playback. PNG paths are retained for reconstruction even when another format is requested. GIF has palette/binary-alpha and centisecond timing limits; lossless animated WebP and PNG preserve RGBA.
- `cards`: ordered A4 PDF step cards, PNG first-page preview and `cards.json` containing page/order/label/source hashes and print dimensions. Print at 100% and verify physical size; no automatic printer integration.
- `flipbook`: cards plus an ordered zoetrope strip, slit marks, print PDF/PNG and assembly metadata. Physical assembly and viewing speed remain manual.
- `board`: readable buttons with static alternatives and selectable animation, without clinical-validation claims. Requires `browser` in the profile.
- `stimuli`: condition/frame CSV, source and export hashes, intended durations and explicit timing limitations. Experiment randomization, calibration and actual onset recording remain external.
- `cursor`: one Xcursor file per state, explicit hotspots and delays, reconstruction metadata and a locally scoped browser cursor adapter. No global pointer settings change. The binary format follows the [X.Org Xcursor image-chunk contract](https://xorg.freedesktop.org/releases/X11R7.5/doc/man/man3/Xcursor.3.html). Partial-alpha RGB uses premultiplication and integer rounding. Windows/macOS native cursors require another adapter.
- `craft`: grid-aligned motif PNG/PDF, symbol grid, named palette, counts and readable legend. Nearest-palette mapping and alpha threshold 128 are explicit; thread/bead equivalence, physical pitch and construction need review.

An exported asset, a locally tested consumer, and a verified external integration are separate outcomes. Every example states the remaining consumer work. No external deployment is performed by these commands.
