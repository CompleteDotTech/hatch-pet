#!/usr/bin/env python3
"""Render lightweight animated QA previews from extracted Codex pet frames."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image

from profile_spec import load_profile, profile_for_run, indexed_frames

ROW_DURATIONS = {state['id']: state['durations'] for state in load_profile()['states']}
IMAGE_SUFFIXES = {".png", ".webp", ".jpg", ".jpeg"}


def frame_files(state_dir: Path) -> list[Path]:
    if not state_dir.is_dir():
        return []
    return sorted(path for path in state_dir.iterdir() if path.suffix.lower() in IMAGE_SUFFIXES)


def load_frames(frames_root: Path, state: str, expected_count: int) -> list[Image.Image]:
    files = indexed_frames(frames_root, state, expected_count)
    if len(files) != expected_count:
        raise SystemExit(
            f"{state} preview needs {expected_count} frames, found {len(files)} under {frames_root / state}"
        )
    frames = []
    for path in files:
        with Image.open(path) as opened:
            frames.append(opened.convert("RGBA"))
    return frames


def save_preview(frames: list[Image.Image], durations: list[int], output: Path,
                 mode: str = 'loop', hold_frame: int = 0) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    if mode not in ('loop', 'once', 'hold'):
        raise ValueError('unsupported preview playback mode: ' + mode)
    if not frames or not 0 <= hold_frame < len(frames) or len(durations) != len(frames):
        raise ValueError('preview requires aligned frames, durations and a valid hold frame')
    selected = [frames[hold_frame]] if mode == 'hold' else frames
    timing = [durations[hold_frame]] if mode == 'hold' else durations
    # Omitting the GIF loop extension means one play. A loop value of 1 would
    # request a repeat in common GIF consumers, so it is not a one-shot.
    options = {'loop': 0} if mode == 'loop' else {}
    selected[0].save(
        output,
        save_all=True,
        append_images=selected[1:],
        duration=timing,
        disposal=2,
        optimize=False,
        **options,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frames-root", required=True)
    parser.add_argument("--profile")
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    frames_root = Path(args.frames_root).expanduser().resolve()
    output_dir = Path(args.output_dir).expanduser().resolve()
    profile = profile_for_run(frames_root, args.profile)
    previews = []
    for spec in profile['states']:
        state, durations = spec['id'], spec['durations']
        frames = load_frames(frames_root, state, len(durations))
        output = output_dir / f"{state}.gif"
        playback = spec.get('playback', {})
        save_preview(frames, durations, output, playback.get('mode', 'loop'), playback.get('hold_frame', 0))
        previews.append({"state": state, "path": str(output), "frames": len(frames)})

    result = {"ok": True, "output_dir": str(output_dir), "previews": previews}
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
