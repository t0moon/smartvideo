from pydantic import BaseModel, Field


class VisualBlock(BaseModel):
    scene: str = ""
    subjects: list[str] = Field(default_factory=list)
    actions: list[str] = Field(default_factory=list)
    ui_elements: list[str] = Field(default_factory=list)
    key_props: list[str] = Field(default_factory=list)
    style: list[str] = Field(default_factory=list)


class OnScreenTextItem(BaseModel):
    text: str
    type: str = ""
    position_hint: str | None = None
    source: str | None = None
    confidence: str | None = None


class VoiceoverBlock(BaseModel):
    text: str | None = None


class SfxMusicBlock(BaseModel):
    sfx: list[str] = Field(default_factory=list)
    music: list[str] = Field(default_factory=list)


class CtaBlock(BaseModel):
    type: str = "none"
    text: str | None = None


class ShotScript(BaseModel):
    """分镜头脚本单条镜头（与 SKILL.md 一致）。"""

    id: str
    start_s: float = 0.0
    end_s: float = 0.0
    goal: str = ""
    visual: VisualBlock = Field(default_factory=VisualBlock)
    on_screen_text: list[OnScreenTextItem] = Field(default_factory=list)
    voiceover: VoiceoverBlock = Field(default_factory=VoiceoverBlock)
    sfx_music: SfxMusicBlock = Field(default_factory=SfxMusicBlock)
    cta: CtaBlock = Field(default_factory=CtaBlock)


class StoryboardTemplate(BaseModel):
    """由第 2 步（skills + LLM）产出；与 storyboard_template/SKILL.md 对齐。"""

    template_version: str = "v1"
    tone_style: list[str] = Field(default_factory=list)
    shots: list[ShotScript] = Field(default_factory=list)


class WorldConstraints(BaseModel):
    """世界观 / 合规 / 画风硬约束。"""

    hard_rules: list[str] = Field(default_factory=list)
    soft_preferences: list[str] = Field(default_factory=list)
    visual_style: str = ""


class Scene(BaseModel):
    id: str
    duration_sec: float = 5.0
    visual_prompt: str = ""
    negative_prompt: str = ""
    narration: str = ""


class SkillsGenerationOutput(BaseModel):
    """第 2 步：结合 SKILL.md 与品牌信息，生成分镜模板与世界观约束。"""

    storyboard_template: StoryboardTemplate
    world_constraints: WorldConstraints


class ScenesPayload(BaseModel):
    """第 3 步前段：可执行分镜列表。"""

    scenes: list[Scene]


_TIMELINE_EPS = 1e-6


def validate_storyboard_template(t: StoryboardTemplate) -> list[str]:
    """skills 节点在 LLM 返回后的业务校验（与 SKILL 时间轴约定一致）。"""
    errs: list[str] = []
    if not t.shots:
        errs.append("storyboard_template.shots 不能为空。")
        return errs
    prev_end: float | None = None
    for shot in t.shots:
        if not (shot.id or "").strip():
            errs.append("存在 id 为空的镜头，请为每条 shot 填写 id（如 S01）。")
        if shot.end_s <= shot.start_s:
            errs.append(f"镜头 {shot.id!r}: end_s 必须大于 start_s。")
        if prev_end is not None and shot.start_s + _TIMELINE_EPS < prev_end:
            errs.append(
                f"镜头 {shot.id!r}: start_s（{shot.start_s}）不得早于上一镜的 end_s（{prev_end}）。"
            )
        prev_end = shot.end_s
    return errs


def validate_scenes_list(scenes: list[Scene]) -> list[str]:
    """scenes 节点在 LLM 返回后的业务校验。"""
    errs: list[str] = []
    if not scenes:
        errs.append("scenes 不能为空。")
        return errs
    seen: set[str] = set()
    for i, sc in enumerate(scenes):
        sid = (sc.id or "").strip()
        if not sid:
            errs.append(f"第 {i + 1} 条 scene 缺少有效 id。")
            continue
        if sid in seen:
            errs.append(f"scene id 重复：{sid!r}（会导致片段路径冲突）。")
        seen.add(sid)
        if sc.duration_sec <= 0:
            errs.append(f"scene {sid!r}: duration_sec 必须为正数。")
    return errs
