from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class LoadedSkill:
    skill_id: str
    path: Path
    text: str


class SkillLoader:
    """从外部 SKILL.md 读取正文，供运行时注入 prompt。"""

    def __init__(self, skills_root: Path) -> None:
        self._root = skills_root.resolve()

    def load(self, skill_id: str, filename: str = "SKILL.md") -> LoadedSkill:
        if Path(skill_id).is_absolute() or ".." in Path(skill_id).parts:
            raise ValueError(f"Invalid skill_id: {skill_id!r}")
        base = (self._root / skill_id).resolve()
        try:
            base.relative_to(self._root)
        except ValueError as exc:
            raise ValueError(f"Invalid skill path for {skill_id!r}") from exc
        path = base / filename
        text = path.read_text(encoding="utf-8")
        return LoadedSkill(skill_id=skill_id, path=path, text=text)


def load_default_skills(skills_root: Path) -> dict[str, str]:
    loader = SkillLoader(skills_root)
    return {
        "storyboard_template": loader.load("storyboard_template").text,
        "world_constraints": loader.load("world_constraints").text,
    }
