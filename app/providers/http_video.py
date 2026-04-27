from __future__ import annotations

import base64
import json
import os
import re
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx

from app.media.ffmpeg import transcode_clip_for_concat_copy


_URL_KEYS = (
    "url",
    "video_url",
    "download_url",
    "output_url",
    "href",
    "video",
    "file",
    "link",
    "src",
    "mp4",
    "output",
    "result_url",
    "file_url",
)


def _extract_url_from_json(obj: Any, depth: int = 0) -> str | None:
    if depth > 10:
        return None
    if isinstance(obj, str) and obj.startswith(("http://", "https://")):
        return obj
    if isinstance(obj, dict):
        for key in _URL_KEYS:
            v = obj.get(key)
            if isinstance(v, str) and v.startswith(("http://", "https://")):
                return v
        for v in obj.values():
            found = _extract_url_from_json(v, depth + 1)
            if found:
                return found
    if isinstance(obj, list):
        for item in obj:
            found = _extract_url_from_json(item, depth + 1)
            if found:
                return found
        return None
    return None


def _extract_url_loose(obj: Any) -> str | None:
    """Try structured URL fields first, then fallback to regex URL extraction."""
    u = _extract_url_from_json(obj)
    if u:
        return u
    try:
        s = json.dumps(obj, ensure_ascii=False)
    except (TypeError, ValueError):
        s = str(obj)
    for m in re.finditer(r"https?://[^\s\"'<>\\]+", s):
        link = m.group(0).rstrip("\"'.,);\\]}")
        if link.startswith(("http://", "https://")):
            return link
    return None


def _join_api_url(base: str, path: str) -> str:
    path = (path or "").strip()
    if path.startswith(("http://", "https://")):
        return path
    base = base.rstrip("/")
    if not path.startswith("/"):
        path = "/" + path
    return base + path


_STATUS_DONE = frozenset({"completed", "success", "succeeded", "done", "complete"})
_STATUS_FAIL = frozenset({"failed", "error", "cancelled", "canceled"})
_STATUS_WAIT = frozenset(
    {"queued", "pending", "processing", "in_progress", "running", "generating", "waiting"}
)
_RETRYABLE_HTTP_STATUS = frozenset({408, 409, 425, 429, 500, 502, 503, 504})
_RETRYABLE_ERR_KEYWORDS_LOWER = (
    "try again",
    "temporary",
    "timeout",
    "timed out",
    "rate limit",
    "overload",
    "service unavailable",
    "internal error",
    "gateway",
)
_RETRYABLE_ERR_KEYWORDS_CN = (
    "重新发起请求",
    "稍后重试",
    "服务繁忙",
    "系统繁忙",
    "生成过程中出现异常",
    "超时",
    "限流",
)


class _RetryableGenerateError(RuntimeError):
    pass


def _error_to_text(err: Any) -> str:
    if isinstance(err, str):
        return err
    if isinstance(err, (dict, list, tuple)):
        try:
            return json.dumps(err, ensure_ascii=False)
        except (TypeError, ValueError):
            return str(err)
    return str(err)


def _is_retryable_failure_error(err: Any) -> bool:
    text = _error_to_text(err)
    if not text:
        return False
    lowered = text.lower()
    if any(k in lowered for k in _RETRYABLE_ERR_KEYWORDS_LOWER):
        return True
    return any(k in text for k in _RETRYABLE_ERR_KEYWORDS_CN)


def _status_lower(payload: dict[str, Any]) -> str:
    return str(payload.get("status") or "").strip().lower()


def _origin_from_endpoint(create_endpoint: str) -> str:
    u = urlparse(create_endpoint)
    return f"{u.scheme}://{u.netloc}"


def _retrieve_meta_url(create_endpoint: str, job_id: str) -> str:
    """Resolve job metadata URL, optionally overridden by VIDEO_HTTP_RETRIEVE_URL."""
    tpl = (os.getenv("VIDEO_HTTP_RETRIEVE_URL") or "").strip()
    if tpl:
        return tpl.replace("{id}", job_id).replace("{video_id}", job_id)
    # 榛樿锛氬鏁?OpenAI 鍏煎缃戝叧涓?GET {origin}/v1/videos/{id}锛堜笌 POST /v1/videos 鎴?/v1/video/create 骞跺瓨锛?
    return f"{_origin_from_endpoint(create_endpoint)}/v1/videos/{job_id}"


def _content_download_url(create_endpoint: str, job_id: str) -> str:
    tpl = (os.getenv("VIDEO_HTTP_CONTENT_URL") or "").strip()
    if tpl:
        return tpl.replace("{id}", job_id).replace("{video_id}", job_id)
    return f"{_origin_from_endpoint(create_endpoint)}/v1/videos/{job_id}/content"


def _resolve_endpoint(base_url: str, api_path: str) -> str:
    """Resolve POST endpoint. Empty api_path means base_url is the full endpoint."""
    p = (api_path or "").strip()
    if not p or p == "/":
        return base_url.rstrip("/")
    return _join_api_url(base_url, p)


def _env_bool(name: str, *, default: bool = True) -> bool:
    raw = (os.getenv(name) or "").strip().lower()
    if raw == "":
        return default
    return raw in ("1", "true", "yes", "on")


def _image_urls_from_env() -> list[str]:
    """Parse comma-separated HTTPS image URLs from VIDEO_HTTP_IMAGE_URLS."""
    raw = (os.getenv("VIDEO_HTTP_IMAGE_URLS") or "").strip()
    if not raw:
        return []
    return [u.strip() for u in raw.split(",") if u.strip().startswith(("http://", "https://"))]


def _aspect_ratio_from_env() -> str:
    ar = (os.getenv("VIDEO_ASPECT_RATIO") or "").strip()
    if ar:
        return ar
    size = (os.getenv("VIDEO_SIZE") or "1280x720").lower().replace(" ", "")
    if "9:16" in size or "720x1280" in size or "1080x1920" in size:
        return "9:16"
    return "16:9"


def build_http_video_create_body(
    *,
    scene_id: str,
    prompt: str,
    negative_prompt: str,
    duration_sec: float,
    model: str,
) -> dict[str, Any]:
    """鏋勫缓 POST /v1/video/create 鐨?JSON body銆?

    榛樿 ``VIDEO_HTTP_BODY_MODE=veo`` 瀵归綈缃戝叧绀轰緥锛歱rompt銆乵odel銆乮mages锛堝彲閫夛級銆?
    enhance_prompt銆乤spect_ratio銆乿eo_fl_close銆?

    鑻ラ渶鏃х増鑷畾涔夊瓧娈碉紙scene_id銆乶egative_prompt銆乨uration_sec锛夛紝璁剧疆
    ``VIDEO_HTTP_BODY_MODE=legacy``銆?
    """
    mode = (os.getenv("VIDEO_HTTP_BODY_MODE") or "veo").strip().lower()
    if mode in ("legacy", "generic", "old"):
        body: dict[str, Any] = {
            "scene_id": scene_id,
            "prompt": prompt,
            "negative_prompt": negative_prompt,
            "duration_sec": float(duration_sec),
        }
        if model.strip():
            body["model"] = model.strip()
        return body

    full_prompt = (prompt or "").strip()
    neg = (negative_prompt or "").strip()
    if neg:
        full_prompt = (
            f"{full_prompt}\n\nAvoid / negative: {neg}"
            if full_prompt
            else f"Avoid / negative: {neg}"
        )

    body_veo: dict[str, Any] = {
        "prompt": full_prompt,
        "enhance_prompt": _env_bool("VIDEO_ENHANCE_PROMPT", default=True),
        "aspect_ratio": _aspect_ratio_from_env(),
        "veo_fl_close": _env_bool("VIDEO_VEO_FL_CLOSE", default=True),
    }
    if model.strip():
        body_veo["model"] = model.strip()

    imgs = _image_urls_from_env()
    if imgs:
        body_veo["images"] = imgs

    if _env_bool("VIDEO_HTTP_SEND_DURATION", default=False):
        body_veo["duration_sec"] = float(duration_sec)

    return body_veo


class HttpVideoProvider:
    """HTTP JSON video provider that downloads/transcodes clips for stitching."""

    def __init__(
        self,
        *,
        work_dir: Path,
        base_url: str,
        api_key: str,
        api_path: str = "",
        model: str = "",
        timeout_sec: float = 120.0,
        poll_interval_sec: float = 3.0,
        poll_timeout_sec: float = 600.0,
        download_read_timeout_sec: float = 1200.0,
        max_retries: int | None = None,
        retry_backoff_sec: float | None = None,
    ) -> None:
        self._work_dir = work_dir
        self._base = base_url.rstrip("/")
        self._key = api_key
        self._path = api_path
        self._model = model
        self._timeout = timeout_sec
        self._poll_interval = poll_interval_sec
        self._poll_timeout = poll_timeout_sec
        self._download_read_timeout = download_read_timeout_sec
        mr_raw = max_retries if max_retries is not None else os.getenv("VIDEO_HTTP_MAX_RETRIES", "2")
        rb_raw = (
            retry_backoff_sec
            if retry_backoff_sec is not None
            else os.getenv("VIDEO_HTTP_RETRY_BACKOFF_SEC", "2")
        )
        self._max_retries = max(0, int(mr_raw))
        self._retry_backoff_sec = max(0.0, float(rb_raw))

    def generate(
        self,
        scene_id: str,
        prompt: str,
        negative_prompt: str,
        *,
        duration_sec: float = 5.0,
    ) -> str:
        total_attempts = self._max_retries + 1
        last_error: Exception | None = None
        for attempt in range(1, total_attempts + 1):
            try:
                return self._generate_once(
                    scene_id=scene_id,
                    prompt=prompt,
                    negative_prompt=negative_prompt,
                    duration_sec=duration_sec,
                )
            except (_RetryableGenerateError, TimeoutError, httpx.TimeoutException, httpx.TransportError) as e:
                last_error = e
            except RuntimeError as e:
                if not _is_retryable_failure_error(e):
                    raise
                last_error = e

            if attempt < total_attempts:
                time.sleep(self._retry_backoff_sec * attempt)

        assert last_error is not None
        raise RuntimeError(f"{last_error} (retried {total_attempts - 1} times)") from last_error

    def _generate_once(
        self,
        scene_id: str,
        prompt: str,
        negative_prompt: str,
        *,
        duration_sec: float = 5.0,
    ) -> str:
        if not self._base or not self._key:
            raise RuntimeError("HttpVideoProvider requires base_url and api_key.")

        endpoint = _resolve_endpoint(self._base, self._path)
        body = build_http_video_create_body(
            scene_id=scene_id,
            prompt=prompt,
            negative_prompt=negative_prompt,
            duration_sec=duration_sec,
            model=self._model,
        )

        headers = {
            "Authorization": f"Bearer {self._key}",
            "Content-Type": "application/json",
        }
        poll_headers = {
            "Authorization": f"Bearer {self._key}",
            "Accept": "application/json",
        }

        safe = re.sub(r"[^0-9A-Za-z._-]+", "_", scene_id).strip("_") or "scene"
        raw_path = self._work_dir / f"{safe}.raw.http.mp4"
        out_path = self._work_dir / f"{safe}.mp4"
        self._work_dir.mkdir(parents=True, exist_ok=True)

        with httpx.Client(timeout=self._timeout) as client:
            resp = client.post(endpoint, json=body, headers=headers)
            ct = (resp.headers.get("content-type") or "").split(";")[0].strip().lower()

            if resp.status_code >= 400:
                detail = resp.text[:2000] if resp.text else ""
                msg = f"Video API HTTP {resp.status_code}: {detail}"
                if resp.status_code in _RETRYABLE_HTTP_STATUS:
                    raise _RetryableGenerateError(msg)
                raise RuntimeError(msg)

            if ct.startswith("video/") or (
                ct == "application/octet-stream" and len(resp.content) > 100
            ):
                raw_path.write_bytes(resp.content)
            else:
                try:
                    payload = resp.json()
                except json.JSONDecodeError as e:
                    raise RuntimeError(f"Video API returned non-JSON payload: {ct} {e}") from e

                payload = self._maybe_poll_job(client, endpoint, payload, poll_headers)
                url = _extract_url_loose(payload) if isinstance(payload, dict) else None
                if url:
                    self._download_url(client, url, raw_path)
                else:
                    b64 = None
                    if isinstance(payload, dict):
                        b64 = payload.get("b64_json") or payload.get("video_b64")
                    if isinstance(b64, str) and b64:
                        raw_path.write_bytes(base64.b64decode(b64))
                    elif isinstance(payload, dict) and _status_lower(payload) in _STATUS_DONE:
                        jid = str(payload.get("id") or "").strip()
                        if jid:
                            self._download_job_content(client, endpoint, jid, raw_path, poll_headers)
                        else:
                            preview = json.dumps(payload, ensure_ascii=False)[:800]
                            raise RuntimeError(
                                "Task completed but no job id returned, cannot download content."
                                f" Response preview: {preview}"
                            )
                    else:
                        preview = (
                            json.dumps(payload, ensure_ascii=False)[:800]
                            if isinstance(payload, (dict, list))
                            else str(payload)[:800]
                        )
                        raise RuntimeError(
                            "Could not parse url or video bytes from video API response."
                            f" Response preview: {preview}"
                        )

        transcode_clip_for_concat_copy(raw_path, out_path)
        try:
            raw_path.unlink(missing_ok=True)
        except OSError:
            pass
        return str(out_path.resolve())

    def _maybe_poll_job(
        self,
        client: httpx.Client,
        create_endpoint: str,
        payload: Any,
        poll_headers: dict[str, str],
    ) -> Any:
        """Poll metadata for async jobs until completion or failure."""
        if not isinstance(payload, dict):
            return payload
        jid = str(payload.get("id") or "").strip()
        st = _status_lower(payload)
        if st in _STATUS_FAIL:
            err = payload.get("error", payload)
            msg = f"Video task failed: {err}"
            if _is_retryable_failure_error(err):
                raise _RetryableGenerateError(msg)
            raise RuntimeError(msg)
        if st in _STATUS_DONE or not jid:
            return payload
        if st not in _STATUS_WAIT:
            return payload

        meta_url = _retrieve_meta_url(create_endpoint, jid)
        deadline = time.monotonic() + float(self._poll_timeout)
        cur: dict[str, Any] = payload
        while time.monotonic() < deadline:
            time.sleep(self._poll_interval)
            pr = client.get(meta_url, headers=poll_headers)
            if pr.status_code >= 400:
                detail = pr.text[:2000] if pr.text else ""
                msg = f"Video task query HTTP {pr.status_code}: {detail}"
                if pr.status_code in _RETRYABLE_HTTP_STATUS:
                    raise _RetryableGenerateError(msg)
                raise RuntimeError(msg)
            try:
                cur = pr.json()
            except json.JSONDecodeError as e:
                raise RuntimeError(f"Video task query returned non-JSON payload: {e}") from e
            if not isinstance(cur, dict):
                raise RuntimeError(f"Video task query returned invalid payload: {cur!r}")
            st = _status_lower(cur)
            if st in _STATUS_FAIL:
                err = cur.get("error", cur)
                msg = f"Video task failed: {err}"
                if _is_retryable_failure_error(err):
                    raise _RetryableGenerateError(msg)
                raise RuntimeError(msg)
            if st in _STATUS_DONE:
                return cur
            if st not in _STATUS_WAIT and st not in _STATUS_DONE:
                return cur
        raise TimeoutError(f"Timed out waiting for video task completion (> {self._poll_timeout}s): {jid}")

    def _download_job_content(
        self,
        client: httpx.Client,
        create_endpoint: str,
        job_id: str,
        dest: Path,
        poll_headers: dict[str, str],
    ) -> None:
        cu = _content_download_url(create_endpoint, job_id)
        dl_h = {**poll_headers, "Accept": "video/mp4, application/octet-stream, */*"}
        timeout = httpx.Timeout(120.0, read=float(self._download_read_timeout))
        with client.stream("GET", cu, headers=dl_h, follow_redirects=True, timeout=timeout) as r:
            try:
                r.raise_for_status()
            except httpx.HTTPStatusError as e:
                detail = (e.response.text[:2000] if e.response is not None else "") or ""
                raise RuntimeError(f"Failed to download video content: {e!s} {detail}") from e
            with dest.open("wb") as f:
                for chunk in r.iter_bytes():
                    f.write(chunk)

    def _download_url(self, client: httpx.Client, url: str, dest: Path) -> None:
        with client.stream("GET", url, follow_redirects=True) as r:
            r.raise_for_status()
            with dest.open("wb") as f:
                for chunk in r.iter_bytes():
                    f.write(chunk)
