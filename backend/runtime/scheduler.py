from __future__ import annotations

import asyncio
from typing import Any, Callable


class WorkflowScheduler:
    def __init__(self, max_workers: int = 4) -> None:
        self.max_workers = max_workers

    async def run_async(self, fn: Callable[[], Any]) -> Any:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, fn)

    async def run_parallel(self, tasks: list[Callable[[], Any]]) -> list[Any]:
        import asyncio
        coros = [asyncio.to_thread(t) for t in tasks]
        return await asyncio.gather(*coros, return_exceptions=True)

    async def wait_for_condition(self, check_fn: Callable[[], bool], timeout: float = 300.0, interval: float = 2.0) -> bool:
        elapsed = 0.0
        while elapsed < timeout:
            if check_fn():
                return True
            await asyncio.sleep(interval)
            elapsed += interval
        return False

    async def wait_for_review(self, project_id: str, review_id: str, timeout: float = 86400.0) -> bool:
        from review.service import ReviewService
        svc = ReviewService()

        def check() -> bool:
            r = svc.get_review(review_id)
            return r is not None and r.status.value != 'pending'

        return await self.wait_for_condition(check, timeout=timeout)
