from __future__ import annotations

import yaml
from pathlib import Path
from typing import Any

from project.service import ProjectService
from workspace.manager import WorkspaceManager
from agents.lead_agent import LeadAgent
from shared.schemas import ProjectStage, WorkflowState, BrandProfile, VideoSpec, Storyboard, AssetType
from shared.constants import FINAL_VIDEO_FILE
from shared.exceptions import AgentError
from providers.video import get_video_provider
from review.service import ReviewService
from events.bus import Event, get_event_bus, EVENT_PIPELINE_STARTED, EVENT_PIPELINE_PAUSED, EVENT_PIPELINE_COMPLETED, EVENT_PIPELINE_ERROR
from review.comment import ReviewStage
from observability.langfuse_tracing import get_langfuse, stage_span, flush_traces
from runtime.state_machine import WorkflowStateMachine


class WorkflowRuntime:
    def __init__(self) -> None:
        self.projects = ProjectService()
        self.workspace = WorkspaceManager()
        self.agent = LeadAgent()
        self.video_provider = get_video_provider()
        self.reviews = ReviewService()

    # ------------------------------------------------------------------
    # Engine entry points
    # ------------------------------------------------------------------
    def run_pipeline(self, project_id: str, brief: str) -> str:
        """Legacy (v1) hardcoded pipeline entry point.

        Executes the requirement stage and pauses for human review. All
        subsequent stages are driven by resume(). Kept as a fallback so the
        Web API / Feishu (which call this method) keep working unchanged.
        """
        state = WorkflowState(project_id=project_id)
        bus = get_event_bus()
        bus.publish(Event(EVENT_PIPELINE_STARTED, {'project_id': project_id}))
        self._save_state(project_id, state)
        try:
            self._exec_requirement(project_id, state, brief)
            if state.paused and state.meta.get('pause_review_id'):
                return f"__PAUSED__:{state.meta['pause_review_id']}"
            return state.final_video_path or ''
        except Exception as exc:
            state.errors.append({'step': 'pipeline', 'message': str(exc)})
            print(f'  [Error] {exc}')
            flush_traces()
            return ''

    def run_pipeline_v2(self, project_id: str, brief: str, workflow_name: str = 'product_ad') -> str:
        """YAML-driven (v2) pipeline entry point.

        Loads the workflow graph from ``workflows/<name>_v1.yaml``, executes the
        first stage and pauses. Each subsequent stage is selected by the YAML
        ``next`` edges inside resume() — so reordering / adding / removing
        stages (and their pause points) is a pure configuration change.
        """
        state = WorkflowState(project_id=project_id)
        state.meta['engine'] = 'v2'
        state.meta['workflow_name'] = workflow_name
        bus = get_event_bus()
        bus.publish(Event(EVENT_PIPELINE_STARTED, {'project_id': project_id}))
        self._save_state(project_id, state)
        try:
            sm = self._load_yaml(workflow_name)
            first = sm.get_first_stage()
            handler = self._stage_handlers().get(first)
            if handler is None:
                print(f'  [v2] No handler for first stage: {first}')
                return ''
            handler(project_id, state, brief)
            if state.paused and state.meta.get('pause_review_id'):
                return f"__PAUSED__:{state.meta['pause_review_id']}"
            return state.final_video_path or ''
        except Exception as exc:
            state.errors.append({'step': 'pipeline_v2', 'message': str(exc)})
            print(f'  [Error] {exc}')
            flush_traces()
            return ''

    def resume(self, project_id: str, review_id: str) -> str:
        """Resume a paused pipeline. Engine-agnostic: the next stage is resolved
        from the YAML workflow graph (with a hardcoded fallback) so v1 and v2
        projects share the same code path.

        Human-in-the-loop feedback backflow: any comment text attached to the
        resolved review is collected and injected into the next LLM-driven
        stage (storyboard / scene_gen) so reviewers' edits actually reshape the
        generated artifact instead of being silently archived.
        """
        state = self._load_state(project_id)
        review = self.reviews.get_review(review_id)
        if not review or review.status.value not in ('approved', 'rejected', 'partial_revision'):
            print(f'  [Resume] Review {review_id} not resolved')
            return ''

        feedback = self._collect_feedback(review)

        # Storyboard revision: regenerate the storyboard with the user's edit
        # notes and re-pause for another review round (instead of advancing).
        if review.status.value == 'partial_revision' and review.stage == ReviewStage.STORYBOARD and feedback:
            return self._revise_storyboard(project_id, state, feedback)

        if review.status.value == 'rejected':
            print(f'  [Resume] Review rejected, aborting')
            self.projects.advance_stage(project_id, ProjectStage.REVIEW)
            return ''

        print(f'  [Resume] Review approved, continuing')
        state.paused = False
        project = self.projects.get_project(project_id)
        brief = project.brief

        pause_stage = state.meta.get('pause_stage', '')
        workflow_name = state.meta.get('workflow_name', 'product_ad')
        next_stage = self._route_next_stage(pause_stage, workflow_name)
        handler = self._stage_handlers().get(next_stage) if next_stage else None

        if handler is None:
            print(f'  [Resume] No handler for next stage after {pause_stage}, finalizing')
            self.projects.advance_stage(project_id, ProjectStage.DONE)
            self._save_state(project_id, state)
            flush_traces()
            return state.final_video_path or ''

        # Non-pausing stages cascade internally (scene_gen->video_gen, stitch->publish).
        # Feedback is only meaningful for LLM-driven stages.
        if next_stage in ('storyboard', 'scene_gen'):
            handler(project_id, state, brief, feedback=feedback)
        else:
            handler(project_id, state, brief)

        flush_traces()
        if state.paused:
            return f"__PAUSED__:{state.meta.get('pause_review_id', '')}"
        return state.final_video_path or ''

    @staticmethod
    def _collect_feedback(review) -> str:
        """Join non-empty review comment texts into a single feedback blob."""
        parts = [
            c.text.strip()
            for c in (review.comments or [])
            if getattr(c, 'text', '').strip()
        ]
        return '\n'.join(parts)

    def _revise_storyboard(self, project_id: str, state: WorkflowState, feedback: str) -> str:
        """Regenerate the storyboard incorporating reviewer feedback, then
        re-create a storyboard review and pause again for another round."""
        from shared.schemas import VideoSpec
        spec = VideoSpec.model_validate(state.video_spec.model_dump() if state.video_spec else {})
        brand = BrandProfile(brand_name=spec.brand)
        storyboard = self.agent.generate_storyboard(spec, brand, feedback=feedback)
        state.storyboard = storyboard
        self.workspace.write_artifact(project_id, 'default', 'storyboard.json', storyboard.model_dump())

        sb_text = self._gather_scene_text(storyboard.scenes)
        sb_violations, sb_hard = self._collect_violations(self._run_guardrails(sb_text))
        if sb_hard:
            state.errors.append({'step': 'guardrail', 'message': 'Content safety violation in storyboard', 'details': sb_violations})
            self._save_state(project_id, state)
            get_event_bus().publish(Event(EVENT_PIPELINE_ERROR, {
                'project_id': project_id, 'error': 'Content safety violation in storyboard'}))
            return ''

        from tools.storyboard_text import storyboard_to_txt
        sb_payload = storyboard.model_dump()
        sb_payload['readable_text'] = storyboard_to_txt(storyboard)
        if sb_violations:
            sb_payload['guardrail_violations'] = sb_violations
        r2 = self.reviews.create_storyboard_review(project_id, sb_payload)
        state.paused = True
        state.meta['pause_review_id'] = r2.review_id
        state.meta['pause_stage'] = 'storyboard'
        self._save_state(project_id, state)
        print(f'  [Pause] Storyboard revised, review: {r2.review_id}')
        get_event_bus().publish(Event(EVENT_PIPELINE_PAUSED, {
            'project_id': project_id, 'review_id': r2.review_id, 'stage': 'storyboard'}))
        return f"__PAUSED__:{r2.review_id}"

    # ------------------------------------------------------------------
    # Stage handlers (each maps 1:1 to a YAML stage id)
    # ------------------------------------------------------------------
    def _exec_requirement(self, project_id: str, state: WorkflowState, brief: str = '') -> None:
        """Stage: requirement understanding."""
        run_id = 'default'
        lf = get_langfuse()
        lf_trace_id = lf.create_trace_id()
        state.meta['langfuse_trace_id'] = lf_trace_id
        _tctx = {"trace_id": lf_trace_id}

        self.projects.advance_stage(project_id, ProjectStage.REQUIREMENT)
        with stage_span("requirement", {"project_id": project_id}):
            with lf.start_as_current_observation(name="llm.requirement", trace_context=_tctx, as_type="generation", end_on_exit=True):
                # Enrich the requirement analysis with real-world search context
                # (product / competitor / audience info). Degrades to '' when no
                # search provider is configured.
                from tools.search import gather_requirement_context
                search_context = gather_requirement_context(brief=brief)
                if search_context:
                    print(f'  [Requirement] search context gathered ({len(search_context)} chars)')
                spec = self.agent.understand_requirement(brief, search_context=search_context)
        state.video_spec = spec
        self.workspace.write_artifact(project_id, run_id, 'video_spec.json', spec.model_dump())
        print(f'  [Requirement] Duration: {spec.duration_sec}s, Style: {spec.style}')

        r1 = self.reviews.create_requirement_review(project_id, spec.model_dump())
        state.paused = True
        state.meta['pause_review_id'] = r1.review_id
        state.meta['pause_stage'] = 'requirement'
        self._save_state(project_id, state)
        print(f'  [Pause] Review required: {r1.review_id}')
        get_event_bus().publish(Event(EVENT_PIPELINE_PAUSED, {
            'project_id': project_id, 'review_id': r1.review_id, 'stage': 'requirement'}))

    def _exec_storyboard(self, project_id: str, state: WorkflowState, brief: str = '', feedback: str = '') -> None:
        """Stage: storyboard generation + review (HITL #2)."""
        from shared.schemas import VideoSpec
        spec = VideoSpec.model_validate(state.video_spec.model_dump() if state.video_spec else {})
        brand = BrandProfile(brand_name=spec.brand)
        storyboard = self.agent.generate_storyboard(spec, brand, feedback=feedback)
        state.storyboard = storyboard
        self.workspace.write_artifact(project_id, 'default', 'storyboard.json', storyboard.model_dump())

        sb_text = self._gather_scene_text(storyboard.scenes)
        sb_violations, sb_hard = self._collect_violations(self._run_guardrails(sb_text))
        if sb_hard:
            state.errors.append({'step': 'guardrail', 'message': 'Content safety violation in storyboard', 'details': sb_violations})
            self._save_state(project_id, state)
            get_event_bus().publish(Event(EVENT_PIPELINE_ERROR, {
                'project_id': project_id, 'error': 'Content safety violation in storyboard'}))
            return

        from tools.storyboard_text import storyboard_to_txt
        sb_payload = storyboard.model_dump()
        # Human-readable artifact for the review UI / Feishu card.
        sb_payload['readable_text'] = storyboard_to_txt(storyboard)
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

    def _exec_asset_prep(self, project_id: str, state: WorkflowState, brief: str = '') -> None:
        """Stage: asset preparation + review (HITL #3)."""
        sb_data = self.workspace.read_artifact(project_id, 'default', 'storyboard.json')
        if not sb_data:
            print('  [Resume] No storyboard found for asset prep')
            self._exec_scene_gen(project_id, state)
            return

        self.projects.advance_stage(project_id, ProjectStage.ASSET_PREP)

        from shared.schemas import VideoSpec
        from shared.enums import AssetType
        spec_data = self.workspace.read_artifact(project_id, 'default', 'video_spec.json')
        spec = VideoSpec.model_validate(spec_data) if spec_data else VideoSpec()
        storyboard = Storyboard.model_validate(sb_data)

        # ── Collect user-uploaded assets for the project ────────────────
        uploaded: dict[str, list[dict]] = {}
        try:
            from assets.service import AssetService
            svc = AssetService()
            for atype, label in [(AssetType.IMAGE, 'product_images'),
                                 (AssetType.CHARACTER, 'characters'),
                                 (AssetType.VOICE, 'voice_samples'),
                                 (AssetType.BGM, 'bgm_tracks')]:
                items = svc.list_assets(asset_type=atype, project_id=project_id)
                if items:
                    uploaded[label] = [{
                        'name': a.name, 'file_path': a.file_path,
                        'asset_id': a.asset_id, 'mime_type': getattr(a, 'mime_type', ''),
                    } for a in items]
            # ── ASR: transcribe uploaded voice samples for a richer brief ──
            if uploaded.get('voice_samples'):
                try:
                    from tools.transcription import transcribe_audio
                    for vs in uploaded['voice_samples']:
                        fp = vs.get('file_path')
                        if fp:
                            vs['transcript'] = transcribe_audio(fp)
                except Exception as exc:
                    print(f'  [AssetPrep] ASR enrichment skipped: {exc}')

            if uploaded:
                print(f'  [AssetPrep] Found user uploads: {list(uploaded.keys())}')
        except Exception as exc:
            print(f'  [AssetPrep] Asset lookup skipped: {exc}')

        # ── Build review payload with both suggestions and uploads ─────
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
            'user_uploads': uploaded,
        }

        from skills.loader import get_skill_prompt as _gsp
        skill_text = _gsp('asset_prep')
        if skill_text:
            asset_payload['skill_guidance'] = skill_text[:500]

        r_asset = self.reviews.create_asset_review(project_id, asset_payload)
        state.paused = True
        state.meta['pause_review_id'] = r_asset.review_id
        state.meta['pause_stage'] = 'asset_prep'
        self._save_state(project_id, state)
        print(f'  [Pause] Asset preparation review: {r_asset.review_id}')
        get_event_bus().publish(Event(EVENT_PIPELINE_PAUSED, {
            'project_id': project_id, 'review_id': r_asset.review_id, 'stage': 'asset_prep'}))

    def _exec_scene_gen(self, project_id: str, state: WorkflowState, brief: str = '', feedback: str = '') -> None:
        """Stage: scene generation (no pause) — cascades to video generation. Accepts optional feedback from review revisions."""
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
                scenes = self.agent.generate_scenes(storyboard, brand, feedback=feedback)
        state.scenes = scenes
        self.workspace.write_artifact(project_id, run_id, 'scenes.json', [s.model_dump() for s in scenes])
        print(f'  [Scenes] {len(scenes)} scenes generated')

        # Guardrail pre-check before spending Kling credits, then cascade.
        scene_text = self._gather_scene_text(scenes)
        scene_violations, scene_hard = self._collect_violations(self._run_guardrails(scene_text))
        if scene_hard:
            state.errors.append({'step': 'guardrail', 'message': 'Content safety violation in scenes', 'details': scene_violations})
            self._save_state(project_id, state)
            get_event_bus().publish(Event(EVENT_PIPELINE_ERROR, {
                'project_id': project_id, 'error': 'Content safety violation in scenes'}))
            return

        self._exec_video_gen(project_id, state)

    def _exec_video_gen(self, project_id: str, state: WorkflowState, brief: str = '') -> None:
        """Stage: video clip generation + review (HITL #4)."""
        run_id = 'default'
        lf = get_langfuse()
        lf_trace_id = state.meta.get('langfuse_trace_id', lf.create_trace_id())
        _tctx = {"trace_id": lf_trace_id}

        scenes = state.scenes or []
        self.projects.advance_stage(project_id, ProjectStage.VIDEO_PROD)
        clip_paths: dict[str, str] = {}
        clip_dir = self.workspace.artifacts_dir(project_id, run_id) / 'clips'
        clip_dir.mkdir(exist_ok=True)

        # Collect user-uploaded reference images as fallback for scenes that
        # don't have their own reference_image set.
        user_refs: list[str] = []
        try:
            from assets.service import AssetService
            from shared.enums import AssetType
            svc = AssetService()
            img_assets = svc.list_assets(asset_type=AssetType.IMAGE, project_id=project_id)
            user_refs = [a.file_path for a in img_assets if a.file_path]
        except Exception:
            pass
        fallback_ref = user_refs[0] if user_refs else ''

        with stage_span("video_prod", {"project_id": project_id, "scene_count": len(scenes)}):
            clip_idx = 0
            for scene_i, scene in enumerate(scenes):
                # Resolve reference image: scene field > uploaded asset > empty
                ref_img = getattr(scene, 'reference_image', '') or ''
                if not ref_img:
                    ref_img = fallback_ref
                shot_ref = ref_img  # per-scene ref; shots inherit unless overridden

                # Only pass reference_image when it is a real URL or file
                def _is_valid_ref(ri):
                    if not ri:
                        return False
                    if ri.startswith(('http://', 'https://')):
                        return True
                    if ri.startswith('data:'):
                        return True
                    if any(ri.lower().endswith(e) for e in ('.png','.jpg','.jpeg','.webp','.bmp','.gif')):
                        return Path(ri).exists() if Path(ri).is_absolute() else False
                    if len(ri) > 20 and any('\u4e00' <= c <= '\u9fff' for c in ri):
                        return False
                    return Path(ri).exists()

                shots = scene.shots or []
                if not shots:
                    clip_idx += 1
                    with lf.start_as_current_observation(name=f"video.clip_{clip_idx}", trace_context=_tctx, as_type="tool", end_on_exit=True):
                        prompt = scene.prompt or f'Scene {scene_i + 1}: {scene.description}'
                        kwargs: dict = {'duration_sec': scene.duration_sec}
                        if ref_img and _is_valid_ref(ref_img):
                            kwargs['reference_image'] = ref_img
                        elif ref_img:
                            print(f'  [Video] Skipping non-file reference: {ref_img[:60]}...')
                        task_id = self.video_provider.generate_clip(prompt, **kwargs)
                        clip_name = f'clip_{clip_idx:03d}.mp4'
                        clip_path = str(clip_dir / clip_name)
                        result_path = self.video_provider.download_result(
                            task_id, clip_path, duration_sec=scene.duration_sec,
                        )
                        if result_path:
                            clip_paths[scene.scene_id or f'scene_{scene_i}'] = result_path
                            print(f'  [Video] Clip {clip_idx} (scene {scene_i + 1}){" [ref-img]" if ref_img else ""}: {result_path}')
                        else:
                            print(f'  [Video] Clip {clip_idx} (scene {scene_i + 1}): generation failed or timed out')
                    continue

                for shot in shots:
                    clip_idx += 1
                    shot_id = shot.shot_id or f'shot_{clip_idx}'
                    duration = shot.duration_sec or 5
                    with lf.start_as_current_observation(name=f"video.clip_{clip_idx}", trace_context=_tctx, as_type="tool", end_on_exit=True):
                        prompt = shot.prompt or shot.description or f'Scene {scene_i + 1} shot'
                        kwargs = {'duration_sec': duration}
                        if shot_ref and _is_valid_ref(shot_ref):
                            kwargs['reference_image'] = shot_ref
                        elif shot_ref:
                            print(f'  [Video] Skipping non-file reference: {shot_ref[:60]}...')
                        task_id = self.video_provider.generate_clip(prompt, **kwargs)
                        clip_name = f'clip_{clip_idx:03d}.mp4'
                        clip_path = str(clip_dir / clip_name)
                        result_path = self.video_provider.download_result(
                            task_id, clip_path, duration_sec=duration,
                        )
                        if result_path:
                            clip_paths[shot_id] = result_path
                            print(f'  [Video] Clip {clip_idx} (shot {shot_id}){" [ref-img]" if shot_ref else ""}: {result_path}')
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
        scene_text = self._gather_scene_text(scenes)
        _, scene_violations = self._collect_violations(self._run_guardrails(scene_text))
        if scene_violations:
            video_payload['guardrail_violations'] = scene_violations
        r3 = self.reviews.create_video_review(project_id, video_payload)
        state.paused = True
        state.meta['pause_review_id'] = r3.review_id
        state.meta['pause_stage'] = 'video_gen'
        self._save_state(project_id, state)
        print(f'  [Pause] Video review required: {r3.review_id}')
        get_event_bus().publish(Event(EVENT_PIPELINE_PAUSED, {
            'project_id': project_id, 'review_id': r3.review_id, 'stage': 'video_gen'}))

    def _exec_stitch(self, project_id: str, state: WorkflowState, brief: str = '') -> None:
        """Stage: stitch final video (TTS + subtitles + render). Cascades to publish."""
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

            # 需求三: 若用户上传了 BGM，混入最终视频
            bgm_path: str | None = None
            try:
                from assets.service import AssetService
                bgm_assets = AssetService().list_assets(asset_type=AssetType.BGM, project_id=project_id)
                if bgm_assets:
                    bgm_path = bgm_assets[0].file_path
                    print(f'  [Stitch] Using user-uploaded BGM: {bgm_path}')
            except Exception as exc:
                print(f'  [Stitch] BGM lookup skipped (non-fatal): {exc}')

            render_final(
                clip_paths=list(state.clips.values()),
                voiceover_paths=voiceover_paths or None,
                srt_path=srt_path,
                bgm_path=bgm_path,
                output_path=final_path,
                work_dir=str(work_dir / 'render'),
            )

        state.final_video_path = final_path
        print(f'  [Stitch] Final video: {final_path}')

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

        self.projects.advance_stage(project_id, ProjectStage.PUBLISH)
        self._save_state(project_id, state)
        # Cascade to publish stage (no pause)
        self._exec_publish(project_id, state)

    def _exec_publish(self, project_id: str, state: WorkflowState, brief: str = '') -> None:
        """Stage: publish — export the final video to the publish output dir."""
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
            'project_id': project_id, 'final_video_path': state.final_video_path}))
        flush_traces()

    # ------------------------------------------------------------------
    # YAML workflow graph helpers
    # ------------------------------------------------------------------
    def _stage_handlers(self) -> dict[str, Any]:
        return {
            'requirement': self._exec_requirement,
            'storyboard': self._exec_storyboard,
            'asset_prep': self._exec_asset_prep,
            'scene_gen': self._exec_scene_gen,
            'video_gen': self._exec_video_gen,
            'stitch': self._exec_stitch,
            'publish': self._exec_publish,
        }

    def _load_yaml(self, workflow_name: str = 'product_ad') -> WorkflowStateMachine:
        root = Path(__file__).resolve().parent.parent
        path = root / 'workflows' / f'{workflow_name}_v1.yaml'
        if not path.exists():
            path = root / 'workflows' / f'{workflow_name}.yaml'
        if not path.exists():
            raise FileNotFoundError(f'Workflow not found: {workflow_name}')
        with open(path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
        sm = WorkflowStateMachine(workflow_name=data.get('name', workflow_name))
        for stage in data.get('stages', []):
            sm.add_stage(stage['id'], stage)
        for stage in data.get('stages', []):
            sm.add_edge(stage['id'], stage.get('next'))
        return sm

    def _route_next_stage(self, pause_stage: str, workflow_name: str = 'product_ad') -> str | None:
        """Resolve the next stage after *pause_stage*. Prefers the YAML workflow
        graph; falls back to a hardcoded map if the YAML is missing/malformed
        (keeps the legacy engine working)."""
        try:
            sm = self._load_yaml(workflow_name)
            nxt = sm.get_next_stages(pause_stage)
            if nxt:
                return nxt[0]
        except Exception:
            pass
        fallback = {
            'requirement': 'storyboard',
            'storyboard': 'asset_prep',
            'asset_prep': 'scene_gen',
            'video_gen': 'stitch',
            'video_review': 'stitch',  # backward-compat for pre-v2 paused projects
        }
        return fallback.get(pause_stage)

    # ------------------------------------------------------------------
    # State persistence
    # ------------------------------------------------------------------
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

    def _stitch_videos(self, video_paths: list[str], output_path: str) -> None:
        from tools.ffmpeg import concat_videos
        concat_videos(video_paths, output_path)
