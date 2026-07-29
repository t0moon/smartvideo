from __future__ import annotations

from typing import Any

from review.service import ReviewService
from review.comment import ReviewStatus


class ReviewContextProvider:
    name = 'review'

    def provide(self, project_id: str, run_id: str = 'default') -> dict[str, Any]:
        svc = ReviewService()
        reviews = svc.list_by_project(project_id)
        pending = [r for r in reviews if r.status == ReviewStatus.PENDING]
        return {
            'total_reviews': len(reviews),
            'pending_count': len(pending),
            'pending_reviews': [
                {'review_id': r.review_id, 'stage': r.stage.value, 'status': r.status.value}
                for r in pending
            ],
            'is_blocked': svc.is_project_blocked(project_id),
        }
