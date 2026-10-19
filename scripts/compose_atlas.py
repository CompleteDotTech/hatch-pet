#!/usr/bin/env python3
"""Compose or normalize a Codex pet spritesheet atlas."""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image

from profile_spec import load_profile, profile_for_run, indexed_frames, row_specs

PROFILE = load_profile()
COLUMNS = PROFILE['layout']['columns']
ROWS = len(PROFILE['states'])
CELL_WIDTH = PROFILE['layout']['cell_width']
CELL_HEIGHT = PROFILE['layout']['cell_height']
ATLAS_WIDTH = COLUMNS * CELL_WIDTH
ATLAS_HEIGHT = ROWS * CELL_HEIGHT
ATLAS_ASPECT_RATIO = ATLAS_WIDTH / ATLAS_HEIGHT
ROW_SPECS = row_specs(PROFILE)
IMAGE_SUFFIXES = {".png", ".webp", ".jpg", ".jpeg"}


def image_files(path: Path) -> list[Path]:
    return sorted(p for p in path.iterdir() if p.suffix.lower() in IMAGE_SUFFIXES)


def find_row_frames(root: Path, state: str, row_index: int, count=None) -> list[Path]:
    if count is None:
        count = next(n for name, _, n in ROW_SPECS if name == state)
    return indexed_frames(root, state, count)


def paste_centered(atlas: Image.Image, source: Image.Image, row: int, column: int, profile=None) -> None:
    p = load_profile(profile)
    CELL_WIDTH, CELL_HEIGHT = p["layout"]["cell_width"], p["layout"]["cell_height"]
    frame = source.convert("RGBA")
    if frame.size != (CELL_WIDTH, CELL_HEIGHT):
        raise ValueError(f"frame must already match profile cell {CELL_WIDTH}x{CELL_HEIGHT}; got {frame.size}")
    left = column * CELL_WIDTH + (CELL_WIDTH - frame.width) // 2
    top = row * CELL_HEIGHT + (CELL_HEIGHT - frame.height) // 2
    atlas.alpha_composite(frame, (left, top))


def compose_from_source_atlas(path: Path, resize_source: bool, profile=None) -> Image.Image:
    p = load_profile(profile)
    CELL_WIDTH, CELL_HEIGHT = p["layout"]["cell_width"], p["layout"]["cell_height"]
    ATLAS_WIDTH, ATLAS_HEIGHT = p["layout"]["width"], p["layout"]["height"]
    ATLAS_ASPECT_RATIO = ATLAS_WIDTH / ATLAS_HEIGHT
    ROW_SPECS = row_specs(p)
    with Image.open(path) as opened:
        source = opened.convert("RGBA")
    if source.size != (ATLAS_WIDTH, ATLAS_HEIGHT):
        if not resize_source:
            raise SystemExit(
                f"source atlas must be {ATLAS_WIDTH}x{ATLAS_HEIGHT}; got {source.width}x{source.height}"
            )
        source_ratio = source.width / source.height
        if abs(source_ratio - ATLAS_ASPECT_RATIO) > 0.02:
            raise SystemExit(
                "refusing to resize source atlas because its aspect ratio does not match "
                f"the Codex atlas ratio {ATLAS_ASPECT_RATIO:.3f}; got {source_ratio:.3f}. "
                "Generate exact atlas dimensions or use --frames-root."
            )
        source = source.resize((ATLAS_WIDTH, ATLAS_HEIGHT), Image.Resampling.LANCZOS)

    atlas = Image.new("RGBA", (ATLAS_WIDTH, ATLAS_HEIGHT), (0, 0, 0, 0))
    for _state, row, frame_count in ROW_SPECS:
        for column in range(frame_count):
            left = column * CELL_WIDTH
            top = row * CELL_HEIGHT
            cell = source.crop((left, top, left + CELL_WIDTH, top + CELL_HEIGHT))
            atlas.alpha_composite(cell, (left, top))
    return atlas


def compose_from_frames(root: Path, profile=None) -> Image.Image:
    p = profile_for_run(root, profile)
    atlas = Image.new('RGBA', (p['layout']['width'], p['layout']['height']), (0,0,0,0))
    for state, row, frame_count in row_specs(p):
        files = indexed_frames(root, state, frame_count)
        for column, frame_path in enumerate(files):
            with Image.open(frame_path) as frame:
                paste_centered(atlas, frame, row, column, p)
    return atlas


def clear_transparent_rgb(image: Image.Image) -> Image.Image:
    rgba = image.convert("RGBA")
    data = bytearray(rgba.tobytes())
    for index in range(0, len(data), 4):
        if data[index + 3] == 0:
            data[index] = 0
            data[index + 1] = 0
            data[index + 2] = 0
    return Image.frombytes("RGBA", rgba.size, bytes(data))


def save_outputs(atlas: Image.Image, output: Path, webp_output: Path | None) -> None:
    atlas = clear_transparent_rgb(atlas)
    output.parent.mkdir(parents=True, exist_ok=True)
    atlas.save(output)
    if webp_output is not None:
        webp_output.parent.mkdir(parents=True, exist_ok=True)
        atlas.save(
            webp_output,
            format="WEBP",
            lossless=True,
            quality=100,
            method=6,
            exact=True,
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--source-atlas")
    source.add_argument("--frames-root")
    parser.add_argument("--output", required=True)
    parser.add_argument("--profile")
    parser.add_argument("--webp-output")
    parser.add_argument(
        "--resize-source",
        action="store_true",
        help="Resize a lower-resolution source atlas only when it already has the Codex atlas aspect ratio.",
    )
    args = parser.parse_args()

    if args.source_atlas:
        atlas = compose_from_source_atlas(
            Path(args.source_atlas).expanduser().resolve(), args.resize_source, args.profile
        )
    else:
        atlas = compose_from_frames(Path(args.frames_root).expanduser().resolve(), args.profile)

    save_outputs(
        atlas,
        Path(args.output).expanduser().resolve(),
        Path(args.webp_output).expanduser().resolve() if args.webp_output else None,
    )
    print(f"wrote {Path(args.output).expanduser().resolve()}")
    if args.webp_output:
        print(f"wrote {Path(args.webp_output).expanduser().resolve()}")


if __name__ == "__main__":
    main()
