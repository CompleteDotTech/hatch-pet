# Production payload publication review

This audit accompanies the user's explicit request to complete public distribution in `CompleteDotTech/hatch-pet`. It describes the concrete payload submitted for approval; it is not itself an approval decision. Publication and merge results are maintained in [delivery status](../DELIVERY_STATUS.md).

## Original assets and authorship

The four original PNGs belong to the retained v3 Milo/Luma acquisition. The original jobs, handoff templates, source hashes, prompt/input relationships, local claim IDs and one-attempt histories remain unchanged. The boards depict a fictional amber bear and teal rabbit, including component sheets. They contain no person photograph or embedded PNG metadata. This repair did not call image generation or introduce replacement artwork.

Original PNG SHA-256 values:

| Source | SHA-256 |
| --- | --- |
| Milo turnaround | `cb88dd18e162ee7e8d7a40da6b510e7ae4431595458b548fb4414db18eb225da` |
| Milo components | `84e0abc18797bbeb5224dacc281873cfd7b39ed64d7ef0ac2161947772c63588` |
| Luma turnaround | `270eb609c8cc566a61f3081d09c6e2f47390592d7650e9547872a64cb9f1cced` |
| Luma components | `bdfb919fd64776e45014f9654f41cf83d56bd5f34a2d1979b1bb09fd80be32f6` |

The five original WAVs contain the authored fictional dialogue printed in the [production recipe](production-pilot.md#shot-and-dialogue-plan), synthesized with the recorded Flite `rms` and `slt` voices. They are not recordings of private conversations. Original text, engine/version receipts, audio hashes and the supplied `audio/original/flite-package-copyright.txt` are retained byte-for-byte. Its SHA-256 is `77d13a5e6cbe7277b4721033f9ad15707241c2832baa8c74ec823c9ee5ebf71c`.

The repository's existing [Apache 2.0 license](../LICENSE.txt) is unchanged. Original attribution notices are preserved; this repair does not replace third-party terms. The upstream [Flite COPYING notice](https://github.com/festvox/flite/blob/master/COPYING) documents its redistribution conditions. OpenAI's [content ownership terms](https://openai.com/policies/terms-of-use/#content) distinguish the user's output rights from third-party content and other users' output. These references support the provenance assessment; the audit does not manufacture a separate rights grant, guarantee exclusivity, or attribute generated artwork to a human illustrator.

## Privacy and credential inspection

The assembled textual sources and retained metadata were scanned for private-key blocks, GitHub credentials, AWS access IDs, common service-key formats and nonempty credential fields. No matches requiring removal were found. The 20 occurrences of `token` in transported JSON are 32-character hexadecimal local job-correlation UUIDs. Their function is documented in [acquisition/README.md](../examples/production-pilot/acquisition/README.md) and implemented by `hatch.py::claim`; they authorize no network account or provider service.

Historical workspace paths, assistant reviewer identity, timestamps and source acquisition names remain because the user requested original provenance. Original third-party copyright notices contain their authors' public attribution addresses. There is no human-review claim, live application credential or private human voice recording in the proposed payload. A pattern scan is one audit step; the source boards, dialogue text, provenance and review identities were also inspected.

## Exact transport binding and the earlier rejection

The prior automatic review rejected an upload because its opaque base64 content was not adequately tied to the immediately verified fragment. The affected original was Milo's turnaround; the named fragment was:

`source-bundle/parts/6a38af6056b71410d1626c0f270886a8d232f08f897439a484b61906b2e66aaf.bin`

That fragment is exactly **65,535 bytes**, belongs at original byte offset **589,815**, has the SHA-256 encoded in its name, and has an exact base64 wire length of **87,380 characters**. The assembled original hash is the Milo turnaround hash above. The recovery audit ties the retained bytes to preservation commit `ebdb5d64a0d36e6a2fd6fbf5cb574fc6968f4404`.

Every proposed fragment is bound by its pinned bundle index to one or more original file hashes and ordered offsets. Before upload, the publisher checks the local bytes, byte count, base64 roundtrip and Git blob ID; the returned remote blob ID must match. A complete tree is attached to the delivery branch only after all required payload objects are present. Interrupted or rejected object transfers must not publish a partial production tree or advance `main`.

The payload is submitted through the legitimate GitHub connection and automatic approval process. An approval rejection is a blocker, not a reason to switch encoding, hide payloads, bypass controls or merge incomplete transports.

## Verified publication result

On 2026-10-20, the connected GitHub approval process accepted all 313 changed blob objects, including the previously rejected fragment above. Each returned Git object ID matched its locally verified payload. The recovery tree was `51aa425bd910abf049354275a386342c490cf3d1`; the implementation tree was `17a3710d33ae3c088a6760a5c251dfda9ccd1cd8`. The branch ref was created only after both complete trees matched.

The public commits are [25453d3](https://github.com/CompleteDotTech/hatch-pet/commit/25453d3cc1825a2704975f84df671112fe53b781) and [51d0e5a](https://github.com/CompleteDotTech/hatch-pet/commit/51d0e5a951465993d2ebf3556ef4eb870bc4d640), reviewed through [PR #8](https://github.com/CompleteDotTech/hatch-pet/pull/8). An anonymous clone with credential helpers disabled verified every required transport and restored the full model and a portable archive; its [unaltered verification report](../tests/results/public-delivery-public-clone.json) identifies the exact public revision and checkout hashes. Publication acceptance establishes permission for those submitted bytes, not an artistic or human approval.

## Review and render evidence

The original 20-record assistant ledger and its supporting metadata are recovered originals. Ten historical inspection PNGs match pre-existing hashes exactly. Newly executed tests, render validation, previews and editor-format checks are labeled with their actual environment and scope; they do not append artistic approvals or human signoff to the historical chain.

Historical private master ZIP receipts remain original records, even where those ZIP downloads were unavailable. The public delivery reconstructs complete production renders from the original inputs and exposes actual verification artifacts. It does not relabel a new ZIP as the historical ZIP or claim a matching archive hash without checking it.

## Additional exact sources and public demonstration media

The project transport preserves 42 original derived files and 24 serialized model files, all bound to pre-existing original project hashes; [recovery proof](public-derived-recovery.json) records the exact successful public-CI source. This avoids substituting platform-dependent reauthoring for original bytes.

The [public media payload](../examples/production-pilot/media/provenance.json) contains two actual rendered MP4s, two sampled PNG storyboards and two OpenRaster drawings from the successful public Linux gate. It totals 3,480,688 bytes before the provenance JSON. The fictional characters and original licensed/attributed speech are unchanged. Public media hashes are mandatory delivery inventory checks. These outputs are new renders of original production inputs, with their own provenance; no private conversation, provider credential, fresh synthesis, historical-archive identity or new human approval is claimed. The same normal GitHub approval and complete-tree publication checks apply to these payloads.
