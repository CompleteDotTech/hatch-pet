"""Observe the v1 continuity boundary for issue #112 using synthetic data only.

Run from the repository root: python tests/continuity_baseline_probe.py
This is an audit probe, not a specification freezing the observed limitations.
It never reads or changes the retained production pilot or records a review.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from production_contracts import load_project
from production_fixture import build_fixture_project, refresh_project_hashes, track, write_json
from production_performance import evaluate_instance_performance, prop_owner


def observe_project(root, mutate):
    path = build_fixture_project(root)
    bundle = load_project(path)
    first, second = copy.deepcopy(bundle["scenes"])
    mutate(first, second)
    write_json(root / "first-scene.json", first)
    write_json(root / "second-scene.json", second)
    refresh_project_hashes(root)
    try:
        load_project(path)
    except ValueError as error:
        return {"accepted": False, "error": str(error)}
    return {"accepted": True}


def main():
    with tempfile.TemporaryDirectory(prefix="hatch-continuity-audit-") as temporary:
        root = Path(temporary)
        bundle = load_project(build_fixture_project(root / "base"))
        shot = copy.deepcopy(bundle["shots"]["exchange"])
        actor = shot["instances"][0]
        actor["tracks"]["root"] = {"offset": track([0, 0], [12, 0], end=12)}
        prop = shot["props"][0]
        observations = {
            "evidence_kind": "synthetic_software_contract_probe",
            "production_art_approval": False,
            "terminal_root_position": {
                str(frame): evaluate_instance_performance(bundle, shot, actor, frame)["position"]
                for frame in (11, 12)
            },
            "ownership_at_handoff": {str(frame): prop_owner(prop, frame) for frame in (5, 6, 12)},
        }

        def reset_position(first, second):
            second["shots"][0]["instances"][0]["position"][0] += 1

        def reset_without_link(first, second):
            reset_position(first, second)
            second["continuity"] = []

        def wrong_owner(first, second):
            second["shots"][0]["props"][0].update(
                owner="a", attachment={"instance": "a", "component": "hand", "anchor": "grip"}
            )

        def attachment_change(first, second):
            second["shots"][0]["props"][0]["attachment"].update(component="body", anchor="hand")

        def duplicate_character_owner(first, second):
            for scene in (first, second):
                duplicate = copy.deepcopy(scene["shots"][0]["instances"][1])
                duplicate["id"] = "b-copy"
                scene["shots"][0]["instances"].append(duplicate)
            second["shots"][0]["props"][0].update(
                owner="b-copy", attachment={"instance": "b-copy", "component": "hand", "anchor": "grip"}
            )

        for name, mutation in (
            ("declared_position_mismatch", reset_position),
            ("authored_reset_without_link", reset_without_link),
            ("different_character_owner", wrong_owner),
            ("same_owner_attachment_change", attachment_change),
            ("different_instance_same_character_owner", duplicate_character_owner),
        ):
            observations[name] = observe_project(root / name, mutation)
        print(json.dumps(observations, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
