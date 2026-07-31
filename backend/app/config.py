from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

BACKEND_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(BACKEND_ROOT / '.env', override=True)

# ���� General ����������������������������������������������������������������������������������������������������
DATA_DIR = BACKEND_ROOT / 'data'
PROJECTS_DIR = DATA_DIR / 'projects'
ASSETS_DIR = DATA_DIR / 'assets'
WORKFLOWS_DIR = BACKEND_ROOT / 'workflows'
SKILLS_DIR = BACKEND_ROOT / 'skills'

DATA_DIR.mkdir(parents=True, exist_ok=True)
PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
ASSETS_DIR.mkdir(parents=True, exist_ok=True)

# ���� LLM ������������������������������������������������������������������������������������������������������������
LLM_PROVIDER = (os.getenv('LLM_PROVIDER') or 'openai').strip().lower()
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', '')
OPENAI_BASE_URL = os.getenv('OPENAI_BASE_URL', '')
OPENAI_MODEL = os.getenv('OPENAI_MODEL', 'gpt-4o-mini')

# ── DeepSeek (OpenAI-compatible) ──────────────────────────────────────────
DEEPSEEK_API_KEY = os.getenv('DEEPSEEK_API_KEY', '')
DEEPSEEK_BASE_URL = (os.getenv('DEEPSEEK_BASE_URL') or 'https://api.deepseek.com').strip().rstrip('/')
DEEPSEEK_MODEL = (os.getenv('DEEPSEEK_MODEL') or 'deepseek-v4-flash').strip()

# ���� Video ��������������������������������������������������������������������������������������������������������
VIDEO_PROVIDER = (os.getenv('VIDEO_PROVIDER') or 'placeholder').strip().lower()
VIDEO_API_BASE_URL = os.getenv('VIDEO_API_BASE_URL', '')
VIDEO_API_KEY = os.getenv('VIDEO_API_KEY', '')
VIDEO_MODEL = os.getenv('VIDEO_MODEL', '')
VIDEO_SIZE = (os.getenv('VIDEO_SIZE') or '1280x720').strip()
VIDEO_POLL_INTERVAL_SEC = float(os.getenv('VIDEO_POLL_INTERVAL_SEC') or '3')
VIDEO_POLL_TIMEOUT_SEC = float(os.getenv('VIDEO_POLL_TIMEOUT_SEC') or '600')
VIDEO_REQUEST_TIMEOUT_SEC = float(os.getenv('VIDEO_REQUEST_TIMEOUT_SEC') or '120')

# ���� Audio ��������������������������������������������������������������������������������������������������������
# --- Kling Video Provider ---
KLING_API_KEY = os.getenv('KLING_API_KEY', '')
KLING_BASE_URL = (os.getenv('KLING_BASE_URL') or 'https://api-beijing.klingai.com').strip().rstrip('/')
KLING_MODEL = (os.getenv('KLING_MODEL') or 'kling-2.5-turbo').strip()
KLING_DURATION = int(os.getenv('KLING_DURATION', '5'))
KLING_ASPECT_RATIO = (os.getenv('KLING_ASPECT_RATIO') or '16:9').strip()
KLING_RESOLUTION = (os.getenv('KLING_RESOLUTION') or '720p').strip()
KLING_AUDIO = (os.getenv('KLING_AUDIO') or 'off').strip().lower()
KLING_POLL_INTERVAL = float(os.getenv('KLING_POLL_INTERVAL', '5'))
KLING_POLL_TIMEOUT = float(os.getenv('KLING_POLL_TIMEOUT', '600'))

AUDIO_ENABLE = True
AUDIO_TTS_PROVIDER = (os.getenv('AUDIO_TTS_PROVIDER') or 'openai').strip().lower()
AUDIO_TTS_MODEL = (os.getenv('AUDIO_TTS_MODEL') or 'gpt-4o-mini-tts').strip()
AUDIO_TTS_VOICE = (os.getenv('AUDIO_TTS_VOICE') or 'alloy').strip()
AUDIO_TTS_SPEED = float(os.getenv('AUDIO_TTS_SPEED') or '1.0')
AUDIO_TTS_BASE_URL = os.getenv('AUDIO_TTS_BASE_URL', '')
AUDIO_TTS_API_KEY = os.getenv('AUDIO_TTS_API_KEY', '')

# ── Feishu ────────────────────────────────────────────────────
FEISHU_APP_ID = os.getenv('FEISHU_APP_ID', '')
FEISHU_APP_SECRET = os.getenv('FEISHU_APP_SECRET', '')
FEISHU_ENABLED = bool(FEISHU_APP_ID and FEISHU_APP_SECRET)
FEISHU_REVIEWER_OPEN_ID = os.getenv('FEISHU_REVIEWER_OPEN_ID', '')
FEISHU_CALLBACK_MODE = (os.getenv('FEISHU_CALLBACK_MODE') or 'webhook').strip().lower()

# ── FFmpeg ────────────────────────────────────────────────────
# Optional explicit path to the ffmpeg binary. When unset, tools.ffmpeg
# auto-detects common install locations (WinGet temp, Program Files, etc.)
# so the backend does not depend on the launching shell's PATH.
FFMPEG_BIN = os.getenv('FFMPEG_BIN', '')
