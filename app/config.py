import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
# 项目根 .env 优先于系统/终端里已存在的同名变量（避免 SESSION 里 VIDEO_PROVIDER=lavfi 覆盖 .env）
load_dotenv(PROJECT_ROOT / ".env", override=True)
SKILLS_ROOT = Path(os.getenv("SMARTVIDEO_SKILLS_ROOT", PROJECT_ROOT / "skills")).resolve()
# 每次运行产物目录；默认项目下 outputs/，可用 SMARTVIDEO_ARTIFACTS_DIR 覆盖（仍为「根目录」，子文件夹由时间戳命名）
ARTIFACTS_DIR = Path(os.getenv("SMARTVIDEO_ARTIFACTS_DIR", PROJECT_ROOT / "outputs")).resolve()

# ---- 品牌联网调研：tools = 模型选工具多轮；pipeline = 自动拉 brief 内 URL + DDG ----
BRAND_RESEARCH_STRATEGY = (os.getenv("BRAND_RESEARCH_STRATEGY") or "tools").strip().lower()
BRAND_TOOL_AGENT_MAX_ROUNDS = int(os.getenv("BRAND_TOOL_AGENT_MAX_ROUNDS") or "10")

# ---- LLM（品牌抽取、分镜模板、scenes 等，经 langchain_openai）----
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL")

# ---- 视频生成 API（与 LLM 共用同一 .env；VIDEO_* 未设时回退到 OPENAI_*）----
VIDEO_PROVIDER = (os.getenv("VIDEO_PROVIDER") or "placeholder").strip().lower()
# 单次强制（例如 HTTP 视频网关报错时仍要跑通拼接）：优先级高于 .env 里的 VIDEO_PROVIDER
_fvp = (os.getenv("SMARTVIDEO_FORCE_VIDEO_PROVIDER") or "").strip().lower()
if _fvp:
    VIDEO_PROVIDER = _fvp
VIDEO_API_BASE_URL = os.getenv("VIDEO_API_BASE_URL")
VIDEO_API_KEY = os.getenv("VIDEO_API_KEY")
VIDEO_MODEL = os.getenv("VIDEO_MODEL", "")
VIDEO_SIZE = (os.getenv("VIDEO_SIZE") or "1280x720").strip()
VIDEO_POLL_INTERVAL_SEC = float(os.getenv("VIDEO_POLL_INTERVAL_SEC") or "3")
VIDEO_POLL_TIMEOUT_SEC = float(os.getenv("VIDEO_POLL_TIMEOUT_SEC") or "600")
VIDEO_REQUEST_TIMEOUT_SEC = float(os.getenv("VIDEO_REQUEST_TIMEOUT_SEC") or "120")
VIDEO_DOWNLOAD_READ_TIMEOUT_SEC = float(os.getenv("VIDEO_DOWNLOAD_READ_TIMEOUT_SEC") or "1200")
# HttpVideoProvider：留空表示 VIDEO_API_BASE_URL 本身即为完整 POST 地址
VIDEO_API_PATH = os.getenv("VIDEO_API_PATH", "")
VIDEO_HTTP_TIMEOUT = float(os.getenv("VIDEO_HTTP_TIMEOUT") or "120")


def _env_bool(name: str, default: bool) -> bool:
    raw = (os.getenv(name) or "").strip().lower()
    if raw == "":
        return default
    return raw in ("1", "true", "yes", "on")


# ---- Audio post-processing (tts/sfx/bgm/mastering) ----
AUDIO_ENABLE = _env_bool("AUDIO_ENABLE", True)
AUDIO_FAILOPEN = _env_bool("AUDIO_FAILOPEN", True)
AUDIO_TTS_ENABLE = _env_bool("AUDIO_TTS_ENABLE", True)
AUDIO_SFX_ENABLE = _env_bool("AUDIO_SFX_ENABLE", True)
AUDIO_BGM_ENABLE = _env_bool("AUDIO_BGM_ENABLE", True)
AUDIO_BGM_DUCKING = _env_bool("AUDIO_BGM_DUCKING", True)
AUDIO_TTS_PROVIDER = (os.getenv("AUDIO_TTS_PROVIDER") or "openai").strip().lower()
AUDIO_TTS_MODEL = (os.getenv("AUDIO_TTS_MODEL") or "gpt-4o-mini-tts").strip()
AUDIO_TTS_VOICE = (os.getenv("AUDIO_TTS_VOICE") or "alloy").strip()
AUDIO_TTS_SPEED = float(os.getenv("AUDIO_TTS_SPEED") or "1.0")
AUDIO_TTS_TIMEOUT_SEC = float(os.getenv("AUDIO_TTS_TIMEOUT_SEC") or "120")
AUDIO_TTS_API_KEY = (os.getenv("AUDIO_TTS_API_KEY") or "").strip()
AUDIO_TTS_BASE_URL = (os.getenv("AUDIO_TTS_BASE_URL") or "").strip()
AUDIO_BGM_PATH = (os.getenv("AUDIO_BGM_PATH") or "").strip()
AUDIO_BGM_GAIN_DB = float(os.getenv("AUDIO_BGM_GAIN_DB") or "-24")
AUDIO_TARGET_LUFS = float(os.getenv("AUDIO_TARGET_LUFS") or "-14")
AUDIO_DUCKING_RATIO = float(os.getenv("AUDIO_DUCKING_RATIO") or "10")
AUDIO_NARRATION_GAIN_DB = float(os.getenv("AUDIO_NARRATION_GAIN_DB") or "2")
AUDIO_SFX_GAIN_DB = float(os.getenv("AUDIO_SFX_GAIN_DB") or "-2")


def effective_video_api_base_url() -> str | None:
    raw = (VIDEO_API_BASE_URL or OPENAI_BASE_URL or "").strip()
    return raw or None


def effective_video_api_key() -> str | None:
    raw = (VIDEO_API_KEY or os.getenv("OPENAI_API_KEY") or "").strip()
    return raw or None


def effective_audio_tts_base_url() -> str | None:
    raw = (AUDIO_TTS_BASE_URL or OPENAI_BASE_URL or "").strip()
    return raw or None


def effective_audio_tts_api_key() -> str | None:
    raw = (AUDIO_TTS_API_KEY or os.getenv("OPENAI_API_KEY") or "").strip()
    return raw or None
