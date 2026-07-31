"""Skill loading system — bridges SKILL.md prompt assets into LeadAgent calls.

Design
------
Each ``skills/<name>/SKILL.md`` is a **prompt engineering asset** with YAML
frontmatter (``skill_id``, ``description``) followed by a markdown body that
contains domain-specific instructions, output schemas, and guardrails.

The loader scans these files at import time, builds an in-memory index, and
exposes :func:`get_skill_prompt(stage_name)` which returns the concatenated
prompt bodies of all skills that match a given workflow stage.

Stage-to-skill mapping is driven by **heuristic matching** on frontmatter
fields (``skill_id``, ``description``) and directory name.  This keeps the
system zero-config: adding a new ``skills/foo/SKILL.md`` makes it available
to any stage whose name overlaps with its metadata.

Usage (inside LeadAgent)::

    from skills.loader import get_skill_prompt

    def generate_storyboard(self, spec, brand=None):
        system = self._load_prompt('storyboard')
        skill_text = get_skill_prompt('storyboard')  # <-- injected here
        if skill_text:
            system = f"{system}\n\n## Domain Skill Instructions\n\n{skill_text}"
        ...
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# Root of the skills/ directory relative to this file.
_SKILLS_ROOT = Path(__file__).parent


@dataclass
class SkillDef:
    """A parsed SKILL.md file."""

    skill_id: str = ""
    description: str = ""
    compatibility: str = ""
    body: str = ""                     # Markdown content after frontmatter
    source_path: Path = field(default_factory=lambda: Path())

    # --- matching helpers ---

    @property
    def keywords(self) -> list[str]:
        """Lower-case tokens from id + description for fuzzy matching."""
        parts = [self.skill_id, self.description]
        text = " ".join(p for p in parts if p).lower()
        # Split on non-alphanumeric chars, filter short tokens
        return [t for t in re.split(r"[^a-z0-9_\u4e00-\u9fff]+", text) if len(t) > 1]


# ---------------------------------------------------------------------------
# Index (built once, cached at module level)
# ---------------------------------------------------------------------------

_skills_index: dict[str, SkillDef] = {}   # skill_id -> SkillDef
_index_built: bool = False


def _parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    """Split YAML frontmatter from body. Returns (frontmatter_dict, body).

    Frontmatter must be delimited by lines that contain only ``---``.
    If no frontmatter is found, returns ({}, text).
    """
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", text, re.DOTALL)
    if not m:
        return {}, text
    raw_fm, body = m.group(1), m.group(2)

    fm: dict[str, str] = {}
    for line in raw_fm.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        # Simple "key: value" parsing (no nested YAML needed for our schema)
        if ":" in line:
            k, _, v = line.partition(":")
            fm[k.strip()] = v.strip()
    return fm, body


def _build_index() -> None:
    """Scan skills/ subdirectories and parse every SKILL.md."""
    global _index_built, _skills_index
    if _index_built:
        return

    if not _SKILLS_ROOT.is_dir():
        _index_built = True
        return

    for skill_dir in sorted(_SKILLS_ROOT.iterdir()):
        md = skill_dir / "SKILL.md"
        if not md.is_file():
            continue
        try:
            text = md.read_text(encoding="utf-8")
        except OSError:
            continue

        fm, body = _parse_frontmatter(text)
        sd = SkillDef(
            skill_id=fm.get("skill_id", skill_dir.name),
            description=fm.get("description", ""),
            compatibility=fm.get("compatibility", ""),
            body=body.strip(),
            source_path=md,
        )
        _skills_index[sd.skill_id] = sd

    _index_built = True


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def ensure_index() -> None:
    """Force index construction (useful for testing / REPL)."""
    _build_index()


def list_skills() -> list[SkillDef]:
    """Return all registered skills."""
    _build_index()
    return list(_skills_index.values())


def get_skill(skill_id: str) -> Optional[SkillDef]:
    """Look up a single skill by ID."""
    _build_index()
    return _skills_index.get(skill_id)


# Stage-name aliases used for heuristic matching.
_STAGE_ALIASES: dict[str, list[str]] = {
    "requirement": ["requirement", "brief", "spec", "understand"],
    "storyboard":  ["storyboard", "story", "board", "script", "分镜"],
    "scene":       ["scene", "shot", "场景", "镜头", "分镜", "脚本"],
    "asset_prep":  ["asset", "character", "voice", "数字人", "资产", "world", "constraint"],
    "video_prod":  ["video", "clip", "generate", "视频生成"],
    "stitch":      ["stitch", "render", "合成", "渲染", "subtitle", "tts"],
    "publish":     ["publish", "发布", "export"],
    "review":      ["review", "审核", "approve", "审批"],
}

# Explicit fallback mapping when heuristic scoring yields no results.
# Format: stage_name -> [skill_id, ...]
_EXPLICIT_FALLBACK: dict[str, list[str]] = {
    "scene":      ["storyboard_template"],   # scene gen reuses storyboard methodology
    "asset_prep": ["world_constraints"],      # asset prep needs brand/character guards
}


def _score_match(stage_name: str, skill: SkillDef) -> float:
    """Return a relevance score in [0, 1] for (stage, skill).

    Higher = more relevant.  Exact skill_id match wins; keyword overlap
    is secondary.
    """
    sn = stage_name.lower().replace("-", "_").replace(" ", "_")

    # Exact skill_id contains stage name (or vice versa)
    if sn in skill.skill_id.lower() or skill.skill_id.lower() in sn:
        return 1.0
    if sn in skill.description.lower():
        return 0.85

    # Keyword overlap via aliases
    aliases = _STAGE_ALIASES.get(sn, [sn])
    skill_kw = set(skill.keywords)
    alias_set = set(aliases)
    if not skill_kw:
        return 0.0
    overlap = len(skill_kw & alias_set) / len(alias_set)
    return round(overlap * 0.7, 3)


def get_skill_prompt(stage_name: str, *, min_score: float = 0.15) -> str:
    """Return concatenated prompt bodies of all skills matching *stage_name*.

    Skills are ordered by relevance score (highest first).  The returned
    string is empty when no skill meets *min_score*.

    Typical call inside LeadAgent::

        skill_text = get_skill_prompt('storyboard')
        # => full body of storyboard_template/SKILL.md (721-line ad script guide)
    """
    _build_index()
    if not _skills_index:
        return ""

    scored: list[tuple[float, SkillDef]] = [
        (_score_match(stage_name, s), s) for s in _skills_index.values()
    ]
    scored.sort(key=lambda x: x[0], reverse=True)

    parts: list[str] = []
    for score, skill in scored:
        if score < min_score:
            break
        header = f"<!-- skill: {skill.skill_id} (relevance: {score}) -->"
        parts.append(f"{header}\n{skill.body}")

    # Fallback: if heuristic scoring found nothing, check explicit map.
    if not parts:
        fallback_ids = _EXPLICIT_FALLBACK.get(stage_name, [])
        for sid in fallback_ids:
            skill = _skills_index.get(sid)
            if skill:
                parts.append(f"<!-- skill: {skill.skill_id} (explicit) -->\n{skill.body}")

    return "\n\n".join(parts) if parts else ""
