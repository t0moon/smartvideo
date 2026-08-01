"""Empirical test: reproduce the asset_prep notify_review path for the live review."""
import os, sys, traceback, logging

# load .env
env_path = os.path.join(os.path.dirname(__file__), ".env")
if os.path.exists(env_path):
    for line in open(env_path, encoding="utf-8"):
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())

logging.basicConfig(level=logging.WARNING, stream=sys.stdout)

PID = "proj_35fe6157acab"
RID = "7a33b6ea932940c1"

print("[diag] importing channel components ...", flush=True)
from channels.feishu import FeishuChannel
from app.config import FEISHU_APP_ID, FEISHU_APP_SECRET, FEISHU_REVIEWER_OPEN_ID
from channels.feishu.async_executor import run_async

print(f"[diag] APP_ID={FEISHU_APP_ID} reviewer={FEISHU_REVIEWER_OPEN_ID}", flush=True)
ch = FeishuChannel(FEISHU_APP_ID, FEISHU_APP_SECRET, FEISHU_REVIEWER_OPEN_ID)

print(f"[diag] calling notify_review({PID}, {RID}, 'asset_prep') ...", flush=True)
try:
    res = run_async(ch.notify_review(PID, RID, "asset_prep"))
    print("[diag] NOTIFY RESULT:", res, flush=True)
except Exception as e:
    print("[diag] NOTIFY RAISED:", repr(e), flush=True)
    traceback.print_exc()

print("[diag] done", flush=True)
