from __future__ import annotations

from langchain_core.messages import AIMessage

from app.artifacts import resolve_artifact_run_id, write_artifact_json
from app.graph.state import AgentState
from app.llm import chat_with_structured_output
from app.schemas.storyboard import Scene, ScenesPayload, validate_scenes_list


_SCENES_SYSTEM = """你是分镜执行单生成助手。基于品牌档案、分镜模板 storyboard_template（含 tone_style 与 shots 时间轴）、世界观约束，生成可交给视频模型的分镜列表。
要求：
- 每个 scene 的 id 优先沿用 shots[].id（如 S01）；若需拆分再使用 scene_1 等并说明顺序与模板对应关系。
- duration_sec 为正数；优先取 shots 中 (end_s - start_s)，可与模板略有调整但需说明。
- visual_prompt 必须综合该镜的 visual.scene、subjects、actions、style 与 tone_style，具体可拍摄；与 world_constraints.visual_style 一致。
- negative_prompt 列出要避免的画面元素，并覆盖 taboo_points 中的视觉化禁忌。
- narration 对齐 voiceover.text 与 on_screen_text 要点，可为空。
镜头数量与 storyboard_template.shots 对齐或为其子集/合理细分，不要无故增加与 brief 无关的镜头。"""


def node_generate_scenes(state: AgentState) -> dict:
    brand = state.get("brand_profile") or {}
    template = state.get("storyboard_template") or {}
    world = state.get("world_constraints") or {}
    if not template or not world:
        err = {"step": "scenes", "message": "缺少 storyboard_template 或 world_constraints。"}
        return {"errors": (state.get("errors") or []) + [err]}

    llm = chat_with_structured_output(ScenesPayload)
    user_payload = (
        f"brand_profile={brand}\n\n"
        f"storyboard_template={template}\n\n"
        f"world_constraints={world}\n"
    )
    try:
        out = llm.invoke(
            [
                ("system", _SCENES_SYSTEM),
                ("human", user_payload),
            ]
        )
    except Exception as exc:  # noqa: BLE001
        err = {"step": "scenes", "message": f"LLM 调用或解析失败：{exc}"}
        return {"errors": (state.get("errors") or []) + [err]}
    if out is None:
        shots = list((template.get("shots") or []))
        if not shots:
            err = {"step": "scenes", "message": "结构化输出为空且 storyboard_template.shots 不可用。"}
            return {"errors": (state.get("errors") or []) + [err]}
        scenes_fb: list[Scene] = []
        taboo = " ".join((brand.get("taboo_points") or [])[:5])
        for sh in shots:
            sid = str((sh.get("id") or "")).strip()
            if not sid:
                continue
            start = float(sh.get("start_s") or 0.0)
            end = float(sh.get("end_s") or (start + 5.0))
            dur = max(0.1, end - start)
            vis = sh.get("visual") or {}
            parts = [
                str(vis.get("scene") or "").strip(),
                ", ".join(vis.get("subjects") or []),
                ", ".join(vis.get("actions") or []),
                ", ".join(vis.get("style") or []),
            ]
            vp = "；".join(p for p in parts if p).strip() or "产品展示，清晰写实"
            vo = None
            vob = sh.get("voiceover")
            if isinstance(vob, dict):
                vo = vob.get("text")
            neg_bits = ["低分辨率", "变形人脸", "水印"]
            if taboo:
                neg_bits.append(taboo)
            scenes_fb.append(
                Scene(
                    id=sid,
                    duration_sec=dur,
                    visual_prompt=vp,
                    negative_prompt="；".join(neg_bits),
                    narration=(vo or "").strip(),
                )
            )
        if not scenes_fb:
            err = {"step": "scenes", "message": "从 storyboard_template 无法生成有效 scenes。"}
            return {"errors": (state.get("errors") or []) + [err]}
        out = ScenesPayload(scenes=scenes_fb)
    scene_errs = validate_scenes_list(out.scenes)
    if scene_errs:
        err = {"step": "scenes", "message": "；".join(scene_errs)}
        return {"errors": (state.get("errors") or []) + [err]}
    scenes = [s.model_dump() for s in out.scenes]

    rid, extra = resolve_artifact_run_id(state)  # type: ignore[arg-type]
    write_artifact_json(rid, "scenes.json", scenes)
    write_artifact_json(
        rid,
        "storyboard_script.json",
        {
            "storyboard_template": template,
            "world_constraints": world,
            "scenes": scenes,
        },
    )

    return {
        "scenes": scenes,
        "messages": [AIMessage(content=f"已生成 {len(scenes)} 条分镜。")],
        **extra,
    }
