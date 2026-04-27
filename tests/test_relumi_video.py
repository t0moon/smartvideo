"""Relumi（Google Play）相关：品牌 brief 校验、结构化入库与占位视频链路测试。

商店参考：https://play.google.com/store/apps/details?id=com.repairitandroid.prd&hl=en
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from langchain_core.messages import HumanMessage

import app.artifacts as artifacts_mod
from app.graph.nodes.brand import node_extract_brand_profile
from app.graph.nodes import stitch as stitch_mod
from app.graph.nodes import video as video_mod
from app.graph.nodes.stitch import node_stitch_final
from app.graph.nodes.video import node_generate_clips
from app.graph.state import AgentState
from app.media.ffmpeg import ffmpeg_available
from app.providers import factory as video_factory
from app.remake_clips import _load_scenes
from app.schemas.brand import BrandProfile
from app.schemas.storyboard import Scene, validate_scenes_list

_RELUMI_PLAY = (
    "https://play.google.com/store/apps/details?id=com.repairitandroid.prd&hl=en"
)


def _relumi_fixture_text() -> str:
    p = Path(__file__).resolve().parent / "fixtures" / "relumi_brand_brief.json"
    return p.read_text(encoding="utf-8")


def test_relumi_play_store_url_documented() -> None:
    """确保测试与文档中的商店链接一致（防误删）。"""
    raw = _relumi_fixture_text()
    assert _RELUMI_PLAY in raw


def test_relumi_brand_brief_json_validates_as_brand_profile() -> None:
    text = _relumi_fixture_text()
    data = json.loads(text)
    profile = BrandProfile.model_validate(data)
    assert profile.brand_name == "Relumi"
    assert "AI" in profile.product_name or "Retake" in profile.product_name


def test_relumi_extract_brand_profile_accepts_json_without_research(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """与 app.run 传入整段 JSON brief 一致：应直接结构化落盘，不触发联网调研。"""
    monkeypatch.setattr("app.artifacts.ARTIFACTS_DIR", tmp_path)

    brief = _relumi_fixture_text().strip()
    state: AgentState = {
        "messages": [HumanMessage(content=brief)],
        "artifact_run_id": "test_relumi_brand",
    }
    out = node_extract_brand_profile(state)
    assert not out.get("errors")
    bp = out.get("brand_profile") or {}
    assert bp.get("brand_name") == "Relumi"
    assert "开放平台" not in (bp.get("product_description") or "")

    written = tmp_path / "test_relumi_brand" / "brand_profile.json"
    assert written.is_file()
    saved = json.loads(written.read_text(encoding="utf-8"))
    assert saved.get("brand_name") == "Relumi"


def test_relumi_scenes_fixture_passes_video_remake_schema() -> None:
    """示例分镜：与 Relumi 卖点对齐，可通过 remake_clips / 视频节点前的校验。"""
    scenes = [
        Scene(
            id="S01",
            duration_sec=5.0,
            visual_prompt=(
                "智能手机屏幕，相册里一张略有瑕疵的合影；"
                "柔和室内光；界面暗示「修复前/预览」类操作，无真实第三方 logo"
            ),
            negative_prompt="低分辨率；畸形手指；可识别人脸身份；水印",
            narration="有些瞬间没法重拍，但照片还可以再温柔一点。",
        ),
        Scene(
            id="S02",
            duration_sec=5.0,
            visual_prompt=(
                "泛黄老照片平铺在桌面，同位置叠化出更清晰、划痕减轻的版本；"
                "怀旧暖色，写实风格"
            ),
            negative_prompt="低分辨率；过度塑料磨皮；水印",
            narration="把旧回忆擦亮一点，仍然像记忆里那样真实。",
        ),
        Scene(
            id="S03",
            duration_sec=5.0,
            visual_prompt=(
                "一张旅行人像从静态轻微「活」起来：发丝与衣角微动，"
                "背景轻微微动效；结尾留出简洁留白与「先预览再保存」式 UI 暗示"
            ),
            negative_prompt="低分辨率；恐怖谷人脸；水印",
            narration="预览满意再保存，把值得发的版本留给自己。",
        ),
    ]
    assert validate_scenes_list(scenes) == []
    loaded = _load_scenes([s.model_dump() for s in scenes])
    assert [x["id"] for x in loaded] == ["S01", "S02", "S03"]


@pytest.mark.skipif(not ffmpeg_available(), reason="需要系统 PATH 或 FFMPEG_PATH 中的 ffmpeg")
def test_relumi_placeholder_clips_and_final_stitch(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """VIDEO_PROVIDER=lavfi 占位：整链不调用外网视频 API，验证 Relumi 分镜可落成 final.mp4。"""
    monkeypatch.setattr(video_factory, "VIDEO_PROVIDER", "lavfi")
    monkeypatch.setattr(artifacts_mod, "ARTIFACTS_DIR", tmp_path)
    monkeypatch.setattr(video_mod, "ARTIFACTS_DIR", tmp_path)
    monkeypatch.setattr(stitch_mod, "ARTIFACTS_DIR", tmp_path)

    scenes = [
        {
            "id": "S01",
            "duration_sec": 2.0,
            "visual_prompt": "Relumi 风格：手机修图应用界面示意，抽象 UI",
            "negative_prompt": "水印",
            "narration": "",
        },
        {
            "id": "S02",
            "duration_sec": 2.0,
            "visual_prompt": "老照片与修复后对比，柔光桌面",
            "negative_prompt": "水印",
            "narration": "",
        },
    ]
    state: AgentState = {
        "scenes": scenes,
        "artifact_run_id": "test_relumi_video",
    }
    v = node_generate_clips(state)
    assert not v.get("errors"), v.get("errors")
    state.update(v)

    s = node_stitch_final(state)
    assert not s.get("errors"), s.get("errors")
    final = Path(s["final_video_path"])
    assert final.is_file()
    assert final.stat().st_size > 0
