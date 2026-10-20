# Milo and Luma: a reusable production cast

The current pilot has two original, non-fixture imagegen characters, **20 reusable clips**, five shots, and two completed audiovisual scenes. Both scenes select the same `milo@3.0.0` and `luma@3.0.0` assets. The original artwork, construction decisions, original dialogue, actual acquisition history, scoped reviews, and deterministic rendering evidence remain distinct.

**Delivery status:** all previously missing artwork/audio fragments and the original review-history index have been recovered from preservation commit `ebdb5d64a0d36e6a2fd6fbf5cb574fc6968f4404`. Ten historical inspection PNGs were reconstructed byte-for-byte and checked against their pre-existing review hashes. See the [current delivery status](../../DELIVERY_STATUS.md) and [recovery audit](../../references/public-asset-recovery.json). The retained [delivery-blockers record](evidence/delivery-blockers.json) describes the earlier publication attempt; it is immutable historical evidence, not a current status feed.

![Actual completed exchange frame](../../assets/production-pilot.jpg)

## Contents

- [Completed films and inspectable outputs](#completed-films-and-inspectable-outputs)
- [Sources and editable production model](#sources-and-editable-production-model)
- [Actual inspection and acceptance](#actual-inspection-and-acceptance)
- [Repairs and measured reuse](#repairs-and-measured-reuse)
- [Reconstruct the project](#reconstruct-the-project)
- [Restore the original review history](#restore-the-original-review-history)
- [Constraints and integration boundaries](#constraints-and-integration-boundaries)

## Completed films and inspectable outputs

| Scene | Exact duration | Performances |
| --- | --- | --- |
| **Seed exchange** | 432 frames / 36 seconds at 12 fps | Entrances, repeated stepping, stops, Milo's question, Luma's reply, listening and reactions, synchronized packet exchange, two camera cuts, a spoken invitation and exits |
| **Garden promise** | 264 frames / 22 seconds at 12 fps | A distinct garden setting, the same cast and packet owner, two original lines, independent mouth and listening tracks, reactions, and another camera cut |

Both films are 640 × 360. Exact RGBA PNG frames, per-track layers, integer-frame manifests and 48 kHz PCM masters are authoritative. H.264/AAC MP4 files are flattened review copies. The local previews provide scrubbing, frame stepping, timing/source inspection, layer visibility and pinned comparison.

The original private delivery used the following package names. Their historical sizes, hashes and inventories remain in [render delivery](evidence/render-delivery.json). These names are not public download links. The public reconstruction commands produce complete current renders, previews and editor handoffs directly from the retained inputs; CI retains its actual reports, portable project, storyboards, review movies and OpenRaster snapshots as run artifacts.

| File | Contents |
| --- | --- |
| `Milo-Luma_Seed-Exchange.mp4` | Completed 36-second review film |
| `Milo-Luma_Garden-Promise.mp4` | Completed 22-second review film |
| `Milo-Luma_Seed-Exchange_Masters.zip` | All current frame/layer PNGs, PCM, manifests, previews and inspection sheets for the first scene |
| `Milo-Luma_Garden-Promise_Masters.zip` | Corresponding complete output for the second scene |
| `Milo-Luma_Editor-Handoff.zip` | 168-frame exchange sequence, WAV, three exchange OpenRaster snapshots, and a separate 26-layer arrival snapshot |
| `Hatch_Synthetic-Regression_Masters.zip` | Three explicitly synthetic rendered scenes, 300 frames total |
| `Hatch_Synthetic-Performances.mp4` | The 23-second synthetic performance reel |

After rebuilding or restoring a project, open `renders/seed-exchange/preview.html` or `renders/garden-promise/preview.html` through a local HTTP server. The generated `evidence/inspect-{shot}.png` files show chronological inspection samples; the two `*-storyboard.png` files show complete scene structure. These generated master paths are not ordinary Git links: use the output packages or the reconstruction commands below.

## Sources and editable production model

| Record | Purpose |
| --- | --- |
| [project.json](project.json) | Project identity, source selections, scene relationships, rendering settings and resource limits |
| [cast.json](cast.json) | Shared identities, proportions, palette/materials, scale, costumes, views, layered components, anchors and variant restrictions |
| [clips](clips/) | Versioned idle, walk, walk-start, stop, reaction, reach, hold, release and exchange contracts |
| [seed-exchange.json](scenes/seed-exchange.json), [garden-promise.json](scenes/garden-promise.json) | Shot edits, actor/prop/camera tracks, original dialogue, independent facial tracks and cross-scene continuity |
| [acquisition](acquisition/README.md) | Genuine installed-imagegen handoffs, exact native claim/attempt history, provenance and the honest prior-loss record |
| [source index](source-bundle/sources-index.json) | Exact four original imagegen outputs and their retained acquisition/canonical source files, transported as bounded content-addressed parts |
| [audio index](audio-source-bundle/sources-index.json) | Five original local Flite TTS WAVs, authored text, actual synthesis receipts and supplied package attribution |
| [review-history index](reviews-source-bundle/sources-index.json) | Exact UTF-8 bytes of the actual production workflow/review history; transport is not a new approval |
| [historical image index](evidence-source-bundle/sources-index.json) | Five inspection sheets and five reviewed frames whose exact bytes match the historical ledger |
| [exact project index](project-source-bundle/sources-index.json) | Original serialized project and derived PNG/PCM bytes, preserving every pre-existing model hash across platforms |
| [delivery manifest](delivery-manifest.json) | Pinned inventories for all five transports, production model, supporting metadata and review-chain identity |
| [review transport evidence](evidence/review-history-transport.json) | Decoded history hash, 20-record chain identity and exact restoration check |

The current production acquisition made **four actual imagegen calls**, one turnaround and one component board per character, with one attempt each and concurrency one. The configured current limit is four calls; none remain. Provider request/model/parameter identifiers were not exposed and remain explicitly unavailable. The local claim IDs are genuine hatch correlation IDs, not invented provider IDs. Earlier lost artifacts and eight previously observed calls are disclosed separately and do not approve the replacement cast.

Original scenery and the packet are code-authored imported drawings, with their own provenance. The character components are derived crops/registrations of genuine generated originals. TTS, deterministic extraction, geometric checks, rendering, imagegen, visual review and external application exercise are separately labeled.

## Actual inspection and acceptance

[Historical review status](evidence/reviews-final.json) contains two construction targets, **13 used clip targets**, and five shot targets. At that recorded inspection, each shot had decisions in all eight review dimensions. [Recording results](evidence/review-recording-results.json) identify the actual reviewer as `assistant:/root`; **human review is false**. Seven unused clips remain unreviewed rather than inheriting acceptance from related performances. Reconstructed outputs must be checked against current dependencies; the retained decisions are not rewritten to approve later code.

The primary assistant inspected original boards, repaired construction frames, both scene storyboards and the chronological samples listed in [inspection-sheets.json](evidence/inspection-sheets.json). Final shot decisions bind actual inspected frame files, the complete frame/layer/audio inventory, exact dependencies and the renderer version. [Actual browser playback](evidence/browser-playback.json) completed both films with audio clocks of 36 and 22 seconds and final frames 431 and 263. Browser control observations are automated evidence, separate from visual decisions.

The accepted scope is a limited frontal puppet production pilot. Mouth choices and small eye-patch gaze offsets remain editable approximations. No auditory listening, phoneme-accurate alignment, human signoff or persuasive vocal-acting verdict is claimed. The explicit notes in each review preserve these limits; passing sample-count checks alone did not establish an artistic decision.

[Final coverage](evidence/coverage-final.json) reports **245 reusable requirements**, zero missing or incompatible requirements, zero unreviewed required work and zero expected generation. Coverage readiness is separate from final shot review. [Generation evidence](evidence/generation-final.json) retains the bounded acquisition accounting.

## Repairs and measured reuse

[Inspection and repair notes](evidence/inspection-and-repairs.md) describe the actual defects: duplicate arm silhouettes, wrist/hip registration, head-edge contamination, limited muzzle drawings, and a generic walk-start blend that slid a planted foot. The final pilot uses an authored 12-frame start. Sources were retained; no individual performance frame was independently resized to hide a mismatch.

At exchange frames 83, 84 and 85, both grip anchors and the packet agree at approximately **[329.990865592, 240.936492272]** world pixels. Ownership changes from Milo to Luma exactly at frame 84. See [contact evidence](evidence/contact-frame-84.json) and [authored reach geometry](evidence/authored-geometry.json). The actual visible overlap was inspected separately from the anchor calculations.

The historical approved rerender reused **all 432 + 264 frames**, with zero new frames: [first scene](evidence/render-seed-approved-reuse.json), [second scene](evidence/render-garden-approved-reuse.json). The current verification command independently checks complete-frame reuse without recording a new artistic approval. The garden scene uses the existing cast and idle/reaction clips, new scenery/timing/audio, and no new character generation.

[Operational evidence](evidence/operational-evidence.json) records real isolated changes: the exchange camera affects only that shot; Milo's shared mouth rest offset affects all five shots; Milo's reaction clip affects only garden and tomorrow. Each report explains the required rerender/review work and the reusable shots. The changed experimental variants were not promoted or approved.

[Archive and restore evidence](evidence/archive-restore-final.json) records the actual complete project archive, fresh-directory restore, preserved review chain, current cached renders and coverage. Old unused cache files are kept outside the clean archive; the unchanged resource guard remains enforced.

## Reconstruct the project

The [full production recipe](../../references/production-pilot.md) gives commands for extraction, clips, dialogue, interactions, coverage, rendering, review, reuse, archives and editor handoff. Source reconstruction makes **no model or TTS calls**. Install the pinned delivery dependencies. Exact restoration uses the original serialized model and derived asset bytes; rendering records its actual platform and PNG backend.

```bash
python -m pip install -r requirements-delivery.txt
python scripts/production_sources.py verify-delivery
python scripts/production_sources.py restore-pilot --destination output/hatch-pilot
python scripts/production.py validate --project output/hatch-pilot
python scripts/production.py render --project output/hatch-pilot --scene seed-exchange --destination output/hatch-pilot/renders/seed-exchange --video
python scripts/production.py render --project output/hatch-pilot --scene garden-promise --destination output/hatch-pilot/renders/garden-promise --video
python -m http.server 8765 --bind 127.0.0.1 --directory output/hatch-pilot
```

The recipe does not fabricate new approval receipts. Freshly created work requires inspection; archived decisions require exact dependency and artifact freshness. Use the recorded Python/Pillow environment when comparing exact historical pixel and renderer hashes.

## Restore the original review history

`restore-pilot` restores the exact workflow JSON automatically. The smaller review-history transport can also be decoded independently to inspect the actual decisions and generation bindings:

```bash
python scripts/production_sources.py verify --bundle examples/production-pilot/reviews-source-bundle
python scripts/production_sources.py restore --bundle examples/production-pilot/reviews-source-bundle --destination output/hatch-pilot-review-history
```

Read `output/hatch-pilot-review-history/production-workflow.json`. Do not overwrite a working project's existing history with it. `verify-delivery` verifies all 20 linked records and all 13 distinct referenced supporting images/records across the transports and metadata. During `restore-pilot`, historical sampled frames go under `historical/renders/`; their original paths and hashes remain in the ledger and `delivery-restoration.json` maps their inspection locations. New complete renders go under `renders/`. `production.py reviews` explains stale dependencies and missing current-render evidence honestly.

## Constraints and integration boundaries

- Frontal animation components are authored. Turnarounds are design references; they do not supply side/back/three-quarter animation rigs. **Milo's back reference is rejected** because the scarf knot appears on viewer-right in both front and back views; its physical asymmetry needs reconciliation before rear-facing production.
- Hands provide an open-paw packet exchange, not articulated finger wrapping. The registered muzzle family supports limited mouth choices. Gaze is a small editable patch offset. These limits remain explicit in the review notes.
- Motion uses authored transforms, displacement/contact compensation and bounded transitions. It supplies no automatic inverse kinematics, motion synthesis or new-view generation. Full-frame drawings are supported and exercised by the synthetic performance demonstration when transformed parts are insufficient.
- Lighting direction/color treatment are declarations; retained paintings are not automatically relit. Compositing uses 8-bit encoded sRGB with specified alpha/resampling behavior, not a linear-light/ICC pipeline.
- The actual adapter exported PNG/WAV/OpenRaster and verified exact roundtrips. **Krita was unavailable**, so external application and native animation-timeline integration remain unverified. No application was installed and no live settings were changed.
- Default Codex pet state order, frame counts, millisecond timings, dimensions, alpha rules, packaging and installation/rollback contracts remain unchanged. Production rendering does not install a pet.

See [validation](../../references/production-validation.md) and the complete [P01–P15 traceability map](../../references/production-traceability.md) for implementation, test, demonstration and limitation evidence.
