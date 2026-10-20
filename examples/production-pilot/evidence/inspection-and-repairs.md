# Actual pilot inspection and repairs

Reviewer: **ChatGPT, `assistant:/root`**, primary production reviewer. These are actual assistant visual observations from the retained v3 originals and completed current renders. They are not human receipts. The machine-readable chain is preserved by the [review-history transport](review-history-transport.json); current per-target decisions are in [reviews-final.json](reviews-final.json).

## Observed defects and resulting construction

| Observed issue | Repair or explicit constraint | Final inspection evidence |
| --- | --- | --- |
| Milo's torso source included extra lower-arm silhouettes | Authored torso alpha mask keeps scarf/stomach and removes the duplicated arm shapes; original PNG unchanged | Arrival and exchange construction frames and `inspect-arrival.png` / `inspect-exchange.png` |
| Milo paw crops pointed wrist-down | Recorded 180-degree crop rotation registers the wrist; no mirroring | Both original parts board and current exchange/contact frames |
| Luma arm sources already included hands | Cropped at the wrist and attached separately registered paws | Source crop provenance and exchange approach/hold/release samples |
| Hip gaps and exposed shoulder joints | Adjusted fixed torso placement and shoulder anchors; arms draw behind the torso | Final arrival standing frame 96 and garden construction frame 12 |
| A neighboring fur fragment contaminated Luma's head edge | Tightened the source crop's right boundary | Registered head PNG and final transparent silhouette |
| Generated mouth choices included muzzle/nose artwork | Kept a consistently registered muzzle-replacement family; recorded the limitation rather than pretending isolated anatomical lips | Dialogue samples across all five shots; no independent per-frame fitting |
| Generic departure interpolation slid a planted foot by 26.25 world pixels | Authored a 12-frame walk-start with quadratic root acceleration, planted right sole and explicit left swing; preserved clip scale | Every departure frame 0–28 was visually inspected; the actual pilot regression checks world-space stance drift |
| Milo rear turnaround shows scarf knot on viewer-right in both front and rear | Rejected the back design view; retained original unchanged; current frontal scenes do not use it | Actual turnaround inspection and explicit `cast.json` view-review annotation |

Earlier unreviewed iterations were overwritten during repair. This record does not invent retained before-image hashes or claim that missing prior renders are review evidence. The [lost-artifacts record](../acquisition/lost-prior-artifacts.json) separately records earlier workspace losses. No lost approvals were promoted into the current cast.

## Completed visual inspection

The primary reviewer inspected both original turnarounds and parts boards, registered construction PNGs, and full-size representative frames. Both complete scene storyboards were inspected, then chronological per-shot sheets were inspected at the exact frame indices in [inspection-sheets.json](inspection-sheets.json). Those sheets include the arrival stepping/stopping interval; every frame of departure's start/entry transition; exchange approach, shared hold, frames 83/84/85 and release; both dialogue exchanges; blinks; listening; reactions; camera edits; and exit endpoints.

Milo's amber/cream identity and asymmetric coral scarf remain distinct from Luma's tall teal/cream silhouette and ochre waistcoat. Fixed cast scales survive the cuts. The foreground tree's overlap during exits is deliberate. In the garden, the fence/planter change identifies a new setting while costumes and packet ownership remain continuous. Raised brows, small head motions and editable eye-patch offsets create restrained reactions. Mouth drawings alternate inside the recorded speech intervals and return to neutral.

The packet remains visibly connected to the hands around the owner change; contact geometry agrees on [329.990865592, 240.936492272] world pixels. The drawing still depicts open paws holding a packet near its top edge. Numerical alignment is supporting evidence and does not establish finger articulation or anatomical correctness.

## Timing and playback inspection

Offline frame and PCM validation checked exact shot/scene lengths. Actual Chrome ran both complete previews on their audio clocks, reaching 36 and 22 seconds and the final frame. Scrubbing, stepping, pinned comparison and hiding/showing Milo changed the actual rendered canvas. See [browser-playback.json](browser-playback.json).

The first inspection harness unnecessarily required the asynchronous media `ended` flag after the preview stopped. The garden preview had already reached its final frame. The corrected inspection retained the actual clock and boundary state: 22 seconds, frame 263, paused, with `ended` still false. No renderer/application code or regression test was weakened. The [attempt record](browser-inspection-attempts.json) preserves that inspection failure and correction.

No auditory listening occurred. Exact timing, visible mouth intervals and provenance do not certify persuasive vocal acting or phoneme-accurate lip synchronization. The assistant accepts the current visible limited cutout pilot in the scoped records; human signoff and unavailable external-editor integration remain false.
