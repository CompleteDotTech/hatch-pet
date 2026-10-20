# Real 3D engineering demonstrations

These procedural characters exercise actual geometry, skinning, skeletal controls and animation. They are **synthetic engineering fixtures**, with production visual approval pending. [Acceptance measurements](../../references/3d-rigging-acceptance.md) describe verified results and limitations; [acceptance.json](acceptance.json) provides hashes, measured metrics and artifact paths.

| Fixture | Executable motions | Inspectable assets |
| --- | --- | --- |
| Humanoid | Neutral, walk, wave, reach, crouch, blink | [Pose sheet](humanoid/preview/pose-sheet.png), [animated GLB](humanoid/exports/character.glb), [editable Blender](humanoid/exports/character.blend), [silent preview](humanoid/preview/frames/animation.webp), [archive](packages/humanoid.zip) |
| Quadruped | Neutral, walk, trot, sit, tail wag, head turn | [Pose sheet](quadruped/preview/pose-sheet.png), [animated GLB](quadruped/exports/character.glb), [editable Blender](quadruped/exports/character.blend), [silent preview](quadruped/preview/frames/animation.webp), [archive](packages/quadruped.zip) |
| Six-legged winged creature | Neutral, walk, wing flap, tail curl, gaze, combined appendage motion | [Pose sheet](winged-creature/preview/pose-sheet.png), [animated GLB](winged-creature/exports/character.glb), [editable Blender](winged-creature/exports/character.blend), [silent preview](winged-creature/preview/frames/animation.webp), [archive](packages/winged-creature.zip) |
| Robot arm/gripper | Neutral, hinge sweep, gripper slide | [Pose sheet](robotic/preview/pose-sheet.png), [animated GLB](robotic/exports/character.glb), [editable Blender](robotic/exports/character.blend), [archive](packages/robotic.zip) |
| Taller humanoid | Proportion-aware walk retarget | [Pose sheet](humanoid-retarget/preview/pose-sheet.png), [GLB](humanoid-retarget/exports/character.glb), [retarget report](humanoid-retarget/validation/retarget.json), [archive](packages/humanoid-retarget.zip) |
| Smaller quadruped | Proportion-aware walk retarget | [Pose sheet](quadruped-retarget/preview/pose-sheet.png), [GLB](quadruped-retarget/exports/character.glb), [retarget report](quadruped-retarget/validation/retarget.json), [archive](packages/quadruped-retarget.zip) |

Each directory contains `source/`, `rig.json`, `identity.json`, `job.json`, `geometry/`, immutable `rig/` revisions and weights, `animations/`, `exports/`, `validation/` and `preview/`. Source GLBs and source-bound landmark/region annotations are retained exactly. The humanoid includes a real locked manual weight correction. All four principal fixtures include a self-contained `review-ui/`; serve one folder over localhost:

```bash
python -m http.server 8765 --bind 127.0.0.1 --directory examples/rig-3d/winged-creature/review-ui
```

Open `http://127.0.0.1:8765/`. Choose a clip and play or scrub; inspect the skeleton, selected-bone weights, IK targets, morphs and socket/contact markers. Download edited poses or hash-bound corrections for the CLI. The viewer uses locally retained Three.js modules and the real exported GLB.

The four `preview/blender/` folders contain actual transparent Cycles CPU frames rendered from the saved `.blend` files. Their `validation/blender-preview.json` reports retain time, source and frame hashes. These complement the native CPU pose sheets and actual Three.js screenshots.

To recreate the complete set from the deterministic mesh generator and annotations:

```bash
python scripts/verify_rig_demos.py --generate --destination output/new-rig-demos \
  --blender --browser --validator --render --archives
```

The new destination must not already exist. Tool installation and ordinary user-model import are documented in [the 3D workflow guide](../../references/3d-rigging.md). The archives were individually restored and the restored rigs evaluated; an archive hash alone is not the acceptance test.
