from __future__ import annotations

from pathlib import Path
from typing import Any

from project.service import ProjectService
from workspace.manager import WorkspaceManager
from agents.lead_agent import LeadAgent
from shared.schemas import ProjectStage, WorkflowState, BrandProfile, VideoSpec, Storyboard
from shared.constants import FINAL_VIDEO_FILE
from shared.exceptions import AgentError
from providers.video import get_video_provider
from review.service import ReviewService
from events.bus import Event, get_event_bus, EVENT_PIPELINE_STARTED, EVENT_PIPELINE_PAUSED, EVENT_PIPELINE_COMPLETED, EVENT_PIPELINE_ERROR
from review.comment import ReviewStage
from observability.langfuse_tracing import get_langfuse, stage_span, flush_traces


class WorkflowRuntime:
    def __init__(self) -> None:
        self.projects = ProjectService()
        self.workspace = WorkspaceManager()
        self.agent = LeadAgent()
        self.video_provider = get_video_provider()
        self.reviews = ReviewService()

    def run_pipeline(self, project_id: str, brief: str) -> str:
        state = WorkflowState(project_id=project_id)
        bus = get_event_bus()
        bus.publish(Event(EVENT_PIPELINE_STARTED, {'project_id': project_id}))
        run_id = 'default'
        lf = get_langfuse()
        lf_trace_id = lf.create_trace_id()
        state.meta['langfuse_trace_id'] = lf_trace_id
        self._save_state(project_id, state)
        _tctx = {"trace_id": lf_trace_id}

        try:
            # ©¤©¤ 1. Requirement Understanding ©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤
            self.projects.advance_stage(project_id, ProjectStage.REQUIREMENT)
            with stage_span("requirement", {"project_id": project_id}):
                with lf.start_as_current_observation(name="llm.requirement", trace_context=_tctx, as_type="generation", end_on_exit=True):
                    spec = self.agent.understand_requirement(brief)
            state.video_spec = spec
            self.workspace.write_artifact(project_id, run_id, 'video_spec.json', spec.model_dump())
            print(f'  [Requirement] Duration: {spec.duration_sec}s, Style: {spec.style}')

            # Pause for human review
            r1 = self.reviews.create_requirement_review(project_id, spec.model_dump())
            state.paused = True
            state.meta['pause_review_id'] = r1.review_id
            state.meta['pause_stage'] = 'requirement'
            self._save_state(project_id, state)
            print(f'  [Pause] Review required: {r1.review_id}')
            bus.publish(Event(EVENT_PIPELINE_PAUSED, {'project_id': project_id, 'review_id': r1.review_id, 'stage': 'requirement'}))
            return self._wait_for_approval(project_id, state, r1.review_id)

            # ©¤©¤ 2. Storyboard Generation ©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤
            self.projects.advance_stage(project_id, ProjectStage.STORYBOARD)
            brand = BrandProfile(brand_name=spec.brand)
            with stage_span("storyboard", {"project_id": project_id}):
                with lf.start_as_current_observation(name="llm.storyboard", trace_context=_tctx, as_type="generation", end_on_exit=True):
                    storyboard = self.agent.generate_storyboard(spec, brand)
            state.storyboard = storyboard
            self.workspace.write_artifact(project_id, run_id, 'storyboard.json', storyboard.model_dump())
            print(f'  [Storyboard] {len(storyboard.scenes)} scenes, {storyboard.total_duration_sec}s total')

            # Pause for human review
            r2 = self.reviews.create_storyboard_review(project_id, storyboard.model_dump())
            state.paused = True
            state.meta['pause_review_id'] = r2.review_id
            state.meta['pause_stage'] = 'storyboard'
            self._save_state(project_id, state)
            print(f'  [Pause] Storyboard review required: {r2.review_id}')
            return self._wait_for_approval(project_id, state, r2.review_id)

            # ©¤©¤ 3. Scene Generation ©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤
            self.projects.advance_stage(project_id, ProjectStage.SCENE_GEN)
            with stage_span("scene_gen", {"project_id": project_id}):
                with lf.start_as_current_observation(name="llm.scene_gen", trace_context=_tctx, as_type="generation", end_on_exit=True):
                    scenes = self.agent.generate_scenes(storyboard, brand)
            state.scenes = scenes
            self.workspace.write_artifact(project_id, run_id, 'scenes.json', [s.model_dump() for s in scenes])
            print(f'  [Scenes] {len(scenes)} scenes generated')

            # ©¤©¤ 4. Video Generation ©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤
            self.projects.advance_stage(project_id, ProjectStage.VIDEO_PROD)
            with stage_span("video_prod", {"project_id": project_id, "scene_count": len(scenes)}):
                clip_paths = {}
                clip_dir = self.workspace.artifacts_dir(project_id, run_id) / 'clips'
                clip_dir.mkdir(exist_ok=True)
                clip_idx = 0
                for scene_i, scene in enumerate(scenes):
                    shots = scene.shots or []
                    if not shots:
                        clip_idx += 1
                        prompt = scene.prompt or f'Scene {scene_i + 1}: {scene.description}'
                        task_id = self.video_provider.generate_clip(prompt, duration_sec=scene.duration_sec)
                        clip_path = str(clip_dir / f'clip_{clip_idx:03d}.mp4')
                        result_path = self.video_provider.download_result(
                            task_id, clip_path, duration_sec=scene.duration_sec,
                        )
                        if result_path:
                            clip_paths[scene.scene_id or f'scene_{scene_i}'] = result_path
                        continue
                    for shot in shots:
                        clip_idx += 1
                        duration = shot.duration_sec or 5
                        prompt = shot.prompt or shot.description or f'Scene {scene_i + 1} shot'
                        task_id = self.video_provider.generate_clip(prompt, duration_sec=duration)
                        clip_path = str(clip_dir / f'clip_{clip_idx:03d}.mp4')
                        result_path = self.video_provider.download_result(
                            task_id, clip_path, duration_sec=duration,
                        )
                        if result_path:
                            clip_paths[shot.shot_id or f'shot_{clip_idx}'] = result_path
            state.clips = clip_paths

            # Pause for video review
            r3 = self.reviews.create_video_review(project_id, {'clips': clip_paths})
            state.paused = True
            state.meta['pause_review_id'] = r3.review_id
            state.meta['pause_stage'] = 'video_review'
            self._save_state(project_id, state)
            print(f'  [Pause] Video review required: {r3.review_id}')
            return self._wait_for_approval(project_id, state, r3.review_id)

            # ©¤©¤ 5. Stitch final video ©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤
            if clip_paths:
                with stage_span("stitch", {"project_id": project_id, "clip_count": len(clip_paths)}):
                    final_path = self.workspace.artifacts_dir(project_id, run_id) / FINAL_VIDEO_FILE
                    self._stitch_videos(list(clip_paths.values()), str(final_path))
                state.final_video_path = str(final_path)
                print(f'  [Stitch] Final video: {final_path}')

            self.projects.advance_stage(project_id, ProjectStage.DONE)
            flush_traces()
            return state.final_video_path

        except Exception as exc:
            err = {'step': 'pipeline', 'message': str(exc)}
            state.errors.append(err)
            print(f'  [Error] {exc}')
            flush_traces()
            return ''

    def resume(self, project_id: str, review_id: str) -> str:
        state = self._load_state(project_id)
        review = self.reviews.get_review(review_id)
        if not review or review.status.value not in ('approved', 'rejected'):
            print(f'  [Resume] Review {review_id} not resolved')
            return ''

        if review.status.value == 'rejected':
            print(f'  [Resume] Review rejected, aborting')
            self.projects.advance_stage(project_id, ProjectStage.REVIEW)
            return ''

        print(f'  [Resume] Review approved, continuing')
        state.paused = False
        project = self.projects.get_project(project_id)
        brief = project.brief
        spec = self.workspace.read_artifact(project_id, 'default', 'video_spec.json')

        pause_stage = state.meta.get('pause_stage', '')
        if pause_stage == 'requirement':
            # Continue to storyboard
            self._continue_storyboard(project_id, state, spec)
        elif pause_stage == 'storyboard':
            # Storyboard approved → asset preparation (4th HITL)
            self._continue_asset_prep(project_id, state)
        elif pause_stage == 'asset_prep':
            # Asset prep approved → scene generation + video production
            self._continue_scenes(project_id, state)
        elif pause_stage == 'video_review':
            self._continue_stitch(project_id, state)
        else:
            print(f'  [Resume] Unknown pause stage: {pause_stage}')

        flush_traces()
        return state.final_video_path or ''

    def _wait_for_approval(self, project_id: str, state: WorkflowState, review_id: str) -> str:
        return f'__PAUSED__:{review_id}'

    def _save_state(self, project_id: str, state: WorkflowState) -> None:
        self.workspace.write_artifact(project_id, 'default', 'workflow_state.json', state.model_dump())

    def _load_state(self, project_id: str) -> WorkflowState:
        data = self.workspace.read_artifact(project_id, 'default', 'workflow_state.json')
        if data:
            return WorkflowState.model_validate(data)
        return WorkflowState(project_id=project_id)

    def record_resume_error(self, project_id: str, error: str) -> None:
        """Persist a resume failure to workflow_state so a silently swallowed
        exception (e.g. in a background approval thread) becomes visible."""
        try:
            state = self._load_state(project_id)
            state.errors.append({'step': 'resume', 'message': str(error)})
            self._save_state(project_id, state)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Guardrail helpers (legal / brand / content-safety compliance)
    # ------------------------------------------------------------------
    def _gather_scene_text(self, scenes: list) -> str:
        """Concatenate the natural-language fields of scenes/shots so the
        guardrail word lists can run against the LLM output."""
        parts: list[str] = []
        for scene in scenes or []:
            if getattr(scene, 'prompt', ''):
                parts.append(scene.prompt)
            if getattr(scene, 'narration', ''):
                parts.append(scene.narration)
            for shot in (getattr(scene, 'shots', None) or []):
                if getattr(shot, 'prompt', ''):
                    parts.append(shot.prompt)
                if getattr(shot, 'narration', ''):
                    parts.append(shot.narration)
        return "\n".join(parts)

    def _run_guardrails(self, text: str):
        """Run all registered guardrails. Returns the list of GuardrailResult."""
        from guardrails.registry import get_registry, register_defaults
        register_defaults()  # idempotent: ensures the 3 default rules are loaded
        return get_registry().check_all(text)

    def _collect_violations(self, results) -> tuple[list[str], bool]:
        """Return (human-readable violations, content_safety_hit) from results."""
        violations: list[str] = []
        hard_block = False
        for r in results:
            if not r.passed:
                violations.extend(r.details)
                if r.rule == 'content_safety':
                    hard_block = True
        return violations, hard_block

    def _continue_storyboard(self, project_id: str, state: WorkflowState, spec_data: dict) -> None:
        from shared.schemas import VideoSpec
        spec = VideoSpec.model_validate(spec_data)
        brand = BrandProfile(brand_name=spec.brand)
        storyboard = self.agent.generate_storyboard(spec, brand)
        state.storyboard = storyboard
        self.workspace.write_artifact(project_id, 'default', 'storyboard.json', storyboard.model_dump())

        # Guardrail check on the generated storyboard content (HITL-friendly)
        sb_text = self._gather_scene_text(storyboard.scenes)
        sb_violations, sb_hard = self._collect_violations(self._run_guardrails(sb_text))
        if sb_hard:
            # Content-safety red line: hard block, do not proceed to review.
            state.errors.append({'step': 'guardrail', 'message': 'Content safety violation in storyboard', 'details': sb_violations})
            self._save_state(project_id, state)
            get_event_bus().publish(Event(EVENT_PIPELINE_ERROR, {'project_id': project_id, 'error': 'Content safety violation in storyboard'}))
            return

        # Pause for storyboard review (non-safety violations attached for human sight)
        sb_payload = storyboard.model_dump()
        if sb_violations:
            sb_payload['guardrail_violations'] = sb_violations
        r2 = self.reviews.create_storyboard_review(project_id, sb_payload)
        state.paused = True
        state.meta['pause_review_id'] = r2.review_id
        state.meta['pause_stage'] = 'storyboard'
        self._save_state(project_id, state)
        print(f'  [Pause] Storyboard review: {r2.review_id}')
        get_event_bus().publish(Event(EVENT_PIPELINE_PAUSED, {
            'project_id': project_id, 'review_id': r2.review_id, 'stage': 'storyboard'}))
        state.final_video_path = self._wait_for_approval(project_id, state, r2.review_id)

    def _continue_asset_prep(self, project_id: str, state: WorkflowState) -> None:
        """Continue from storyboard approval: prepare assets and pause for 4th HITL."""
        sb_data = self.workspace.read_artifact(project_id, 'default', 'storyboard.json')
        if not sb_data:
            print('  [Resume] No storyboard found for asset prep')
            # Fallback: skip to scenes
            self._continue_scenes(project_id, state)
            return

        self.projects.advance_stage(project_id, ProjectStage.ASSET_PREP)

        spec_data = self.workspace.read_artifact(project_id, 'default', 'video_spec.json')
        spec = VideoSpec.model_validate(spec_data) if spec_data else VideoSpec()
        storyboard = Storyboard.model_validate(sb_data)

        # Build asset suggestions from storyboard + spec for human confirmation
        asset_payload = {
            'type': 'asset_prep',
            'suggested_characters': [
                {
                    'role': s.title or f'Scene {i+1}',
                    'description': s.description,
                    'use_digital_human': getattr(spec, 'use_digital_human', False),
                }
                for i, s in enumerate(storyboard.scenes or [])
            ],
            'suggested_voice': getattr(spec, 'voice_over', '') or 'TBD',
            'suggested_brand': getattr(spec, 'brand', '') or 'TBD',
            'platform': getattr(spec, 'platform', '') or 'TBD',
            'style_notes': getattr(storyboard, 'style_notes', ''),
        }

        # Inject world_constraints skill into asset context for LLM-assisted suggestions
        from skills.loader import get_skill_prompt as _gsp
        skill_text = _gsp('asset_prep')
        if skill_text:
            asset_payload['skill_guidance'] = skill_text[:500]  # Truncate for review display

        r_asset = self.reviews.create_asset_review(project_id, asset_payload)
        state.paused = True
        state.meta['pause_review_id'] = r_asset.review_id
        state.meta['pause_stage'] = 'asset_prep'
        self._save_state(project_id, state)
        print(f'  [Pause] Asset preparation review: {r_asset.review_id}')
        get_event_bus().publish(Event(EVENT_PIPELINE_PAUSED, {
            'project_id': project_id,
            'review_id': r_asset.review_id,
            'stage': 'asset_prep'}))
        state.final_video_path = self._wait_for_approval(project_id, state, r_asset.review_id)

    def _continue_scenes(self, project_id: str, state: WorkflowState) -> None:
        """Continue from storyboard approval: scene_gen -> video_gen -> pause for video review."""
        run_id = 'default'
        lf = get_langfuse()
        lf_trace_id = state.meta.get('langfuse_trace_id', lf.create_trace_id())
        _tctx = {"trace_id": lf_trace_id}

        sb_data = self.workspace.read_artifact(project_id, run_id, 'storyboard.json')
        if not sb_data:
            print('  [Resume] No storyboard found, cannot continue')
            state.errors.append({'step': 'scene_gen', 'message': 'No storyboard found'})
            self._save_state(project_id, state)
            return

        storyboard = Storyboard.model_validate(sb_data)
        spec_data = self.workspace.read_artifact(project_id, run_id, 'video_spec.json')
        spec = VideoSpec.model_validate(spec_data) if spec_data else VideoSpec()
        brand = BrandProfile(brand_name=spec.brand)

        self.projects.advance_stage(project_id, ProjectStage.SCENE_GEN)
        with stage_span("scene_gen", {"project_id": project_id}):
            with lf.start_as_current_observation(name="llm.scene_gen", trace_context=_tctx, as_type="generation", end_on_exit=True):
                scenes = self.agent.generate_scenes(storyboard, brand)
        state.scenes = scenes
        self.workspace.write_artifact(project_id, run_id, 'scenes.json', [s.model_dump() for s in scenes])
        print(f'  [Scenes] {len(scenes)} scenes generated')

        # Guardrail check before spending Kling credits (HITL-friendly)
        scene_text = self._gather_scene_text(scenes)
        scene_violations, scene_hard = self._collect_violations(self._run_guardrails(scene_text))
        if scene_hard:
            # Content-safety red line: hard block, do not generate video.
            state.errors.append({'step': 'guardrail', 'message': 'Content safety violation in scenes', 'details': scene_violations})
            self._save_state(project_id, state)
            get_event_bus().publish(Event(EVENT_PIPELINE_ERROR, {'project_id': project_id, 'error': 'Content safety violation in scenes'}))
            return

        self.projects.advance_stage(project_id, ProjectStage.VIDEO_PROD)
        clip_paths: dict[str, str] = {}
        clip_dir = self.workspace.artifacts_dir(project_id, run_id) / 'clips'
        clip_dir.mkdir(exist_ok=True)

        with stage_span("video_prod", {"project_id": project_id, "scene_count": len(scenes)}):
            clip_idx = 0
            for scene_i, scene in enumerate(scenes):
                shots = scene.shots or []
                if not shots:
                    # No shots defined: generate one clip for the whole scene.
                    clip_idx += 1
                    with lf.start_as_current_observation(name=f"video.clip_{clip_idx}", trace_context=_tctx, as_type="tool", end_on_exit=True):
                        prompt = scene.prompt or f'Scene {scene_i + 1}: {scene.description}'
                        task_id = self.video_provider.generate_clip(prompt, duration_sec=scene.duration_sec)
                        clip_name = f'clip_{clip_idx:03d}.mp4'
                        clip_path = str(clip_dir / clip_name)
                        result_path = self.video_provider.download_result(
                            task_id, clip_path, duration_sec=scene.duration_sec,
                        )
                        if result_path:
                            clip_paths[scene.scene_id or f'scene_{scene_i}'] = result_path
                            print(f'  [Video] Clip {clip_idx} (scene {scene_i + 1}): {result_path}')
                        else:
                            print(f'  [Video] Clip {clip_idx} (scene {scene_i + 1}): generation failed or timed out')
                    continue

                # Generate one clip per shot so each shot is an independent cut.
                for shot in shots:
                    clip_idx += 1
                    shot_id = shot.shot_id or f'shot_{clip_idx}'
                    duration = shot.duration_sec or 5
                    with lf.start_as_current_observation(name=f"video.clip_{clip_idx}", trace_context=_tctx, as_type="tool", end_on_exit=True):
                        prompt = shot.prompt or shot.description or f'Scene {scene_i + 1} shot'
                        task_id = self.video_provider.generate_clip(prompt, duration_sec=duration)
                        clip_name = f'clip_{clip_idx:03d}.mp4'
                        clip_path = str(clip_dir / clip_name)
                        # download_result internally polls until the task is completed/failed/timed out
                        result_path = self.video_provider.download_result(
                            task_id, clip_path, duration_sec=duration,
                        )
                        if result_path:
                            clip_paths[shot_id] = result_path
                            print(f'  [Video] Clip {clip_idx} (shot {shot_id}): {result_path}')
                        else:
                            print(f'  [Video] Clip {clip_idx} (shot {shot_id}): generation failed or timed out')

        state.clips = clip_paths
        self._save_state(project_id, state)

        if not clip_paths:
            print('  [Resume] No clips generated, aborting')
            state.errors.append({'step': 'video_gen', 'message': 'No clips generated'})
            self._save_state(project_id, state)
            get_event_bus().publish(Event(EVENT_PIPELINE_ERROR, {
                'project_id': project_id, 'error': 'No clips generated'}))
            return

        video_payload = {'clips': clip_paths}
        if scene_violations:
            video_payload['guardrail_violations'] = scene_violations
        r3 = self.reviews.create_video_review(project_id, video_payload)
        state.paused = True
        state.meta['pause_review_id'] = r3.review_id
        state.meta['pause_stage'] = 'video_review'
        self._save_state(project_id, state)
        print(f'  [Pause] Video review required: {r3.review_id}')
        get_event_bus().publish(Event(EVENT_PIPELINE_PAUSED, {
            'project_id': project_id, 'review_id': r3.review_id, 'stage': 'video_review'}))

    def _continue_stitch(self, project_id: str, state: WorkflowState) -> None:
        """Continue from video review approval: TTS + subtitles + final render."""
        run_id = 'default'
        work_dir = self.workspace.artifacts_dir(project_id, run_id)

        if not state.clips:
            print('  [Resume] No clips to stitch')
            self.projects.advance_stage(project_id, ProjectStage.DONE)
            self._save_state(project_id, state)
            return

        with stage_span("stitch", {"project_id": project_id, "clip_count": len(state.clips)}):
            voiceover_paths: list[str] = []

            if state.scenes and state.clips:
                from tools.tts import generate_narration
                narration_dir = str(work_dir / 'narration')
                audio_map = generate_narration(state.scenes, narration_dir)
                # Align voiceovers 1:1 with the clips that were actually produced.
                # state.clips is keyed by shot_id (or scene_id for shot-less
                # scenes) and ordered by playback order, so iterating its keys
                # keeps audio and video in lockstep even if a shot failed.
                for key in state.clips.keys():
                    if key in audio_map:
                        voiceover_paths.append(audio_map[key])

            srt_path = None
            if state.scenes:
                from tools.subtitle import generate_srt
                srt_path = str(work_dir / 'subtitles.srt')
                generate_srt(state.scenes, srt_path)

            from tools.ffmpeg import render_final
            final_path = str(work_dir / FINAL_VIDEO_FILE)
            render_final(
                clip_paths=list(state.clips.values()),
                voiceover_paths=voiceover_paths or None,
                srt_path=srt_path,
                bgm_path=None,
                output_path=final_path,
                work_dir=str(work_dir / 'render'),
            )

        state.final_video_path = final_path
        print(f'  [Stitch] Final video: {final_path}')

        # B1: collect generated assets into the asset library (non-fatal)
        try:
            from assets.service import AssetService
            artifacts: dict[str, Any] = {}
            spec = state.video_spec
            if spec is not None:
                artifacts['brand_profile'] = {
                    'brand_name': getattr(spec, 'brand', '') or '',
                    'product_description': getattr(spec, 'description', '') or '',
                    'industry': getattr(spec, 'platform', '') or '',
                }
            if state.storyboard is not None:
                artifacts['storyboard'] = state.storyboard.model_dump()
            if state.clips:
                artifacts['clips'] = state.clips
            if artifacts:
                created = AssetService().collect_project_assets(project_id, artifacts)
                print(f'  [Assets] Collected {len(created)} assets for project {project_id}')
        except Exception as exc:
            print(f'  [Assets] Collection failed (non-fatal): {exc}')

        # Publish: export final video to publish output directory
        self.projects.advance_stage(project_id, ProjectStage.PUBLISH)
        try:
            from tools.publish import publish_local
            spec = state.video_spec
            title = f"{getattr(spec, 'brand', 'smartvideo')}_{project_id[:8]}"
            pub_result = publish_local(state.final_video_path, title=title)
            state.meta['publish_result'] = pub_result
            print(f'  [Publish] {pub_result.get("status", "unknown")}: {pub_result.get("output_path", "")}')
        except Exception as exc:
            print(f'  [Publish] Export failed (non-fatal): {exc}')
            state.meta['publish_result'] = {'status': 'error', 'message': str(exc)}

        self.projects.advance_stage(project_id, ProjectStage.DONE)
        self._save_state(project_id, state)
        get_event_bus().publish(Event(EVENT_PIPELINE_COMPLETED, {
            'project_id': project_id, 'final_video_path': final_path}))
        flush_traces()

    def _stitch_videos(self, video_paths: list[str], output_path: str) -> None:
        from tools.ffmpeg import concat_videos
        concat_videos(video_paths, output_path)
