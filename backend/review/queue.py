from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from review.comment import ReviewRecord, ReviewStage, ReviewStatus


class ReviewQueue:
    def __init__(self) -> None:
        self._records: dict[str, ReviewRecord] = {}

    def create_review(
        self,
        project_id: str,
        stage: ReviewStage,
        content: dict[str, Any] | None = None,
    ) -> ReviewRecord:
        record = ReviewRecord(
            project_id=project_id,
            stage=stage,
            content=content or {},
        )
        self._records[record.review_id] = record
        return record

    def get_review(self, review_id: str) -> ReviewRecord | None:
        return self._records.get(review_id)

    def list_reviews(self, project_id: str | None = None, status: str | None = None) -> list[ReviewRecord]:
        results = list(self._records.values())
        if project_id:
            results = [r for r in results if r.project_id == project_id]
        if status:
            results = [r for r in results if r.status.value == status]
        results.sort(key=lambda r: r.created_at, reverse=True)
        return results

    def approve(self, review_id: str, reviewer: str = '', comment: str = '') -> ReviewRecord | None:
        r = self.get_review(review_id)
        if r:
            r.approve(reviewer, comment)
        return r

    def reject(self, review_id: str, reviewer: str = '', comment: str = '') -> ReviewRecord | None:
        r = self.get_review(review_id)
        if r:
            r.reject(reviewer, comment)
        return r

    def add_comment(self, review_id: str, text: str, reviewer: str = '') -> ReviewRecord | None:
        r = self.get_review(review_id)
        if r:
            r.add_comment(text, reviewer)
        return r

    def pending_count(self) -> int:
        return sum(1 for r in self._records.values() if r.status == ReviewStatus.PENDING)


_queue = ReviewQueue()


def get_review_queue() -> ReviewQueue:
    return _queue
