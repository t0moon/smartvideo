"""Rebuild clips/final video from saved scenes.json without rerunning LLM steps."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Load .env side effects.
import app.config  # noqa: F401
from app.artifacts import new_artifact_run_id
from app.config import ARTIFACTS_DIR
from app.graph.nodes.audio import node_generate_audio
from app.graph.nodes.stitch import node_stitch_final
from app.graph.nodes.video import node_generate_clips
from app.graph.state import AgentState
from app.schemas.storyboard import Scene, validate_scenes_list


def _load_scenes(raw: object) -> list[dict]:
    if isinstance(raw, dict) and "scenes" in raw:
        raw = raw["scenes"]
    if not isinstance(raw, list):
        raise ValueError('Input must be a JSON array or an object with key "scenes".')
    parsed: list[Scene] = []
    for i, item in enumerate(raw):
        if not isinstance(item, dict):
            raise ValueError(f"scene #{i + 1} must be an object.")
        parsed.append(Scene.model_validate(item))
    errs = validate_scenes_list(parsed)
    if errs:
        raise ValueError("; ".join(errs))
    return [s.model_dump() for s in parsed]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Rerun only video/audio/stitch from scenes.json or outputs/<run_id>/scenes.json.",
    )
    parser.add_argument(
        "source",
        nargs="?",
        default="",
        help="Path to scenes.json, or an output directory containing scenes.json.",
    )
    parser.add_argument(
        "--run-id",
        dest="run_id",
        default="",
        help="New output run id. Mutually exclusive with --in-place.",
    )
    parser.add_argument(
        "--in-place",
        dest="in_place",
        default="",
        metavar="RUN_ID",
        help="Write into existing outputs/<RUN_ID>/ and overwrite same-name media files.",
    )
    args = parser.parse_args()

    src = (args.source or "").strip()
    if not src:
        print(
            "Usage: python -m app.remake_clips <scenes.json | outputs/<run_id>>",
            file=sys.stderr,
        )
        raise SystemExit(2)

    path = Path(src)
    if path.is_dir():
        json_path = path / "scenes.json"
        if not json_path.is_file():
            print(f"scenes.json not found: {json_path}", file=sys.stderr)
            raise SystemExit(2)
        path = json_path

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except OSError as e:
        print(f"Cannot read input: {e}", file=sys.stderr)
        raise SystemExit(2) from e
    except json.JSONDecodeError as e:
        print(f"Invalid JSON: {e}", file=sys.stderr)
        raise SystemExit(2) from e

    try:
        scenes = _load_scenes(data)
    except ValueError as e:
        print(f"Scenes validation failed: {e}", file=sys.stderr)
        raise SystemExit(2) from e

    in_place = (args.in_place or "").strip()
    if in_place and (args.run_id or "").strip():
        print("Do not use --run-id and --in-place together.", file=sys.stderr)
        raise SystemExit(2)

    if in_place:
        run_id = in_place
    elif (args.run_id or "").strip():
        run_id = args.run_id.strip()
    else:
        run_id = new_artifact_run_id()

    out_dir = ARTIFACTS_DIR / run_id
    if in_place and not out_dir.is_dir():
        print(f"Output directory does not exist: {out_dir}", file=sys.stderr)
        raise SystemExit(2)

    state: AgentState = {
        "scenes": scenes,
        "artifact_run_id": run_id,
    }

    v = node_generate_clips(state)
    if v.get("errors"):
        print("Video stage errors:", v["errors"], file=sys.stderr)
        raise SystemExit(1)
    state.update(v)

    a = node_generate_audio(state)
    if a.get("errors"):
        print("Audio stage errors:", a["errors"], file=sys.stderr)
        raise SystemExit(1)
    state.update(a)

    s = node_stitch_final(state)
    if s.get("errors"):
        print("Stitch stage errors:", s["errors"], file=sys.stderr)
        raise SystemExit(1)

    print(s.get("final_video_path", ""))


if __name__ == "__main__":
    main()
