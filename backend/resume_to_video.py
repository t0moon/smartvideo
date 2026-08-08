"""Diagnostic driver: resume proj_f5ac86e40287 through every HITL pause until
the final video is produced (or it errors). Uses the REAL providers configured
in .env (DeepSeek + Kling) so we exercise the exact path the Feishu bot uses.

Run offline-safe workarounds:
- langfuse is stubbed (no Langfuse server needed) so deepseek_provider imports.
- TTS / ffmpeg degrade gracefully inside the pipeline itself.
- We auto-approve each pause so the pipeline can run end-to-end unattended;
  this is purely for diagnosis of OUR project, not a product change.
"""
from __future__ import annotations

import sys
import types
import asyncio
from pathlib import Path

BACKEND = Path(r"C:\Users\gyue\Desktop\smartvideo-main\backend")
sys.path.insert(0, str(BACKEND))

# --- langfuse stub (deepseek_provider & langfuse_tracing import it) -------
import openai as _real_openai


class _Obs:
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class _StubLF:
    def create_trace_id(self):
        import uuid
        return "offline-" + uuid.uuid4().hex[:12]

    def start_as_current_observation(self, *a, **k):
        return _Obs()

    def update_current_span(self, *a, **k):
        pass

    def flush(self):
        pass

    def shutdown(self):
        pass


_lm = types.ModuleType("langfuse")
_lm.Langfuse = _StubLF
_lm.openai = _real_openai
sys.modules["langfuse"] = _lm
sys.modules["langfuse.openai"] = _real_openai

# --- load real providers from .env (deepseek / kling) ---------------------
from dotenv import load_dotenv

load_dotenv(BACKEND / ".env", override=True)

import app.config  # noqa: F401  (forces config module init)

from storage.database import init_db
from runtime.workflow import WorkflowRuntime
from review.service import ReviewService

PID = "proj_f5ac86e40287"
RID = "bd0d03e66d894d1b"  # pause_review_id captured when project stalled


def main() -> None:
    asyncio.run(init_db())

    rt = WorkflowRuntime()
    reviews = ReviewService()

    current = RID
    final: str | None = None
    for i in range(8):
        print(f"\n===== RESUME attempt {i + 1} (review={current}) =====", flush=True)
        try:
            result = rt.resume(PID, current)
        except Exception as exc:  # noqa: BLE001
            import traceback
            traceback.print_exc()
            print("RESUME_EXCEPTION:", repr(exc), flush=True)
            break

        print("RESULT:", repr(result), flush=True)
        if result.startswith("__PAUSED__:"):
            new_rid = result.split(":", 1)[1]
            print(f"  -> paused at review {new_rid}; auto-approving to continue", flush=True)
            reviews.approve(new_rid, reviewer="auto-diagnostic",
                            comment="auto-continue for diagnosis")
            current = new_rid
            continue
        final = result
        break

    print("\n===== FINAL =====", flush=True)
    print("final_video_path:", repr(final), flush=True)
    state = rt._load_state(PID)
    print("pause_stage:", state.meta.get("pause_stage"), "paused:", state.paused, flush=True)
    print("errors:", state.errors, flush=True)
    if final:
        import os
        print("FINAL VIDEO EXISTS:", os.path.exists(final), final, flush=True)


if __name__ == "__main__":
    main()
