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
                for i, scene in enumerate(scenes):
                    with lf.start_as_current_observation(name=f"video.clip_{i+1}", trace_context=_tctx, as_type="tool", end_on_exit=True):
                        prompt = scene.prompt or f'Scene {i+1}: {scene.description}'
                        task_id = self.video_provider.generate_clip(prompt, duration_sec=scene.duration_sec)
                        status = self.video_provider.poll_status(task_id)
                if status == 'completed':
                    clip_name = f'clip_{i+1:03d}.mp4'
                    clip_dir = self.workspace.artifacts_dir(project_id, run_id) / 'clips'
                    clip_dir.mkdir(exist_ok=True)
                    clip_path = str(clip_dir / clip_name)
                    self.video_provider.download_result(
                        task_id, clip_path,
                        duration_sec=scene.duration_sec,
                    )
                    clip_paths[scene.scene_id or f'scene_{i}'] = clip_path
                    print(f'  [Video] Scene {i+1}: {clip_path}')
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

    def _continue_storyboard(self, project_id: str, state: WorkflowState, spec_data: dict) -> None:
        from shared.schemas import VideoSpec
        spec = VideoSpec.model_validate(spec_data)
        brand = BrandProfile(brand_name=spec.brand)
        storyboard = self.agent.generate_storyboard(spec, brand)
        state.storyboard = storyboard
        self.workspace.write_artifact(project_id, 'default', 'storyboard.json', storyboard.model_dump())
        # Pause for storyboard review
        r2 = self.reviews.create_storyboard_review(project_id, storyboard.model_dump())
        state.paused = True
        state.meta['pause_review_id'] = r2.review_id
        state.meta['pause_stage'] = 'storyboard'
        self._save_state(project_id, state)
        print(f'  [Pause] Storyboard review: {r2.review_id}')
        get_event_bus().publish(Event(EVENT_PIPELINE_PAUSED, {
            'project_id': project_id, 'review_id': r2.review_id, 'stage': 'storyboard'}))
        state.final_video_path = self._wait_for_approval(project_id, state, r2.review_id)

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

        self.projects.advance_stage(project_id, ProjectStage.VIDEO_PROD)
        clip_paths: dict[str, str] = {}
        clip_dir = self.workspace.artifacts_dir(project_id, run_id) / 'clips'
        clip_dir.mkdir(exist_ok=True)

        with stage_span("video_prod", {"project_id": project_id, "scene_count": len(scenes)}):
            for i, scene in enumerate(scenes):
                with lf.start_as_current_observation(name=f"video.clip_{i+1}", trace_context=_tctx, as_type="tool", end_on_exit=True):
                    prompt = scene.prompt or f'Scene {i+1}: {scene.description}'
                    task_id = self.video_provider.generate_clip(prompt, duration_sec=scene.duration_sec)
                    clip_name = f'clip_{i+1:03d}.mp4'
                    clip_path = str(clip_dir / clip_name)
                    # download_result internally polls until the task is completed/failed/timed out
                    result_path = self.video_provider.download_result(
                        task_id, clip_path,
                        duration_sec=scene.duration_sec,
                    )
                    if result_path:
                        clip_paths[scene.scene_id or f'scene_{i}'] = result_path
                        print(f'  [Video] Scene {i+1}: {result_path}')
                    else:
                        print(f'  [Video] Scene {i+1}: generation failed or timed out')

        state.clips = clip_paths
        self._save_state(project_id, state)

        if not clip_paths:
            print('  [Resume] No clips generated, aborting')
            state.errors.append({'step': 'video_gen', 'message': 'No clips generated'})
            self._save_state(project_id, state)
            get_event_bus().publish(Event(EVENT_PIPELINE_ERROR, {
                'project_id': project_id, 'error': 'No clips generated'}))
            return

        r3 = self.reviews.create_video_review(project_id, {'clips': clip_paths})
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

            if state.scenes:
                from tools.tts import generate_narration
                narration_dir = str(work_dir / 'narration')
                audio_map = generate_narration(state.scenes, narration_dir)
                for i, scene in enumerate(state.scenes):
                    sid = scene.scene_id or f'scene_{i}'
                    if sid in audio_map:
                        voiceover_paths.append(audio_map[sid])

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
        self.projects.advance_stage(project_id, ProjectStage.DONE)
        self._save_state(project_id, state)
        get_event_bus().publish(Event(EVENT_PIPELINE_COMPLETED, {
            'project_id': project_id, 'final_video_path': final_path}))
        flush_traces()

    def _stitch_videos(self, video_paths: list[str], output_path: str) -> None:
        from tools.ffmpeg import concat_videos
        concat_videos(video_paths, output_path)
