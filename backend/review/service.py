from __future__ import annotations

from typing import Any

from review.queue import ReviewQueue, get_review_queue
from review.comment import ReviewRecord, ReviewStage, ReviewStatus
from events.bus import Event, get_event_bus, EVENT_REVIEW_RESOLVED


class ReviewService:
    def __init__(self, queue: ReviewQueue | None = None) -> None:
        self.queue = queue or get_review_queue()

    def _publish_resolved(self, review: ReviewRecord) -> None:
        bus = get_event_bus()
        bus.publish(Event(EVENT_REVIEW_RESOLVED, {
            "project_id": review.project_id,
            "review_id": review.review_id,
            "stage": review.stage.value,
            "status": review.status.value,
            "reviewer": review.reviewer,
        }))

    def create_requirement_review(self, project_id: str, video_spec: dict[str, Any]) -> ReviewRecord:
        return self.queue.create_review(
            project_id=project_id,
            stage=ReviewStage.REQUIREMENT,
            content={"type": "video_spec", "spec": video_spec},
        )

    def create_storyboard_review(self, project_id: str, storyboard: dict[str, Any]) -> ReviewRecord:
        return self.queue.create_review(
            project_id=project_id,
            stage=ReviewStage.STORYBOARD,
            content={"type": "storyboard", "storyboard": storyboard},
        )

    def create_asset_review(self, project_id: str, assets: dict[str, Any]) -> ReviewRecord:
        return self.queue.create_review(
            project_id=project_id,
            stage=ReviewStage.ASSET_PREP,
            content={"type": "assets", "assets": assets},
        )

    def create_video_review(self, project_id: str, video_info: dict[str, Any]) -> ReviewRecord:
        return self.queue.create_review(
            project_id=project_id,
            stage=ReviewStage.VIDEO_REVIEW,
            content={"type": "video", "video": video_info},
        )

    def approve(self, review_id: str, reviewer: str = "", comment: str = "") -> ReviewRecord | None:
        r = self.queue.approve(review_id, reviewer, comment)
        if r:
            self._publish_resolved(r)
        return r

    def reject(self, review_id: str, reviewer: str = "", comment: str = "") -> ReviewRecord | None:
        r = self.queue.reject(review_id, reviewer, comment)
        if r:
            self._publish_resolved(r)
        return r

    def partial_revision(self, review_id: str, reviewer: str = "", comment: str = "") -> ReviewRecord | None:
        r = self.queue.get_review(review_id)
        if r:
            r.partial_revision(reviewer, comment)
            self._publish_resolved(r)
        return r

    def add_comment(self, review_id: str, text: str, reviewer: str = "") -> ReviewRecord | None:
        return self.queue.add_comment(review_id, text, reviewer)

    def get_review(self, review_id: str) -> ReviewRecord | None:
        return self.queue.get_review(review_id)

    def list_pending(self, project_id: str | None = None) -> list[ReviewRecord]:
        return self.queue.list_reviews(project_id=project_id, status="pending")

    def list_by_project(self, project_id: str) -> list[ReviewRecord]:
        return self.queue.list_reviews(project_id=project_id)

    def is_project_blocked(self, project_id: str) -> bool:
        return any(
            r.status == ReviewStatus.PENDING
            for r in self.queue.list_reviews(project_id=project_id)
        )
