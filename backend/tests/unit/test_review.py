"""Tests for Human in the Loop review system."""
from __future__ import annotations

from review.service import ReviewService
from review.queue import ReviewQueue
from review.comment import ReviewStatus, ReviewStage


class TestReviewService:
    def _svc(self) -> ReviewService:
        return ReviewService(ReviewQueue())

    def test_create_requirement_review(self) -> None:
        svc = self._svc()
        r = svc.create_requirement_review("proj_1", {"duration_sec": 30})
        assert r.project_id == "proj_1"
        assert r.stage == ReviewStage.REQUIREMENT
        assert r.status == ReviewStatus.PENDING

    def test_create_storyboard_review(self) -> None:
        svc = self._svc()
        r = svc.create_storyboard_review("proj_1", {"scenes": []})
        assert r.stage == ReviewStage.STORYBOARD

    def test_approve(self) -> None:
        svc = self._svc()
        r = svc.create_requirement_review("proj_1", {})
        svc.approve(r.review_id, "reviewer1", "Looks good")
        updated = svc.get_review(r.review_id)
        assert updated is not None
        assert updated.status == ReviewStatus.APPROVED
        assert updated.reviewer == "reviewer1"
        assert len(updated.comments) == 1

    def test_reject(self) -> None:
        svc = self._svc()
        r = svc.create_requirement_review("proj_1", {})
        svc.reject(r.review_id, "reviewer1", "Needs changes")
        updated = svc.get_review(r.review_id)
        assert updated is not None
        assert updated.status == ReviewStatus.REJECTED
        assert len(updated.comments) == 1

    def test_partial_revision(self) -> None:
        svc = self._svc()
        r = svc.create_storyboard_review("proj_1", {})
        svc.partial_revision(r.review_id, "reviewer1", "Scene 2 needs rework")
        updated = svc.get_review(r.review_id)
        assert updated is not None
        assert updated.status == ReviewStatus.PARTIAL_REVISION

    def test_add_comment(self) -> None:
        svc = self._svc()
        r = svc.create_requirement_review("proj_1", {})
        svc.add_comment(r.review_id, "Any update on this?", "manager")
        updated = svc.get_review(r.review_id)
        assert updated is not None
        assert len(updated.comments) == 1
        assert updated.comments[0].text == "Any update on this?"

    def test_list_pending(self) -> None:
        svc = self._svc()
        r1 = svc.create_requirement_review("proj_a", {})
        r2 = svc.create_storyboard_review("proj_b", {})
        svc.approve(r1.review_id)
        pending = svc.list_pending()
        assert len(pending) == 1
        assert pending[0].review_id == r2.review_id

    def test_is_project_blocked(self) -> None:
        svc = self._svc()
        r = svc.create_requirement_review("blocked_proj", {})
        assert svc.is_project_blocked("blocked_proj") is True
        svc.approve(r.review_id)
        assert svc.is_project_blocked("blocked_proj") is False

    def test_list_by_project(self) -> None:
        svc = self._svc()
        svc.create_requirement_review("proj_x", {})
        svc.create_storyboard_review("proj_x", {})
        svc.create_requirement_review("proj_y", {})
        reviews = svc.list_by_project("proj_x")
        assert len(reviews) == 2
