from __future__ import annotations


class SmartVideoError(Exception):
    pass


class ProjectNotFoundError(SmartVideoError):
    def __init__(self, project_id: str) -> None:
        super().__init__(f'Project not found: {project_id}')


class WorkspaceError(SmartVideoError):
    pass


class ProviderError(SmartVideoError):
    def __init__(self, provider: str, message: str) -> None:
        super().__init__(f'[{provider}] {message}')


class LLMError(ProviderError):
    def __init__(self, message: str) -> None:
        super().__init__('LLM', message)


class VideoProviderError(ProviderError):
    def __init__(self, message: str) -> None:
        super().__init__('Video', message)


class AgentError(SmartVideoError):
    def __init__(self, step: str, message: str) -> None:
        super().__init__(f'[{step}] {message}')


class GuardrailError(SmartVideoError):
    def __init__(self, rule: str, message: str) -> None:
        super().__init__(f'Guardrail [{rule}]: {message}')


class ReviewError(SmartVideoError):
    pass


class PublishError(SmartVideoError):
    pass
