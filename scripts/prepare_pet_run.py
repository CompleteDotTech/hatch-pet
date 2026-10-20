#!/usr/bin/env python3
"""Create a Codex pet run folder, prompts, and imagegen job manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from PIL import Image
from PIL import ImageDraw
from profile_spec import load_profile
from asset_contracts import validate_identity, reference_roles, check_image

# Module defaults come from the same profile as every deterministic consumer.
_DEFAULT_PROFILE = load_profile()
ATLAS = dict(_DEFAULT_PROFILE["layout"])
ROWS = [(s["id"], i, s["frames"], s["purpose"]) for i, s in enumerate(_DEFAULT_PROFILE["states"])]

PET_SAFE_STYLE = (
    "Pet-safe sprite: compact full-body mascot, readable at the selected profile cell size, "
    "clear silhouette, simple face, stable palette/materials, and crisp edges "
    "for alpha or selected chroma-key extraction."
)

STYLE_PRESETS = {
    "auto": (
        "Infer the most appropriate pet-safe style from the user request and "
        "reference images, then keep that exact style consistent across every row."
    ),
    "pixel": (
        "Pixel-art-adjacent digital mascot with a chunky silhouette, simple dark "
        "outline, limited palette, flat cel shading, and visible stepped edges."
    ),
    "plush": (
        "Soft plush toy mascot with rounded stitched forms, fuzzy fabric feel, "
        "simple sewn details, and readable toy-like proportions."
    ),
    "clay": (
        "Handmade clay or polymer-clay mascot with rounded sculpted forms, soft "
        "material texture, simple features, and clean readable edges."
    ),
    "sticker": (
        "Polished sticker mascot with bold clean shapes, crisp outline, flat "
        "colors, and minimal highlight detail."
    ),
    "flat-vector": (
        "Flat vector-style mascot with simple geometric forms, crisp color areas, "
        "clean outline, and minimal shading."
    ),
    "3d-toy": (
        "Stylized 3D toy mascot with smooth rounded forms, simple materials, "
        "clear silhouette, and no photoreal complexity."
    ),
    "painterly": (
        "Painterly mascot with simplified brush texture, readable forms, stable "
        "palette, and enough edge clarity for clean extraction."
    ),
    "brand-inspired": (
        "Brand-inspired mascot using approved public or user-provided brand cues "
        "such as colors, mascot themes, and vibe while avoiding readable text or "
        "logo copying unless explicitly approved."
    ),
}

CHROMA_KEY_CANDIDATES = [
    ("magenta", "#FF00FF"),
    ("cyan", "#00FFFF"),
    ("yellow", "#FFFF00"),
    ("blue", "#0000FF"),
    ("orange", "#FF7F00"),
    ("green", "#00FF00"),
]

DEFAULT_PET_NAME = "Sprout"
CANONICAL_BASE_PATH = "references/canonical-base.png"
BRAND_DISCOVERY_PATH = "references/brand-discovery.md"
LAYOUT_GUIDE_DIR = "references/layout-guides"
LAYOUT_GUIDE_SAFE_MARGIN_X = 18
LAYOUT_GUIDE_SAFE_MARGIN_Y = 16


def slugify(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    value = re.sub(r"-{2,}", "-", value)
    return value.strip("-")


def display_from_slug(value: str) -> str:
    words = [word for word in re.split(r"[^a-zA-Z0-9]+", value.strip()) if word]
    return " ".join(word.capitalize() for word in words)


def concept_words(value: str) -> list[str]:
    stop_words = {
        "a",
        "an",
        "and",
        "app",
        "based",
        "codex",
        "compact",
        "digital",
        "for",
        "from",
        "in",
        "of",
        "on",
        "pet",
        "ready",
        "small",
        "the",
        "to",
        "with",
    }
    words = [
        word.lower()
        for word in re.findall(r"[a-zA-Z0-9]+", value)
        if word.lower() not in stop_words
    ]
    return words


def infer_name(args: argparse.Namespace, reference_paths: list[Path]) -> str:
    for raw_value in [args.display_name, args.pet_name]:
        value = raw_value.strip()
        if value:
            return value

    if args.pet_id.strip():
        display = display_from_slug(args.pet_id)
        if display:
            return display

    for raw_value in [args.pet_notes, args.description, args.brand_name]:
        words = concept_words(raw_value)
        if words:
            return words[0].capitalize()

    for path in reference_paths:
        display = display_from_slug(path.stem)
        if display:
            return display

    return DEFAULT_PET_NAME


def sentence(value: str) -> str:
    value = " ".join(value.strip().split())
    if not value:
        return value
    if value[-1] not in ".!?":
        value += "."
    return value


def infer_description(args: argparse.Namespace, reference_paths: list[Path]) -> str:
    if args.description.strip():
        return sentence(args.description)
    if args.pet_notes.strip():
        return sentence(f"An animated character: {args.pet_notes}")
    if args.brand_name.strip():
        return sentence(f"An animated character inspired by {args.brand_name}")
    if reference_paths:
        return "An animated character based on the provided reference image."
    return "An original character ready for animation."


def infer_pet_notes(args: argparse.Namespace, reference_paths: list[Path]) -> str:
    if args.pet_notes.strip():
        return args.pet_notes.strip()
    if args.description.strip():
        return args.description.strip().rstrip(".")
    if args.brand_name.strip():
        return f"a compact mascot inspired by {args.brand_name.strip()}"
    if reference_paths:
        return "the pet shown in the reference image(s)"
    return "a compact original Codex pet"


def default_output_dir(pet_id: str) -> Path:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return Path.cwd() / "output" / "hatch-pet" / f"{pet_id}-{timestamp}"


def rel(path: Path, root: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def image_metadata(path: Path) -> dict[str, object]:
    check_image(path)
    with Image.open(path) as image:
        return {
            "path": str(path),
            "width": image.width,
            "height": image.height,
            "mode": image.mode,
            "format": image.format,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }


def draw_dashed_line(
    draw: ImageDraw.ImageDraw,
    start: tuple[int, int],
    end: tuple[int, int],
    *,
    fill: str,
    dash: int = 8,
    gap: int = 6,
) -> None:
    x1, y1 = start
    x2, y2 = end
    if x1 == x2:
        step = dash + gap
        for y in range(min(y1, y2), max(y1, y2), step):
            draw.line((x1, y, x2, min(y + dash, max(y1, y2))), fill=fill)
        return
    if y1 == y2:
        step = dash + gap
        for x in range(min(x1, x2), max(x1, x2), step):
            draw.line((x, y1, min(x + dash, max(x1, x2)), y2), fill=fill)
        return
    raise ValueError("draw_dashed_line only supports horizontal or vertical lines")


def create_layout_guide(path: Path, state: str, frames: int) -> dict[str, object]:
    width = frames * ATLAS["cell_width"]
    height = ATLAS["cell_height"]
    cell_width = ATLAS["cell_width"]
    image = Image.new("RGB", (width, height), "#f7f7f7")
    draw = ImageDraw.Draw(image)

    for index in range(frames):
        left = index * cell_width
        right = left + cell_width - 1
        draw.rectangle((left, 0, right, height - 1), outline="#111111", width=2)

        margin_x = min(LAYOUT_GUIDE_SAFE_MARGIN_X, max(0, (cell_width - 1) // 4))
        margin_y = min(LAYOUT_GUIDE_SAFE_MARGIN_Y, max(0, (height - 1) // 4))
        safe_left = left + margin_x
        safe_top = margin_y
        safe_right = right - margin_x
        safe_bottom = height - 1 - margin_y
        draw.rectangle(
            (safe_left, safe_top, safe_right, safe_bottom),
            outline="#2f80ed",
            width=2,
        )

        center_x = left + cell_width // 2
        center_y = height // 2
        draw_dashed_line(
            draw,
            (center_x, safe_top),
            (center_x, safe_bottom),
            fill="#b8b8b8",
        )
        draw_dashed_line(
            draw,
            (safe_left, center_y),
            (safe_right, center_y),
            fill="#b8b8b8",
        )

    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)
    return {
        "state": state,
        "path": str(path),
        "width": width,
        "height": height,
        "frames": frames,
        "cell_width": ATLAS["cell_width"],
        "cell_height": ATLAS["cell_height"],
        "safe_margin_x": margin_x,
        "safe_margin_y": margin_y,
        "usage": "layout guide input only; do not copy visible guide lines into generated sprite strips",
    }


def create_layout_guides(run_dir: Path) -> list[dict[str, object]]:
    guide_dir = run_dir / LAYOUT_GUIDE_DIR
    return [
        create_layout_guide(guide_dir / f"{state}.png", state, frames)
        for state, _row, frames, _purpose in ROWS
    ]


def parse_hex_color(value: str) -> tuple[int, int, int]:
    if not re.fullmatch(r"#[0-9a-fA-F]{6}", value):
        raise SystemExit(f"invalid chroma key color: {value}; expected #RRGGBB")
    return tuple(int(value[index : index + 2], 16) for index in (1, 3, 5))


def rgb_to_hex(rgb: tuple[int, int, int]) -> str:
    return f"#{rgb[0]:02X}{rgb[1]:02X}{rgb[2]:02X}"


def color_distance(left: tuple[int, int, int], right: tuple[int, int, int]) -> float:
    return math.sqrt(sum((left[index] - right[index]) ** 2 for index in range(3)))


def sampled_reference_pixels(paths: list[Path]) -> list[tuple[int, int, int]]:
    pixels: list[tuple[int, int, int]] = []
    for path in paths:
        with Image.open(path) as opened:
            image = opened.convert("RGBA")
            image.thumbnail((128, 128), Image.Resampling.LANCZOS)
            data = image.tobytes()
            for index in range(0, len(data), 4):
                red, green, blue, alpha = data[index : index + 4]
                if alpha <= 16:
                    continue
                pixels.append((red, green, blue))

    non_background = [
        pixel
        for pixel in pixels
        if not (pixel[0] > 244 and pixel[1] > 244 and pixel[2] > 244)
    ]
    return non_background or pixels


def choose_chroma_key(reference_paths: list[Path], requested: str) -> dict[str, object]:
    if requested.lower() != "auto":
        rgb = parse_hex_color(requested)
        return {
            "hex": rgb_to_hex(rgb),
            "rgb": list(rgb),
            "name": "user-selected",
            "selection": "manual",
        }

    pixels = sampled_reference_pixels(reference_paths)
    if not pixels:
        rgb = parse_hex_color("#FF00FF")
        return {
            "hex": "#FF00FF",
            "rgb": list(rgb),
            "name": "magenta",
            "selection": "fallback",
        }

    scored: list[tuple[float, int, str, tuple[int, int, int]]] = []
    for preference_index, (name, hex_color) in enumerate(CHROMA_KEY_CANDIDATES):
        rgb = parse_hex_color(hex_color)
        distances = sorted(color_distance(rgb, pixel) for pixel in pixels)
        percentile_index = max(0, min(len(distances) - 1, int(len(distances) * 0.01)))
        scored.append((distances[percentile_index], -preference_index, name, rgb))

    score, _preference, name, rgb = max(scored)
    return {
        "hex": rgb_to_hex(rgb),
        "rgb": list(rgb),
        "name": name,
        "selection": "auto",
        "score": round(score, 2),
    }


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def resolved_style_contract(style_preset: str, raw_style_notes: str) -> str:
    style_preset = style_preset.strip().lower()
    if style_preset not in STYLE_PRESETS:
        allowed = ", ".join(sorted(STYLE_PRESETS))
        raise SystemExit(
            f"invalid style preset: {style_preset}; expected one of: {allowed}"
        )
    raw_style_notes = raw_style_notes.strip()
    preset_contract = STYLE_PRESETS[style_preset]
    if not raw_style_notes:
        return f"{PET_SAFE_STYLE} Style `{style_preset}`: {preset_contract}"
    return (
        f"{PET_SAFE_STYLE} Style `{style_preset}`: {preset_contract} "
        f"User style notes: {raw_style_notes}."
    )


def compact(value: str) -> str:
    return " ".join(value.strip().split())


def _constraint_term(value: str) -> str:
    return " ".join(value.casefold().strip(" .;:!?").split())


def _text_list(value, label):
    if not isinstance(value, list) or any(not isinstance(x, str) or not x.strip() for x in value):
        raise ValueError(label + " must be a list of nonempty strings")
    return list(dict.fromkeys(x.strip() for x in value))


def discovery_guidance(path: Path | None) -> dict:
    """Read the established JSON or brief markdown handoff without losing avoidances."""
    if path is None:
        return {"avoid": [], "sources": [], "text": "", "uncertainty": "No researched brand guidance supplied."}
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json" or text.lstrip().startswith("{"):
        value = json.loads(text)
        if not isinstance(value, dict):
            raise ValueError("brand discovery must be an object")
        avoid = value.get("avoid", value.get("brand_avoid", []))
        if isinstance(avoid, str):
            avoid = [x.strip() for x in re.split(r"[,;]", avoid) if x.strip()]
        sources = value.get("sources", value.get("brand_sources", []))
        if isinstance(sources, str):
            sources = [sources]
        return {"avoid": _text_list(avoid, "discovery avoid"), "sources": _text_list(sources, "discovery sources"), "text": str(value.get("brief", value.get("brand_brief", value.get("summary", "")))), "uncertainty": str(value.get("uncertainty", "Inferred brand guidance; source accuracy and applicability require review."))}
    avoid, collecting = [], False
    for line in text.splitlines():
        match = re.match(r"^\s*(?:[-*]\s*)?(?:\*\*)?avoid(?:\*\*)?\s*[:=]\s*(.*)$", line, re.I)
        if match:
            raw = match[1].strip()
            if raw.startswith("["):
                avoid.extend(_text_list(json.loads(raw), "discovery avoid"))
            elif raw:
                avoid.extend(x.strip() for x in re.split(r"[,;]", raw) if x.strip())
            collecting = not bool(raw)
        elif collecting:
            item = re.match(r"^\s*[-*]\s+(.+)$", line)
            if item:
                avoid.append(item[1].strip())
            elif line.strip():
                collecting = False
    sources = list(dict.fromkeys(re.findall(r"https?://[^\s)>]+", text)))
    return {"avoid": _text_list(avoid, "discovery avoid"), "sources": sources, "text": "", "uncertainty": "Inferred from the preserved discovery brief; not a user requirement."}


def build_constraints(raw, required, avoided, discovery, brand_brief="", brand_sources=()):
    if not isinstance(raw, dict):
        raise ValueError("constraints must be a JSON object")
    constraints = json.loads(json.dumps(raw))
    constraints["require"] = _text_list(_text_list(constraints.get("require", []), "require") + list(required), "require")
    constraints["avoid"] = _text_list(_text_list(constraints.get("avoid", []), "avoid") + list(avoided), "avoid")
    required_terms = {_constraint_term(x): x for x in constraints["require"]}
    conflicts = sorted(required_terms.keys() & {_constraint_term(x) for x in constraints["avoid"]})
    if conflicts:
        raise ValueError("conflicting explicit require/avoid constraints: " + ", ".join(required_terms[x] for x in conflicts))
    constraints["brand_avoid"] = _text_list(_text_list(constraints.get("brand_avoid", []), "brand_avoid") + discovery["avoid"], "brand_avoid")
    guidance = constraints.get("brand_guidance", {})
    if not isinstance(guidance, dict):
        raise ValueError("brand_guidance must be an object")
    guidance = dict(guidance)
    if brand_brief or discovery["text"]:
        guidance["text"] = brand_brief or discovery["text"]
    guidance.setdefault("text", "")
    guidance["sources"] = _text_list(_text_list(guidance.get("sources", []), "brand_guidance.sources") + list(brand_sources) + discovery["sources"], "brand_guidance.sources")
    guidance.setdefault("inferred", True)
    if type(guidance["inferred"]) is not bool:
        raise ValueError("brand_guidance.inferred must be boolean")
    guidance.setdefault("uncertainty", discovery["uncertainty"])
    if not isinstance(guidance["text"], str) or not isinstance(guidance["uncertainty"], str):
        raise ValueError("brand guidance text and uncertainty must be strings")
    constraints["brand_guidance"] = guidance
    overridden = [x for x in constraints["brand_avoid"] if _constraint_term(x) in required_terms]
    constraints["conflicts"] = [{"requirement": required_terms[_constraint_term(x)], "inferred_avoidance": x, "resolution": "explicit user requirement takes precedence"} for x in overridden]
    constraints["effective_brand_avoid"] = [x for x in constraints["brand_avoid"] if x not in overridden]
    return constraints


def _settings(args):
    value = getattr(args, "extraction", {})
    return value if isinstance(value, dict) else {}


def _background_instructions(args):
    settings = _settings(args)
    mode = settings.get("background", "auto")
    if mode in ("alpha", "auto"):
        return "Return a true transparent alpha background. Preserve intentional holes, permitted detached details, and antialiased character edges. Do not draw a checkerboard or a solid background."
    key = settings.get("chroma_key", args.chroma_key)
    key = key.get("hex", args.chroma_key["hex"]) if isinstance(key, dict) else key
    return f"Use a perfectly flat {key} chroma-key background. Keep that key and nearby colors out of character surfaces, props, and highlights. If this conflicts with required character colors, report the collision for a different key instead of recoloring the character."


def _constraint_instructions(args):
    constraints = {**getattr(args, "constraints", {}), 'identity': getattr(args, 'identity', {})}
    return "Explicit user requirements and avoidances (preserve across retries):\n" + json.dumps({"require": constraints.get("require", []), "avoid": constraints.get("avoid", [])}, ensure_ascii=False) + "\nInferred brand guidance (subordinate to explicit user instructions; preserve sources and uncertainty):\n" + json.dumps({"guidance": constraints.get("brand_guidance", {}), "effective_avoid": constraints.get("effective_brand_avoid", []), "reported_conflicts": constraints.get("conflicts", [])}, ensure_ascii=False) + "\nComplete structured constraints for provenance:\n" + json.dumps(constraints, ensure_ascii=False)


def _profile_requirements(args, state=None):
    profile = args.profile_data
    records = [profile["generation"]]
    if state is not None:
        records.append(state["generation"])
    items = []
    for record in records:
        if record.get("instructions"):
            items.append(record["instructions"])
        items.extend(record.get("requirements", []))
    return "\n".join("- " + value for value in items)


def artwork_style(args):
    if args.profile_data['schema_version'] == 1:
        return resolved_style_contract(args.style_preset, args.style_notes)
    return f"Consistent reusable artwork; style choice: {args.style_preset}. {args.style_notes}. Follow this profile's subject and medium requirements."


def base_pet_prompt(args: argparse.Namespace) -> str:
    width, height = args.profile_data["layout"]["cell_width"], args.profile_data["layout"]["cell_height"]
    subject = 'full-body character' if args.profile_data['schema_version'] == 1 else 'asset identity'
    return f"""Create one canonical {subject} reference for `{args.pet_id}` using the installed imagegen skill.

Identity: {args.pet_notes}.
Style: {artwork_style(args)}
Preserve the approved input references. Keep the entire subject visible and readable at {width}x{height}.
{_background_instructions(args)}

Profile requirements:
{_profile_requirements(args)}

{_constraint_instructions(args)}
"""


def row_prompt(args: argparse.Namespace, state: str, row: int, frames: int, purpose: str) -> str:
    spec = next(s for s in args.profile_data["states"] if s["id"] == state)
    policy = spec["alignment"]
    detached = args.profile_data["validation"]["allow_detached_details"]
    invariants = 'face, proportions, markings, palette, material, style, and approved props' if args.profile_data['schema_version'] == 1 else 'geometry, proportions, markings, palette, materials, style and approved components'
    return f"""Create one horizontal animation strip for `{args.pet_id}`, state `{state}`, using the installed imagegen skill.

Attach every identity and layout input listed in this job, including the canonical base and all original references. Use the layout guide for slot geometry only; never draw its lines or labels.
Output exactly {frames} complete poses in left-to-right playback order, one pose in each equal-width slot, with clear gutters and no overlap or clipping.
Identity: {args.pet_notes}. Preserve the same {invariants} in every frame except explicitly approved state differences.
Style: {artwork_style(args)}
Action: {purpose}
Frame durations in playback order: {', '.join(str(value) + ' ms' for value in spec['durations'])}.
Playback behavior: {spec.get('playback', {}).get('mode', 'loop')}. {'Draw one intentionally static expressive pose.' if frames == 1 else 'Draw a meaningful pose progression; do not duplicate frames merely to fill the strip. Use the specified durations for intentional holds.'}
Motion policy: {spec['motion']}. Preserve intentional vertical motion, including jump height. Maintain one consistent source viewport and apparent character scale across the row; a wider or taller pose must not be drawn at a different scale.
Extraction alignment: {json.dumps(policy, ensure_ascii=False)}. This describes extraction; do not draw anchors or guides.
Detached character details are {'permitted by this profile when semantically intended' if detached else 'not permitted by this profile'}.
{_background_instructions(args)}

Profile requirements:
{_profile_requirements(args, spec)}

{_constraint_instructions(args)}
"""


def retry_row_prompt(args: argparse.Namespace, state: str, row: int, frames: int, purpose: str) -> str:
    return row_prompt(args, state, row, frames, purpose) + "\nRetry: repair the recorded defect while preserving every original identity, style, layout, and explicit user constraint. Do not reuse an unapproved derivation.\n"


def regenerate_prompts(run_dir: Path, request: dict, profile: dict, settings: dict, include_base=False):
    """Rebuild affected prompts after calibration; retain explicit row repair notes."""
    args = SimpleNamespace(**request)
    args.profile_data = load_profile(profile)
    args.extraction = settings
    args.constraints = request.get("constraints", {})
    args.chroma_key = request["chroma_key"]
    paths = []
    if include_base:
        write_text(run_dir / "prompts/base-pet.md", base_pet_prompt(args))
        paths.append("prompts/base-pet.md")
    for row, spec in enumerate(args.profile_data["states"]):
        for relative, generator in ((f"prompts/rows/{spec['id']}.md", row_prompt), (f"prompts/row-retries/{spec['id']}.md", retry_row_prompt)):
            path = run_dir / relative
            previous = path.read_text(encoding="utf-8") if path.exists() else ""
            repair_start = re.search(r"^Repair required:", previous, re.M)
            notes = previous[repair_start.start():].strip() if repair_start else ""
            text = generator(args, spec['id'], row, spec['frames'], spec['purpose'])
            write_text(path, text + ("\n" + notes if notes else ""))
            paths.append(relative)
    return paths


def make_jobs(run_dir: Path, copied_refs: list[dict[str, object]], profile=None) -> list[dict[str, object]]:
    profile = load_profile(profile)
    reference_inputs = [{"path": ref['copied_path'], "role": ref.get('role', 'identity'), "note": ref.get('note', 'Original required reference')} for ref in copied_refs]
    jobs = [{"id": "base", "kind": "base-pet", "status": "pending", "prompt_file": "prompts/base-pet.md", "input_images": reference_inputs, "output_path": "decoded/base.png", "depends_on": [], "generation_skill": "$imagegen", "requires_grounded_generation": bool(reference_inputs), "allow_prompt_only_generation": not reference_inputs}]
    for spec in profile["states"]:
        state, frames = spec["id"], spec["frames"]
        derivations = spec["allowed_derivations"]
        dependencies = ["base"]
        source_inputs = []
        policy = {"may_derive": bool(derivations), "allowed": derivations, "requires_explicit_approval": bool(derivations)}
        jobs.append({"id": state, "kind": "row-strip", "status": "pending", "prompt_file": f"prompts/rows/{state}.md", "retry_prompt_file": f"prompts/row-retries/{state}.md", "input_images": [*reference_inputs, {"path": f"{LAYOUT_GUIDE_DIR}/{state}.png", "role": f"layout guide for {frames} frame slots; do not copy guide lines"}, {"path": CANONICAL_BASE_PATH, "role": "canonical identity reference"}, *source_inputs], "output_path": f"decoded/{state}.png", "depends_on": dependencies, "generation_skill": "$imagegen", "requires_grounded_generation": True, "allow_prompt_only_generation": False, "identity_reference_paths": [CANONICAL_BASE_PATH], "parallelizable_after": dependencies, "derivation_policy": policy})
    return jobs


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--pet-name",
        default="",
        help="User-facing pet name. Ask the user for this when practical; otherwise choose a short appropriate name.",
    )
    parser.add_argument(
        "--pet-id",
        default="",
        help="Stable pet folder/id slug. Defaults to the slugified pet name.",
    )
    parser.add_argument(
        "--display-name",
        default="",
        help="Display label. Defaults to the pet name.",
    )
    parser.add_argument("--description", default="")
    parser.add_argument("--reference", action="append", default=[])
    parser.add_argument("--output-dir", default="")
    parser.add_argument("--pet-notes", default="")
    parser.add_argument(
        "--brand-name",
        default="",
        help="Brand, company, or product name used for broad mascot inspiration.",
    )
    parser.add_argument(
        "--brand-brief",
        default="",
        help="Compact researched brand cue sentence for the base pet only.",
    )
    parser.add_argument(
        "--brand-source",
        action="append",
        default=[],
        help="Source URL used to produce the brand brief. May be passed multiple times.",
    )
    parser.add_argument(
        "--brand-discovery-file",
        default="",
        help="Optional markdown discovery brief to copy into the run for review.",
    )
    parser.add_argument(
        "--style-preset",
        default="auto",
        choices=sorted(STYLE_PRESETS),
        help="Pet-safe style preset to use across the base and all animation rows.",
    )
    parser.add_argument("--style-notes", default="")
    parser.add_argument(
        "--chroma-key",
        default="auto",
        help="Chroma key as #RRGGBB, or auto to choose a safe key from reference colors.",
    )
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--background", choices=("auto", "alpha", "chroma"), default="auto")
    parser.add_argument("--profile")
    parser.add_argument('--state-selection', help='Catalog compilation sidecar; defaults to PROFILE.selection.json when present')
    parser.add_argument("--avoid", action="append", default=[])
    parser.add_argument("--require", action="append", default=[])
    parser.add_argument("--constraints", help="JSON structured user requirements and inferred guidance")
    parser.add_argument('--identity', help='Versioned structured identity JSON')
    parser.add_argument('--reference-roles', help='JSON list of role/note records, in --reference order')
    args = parser.parse_args()
    global ATLAS, ROWS
    profile = load_profile(args.profile)
    args.profile_data = profile
    ATLAS = dict(profile["layout"])
    ROWS = [(s["id"], i, s["frames"], s["purpose"]) for i, s in enumerate(profile["states"])]
    raw_constraints = json.loads(Path(args.constraints).read_text(encoding="utf-8")) if args.constraints else {}
    args.identity = validate_identity(json.loads(Path(args.identity).read_text(encoding='utf-8')) if args.identity else None, profile)
    selection_path = Path(args.state_selection).expanduser().resolve() if args.state_selection else None
    if selection_path is None and args.profile:
        companion = Path(args.profile).expanduser().resolve().with_suffix('.selection.json')
        if companion.is_file():
            selection_path = companion
    selection = None
    if selection_path is not None:
        from state_selection import read_selection
        selection = read_selection(selection_path, profile, args.identity)
    roles = reference_roles(json.loads(Path(args.reference_roles).read_text(encoding='utf-8')) if args.reference_roles else None, len(args.reference))

    raw_reference_paths = [
        Path(raw_path).expanduser().resolve() for raw_path in args.reference
    ]
    raw_brand_discovery_path = (
        Path(args.brand_discovery_file).expanduser().resolve()
        if args.brand_discovery_file.strip()
        else None
    )

    args.display_name = infer_name(args, raw_reference_paths)
    args.pet_name = (args.pet_name or args.display_name).strip()
    args.description = infer_description(args, raw_reference_paths)
    args.pet_notes = infer_pet_notes(args, raw_reference_paths)
    args.pet_id = slugify(args.pet_id or args.pet_name or args.display_name)
    args.style_preset = args.style_preset.strip().lower()
    args.style_contract = resolved_style_contract(args.style_preset, args.style_notes)
    args.brand_name = compact(args.brand_name)
    args.brand_brief = compact(args.brand_brief)
    args.brand_source = [
        compact(source) for source in args.brand_source if compact(source)
    ]
    if not args.pet_id:
        raise SystemExit("pet id must contain at least one letter or digit")
    constraints = build_constraints(raw_constraints, args.require, args.avoid, discovery_guidance(raw_brand_discovery_path), args.brand_brief, args.brand_source)
    conflicts = set(x.casefold() for x in args.identity['markings'] + args.identity['approved_props']) & set(x.casefold() for x in constraints['avoid'])
    if conflicts:
        raise ValueError('identity contradicts explicit avoidances: ' + ', '.join(sorted(conflicts)))
    args.constraints = constraints

    run_dir = (
        Path(args.output_dir).expanduser().resolve()
        if args.output_dir
        else default_output_dir(args.pet_id).resolve()
    )
    if (run_dir / "imagegen-jobs.json").exists():
        raise SystemExit("existing run: use hatch.py resume or prepare --replace-inputs; --force cannot reuse decoded assets")
    if run_dir.exists() and any(run_dir.iterdir()):
        raise SystemExit(f"{run_dir} is not empty; use hatch.py prepare --replace-inputs to preserve and replace the previous run; --force cannot reuse stale files")
    run_dir.mkdir(parents=True, exist_ok=True)

    ref_dir = run_dir / "references"
    prompt_dir = run_dir / "prompts"
    row_prompt_dir = prompt_dir / "rows"
    row_retry_prompt_dir = prompt_dir / "row-retries"
    for directory in [
        ref_dir,
        prompt_dir,
        row_prompt_dir,
        row_retry_prompt_dir,
        run_dir / "decoded",
        run_dir / "qa",
    ]:
        directory.mkdir(parents=True, exist_ok=True)

    copied_refs: list[dict[str, object]] = []
    copied_ref_paths: list[Path] = []
    for index, source in enumerate(raw_reference_paths, start=1):
        if not source.is_file():
            raise SystemExit(f"reference not found: {source}")
        suffix = source.suffix.lower() or ".png"
        copied = ref_dir / f"reference-{index:02d}{suffix}"
        shutil.copy2(source, copied)
        meta = image_metadata(copied)
        meta["source_path"] = str(source)
        meta['path'] = rel(copied, run_dir)
        meta["copied_path"] = rel(copied, run_dir)
        meta.update(roles[index - 1])
        copied_refs.append(meta)
        copied_ref_paths.append(copied)

    brand_discovery_path = ""
    if raw_brand_discovery_path is not None:
        if not raw_brand_discovery_path.is_file():
            raise SystemExit(f"brand discovery file not found: {raw_brand_discovery_path}")
        copied_discovery = run_dir / ("references/brand-discovery.json" if raw_brand_discovery_path.suffix.lower() == ".json" else BRAND_DISCOVERY_PATH)
        shutil.copy2(raw_brand_discovery_path, copied_discovery)
        brand_discovery_path = rel(copied_discovery, run_dir)

    args.chroma_key = choose_chroma_key(copied_ref_paths, args.chroma_key)
    args.extraction = {"background": args.background, "chroma_key": args.chroma_key, "key_threshold": 48, "shared_scale": None}
    layout_guides = create_layout_guides(run_dir)

    request = {
        "schema_version": 3,
        "identity": args.identity,
        "profile": profile,
        "constraints": constraints,
        "pet_id": args.pet_id,
        "display_name": args.display_name,
        "description": args.description,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "atlas": ATLAS,
        "rows": [
            {"state": state, "row": row, "frames": frames, "purpose": purpose}
            for state, row, frames, purpose in ROWS
        ],
        "layout_guides": [
            {**guide, "path": rel(Path(str(guide["path"])), run_dir)}
            for guide in layout_guides
        ],
        "references": copied_refs,
        "chroma_key": args.chroma_key,
        "extraction": args.extraction,
        "pet_notes": args.pet_notes,
        "style_preset": args.style_preset,
        "style_notes": args.style_notes,
        "style_contract": args.style_contract,
        "brand_name": args.brand_name,
        "brand_brief": args.brand_brief,
        "brand_sources": args.brand_source,
        "pet_safe_style": PET_SAFE_STYLE,
        "primary_generation_skill": "$imagegen",
    }
    if brand_discovery_path:
        request["brand_discovery_path"] = brand_discovery_path
    if selection is not None:
        selection_bytes = (json.dumps(selection, indent=2, ensure_ascii=False) + '\n').encode('utf-8')
        (run_dir / 'state-selection.json').write_bytes(selection_bytes)
        request['state_selection'] = {'path': 'state-selection.json',
            'sha256': hashlib.sha256(selection_bytes).hexdigest(), 'profile_sha256': selection['profile_sha256']}
    (run_dir / "pet_request.json").write_text(
        json.dumps(request, indent=2) + "\n", encoding="utf-8"
    )
    (run_dir / "profile.json").write_text(json.dumps(profile, indent=2) + "\n", encoding="utf-8")

    write_text(prompt_dir / "base-pet.md", base_pet_prompt(args))
    for state, row, frames, purpose in ROWS:
        write_text(
            row_prompt_dir / f"{state}.md",
            row_prompt(args, state, row, frames, purpose),
        )
        write_text(
            row_retry_prompt_dir / f"{state}.md",
            retry_row_prompt(args, state, row, frames, purpose),
        )

    jobs = {
        "schema_version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "run_dir": str(run_dir),
        "primary_generation_skill": "$imagegen",
        "jobs": make_jobs(run_dir, copied_refs, profile),
    }
    (run_dir / "imagegen-jobs.json").write_text(
        json.dumps(jobs, indent=2) + "\n", encoding="utf-8"
    )

    print(
        json.dumps(
            {
                "ok": True,
                "run_dir": str(run_dir),
                "request": str(run_dir / "pet_request.json"),
                "jobs": str(run_dir / "imagegen-jobs.json"),
                "ready_jobs": ["base"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
