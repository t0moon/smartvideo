from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Callable


class ParallelExecutor:
    def __init__(self, max_workers: int = 4) -> None:
        self.max_workers = max_workers

    def run_parallel(self, tasks: list[Callable[[], Any]]) -> list[Any]:
        results: list[Any] = []
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {executor.submit(task): i for i, task in enumerate(tasks)}
            for future in as_completed(futures):
                try:
                    results.append(future.result())
                except Exception as e:
                    results.append({'error': str(e)})
        return results

    def map_scenes(self, scenes: list[dict], processor: Callable[[dict], Any]) -> list[Any]:
        tasks = [lambda s=scene: processor(s) for scene in scenes]
        return self.run_parallel(tasks)
