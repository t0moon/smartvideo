from app.config import SKILLS_ROOT
from app.graph.state import AgentState
from app.skills_loader.loader import SkillLoader, load_default_skills


def node_load_external_skills(state: AgentState) -> dict:
    try:
        docs = load_default_skills(SKILLS_ROOT)
        loader = SkillLoader(SKILLS_ROOT)
        meta: dict = {"skills_root": str(SKILLS_ROOT)}
        for key in ("storyboard_template", "world_constraints"):
            loaded = loader.load(key)
            meta[key] = {"path": str(loaded.path), "mtime_ns": loaded.path.stat().st_mtime_ns}
        return {"skill_docs": docs, "skill_meta": meta}
    except (OSError, ValueError) as exc:
        err = {"step": "load_skills", "message": str(exc)}
        return {"errors": (state.get("errors") or []) + [err]}
