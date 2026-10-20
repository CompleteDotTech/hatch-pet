# Public production delivery status

## Recovery audit — 2026-10-20 UTC

The fresh audit started at public main `19649be829a9badcd789d381a3a22ebe2b3f3a54`. PR [#4](https://github.com/CompleteDotTech/hatch-pet/pull/4) had already merged with incomplete production transports. Its earlier instruction to leave that PR open did not describe the actual repository state. This repair is tracked in [PR #8](https://github.com/CompleteDotTech/hatch-pet/pull/8) on a separate development branch.

The missing bytes were found in an authorized local Git object database at preservation commit `ebdb5d64a0d36e6a2fd6fbf5cb574fc6968f4404`. Recovery copied missing files only and checked each Git object ID, file size and SHA-256. The [recovery audit](references/public-asset-recovery.json) lists all 230 recovered repository files, totaling **19,793,197 bytes**. No replacement artwork, new voice recording or recreated review decision was used.

| Transport | Original logical files | Complete parts | Previously missing parts | Recovered original content |
| --- | ---: | ---: | ---: | --- |
| Artwork and acquisition | 36 | 207 | 113 / 5,910,402 bytes | All 30 affected files; all four original v3 artwork PNGs verify |
| Original speech and attribution | 16 | 39 | 39 / 1,715,251 bytes | All 16 files, including five original WAVs |
| Review ledger | 1 | 64 | 26 plus the index | Exact 4,167,150-byte workflow JSON; 20 linked assistant records |
| Historical inspection images | 10 | 60 | Added exact image transport | Five sheets and five sampled frames match their pre-existing historical SHA-256 values |
| Original project and derived assets | 66 | 92 | Added portable exact-byte transport | 24 original JSON files, 37 PNGs and five padded original-dialogue WAVs match the retained model |

The ten historical PNGs were recovered by deterministic reconstruction from the original artwork, retained project and recorded inspection frame selections using Pillow 13.0.0. Every recovered PNG matches its old review hash exactly. This recovered the recorded bytes; it did not create new review evidence or approvals. All **13 distinct artifacts referenced by the historical reviews** are now hash-verifiable across the transports and supporting metadata. Reviewer identity remains `assistant:/root`; there is no human signoff.

## Distribution and reconstruction

The [delivery manifest](examples/production-pilot/delivery-manifest.json) pins all five ordinary-Git transport indexes, the production model, supporting metadata and original ledger identity. The [derived-source recovery audit](references/public-derived-recovery.json) binds the original project and 42 derived assets to their pre-existing model hashes. Restoration does not recalculate platform-dependent PNG or animation values. The five transports contain **129 logical files and 462 parts**. Each index inventories canonical paths, sizes, SHA-256 hashes and ordered content-addressed fragments. No LFS installation, release download, private artifact store or model account is needed to restore the public project.

```bash
git clone https://github.com/CompleteDotTech/hatch-pet.git
cd hatch-pet
python -m pip install -r requirements-delivery.txt
python scripts/production_sources.py verify-delivery
python scripts/production_sources.py restore-pilot --destination output/milo-luma
python scripts/production.py validate --project output/milo-luma
```

Use Python 3.12 and a new destination. The pinned raster environment is Pillow 13.0.0. The [production recipe](references/production-pilot.md) covers both films, previews, editable construction/dialogue, archives and editor handoffs.

Restoration verifies every required bundle before publishing a complete staged directory. It rejects missing/corrupt fragments, duplicate JSON keys, traversal, symlinks, Windows reserved names, case/Unicode path aliases, conflicting inventories and existing destinations. Exclusive native renames preserve even an empty destination created by a racing writer. Unsupported exclusive-renaming filesystems fail safely. Git attributes and binary I/O preserve source bytes under Windows newline conversion. Missing original audio fails instead of resynthesizing speech.

## Public production previews

Both complete review films, sampled storyboards and two OpenRaster drawings are available in [the public media index](examples/production-pilot/README.md#completed-films-and-inspectable-outputs). Their [provenance and hashes](examples/production-pilot/media/provenance.json) identify the successful public Linux render. Every media file is pinned and verified alongside the source transports. All 696 Linux scene-frame hashes match the pre-existing original shot-review dependencies; this byte comparison preserves the distinction between historical decisions and new render inspection.

## Verification and review gates

The automated gate is:

```bash
python -m playwright install --with-deps chromium
python scripts/verify_public_delivery.py --destination delivery-verification --tests --render --video
```

Git, Node, FFmpeg and ffprobe are required for that complete command. The runner verifies the checkout inventory, full regression suite, portable archive roundtrip, both complete scenes, exact PCM duration, repeat rendering and complete PNG/WAV/OpenRaster editor handoffs. It records hashes of the checkout before/after validation and rejects private pilot overrides or unexpected skips. The only optional application check is native Krita; a Windows-only named-pipe test is inapplicable because that OS lacks `os.mkfifo`. All production, browser and FFmpeg tests are required.

The frozen local suite passed **786 tests** with zero failures/errors and one native Krita skip. Subsequent targeted suites passed all **17 transport** and **6 restoration/checkpoint** cases. Shared disk exhaustion interrupted complete rendering and a subsequent full-gate attempt. The public Linux [full CI gate](https://github.com/CompleteDotTech/hatch-pet/actions/runs/39405174981) then passed all 787 tests, both complete renders, video checks and full editor handoffs. Mac and Windows exposed path-alias bugs and native encoding/math differences. The repairs preserve exact original model/asset bytes and record renderer platform/backend identity. All three platforms must pass the resulting 790-test gate before merge; no required failure becomes an optional skip.

[CI](.github/workflows/public-delivery.yml) runs the complete gate from fresh Linux, Windows and macOS checkouts with read-only repository permissions. It retains actual reports, logs, portable project, storyboards, movies and drawing snapshots. The [validation reference](references/production-public-validation.md) separates current results from the preserved historical reports.

## Publication and merge state

Recovery and implementation are published on `fix/public-production-delivery` in commits [25453d3](https://github.com/CompleteDotTech/hatch-pet/commit/25453d3cc1825a2704975f84df671112fe53b781) and [51d0e5a](https://github.com/CompleteDotTech/hatch-pet/commit/51d0e5a951465993d2ebf3556ef4eb870bc4d640). All 313 changed Git objects were accepted with their expected hashes; both remote trees exactly matched the local reviewed trees. [PR #8](https://github.com/CompleteDotTech/hatch-pet/pull/8) records the merge decision and resulting default-branch commit.

An anonymous public clone of `51d0e5a`, with credential helpers disabled, passed every transport, provenance and historical-evidence check, complete project restoration, and portable archive restoration. Its [actual report](tests/results/public-delivery-public-clone.json) records a clean, unchanged checkout. The documented production CLI also validated two characters, 20 clips, five shots, both scenes and all 696 planned frames with no missing or stale resources. This restoration check does not claim a completed full rendering gate.

The previous automatic approval rejection concerned an opaque upload whose exact contents were not sufficiently bound to the immediately verified fragment. The explicit, hashed and provenance-audited payload was subsequently accepted through the normal GitHub approval process, including the previously blocked fragment. No approval control was bypassed. See the [publication audit](references/publication-review.md). Full CI, production-media inspection and post-merge verification remain separate gates.

## Preserved limitations

- The original history is authentic local hash-linked evidence, not a cryptographic identity-signature service. Historical render reviews can become stale after code/environment changes; reconstruction never changes their decisions.
- Native Krita execution, human review, auditory listening and phoneme-accurate lip sync are not established by automated checks.
- The v3 characters have frontal production rigs. Milo's rear design remains rejected because of scarf asymmetry. Side/back/three-quarter animation rigs are not supplied.
- Earlier artwork lost before the retained v3 acquisition remains lost; the original disclosure records eight earlier observed calls. Those assets are not substituted into or claimed as part of this v3 delivery.
- Historical private master ZIP names remain documented in their original receipts. Their archive transfer was unavailable in this session; exact required inspection PNGs were recovered independently, and the public recipe renders the complete films without those private ZIPs.

The Windows runner additionally exposed a mandatory acquisition-lock byte being included in portable archives. The repair excludes only the exact runtime locks held by the archive operation, preserving all acquisition metadata. Archive creation and project restoration now share exclusive publication, with regressions proving that racing files and empty directories survive unchanged.
