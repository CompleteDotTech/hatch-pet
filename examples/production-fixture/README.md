# Synthetic production regression demonstration

This example retains small acceptance and performance reports for a model-free geometric fixture. The generator recreates its editable source definitions and complete render outputs in a new directory. All review receipts are explicitly synthetic automated regression gates. It has no production-art acceptance, spoken dialogue, auditory review, human review or external application integration.

The main 23-second reel exercises idle/walk/stop with planted feet, stand/sit/stand, reach/grasp/hold/release, independent body/face/gaze/mouth tracks and an explicit full-frame override. Two additional one-second scenes reuse the exact same two character versions and cup asset. The audio consists of deterministic PCM square-wave cues.

| Scene | Frames at 12/1 fps | Duration |
| --- | ---: | ---: |
| `first-scene` | 12 | 1 second |
| `second-scene` | 12 | 1 second |
| `regression-performances` | 276 | 23 seconds |
| Total | **300** | **25 seconds** |

## Regenerate the full local renders

From the repository root, choose a new output directory and run:

```sh
python scripts/production_regression_demo.py --output-dir output/production-regression-review --movie
```

The generator writes a complete project under that destination, including generated geometric `art/`, PCM `audio/`, editable JSON, evidence, all frame/layer assets, storyboards, local previews and MP4 review movies. Full render trees are generated outputs; the paths recorded in JSON evidence are not promises that those files are hosted in this Git directory.

After regeneration, open `renders/first-scene/index.html`, `renders/second-scene/index.html` or `renders/regression-performances/index.html` inside the chosen output directory. Each scene's movie is `renders/SCENE_ID/review.mp4`; each storyboard is `SCENE_ID-storyboard.png`. Keep preview files beside their generated frames, layers and audio.

## Retained generator and evidence

| Purpose | Retained file |
| --- | --- |
| Editable project, cast, scene and clip generator | [production_regression_demo.py](../../scripts/production_regression_demo.py) |
| Current fixture gate | [acceptance.json](acceptance.json) |
| Measured performance | [performance-evidence.json](performance-evidence.json) |

Only this README and the two linked evidence JSON files are retained in this example directory in Git. Project/cast/scene/clip JSON, coverage, dependency snapshots, review history and renders are generated locally by the command above.

The fresh verification built all three scenes in an isolated directory, validated 300 actual frames and PCM timing, and reused all 300 frames on the verification pass. The retained acceptance and performance JSON hashes match the saved local fresh-run report. Four declared planted stances measure zero drift; pickup/putdown positions and ownership boundaries are exact in this fixture.

Those checks establish the documented geometric and file/timing behavior. They do not approve production anatomy, naturalistic motion, speech, listening quality or human acceptance. The separate local production validation report records the non-fixture pilot, real-browser exercises, editor adapter evidence and current delivery limits; public production-evidence publication is incomplete.
