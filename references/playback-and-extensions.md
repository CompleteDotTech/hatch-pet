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

Each state may have `playback: {mode, completion, hold_frame, interruptible, reduced_motion_frame}`. `mode` is `loop` (default), `once`, or `hold`. `once` holds its last frame after completion unless `completion` names another state. `hold` displays `hold_frame` (default zero). Completion transitions require `once` and another existing state. Optional `reduced_motion_frame` selects that state's expressive static alternative and must identify an existing frame; older profiles retain their global/static-frame behavior.

Event rules must agree with the ordinary `events` mapping. `from` lists legal current states, `priority` is 0–100, and `interrupt` is `always`, `higher` than current priority, or `never`. `interruptible: false` on the active state queues legal incoming events until a state boundary: a loop cycle, one-shot completion or held-pose dispatch. New event rules default `restart: false`; repeated same-state events do not restart playback unless requested. Legacy event mappings retain restart behavior. Rejected events return false.

Pending events are bounded by `queue_limit` (0–32), coalesced by event name without resetting their arrival order, and normally ordered by priority then arrival. They are served at a loop boundary, at one-shot completion, or at a single scheduled pending-event boundary for a hold. A hold with no queue has no animation timer. Legality is checked against the state that just performed before applying its automatic completion; stale illegal events are discarded. This lets a queued acknowledgment remain legal when a request completes. A queued event that is bypassed four times is promoted and receives one protected performance cycle/boundary before ordinary interruption resumes. Direct selection and cancellation still override it.

Optional top-level `playback.max_consecutive_interruptions` is 0–32 (default 4). Once the bound is reached while events are waiting, further immediate interruptions queue until a boundary. Repeated high-priority requests therefore cannot indefinitely restart the active animation or prevent an older accepted event from receiving a turn. Queue overflow fails explicitly rather than dropping an unrelated accepted event silently.

An event may declare `resume: true` only when its target is a one-shot. It snapshots the interrupted state's frame, remaining time and priority, and restores them after that one-shot. Suspended snapshots are bounded at 32. Another unrelated event, direct selection or cancellation clears the suspended history; this is local animation state restoration, not resuming a software task. In reduced-motion mode an event selects static feedback without adding a suspended snapshot or hidden timer. Resuming after a user pause uses the separate `resume()` method.

```javascript
hatchPet.dispatchLocalEvent('send'); // boolean acceptance/queue result
hatchPet.selectState('request');     // explicit local selection, clears queue
hatchPet.pause(true);
hatchPet.resume();                   // preserve the paused frame's remaining time
hatchPet.step(1);                    // pause and advance one frame
hatchPet.cancel();                   // clear queue, return to cancel/static state
hatchPet.playback;                   // state, index, priority, queued, deadline, etc.
```

Cancellation and direct selection clear queued and suspended events. Hidden pages pause at the remaining frame duration; becoming visible resumes without racing through a hidden backlog. Manual pause and page visibility are independent: becoming visible does not override a manual pause. Reduced-motion preference selects a static frame, clears pending/suspended events and stops animation. Explicit legal event selection while reduced still updates the chosen state's static alternative. Controls honor user preference changes and retain the paused frame timing when motion is restored.

Catalog compilation enforces canonical legal transitions in generic event mappings. A transition recipe exposes only its declared events and completion edges, preventing a generic `state:*` alias from bypassing its legal sources. Reduced-motion recipe profiles replace automatic animated completion edges with explicit `next:<source-state>` events so each static step remains reachable without timers. The manual selector remains an inspection control. These rules do not implement blending, interpolation, an animation rig, remote events or an external application's workflow engine.

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
