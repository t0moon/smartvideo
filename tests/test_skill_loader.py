from pathlib import Path

from app.skills_loader.loader import SkillLoader


def test_skill_loader_reads_md(tmp_path: Path) -> None:
    root = tmp_path / "skills"
    (root / "demo").mkdir(parents=True)
    (root / "demo" / "SKILL.md").write_text("hello", encoding="utf-8")
    loader = SkillLoader(root)
    loaded = loader.load("demo")
    assert loaded.text == "hello"
