# Decomposition integration validation

Verified on 2026-10-20 against main `c69756fa92c03de8627064e0af1d38c954344ae2`.

The integration retains the style catalog, character-state library and decomposition commands. A compiled state selection can be reused with an imported decomposed base while its component references, identity and original selection survive retries. No artwork generation or semantic acceptance is implied.

The repairs enforce UTF-8 CLI output, read Unicode test evidence explicitly, validate original ZIP member names before host normalization, and pass large playback programs to Node through stdin instead of exceeding Windows command-line limits. Malicious ZIP fixtures preserve their actual stored names on both platforms.

## Final checks

- The complete Linux regression discovered **599 tests**: **584 passed**, with 15 Node runtime cases skipped because Node was absent from that process's PATH. The same 15 cases then passed with installed Node 24.18.0. All 599 distinct cases were exercised successfully, with no remaining untested cases or failures. The complete run took 304.379 seconds; the Node supplement took 2.028 seconds.
- Windows-focused validation ran **61 tests**, with 60 passes and one host-permission symlink skip; the corresponding symlink case passed under Linux. All eight standalone catalog CLI tests also passed on Windows.
- The complete run used a byte-verified Linux copy and checked that its source inventory remained unchanged throughout. Python 3.14.4, Pillow 12.2.0 and Playwright 1.57.0 exercised actual Chromium exports and the decomposition editor. Windows checks used Python 3.14.3, Pillow 12.2.0 and Playwright 1.58.0.
- Schema generation checks, compilation, skill metadata validation and whitespace checks of the PR changes passed. The default Codex profile remains byte-identical.
- The authored creature example produced 13 actual transparent component assets, exported/reloaded them, and prepared an ordinary forward run. Its original/foreground/reconstruction comparison was visually inspected. This is a deterministic fixture with pending semantic review, not production-art acceptance.

Reproduce the suite with Node available on PATH and Chromium installed:

```bash
HATCH_DECOMPOSITION_BROWSER_TEST=1 python -m unittest discover -s tests -v
python scripts/generate_schemas.py --check
python examples/decomposition/build_fixture.py --case creature --output-dir output/decomposition-creature
```

No live installation, production image generation or external application integration was performed during this repair.
