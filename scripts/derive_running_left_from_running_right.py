#!/usr/bin/env python3
"""Conditionally derive running-left by mirroring the approved running-right strip."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image, ImageOps
from profile_spec import load_profile

RUNNING_FRAME_COUNT = next(s['frames'] for s in load_profile()['states'] if s['id'] == 'running-right')


def load_manifest(run_dir: Path) -> dict[str, object]:
    path = run_dir / "imagegen-jobs.json"
    if not path.exists():
        raise SystemExit(f"job manifest not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def job_list(manifest: dict[str, object]) -> list[dict[str, object]]:
    jobs = manifest.get("jobs")
    if not isinstance(jobs, list):
        raise SystemExit("invalid imagegen-jobs.json: jobs must be a list")
    return [job for job in jobs if isinstance(job, dict)]


def find_job(manifest: dict[str, object], job_id: str) -> dict[str, object]:
    for job in job_list(manifest):
        if job.get("id") == job_id:
            return job
    raise SystemExit(f"unknown job id: {job_id}")


def image_metadata(path: Path) -> dict[str, object]:
    with Image.open(path) as image:
        image.verify()
    with Image.open(path) as image:
        return {
            "width": image.width,
            "height": image.height,
            "mode": image.mode,
            "format": image.format,
        }


def manifest_relative(path: Path, run_dir: Path) -> str:
    return str(path.resolve().relative_to(run_dir.resolve()))


def mirror_strip_preserving_frame_order(
    source: Image.Image,
    frame_count: int = RUNNING_FRAME_COUNT,
) -> Image.Image:
    rgba = source.convert("RGBA")
    mirrored = Image.new("RGBA", rgba.size, (0, 0, 0, 0))
    slot_width = rgba.width / frame_count
    for index in range(frame_count):
        left = round(index * slot_width)
        right = round((index + 1) * slot_width)
        mirrored.alpha_composite(
            ImageOps.mirror(rgba.crop((left, 0, right, rgba.height))),
            (left, 0),
        )
    return mirrored


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", required=True)
    parser.add_argument(
        "--confirm-appropriate-mirror",
        action="store_true",
        help="Required after visually confirming the rightward strip can be mirrored without identity/prop issues.",
    )
    parser.add_argument(
        "--decision-note",
        required=True,
        help="Short note explaining why mirroring is acceptable for this pet.",
    )
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    if not args.confirm_appropriate_mirror:
        raise SystemExit("refusing to mirror without --confirm-appropriate-mirror")
    if not args.decision_note.strip():
        raise SystemExit("--decision-note must explain why mirroring is appropriate")

    # Compatibility entry point shares the controller's locking and invalidation gates.
    from hatch import ownership, manifest, derive
    run_dir = Path(args.run_dir).expanduser().resolve()
    with ownership(run_dir):
        result = derive(run_dir, manifest(run_dir), "running-left", args.decision_note,
                        args.confirm_appropriate_mirror)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
