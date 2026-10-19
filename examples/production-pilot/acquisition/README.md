# Real artwork acquisition

The `milo` and `luma` directories are real non-fixture hatch runs. Each has one
base claim and one construction-sheet claim. Both claims were executed through
the installed imagegen skill with true transparency and all required local
attachments, then ingested with the exact claimed input hashes. The four retained
original PNGs live under `art/originals` after source restoration.

The `token` values in these receipts are **local job correlation UUIDs** created
by `uuid.uuid4().hex` in `scripts/hatch.py::claim`. They authorize no provider,
GitHub account, network service or application. `ingest` and `fail` compare them
only with the local run file to reconcile the same attempt. Retaining these
non-secret correlations is necessary to preserve the real claim identity and
attempt history requested for this demonstration. No API credential is included.

The image-generation handoff did not expose provider request IDs, model IDs, or
provider parameter metadata. These fields remain null with an explicit reason.
Local image output filenames are not presented as provider identifiers.

Milo and Luma version 3.0.0 replace lost earlier workspace artifacts. The separate
loss disclosure retains the observed call counts and available facts; old
artwork and review receipts cannot be reconstructed and establish no acceptance
of the current versions. The current replacement pass is bounded at four calls,
two per run, with one attempt per job. All four calls completed and were ingested.

The four-view designs were visually inspected before component generation.
Component segmentation, alpha checks and successful ingestion are separate from
approval of character construction, motion or acting. The generated sheets
contain wrist caps and complete muzzle patches; the deterministic recipe retains
the sources, records exact crop/registration/mask decisions, and requires fresh
assembled-character and shot review.
