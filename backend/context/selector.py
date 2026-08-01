from __future__ import annotations

from typing import Any


# Stage configuration: what each stage needs as input and produces as output
_STAGE_CONFIGS: dict[str, dict[str, Any]] = {
    'requirement': {
        'inputs': ['project'],
        'produces': ['video_spec'],
        'providers': ['project', 'assets'],
    },
    'storyboard': {
        'inputs': ['video_spec'],
        'produces': ['storyboard'],
        'providers': ['project', 'assets'],
    },
    'scene_gen': {
        'inputs': ['storyboard'],
        'produces': ['scenes'],
        'providers': ['project'],
    },
    'asset_prep': {
        'inputs': ['storyboard', 'video_spec'],
        'produces': ['assets'],
        'providers': ['project'],
    },
    'video_gen': {
        'inputs': ['scenes'],
        'produces': ['clips'],
        'providers': ['project'],
    },
    'stitch': {
        'inputs': ['clips'],
        'produces': ['final_video'],
        'providers': ['project'],
    },
    'review': {
        'inputs': ['video_spec', 'storyboard', 'clips'],
        'produces': [],
        'providers': ['project', 'review'],
    },
    'publish': {
        'inputs': ['final_video'],
        'produces': ['publish_result'],
        'providers': ['project'],
    },
}


class ContextSelector:
    def get_stage_config(self, stage_id: str) -> dict[str, Any]:
        return _STAGE_CONFIGS.get(stage_id, {
            'inputs': [],
            'produces': [],
            'providers': [],
        })

    def get_provider(self, name: str):
        from context.providers.project import ProjectContextProvider
        from context.providers.assets import AssetContextProvider
        from context.providers.review import ReviewContextProvider
        providers = {
            'project': ProjectContextProvider(),
            'assets': AssetContextProvider(),
            'review': ReviewContextProvider(),
        }
        return providers.get(name)
