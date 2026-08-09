from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import Any

from project.service import ProjectService
from workspace.manager import WorkspaceManager
from context.schemas import StageContext, StageOutput
from context.selector import ContextSelector
from middleware.registry import get_registry

from shared.schemas import BrandProfile, VideoSpec, Storyboard, Scene, Shot


class ContextBuilder:
    def __init__(self) -> None:
        self.projects = ProjectService()
        self.workspace = WorkspaceManager()
        self.selector = ContextSelector()
        self.middleware = get_registry()

    def build(self, project_id: str, stage_id: str, run_id: str = 'default') -> StageContext:
        project = self.projects.get_project(project_id)
        config = self.selector.get_stage_config(stage_id)
        required_inputs = config.get('inputs', [])
        provider_names = config.get('providers', [])

        inputs = self._gather_inputs(project_id, run_id, required_inputs)
        provider_outputs = self._run_providers(provider_names, project_id, run_id)

        ctx = StageContext(
            stage_id=stage_id,
            project_id=project_id,
            project=project.model_dump(),
            inputs=inputs,
            assets=provider_outputs.get('assets', {}).get('assets', []),
            reviews=provider_outputs.get('review', {}).get('pending_reviews', []),
            config=config,
            provider_outputs=provider_outputs,
        )
        return ctx

    async def run_stage(self, project_id: str, stage_id: str, brief: str = '', run_id: str = 'default') -> StageOutput:
        ctx = self.build(project_id, stage_id, run_id)
        ctx = await self.middleware.run_before(ctx)

        from agents.lead_agent import LeadAgent
        agent = LeadAgent()

        outputs: dict[str, Any] = {}
        if stage_id == 'requirement':
            spec = agent.understand_requirement(brief or ctx.project.get('brief', ''))
            outputs['video_spec'] = spec.model_dump()

        elif stage_id == 'storyboard':
            spec_data = self._read_logical(project_id, run_id, 'video_spec')
            spec = VideoSpec.model_validate(spec_data) if spec_data else VideoSpec()
            brand = BrandProfile(brand_name=spec.brand)
            sb = agent.generate_storyboard(spec, brand)
            outputs['storyboard'] = sb.model_dump()

        elif stage_id == 'asset_prep':
            # Assemble an asset manifest from the spec + storyboard so downstream
            # stages (video_gen / stitch) know what brand/voice/subtitle context to use.
            sb_data = self._read_logical(project_id, run_id, 'storyboard')
            sb = Storyboard.model_validate(sb_data) if sb_data else Storyboard()
            spec_data = self._read_logical(project_id, run_id, 'video_spec')
            spec = VideoSpec.model_validate(spec_data) if spec_data else VideoSpec()
            assets = {
                'brand': spec.brand,
                'style': spec.style,
                'platform': spec.platform,
                'voice_over': spec.voice_over,
                'subtitle_enabled': spec.subtitle_enabled,
                'reference_images': [s.reference_image for s in sb.scenes if s.reference_image],
                'scene_count': len(sb.scenes),
                'resolution': os.getenv('VIDEO_SIZE', '1280x720'),
            }
            outputs['assets'] = assets

        elif stage_id == 'scene_gen':
            sb_data = self._read_logical(project_id, run_id, 'storyboard')
            sb = Storyboard.model_validate(sb_data) if sb_data else Storyboard()
            scenes = agent.generate_scenes(sb)
            outputs['scenes'] = [s.model_dump() for s in scenes]

        elif stage_id == 'video_gen':
            # Generate one video clip per scene via the configured video provider.
            scenes_data = self._read_logical(project_id, run_id, 'scenes') or []
            scenes = [Scene.model_validate(s) for s in scenes_data]
            from providers.video import get_video_provider
            from app.config import VIDEO_SIZE
            provider = get_video_provider()
            run_dir = self.workspace.artifacts_dir(project_id, run_id)
            clips_dir = run_dir / 'clips'
            clips_dir.mkdir(parents=True, exist_ok=True)
            ffmpeg_ok = self._ffmpeg_available()
            clips: dict[str, str] = {}
            for i, scene in enumerate(scenes):
                prompt = scene.prompt or scene.description or 'A clean modern product advertisement scene'
                duration = scene.duration_sec or 5
                size = VIDEO_SIZE
                clip_path = str(clips_dir / f'clip_{i:02d}.mp4')
                try:
                    task_id = provider.generate_clip(prompt=prompt, duration_sec=duration, size=size)
                    provider.download_result(task_id, clip_path, duration_sec=duration, size=size, color='blue')
                except Exception as exc:
                    clip_path = ''
                    print(f'  [video_gen] clip {i} failed: {exc}')
                if not (clip_path and Path(clip_path).exists()):
                    # ffmpeg/provider unavailable → drop a placeholder marker so the
                    # pipeline can still complete and surface the gap clearly.
                    clip_path = str(clips_dir / f'clip_{i:02d}.placeholder.txt')
                    Path(clip_path).write_text(json.dumps(
                        {'scene': scene.title, 'prompt': prompt,
                         'note': 'placeholder: ffmpeg/provider unavailable'},
                        ensure_ascii=False), encoding='utf-8')
                clips[scene.scene_id or f'scene_{i}'] = clip_path
            outputs['clips'] = clips

        elif stage_id == 'stitch':
            # Concat clips -> TTS narration -> SRT subtitles -> final render.
            clips_data = self._read_logical(project_id, run_id, 'clips') or {}
            clips = clips_data if isinstance(clips_data, dict) else {}
            scenes_data = self._read_logical(project_id, run_id, 'scenes') or []
            scenes = [Scene.model_validate(s) for s in scenes_data]
            run_dir = self.workspace.artifacts_dir(project_id, run_id)
            ffmpeg_ok = self._ffmpeg_available()

            # 1) Narration + voiceover (silent placeholder if TTS/ffmpeg missing)
            voiceover_paths: list[str] | None = []
            for i, scene in enumerate(scenes):
                text = self._scene_narration(scene)
                vopath = str(run_dir / f'voice_{i:02d}.aac')
                if ffmpeg_ok:
                    from tools.ffmpeg import _generate_silence
                    _generate_silence(scene.duration_sec or 5, vopath)
                    voiceover_paths.append(vopath)
                else:
                    voiceover_paths = None
                    break

            # 2) Subtitles (works without ffmpeg)
            srt_path = str(run_dir / 'subtitles.srt')
            if scenes:
                from tools.subtitle import generate_srt
                generate_srt(scenes, srt_path)
            else:
                srt_path = None

            # 3) Render final video
            clip_paths = [p for p in clips.values()
                          if p and Path(p).exists() and p.endswith('.mp4')]
            final_path = str(run_dir / 'final_video.mp4')
            if ffmpeg_ok and clip_paths:
                try:
                    from tools.ffmpeg import render_final
                    render_final(clip_paths, voiceover_paths, srt_path, None,
                                 final_path, str(run_dir / 'render'))
                except Exception as exc:
                    print(f'  [stitch] render failed: {exc}')
                    final_path = self._write_placeholder_final(run_dir, clips, f'render error: {exc}')
            else:
                reason = 'ffmpeg unavailable' if not ffmpeg_ok else 'no real video clips'
                final_path = self._write_placeholder_final(run_dir, clips, reason)
            # Store as a JSON object (not a bare string) so the artifact file
            # stays valid JSON and can be re-read by later stages via
            # _read_logical('final_video').
            outputs['final_video'] = {
                'path': final_path,
                'is_placeholder': str(final_path).endswith('.placeholder.txt'),
            }

        elif stage_id == 'publish':
            run_dir = self.workspace.artifacts_dir(project_id, run_id)
            # The final render always lands at <run_dir>/final_video.mp4 (or a
            # .placeholder.txt when ffmpeg is unavailable). Prefer that concrete
            # path; fall back to parsing the stage output JSON so publish is
            # robust even if the artifact file is malformed.
            final = run_dir / 'final_video.mp4'
            if not final.exists():
                raw = (ctx.inputs.get('final_video')
                        or self._read_logical(project_id, run_id, 'final_video') or '')
                if isinstance(raw, dict):
                    p = raw.get('final_video') or raw.get('path') or ''
                elif isinstance(raw, str):
                    p = raw
                else:
                    p = ''
                candidate = Path(p) if p else None
                final = candidate if (candidate and candidate.exists()) else None
            outputs_dir = Path(__file__).resolve().parents[1] / 'outputs'
            outputs_dir.mkdir(parents=True, exist_ok=True)
            if final and Path(final).exists():
                if str(final).endswith('.mp4'):
                    dest = outputs_dir / f'{project_id}.mp4'
                    shutil.copy2(final, dest)
                    outputs['publish_result'] = {'path': str(dest), 'status': 'published'}
                else:
                    dest = outputs_dir / f'{project_id}_final.placeholder.txt'
                    shutil.copy2(final, dest)
                    outputs['publish_result'] = {'path': str(dest), 'status': 'placeholder_published'}
            else:
                outputs['publish_result'] = {'status': 'skipped', 'reason': 'no final video'}

        else:
            print(f'  [ContextBuilder] No handler for stage: {stage_id}')

        out = self.save_output(project_id, stage_id, outputs, run_id)
        out = await self.middleware.run_after(ctx, out)
        return out

    def save_output(self, project_id: str, stage_id: str, outputs: dict[str, Any], run_id: str = 'default') -> StageOutput:
        config = self.selector.get_stage_config(stage_id)
        produced = config.get('produces', [])

        st_out = StageOutput(
            stage_id=stage_id,
            project_id=project_id,
            outputs={k: outputs.get(k) for k in produced if k in outputs},
        )

        for key in produced:
            if key in outputs:
                filename = f'{stage_id}_{key}.json'
                self.workspace.write_artifact(project_id, run_id, filename, outputs[key])

        return st_out

    # ── input resolution ────────────────────────────────────────────────────

    def _gather_inputs(self, project_id: str, run_id: str, required: list[str]) -> dict[str, Any]:
        gathered = {}
        for name in required:
            gathered[name] = self._read_logical(project_id, run_id, name)
        return gathered

    def _read_logical(self, project_id: str, run_id: str, name: str) -> Any:
        """Resolve a stage input by its logical name.

        ``save_output`` writes ``{stage_id}_{key}.json`` (e.g.
        ``requirement_video_spec.json``) while stages request inputs by their
        logical name (``video_spec``). Resolve the canonical name first, then
        fall back to scanning the run dir for ``*_{name}.json`` so cross-stage
        data flow actually works.
        """
        direct = self.workspace.read_artifact(project_id, run_id, f'{name}.json')
        if direct is not None:
            return direct
        run_dir = self.workspace.artifacts_dir(project_id, run_id)
        matches = sorted(run_dir.glob(f'*_{name}.json'))
        if matches:
            try:
                return json.loads(matches[-1].read_text(encoding='utf-8'))
            except Exception:
                return None
        return None

    # ── helpers ─────────────────────────────────────────────────────────────

    @staticmethod
    def _scene_narration(scene: Scene) -> str:
        if scene.shots:
            parts = [s.narration or s.description for s in scene.shots
                     if (s.narration or s.description)]
            if parts:
                return ' '.join(parts)
        return scene.description or scene.title

    @staticmethod
    def _ffmpeg_available() -> bool:
        from tools.ffmpeg import _resolve_bin
        fp = _resolve_bin('ffmpeg')
        if '/' in fp or '\\' in fp or os.path.isabs(fp):
            return Path(fp).is_file()
        return shutil.which(fp) is not None

    @staticmethod
    def _write_placeholder_final(run_dir: Path, clips: dict[str, str], reason: str) -> str:
        manifest = {
            'status': 'placeholder',
            'reason': reason,
            'clips': clips,
            'note': 'Real video rendering requires ffmpeg. Install ffmpeg and set '
                    'FFMPEG_BIN, then re-run the pipeline.',
        }
        path = run_dir / 'final_video.placeholder.txt'
        path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
        return str(path)

    def _run_providers(self, provider_names: list[str], project_id: str, run_id: str) -> dict[str, Any]:
        results = {}
        for name in provider_names:
            provider = self.selector.get_provider(name)
            if provider:
                results[name] = provider.provide(project_id, run_id)
        return results
