# smartvideo

**English** | [简体中文](README.zh-CN.md)

## Demo

Sample run (**staged** master before the final `final.mp4` pass): from local path `outputs/20260427_195844/final.staged.mp4`, stored in-repo as the files below.

GitHub’s README can only use the **browser’s built-in video controls** (no custom JavaScript players inside the README itself). For a **full-featured player** (Plyr: keyboard shortcuts, speed, better UI), open **[docs/demo-player.html](docs/demo-player.html)** in a new tab using one of these:

- [Open Plyr player (HTMLPreview)](https://htmlpreview.github.io/?https://raw.githubusercontent.com/t0moon/smartvideo/main/docs/demo-player.html) (works without GitHub Pages)
- After enabling **Settings → Pages** with the `docs` folder: `https://t0moon.github.io/smartvideo/demo-player.html`

**Inline preview** (native controls + poster frame):

<video
  controls
  playsinline
  preload="metadata"
  poster="https://raw.githubusercontent.com/t0moon/smartvideo/main/docs/assets/demo_final_staged_20260427_poster.jpg"
  style="max-width:100%;border-radius:8px;background:#0d1117;"
  width="100%">
  <source src="https://raw.githubusercontent.com/t0moon/smartvideo/main/docs/assets/demo_final_staged_20260427.mp4" type="video/mp4" />
  <p>Your browser does not support embedded video. <a href="docs/assets/demo_final_staged_20260427.mp4">Download the MP4</a> or use the Plyr link above.</p>
</video>

[Direct link to the MP4 file](docs/assets/demo_final_staged_20260427.mp4) · [Source for the web player](docs/demo-player.html)

## Overview

**smartvideo** is an automated pipeline for **brand advertising video**. You provide a **brand / product brief** (plain text); the system chains LLM and media steps and, at the end, prints the **on-disk path to the final video**. Intermediate artifacts and the final file default to `outputs/` (override the root with `SMARTVIDEO_ARTIFACTS_DIR` if needed).

**What it does:**

1. **Storyboard & narrative**  
   With **`skills/** SKILL.md** files (storyboard template, world constraints, etc.), an LLM turns the brief into structured storyboards, scenes, and shot-level detail for video and voiceover.

2. **Brand context**  
   Extracts and organizes a **brand profile** from the brief. When enabled, it can also run **web research** (strategy and tools are controlled by env vars like `BRAND_RESEARCH_STRATEGY` and related code paths) for better fit with the brand and facts.

3. **Video clips**  
   Per-scene, **pluggable video providers** (placeholder, OpenAI-style async video API, or a custom HTTP gateway) generate clip assets. Retries, timeouts, and fallbacks are governed by `VIDEO_*` and the implementations.

4. **Audio post**  
   Optional **TTS voiceover**, per-shot **SFX**, final **BGM**, loudness / ducking, and similar processing before the final stitch. See `AUDIO_*` in `.env.example`.

5. **Final render**  
   **FFmpeg** on the host **muxes / stitches** clips and audio into one file, and can hard-burn subtitles from narration (`SUBTITLE_*`). On success, the CLI prints the **final video path** to **stdout**.

6. **Reruns**  
   When you already have `scenes.json` (or a prior run’s artifacts), **`smartvideo-remake`** reruns only **video → audio → stitch**, skipping the heavy LLM steps—useful when switching backends or tuning parameters.

**Usage (summary):** Configure `.env` (at least `OPENAI_API_KEY`; see below), then run `smartvideo "your brief"` or `python -m app.run` for a full pass; use `smartvideo-remake` for partial reruns. See **Usage** below for full commands.

## Quick reference

- **Graph** (`app/graph/graph.py`): load skills → brand → storyboard + constraints (LLM + skills) → scenes → video → audio → stitch.
- **Video providers**: `placeholder`, `openai_videos` (OpenAI-compatible async video API), `http` (generic HTTP gateway). See `VIDEO_*`.
- **Audio**: TTS, per-shot SFX, BGM, loudness/ducking. See `AUDIO_*` in `.env.example`.
- **Reruns** (no LLM): `smartvideo-remake` from a saved `scenes.json` or `outputs/<run_id>` to rerun only video/audio/stitch.

## Requirements

- **Python** ≥ 3.11
- **FFmpeg**: the `ffmpeg` binary must be on `PATH` for stitching and A/V work. A Windows build under `.tools/ffmpeg-*` is included if you point your setup at that `bin` directory.

## Install

```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS / Linux:
# source .venv/bin/activate

pip install -e ".[dev]"
```

Copy the env template from the project root and edit it:

```bash
copy .env.example .env
# or: cp .env.example .env
```

Set at least **`OPENAI_API_KEY`**. For a non-OpenAI-compatible gateway, set **`OPENAI_BASE_URL`** (usually including `/v1`) and **`OPENAI_MODEL`**. All other options are documented in `.env.example` (video, audio, skills path, artifacts directory, etc.).

## Usage

**CLI entry points** (registered in `pyproject.toml`):

```bash
smartvideo "Your brand and product brief"
```

or:

```bash
python -m app.run "Your brand and product brief"
```

You can also pass the brief via **stdin**; on success, **stdout** is the final video path.

**Two-step approval flow** (generate storyboard first, continue after user confirmation):

```bash
# step 1: generate storyboard only (prints JSON payload with run_id/storyboard_script_path/storyboard_script)
smartvideo --await-confirm "Your brand and product brief"

# step 2: after user confirms, continue render in-place for that run
smartvideo-remake outputs/<run_id> --in-place <run_id>
# or directly from storyboard_script.json
smartvideo-remake outputs/<run_id>/storyboard_script.json --in-place <run_id>
```

**Rerun only video / audio / stitch** from an existing storyboard (examples):

```bash
smartvideo-remake path/to/scenes.json
# or point at a run directory that contains scenes.json
smartvideo-remake outputs/<run_id>
```

Run `smartvideo-remake --help` for all flags.

**Optional HTTP API** (for mobile/iPad or frontend integration):

```bash
smartvideo-api --host 0.0.0.0 --port 8787
```

- `POST /storyboard/generate` with JSON body `{"brief":"...", "require_confirmation": true}`
- `POST /storyboard/confirm` with JSON body `{"run_id":"<run_id>", "in_place": true}`

## Skills & configuration

- **`SMARTVIDEO_SKILLS_ROOT`** points to the skills root (default: `./skills/`), including **SKILL.md** for storyboard template and world constraints.
- **Brand research** is tuned with **`BRAND_RESEARCH_STRATEGY`** and related settings (see `app/config.py`).

## Development & tests

```bash
pytest
```

**ruff** is optional for linting (see `[tool.ruff]` in `pyproject.toml`).

## Repository layout

| Path | Description |
| --- | --- |
| `app/graph/` | LangGraph state and nodes (brand, storyboard, scenes, video, audio, stitch) |
| `app/providers/` | Video provider implementations |
| `app/media/` | FFmpeg and media helpers |
| `skills/` | External SKILL prompts and templates |
| `tests/` | Unit and smoke tests |
| `outputs/` | Run outputs (default; override with `SMARTVIDEO_ARTIFACTS_DIR`) |

## License

This repository may not include a `LICENSE` file. Add one and comply with it before you redistribute or use the project in production.
