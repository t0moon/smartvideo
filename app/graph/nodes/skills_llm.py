from __future__ import annotations

import re

from langchain_core.messages import AIMessage

from app.artifacts import resolve_artifact_run_id, write_artifact_json
from app.graph.state import AgentState
from app.llm import chat_with_structured_output
from app.schemas.storyboard import (
    SkillsGenerationOutput,
    ShotScript,
    StoryboardTemplate,
    VisualBlock,
    VoiceoverBlock,
    WorldConstraints,
    validate_storyboard_template,
)


_SKILLS_SYSTEM = """你是广告分镜策划与世界观约束生成助手。
你将收到两份由人类维护的 SKILL 文档（分镜模板规则、世界观与合规约束），以及一份结构化品牌档案。
任务：严格遵守 SKILL 中的格式与检查要求，产出：
1) storyboard_template：包含 template_version、tone_style、shots（每镜含 id/start_s/end_s/goal/visual/on_screen_text/voiceover/sfx_music/cta，字段以 SKILL 为准）。
2) world_constraints：hard_rules、soft_preferences、visual_style。

不要编造品牌事实；品牌事实以 brand_profile 为准。禁忌与不确定信息须体现在约束或 shots 文案中。"""


def _brand_hint_from_brief(brand: dict) -> str:
    """结构化字段为空时，从用户 brief（product_description）里尽量抽出品牌/产品简称，避免口播朗读整段说明。"""
    for key in ("brand_name", "product_name"):
        v = (brand.get(key) or "").strip()
        if v:
            return v[:40]
    desc = (brand.get("product_description") or "").strip()
    for pat in (
        r"品牌名[：:]\s*([^\s。,，；;]+)",
        r"品牌[：:]\s*([^\s。,，；;]+)",
        r"产品[：:]\s*([^\s。,，（(]+)",
    ):
        m = re.search(pat, desc)
        if m:
            h = m.group(1).strip()
            if h:
                return h[:40]
    return ""


def _fallback_skills_output(brand: dict) -> SkillsGenerationOutput:
    """部分网关/模型会返回 parsed=None，用最小合法分镜保证流水线可继续（实体产品广告，非 App/修图演示）。"""
    hint = _brand_hint_from_brief(brand)
    if hint:
        s01_vo = f"每天几分钟，{hint}，陪你把护理这件事做得更安心。"
        s02_vo = "看清质地与用法，把温和与光泽留在指尖。"
        s03_vo = f"把{hint}加入你的日常，现在就去了解更多。"
    else:
        s01_vo = "每天几分钟，给肌肤多一点温柔与光泽。"
        s02_vo = "看清质地与用法，把安心感握在手里。"
        s03_vo = "把这一瓶带回家，开启你的下一程护理。"

    return SkillsGenerationOutput(
        storyboard_template=StoryboardTemplate(
            template_version="v1",
            tone_style=["真实", "亲和", "干净"],
            shots=[
                ShotScript(
                    id="S01",
                    start_s=0.0,
                    end_s=5.0,
                    goal="场景共鸣",
                    visual=VisualBlock(
                        scene="居家晨光或通勤前洗手台",
                        subjects=["人物侧脸或手部"],
                        actions=["轻触脸颊、照镜子或涂抹前准备"],
                    ),
                    voiceover=VoiceoverBlock(text=s01_vo),
                ),
                ShotScript(
                    id="S02",
                    start_s=5.0,
                    end_s=10.0,
                    goal="产品展示",
                    visual=VisualBlock(
                        scene="干净桌面或洗手台",
                        subjects=["产品瓶身", "手部"],
                        actions=["挤压、展示质地特写或轻柔涂抹"],
                    ),
                    voiceover=VoiceoverBlock(text=s02_vo),
                ),
                ShotScript(
                    id="S03",
                    start_s=10.0,
                    end_s=15.0,
                    goal="行动号召",
                    visual=VisualBlock(
                        scene="简洁背景产品收尾画面",
                        subjects=["产品与留白背景"],
                        actions=["logo 或瓶身定格，配合口播"],
                    ),
                    voiceover=VoiceoverBlock(text=s03_vo),
                ),
            ],
        ),
        world_constraints=WorldConstraints(
            hard_rules=["不夸大疗效或保证结果", "遵守广告与平台规范"],
            soft_preferences=["自然光线", "人物表情真实", "避免低俗或引人不适画面"],
            visual_style="清晰、写实、偏电商主图与短视频广告质感",
        ),
    )


def node_skills_storyboard_and_world(state: AgentState) -> dict:
    skill_docs = state.get("skill_docs") or {}
    brand = state.get("brand_profile") or {}
    if not skill_docs:
        err = {"step": "skills", "message": "skill_docs 为空，请先执行 load_skills。"}
        return {"errors": (state.get("errors") or []) + [err]}
    if not brand:
        err = {"step": "skills", "message": "brand_profile 为空。"}
        return {"errors": (state.get("errors") or []) + [err]}

    llm = chat_with_structured_output(SkillsGenerationOutput)
    user_payload = (
        "## storyboard_template SKILL\n"
        f"{skill_docs.get('storyboard_template', '')}\n\n"
        "## world_constraints SKILL\n"
        f"{skill_docs.get('world_constraints', '')}\n\n"
        "## brand_profile JSON\n"
        f"{brand}\n"
    )
    try:
        out = llm.invoke(
            [
                ("system", _SKILLS_SYSTEM),
                ("human", user_payload),
            ]
        )
    except Exception as exc:  # noqa: BLE001 — 统一记入 errors，避免整条图崩溃
        err = {"step": "skills", "message": f"LLM 调用或解析失败：{exc}"}
        return {"errors": (state.get("errors") or []) + [err]}
    if out is None:
        out = _fallback_skills_output(brand)
    tmpl_errs = validate_storyboard_template(out.storyboard_template)
    if tmpl_errs:
        err = {"step": "skills", "message": "；".join(tmpl_errs)}
        return {"errors": (state.get("errors") or []) + [err]}

    tmpl_dict = out.storyboard_template.model_dump()
    world_dict = out.world_constraints.model_dump()
    rid, extra = resolve_artifact_run_id(state)  # type: ignore[arg-type]
    write_artifact_json(rid, "storyboard_template.json", tmpl_dict)
    write_artifact_json(rid, "world_constraints.json", world_dict)

    return {
        "storyboard_template": tmpl_dict,
        "world_constraints": world_dict,
        "messages": [AIMessage(content="已生成分镜模板与世界观约束。")],
        **extra,
    }
