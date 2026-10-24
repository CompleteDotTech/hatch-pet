# Timing implementation evidence

Local stack base: #16860acf5cc23567ea0cb3e29d48092d62d153a00d1; #167 publicPR208 pending. No merge/publication claim.

Initial native lifecycle run:46tests PASS36.191seconds, zero skips. Initial timing numerical run:4tests PASS14.044seconds, including six genuine PyBullet simulations at integer24,NTSC30000/1001 and fractional47/2fps with480Hz effective solver steps. `initial-numerical.json` contains actual backend identities, cache/input/output hashes, resource measurements and numerical errors. Source was subsequently extended with explicit per-sample bracket receipts and a Blender numerical oracle; these initial records are preliminary, not final exact-commit acceptance.

`contention.log` preserves a failed static suite: the empty-interpreter discovery test collided with #168's exclusive global slot and returned degraded instead of unavailable. No failure was suppressed; the entire46-test native suite passed after explicit ownership transfer.

Pinned host: /home/complete/.cache/hatch-fleet/rig-py312/bin/python -B
Blender: /home/complete/.cache/hatch-fleet/blender-4.5.3-linux-x64/blender
PyBullet interpreter: /home/complete/.cache/hatch-fleet/pybullet311/bin/python

Tests use `PYTHONPATH=scripts HATCH_PHYSICS_BACKEND_TEST=1 HATCH_BLENDER=... HATCH_PYBULLET_PYTHON=...` and unittest discovery for `test_rig_physics_backends.py` / `test_physics_timing.py`. Set `HATCH_TIMING_EVIDENCE=/absolute/new/directory/numerical.json` to retain actual sampled caches alongside numerical evidence; the artifact directory must not already exist.

No human visual or artistic approval is implied by these numerical checks.

Final runtime: ec9f120. Final test-retention HEAD: a09930f (runtime unchanged). Final local dependency is actual independent Astra PASS1682e1190c, normally merged with Scene59 integer-parity and mainB. `validation.json` binds exact source-file SHA256 values and these checks:

- 48 actual Blender/PyBullet lifecycle tests: PASS47.751seconds, zero skips.
- Six timing tests: PASS34.892seconds, zero skips, including two actual Blender bakes/native reopens/consumption controls, six real PyBullet simulations, paired pinned-output equality, analytic physical errors, rational seeking, terminal boundaries and legacy-cache verification.
- 22 strict physics contract tests: PASS1.543seconds.
- 67 Scene3D contract tests: PASS12.009seconds.
- Generated physics schema consistency: PASS.

`executed/blender-artifacts/{24,30000}` retain actual native `.blend` caches, diagnostic PNGs, complete hash manifests and numerical states; `executed/blender-numerical.json` records numerical errors/tolerances/settings/backend/resource identities. `executed/artifacts` retains all six PyBullet sampled caches, every actual solver-step state, exact timing brackets and contacts. `executed/numerical.json` records paired reproduction classification, numerical errors/tolerances, backend/settings/seed/hardware/resource records and hashes. All remain engineering fixtures and unreviewed visually. Source files and retained #168 caches were preserved.
