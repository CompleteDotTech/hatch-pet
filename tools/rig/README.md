# Optional 3D toolchain

These dependencies are separate from ordinary Hatch 2D execution.

| Tool | Tested pin |
| --- | --- |
| Python | 3.12.14 locally; 3.12 in CI |
| NumPy | 2.3.5 |
| jsonschema | 4.25.1 |
| Pillow | 12.3.0 in the recorded 3D test environment |
| Playwright | 1.55.0; Chromium 140.0.7339.16 |
| pygltflib | 1.16.5 |
| Three.js | 0.180.0; offline vendor files include license/hash manifest |
| Khronos glTF Validator | 2.0.0-dev.3.10 |
| Blender | 4.5.3 LTS; build hash `67807e1800cc` |

`npm ci --ignore-scripts --prefix tools/rig` installs the locked independent validator and source package. The production review bundle uses the committed, locally vendored subset of Three.js. No runtime CDN is needed. Set `HATCH_GLTF_VALIDATOR_ROOT` only when intentionally using a different local installation of the same pinned validator.

## Blender Linux x64

Download `https://download.blender.org/release/Blender4.5/blender-4.5.3-linux-x64.tar.xz` and verify SHA-256 before extracting:

```text
975c58fcb244273838534bba771e64ad87739216b0f9b39a888531a49a72d845
```

Set `HATCH_BLENDER` to the extracted executable. The adapter uses headless CPU execution and disables automatic project scripts. The local engineering environment used a checksum-verified installation trimmed of optional headers, translations, unrelated add-ons, GPU plugin payloads and an optional Mesa fallback to fit a shared disk. The tested glTF importer/exporter, armature evaluation and save/reopen operations remained functional. CI installs the complete official archive.

The worker always comes from this repository, accepts bounded JSON data, checks subprocess exit status and output, and enforces a timeout. Packed `.blend` input is required: make linked libraries local and pack textures first. No arbitrary manifest hook is executed.

## Offline viewer license

Three.js is MIT licensed. Its original license and exact vendored-file SHA-256 inventory are in `assets/rig-viewer/vendor/`. The Khronos validator is installed from its package, preserving its supplied license. Blender is an external GPL application, not redistributed in this repository.
