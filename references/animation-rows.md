# Default Codex animation contract

Generated from profiles/codex-v1.json by python scripts/profile_spec.py --table. The default remains eight columns, nine rows, 192x208 cells, and a 1536x1872 atlas.

| Row | State | Frames | Durations (ms) | Purpose |
| ---: | --- | ---: | --- | --- |
| 0 | idle | 6 | 280, 110, 110, 140, 140, 320 | calm resting, breathing and blinking |
| 1 | running-right | 8 | 120, 120, 120, 120, 120, 120, 120, 220 | rightward drag locomotion |
| 2 | running-left | 8 | 120, 120, 120, 120, 120, 120, 120, 220 | leftward drag locomotion |
| 3 | waving | 4 | 140, 140, 140, 280 | greeting or attention gesture |
| 4 | jumping | 5 | 140, 140, 140, 140, 280 | anticipation, lift, airborne peak, descent and settle |
| 5 | failed | 8 | 140, 140, 140, 140, 140, 140, 140, 240 | blocked, failed or cancelled reaction |
| 6 | waiting | 6 | 150, 150, 150, 150, 150, 260 | waiting for approval, help or user input |
| 7 | running | 6 | 120, 120, 120, 120, 120, 220 | active task work or processing; not foot-running |
| 8 | review | 6 | 150, 150, 150, 150, 150, 280 | focused inspection of completed output |

Unused cells are transparent. Default reduced motion uses idle frame zero. Only explicitly approved framewise mirroring of running-right into running-left can replace generation. See qa-rubric.md for semantic review.
