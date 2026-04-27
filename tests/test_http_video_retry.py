import pytest

from app.providers.http_video import (
    HttpVideoProvider,
    _RetryableGenerateError,
    _is_retryable_failure_error,
)


def _provider(tmp_path, *, max_retries: int = 2) -> HttpVideoProvider:
    return HttpVideoProvider(
        work_dir=tmp_path,
        base_url="https://example.com/v1/video/create",
        api_key="k",
        max_retries=max_retries,
        retry_backoff_sec=0.0,
    )


def test_is_retryable_failure_error() -> None:
    assert _is_retryable_failure_error({"message": "生成过程中出现异常，请重新发起请求"})
    assert _is_retryable_failure_error("service unavailable, try again later")
    assert not _is_retryable_failure_error({"message": "invalid model"})


def test_generate_retries_then_succeeds(tmp_path, monkeypatch) -> None:
    provider = _provider(tmp_path, max_retries=2)
    calls = {"n": 0}

    def fake_generate_once(self, scene_id, prompt, negative_prompt, *, duration_sec=5.0):  # type: ignore[no-untyped-def]
        calls["n"] += 1
        if calls["n"] == 1:
            raise _RetryableGenerateError("temporary failure, try again")
        return "ok.mp4"

    monkeypatch.setattr(HttpVideoProvider, "_generate_once", fake_generate_once)
    monkeypatch.setattr("app.providers.http_video.time.sleep", lambda *_args, **_kwargs: None)

    out = provider.generate("S01", "p", "", duration_sec=2.0)
    assert out == "ok.mp4"
    assert calls["n"] == 2


def test_generate_stops_after_max_retries(tmp_path, monkeypatch) -> None:
    provider = _provider(tmp_path, max_retries=2)
    calls = {"n": 0}

    def always_retry(self, scene_id, prompt, negative_prompt, *, duration_sec=5.0):  # type: ignore[no-untyped-def]
        calls["n"] += 1
        raise _RetryableGenerateError("try again")

    monkeypatch.setattr(HttpVideoProvider, "_generate_once", always_retry)
    monkeypatch.setattr("app.providers.http_video.time.sleep", lambda *_args, **_kwargs: None)

    with pytest.raises(RuntimeError, match=r"retried 2 times"):
        provider.generate("S01", "p", "", duration_sec=2.0)
    assert calls["n"] == 3
