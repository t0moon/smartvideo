"""Offline end-to-end verification of the SmartVideo product_ad_v1 pipeline.

Forces LLM_PROVIDER=mock and VIDEO_PROVIDER=placeholder (the project .env pins
deepseek/kling and load_dotenv(override=True) makes .env win over real env
vars, so we patch the config modules in-memory instead of editing .env).

Goal: run all 7 stages (requirement -> storyboard -> asset_prep -> scene_gen ->
video_gen -> stitch -> publish) and surface what works / what is missing.
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND))
os.chdir(BACKEND)

# 1) Force offline providers BEFORE importing anything that reads config.
import types  # noqa: E402

import app.config as cfg  # noqa: E402

# Stub langfuse (not installed offline) so openai_provider's
# `from langfuse.openai import openai` resolves to the real openai module.
import openai as _real_openai  # noqa: E402
_lf = types.ModuleType('langfuse')
_lf_openai = types.ModuleType('langfuse.openai')
_lf_openai.openai = _real_openai
sys.modules.setdefault('langfuse', _lf)
sys.modules['langfuse.openai'] = _lf_openai

cfg.LLM_PROVIDER = 'mock'
cfg.VIDEO_PROVIDER = 'placeholder'

import providers.llm as pll  # noqa: E402
import providers.video as pvid  # noqa: E402

pll.LLM_PROVIDER = 'mock'
pvid.VIDEO_PROVIDER = 'placeholder'

# 2) Imports that trigger the rest of the graph.
from storage.database import init_db  # noqa: E402
from project.service import ProjectService  # noqa: E402
from runtime.executor import StageExecutor  # noqa: E402


BRIEF = (
    "为一款新上市的便携保温杯做一个 15 秒抖音信息流广告："
    "主打「24 小时长效保温 + 一键开盖」。目标人群 18-30 岁都市年轻人，"
    "风格清爽现代，带字幕与中文旁白。"
)


async def main() -> None:
    # Ensure sqlite schema (reviews table) exists for ReviewService.
    await init_db()

    projects = ProjectService()
    project = projects.create_project(name='离线验证-保温杯广告', brief=BRIEF)
    pid = project.project_id
    print(f'[setup] created project={pid}  workflow={project.workflow_name}')

    executor = StageExecutor()
    print('\n=== running product_ad_v1 pipeline (LLM=mock, VIDEO=placeholder) ===\n')
    result = await executor.execute_workflow('product_ad', pid, BRIEF)

    print('\n=== per-stage outputs ===')
    for key in ['requirement', 'storyboard', 'asset_prep', 'scene_gen',
                'video_gen', 'stitch', 'publish']:
        if key in result:
            out = result[key]
            if isinstance(out, dict):
                keys = list(out.keys())
                # show a short preview of values
                preview = {k: _preview(v) for k, v in out.items()}
                print(f'  [{key}] -> {keys}')
                for k, v in preview.items():
                    print(f'        {k}: {v}')
            else:
                print(f'  [{key}] -> {_preview(out)}')
        else:
            print(f'  [{key}] -> (not present)')

    if '_error' in result:
        print(f'\n[ERROR] pipeline stopped: {result["_error"]}')
    if '_paused' in result:
        print(f'\n[PAUSED] at stage: {result.get("_pause_stage")}')

    state = result.get('_state', {})
    print('\n=== stage states ===')
    for sid, info in state.get('stages', {}).items():
        print(f'  {sid:12s} {info.get("state"):10s} {("err=" + str(info.get("error"))) if info.get("error") else ""}')

    # 3) Show artifact files produced in the run dir.
    run_dir = BACKEND / 'data' / 'projects' / pid / 'runs' / 'default'
    print(f'\n=== run artifacts @ {run_dir} ===')
    if run_dir.exists():
        for f in sorted(run_dir.iterdir()):
            if f.is_file():
                size = f.stat().st_size
                print(f'  {f.name:32s} {size:>8} bytes')
            else:
                print(f'  {f.name}/ (dir)')

    outputs_dir = BACKEND / 'outputs'
    print(f'\n=== published outputs @ {outputs_dir} ===')
    if outputs_dir.exists():
        matched = [o for o in outputs_dir.iterdir() if pid in o.name]
        for o in sorted(matched):
            print(f'  {o.name:40s} {o.stat().st_size:>8} bytes')

    print('\n[done]')


def _preview(v: object, n: int = 90) -> str:
    if isinstance(v, str):
        return v if len(v) <= n else v[:n] + '...'
    if isinstance(v, dict):
        return '{' + ', '.join(f'{k}={_preview(val, 40)}' for k, val in v.items()) + '}'
    if isinstance(v, list):
        return f'[list len={len(v)}] ' + (', '.join(_preview(x, 30) for x in v[:3]))
    return str(v)


if __name__ == '__main__':
    asyncio.run(main())
