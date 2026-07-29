"""Feishu / WeCom webhook handlers: receive card action callbacks and process approvals."""
from __future__ import annotations

from fastapi import APIRouter, Request

from review.service import ReviewService
from runtime.workflow import WorkflowRuntime

router = APIRouter()
svc = ReviewService()


@router.post("/feishu")
async def feishu_webhook(request: Request) -> dict:
    body = await request.json()

    # Feishu URL verification (required for webhook setup)
    if body.get("type") == "url_verification":
        return {"challenge": body.get("challenge", "")}

    # Card action callback (button click)
    if "action" in body:
        value = body.get("action", {}).get("value", {})
        action = value.get("action", "")
        review_id = value.get("review_id", "")
        project_id = value.get("project_id", "")

        if action in ("approve", "reject") and review_id:
            review = svc.get_review(review_id)
            if review is None:
                return {"status": "error", "message": "Review not found"}

            pid = review.project_id
            if action == "approve":
                svc.approve(review_id, reviewer="feishu")
                print(f"  [Webhook] Approved review {review_id} for project {pid}")
            else:
                svc.reject(review_id, reviewer="feishu")
                print(f"  [Webhook] Rejected review {review_id} for project {pid}")

            # Resume pipeline
            runtime = WorkflowRuntime()
            result = runtime.resume(pid, review_id)
            return {
                "status": "ok",
                "action": action,
                "project_id": pid,
                "review_id": review_id,
                "result": "resumed" if result else "completed",
            }

        # Handle "view" action - just log it (user wants to see details in web UI)
        if action == "view":
            return {"status": "ok", "action": "view"}

        return {"status": "received", "action": action}

    # Feishu v2 eventsub webhook: route to WS listener dispatch for full handling
    header = body.get("header", {})
    event_type = header.get("event_type", body.get("type", ""))
    if event_type in ("im.message.receive_v1", "card.action.trigger"):
        from channels.feishu.ws_listener import dispatch
        result = await dispatch(body)
        return result

    return {"status": "received", "event_type": event_type}


@router.post("/wecom")
async def wecom_webhook(request: Request) -> dict:
    """WeCom webhook handler (placeholder)."""
    body = await request.json()
    # WeCom URL verification
    if body.get("MsgType") == "event" and body.get("Event") == "verify":
        return {"echostr": body.get("EchoStr", "")}
    return {"status": "received"}
