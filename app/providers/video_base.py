from typing import Protocol


class VideoProvider(Protocol):
    def generate(
        self,
        scene_id: str,
        prompt: str,
        negative_prompt: str,
        *,
        duration_sec: float = 5.0,
    ) -> str:
        """返回本地视频文件路径，或可直接下载的视频 URL（由节点侧落盘）。"""
        ...
