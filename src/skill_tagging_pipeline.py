from typing import Dict, Any, List

import pandas as pd

from .config import SKILLS_PATH
from .llm_clients import analyze_skills_with_llm  # updated module


def load_skills() -> pd.DataFrame:
    """Load the skills taxonomy table."""
    return pd.read_csv(SKILLS_PATH)


def validate_skill_evidence(
    skills: List[Dict[str, Any]],
    story_text: str,
) -> List[Dict[str, Any]]:
    """
    Filter and clean the skills returned by the LLM.

    We keep only skill objects that:
    - have 'skill_id', 'skill_name', and 'evidence_text'
    - and whose 'evidence_text' is actually a substring of the story text
      (with some mild normalization).

    We are slightly tolerant:
    - strip whitespace,
    - case-insensitive matching,
    - if needed, take a mid-snippet slice of a long evidence string and
      replace evidence_text with that slice when it matches.

    This avoids keeping hallucinated or paraphrased spans while still
    rescuing good skills that only differ in trivial formatting.
    """
    if not skills:
        return []

    if not story_text:
        # Without the story, we cannot validate evidence
        return skills

    story_raw = story_text
    story_lower = story_raw.lower()

    valid: List[Dict[str, Any]] = []

    for s in skills:
        sid = s.get("skill_id")
        name = s.get("skill_name")
        ev = s.get("evidence_text")

        if not sid or not name or not ev:
            continue

        ev_norm = str(ev).strip()
        if not ev_norm:
            continue

        # 1) Direct substring
        if ev_norm in story_raw:
            valid.append(s)
            continue

        # 2) Case-insensitive, but normalize evidence_text to story casing
        lower_ev = ev_norm.lower()
        idx = story_lower.find(lower_ev)
        if idx != -1:
            s["evidence_text"] = story_raw[idx : idx + len(ev_norm)]
            valid.append(s)
            continue

        # 3) Last resort: a shorter snippet from the middle
        if len(ev_norm) > 40:
            mid_start = max(0, len(ev_norm) // 2 - 20)
            mid_end = mid_start + 40
            snippet = ev_norm[mid_start:mid_end].strip()
            if snippet:
                idx2 = story_raw.find(snippet)
                if idx2 == -1:
                    idx2 = story_lower.find(snippet.lower())
                if idx2 != -1:
                    s["evidence_text"] = story_raw[idx2 : idx2 + len(snippet)]
                    valid.append(s)
                    continue

        # Otherwise, drop this skill as ungrounded.
        continue

    return valid

def _normalize_similarity(sim: float) -> float:
    """
    Normalize cosine similarity into [0, 1] with a floor.

    Assumes `sim` is a cosine similarity in [-1, 1]:
      - First map cos -> [0, 1] via (cos + 1) / 2.
      - Then apply a floor so values below ~0.3 are treated as 'weak signal'.
    """
    if sim is None:
        return 0.5  # neutral if unknown

    # Clamp cosine to [-1, 1]
    try:
        sim_val = float(sim)
    except (TypeError, ValueError):
        sim_val = 0.0

    sim_val = max(-1.0, min(1.0, sim_val))

    # Map [-1, 1] -> [0, 1]
    sim_01 = (sim_val + 1.0) / 2.0

    # Shift + scale so 0.3 becomes ~0
    floor = 0.3
    if sim_01 <= floor:
        return 0.0
    return min(1.0, (sim_01 - floor) / (1.0 - floor))


def _combine_confidence(sim: float, llm_conf: float) -> float:
    """
    Hybrid confidence:
    - similarity_score (objective, semantic) weighted higher
    - llm_confidence (subjective, pedagogical) weighted lower

    adjusted_conf = 0.6 * sim_norm + 0.4 * llm_conf_clipped
    """
    sim_norm = _normalize_similarity(sim)

    # Clip LLM confidence into [0, 0.9] to avoid everything being 1.0
    try:
        llm_conf_val = float(llm_conf)
    except (TypeError, ValueError):
        llm_conf_val = 0.5

    llm_conf_val = max(0.0, min(0.9, llm_conf_val))

    adjusted = 0.6 * sim_norm + 0.4 * llm_conf_val
    return round(adjusted, 3)


def analyze_story_skills(story_row, skills_df: pd.DataFrame) -> Dict[str, Any]:
    """
    Run the LLM-based skills analysis for a single story.

    Returns a dict with:
    - story_id
    - skills: list of validated skill dicts, each with:
        - confidence_raw (from LLM)
        - confidence (hybrid: similarity + LLM)
    - needs_human_review_skills: bool indicating if validation struggled
    """
    # Make sure this matches your actual file name:
    #   skill_prefilter_embeddings.py
    from .skill_prefilter_embeddings import prefilter_skills

    # Step 1 — prefilter skill candidates (semantic similarity)
    candidate_skills_df = prefilter_skills(story_row.story_content, skills_df)

    # Build a map: skill_id -> similarity_score
    sim_by_skill_id = {}
    if "similarity_score" in candidate_skills_df.columns:
        for _, r in candidate_skills_df.iterrows():
            sim_by_skill_id[str(r["skill_id"])] = float(r["similarity_score"])

    # Step 2 — only send candidates -> LLM
    llm_result = analyze_skills_with_llm(story_row, candidate_skills_df)

    # LLM response may be missing 'skills' or have it as None
    skills_raw: List[Dict[str, Any]] = llm_result.get("skills") or []

    # Step 3 — evidence validation
    skills_valid = validate_skill_evidence(skills_raw, story_row.story_content)

    # Safeguard: if the LLM returned something but validation dropped everything,
    # keep the original raw skills and mark this as requiring human review.
    needs_human_review_skills = False
    if skills_raw and not skills_valid:
        skills_valid = skills_raw
        needs_human_review_skills = True

    # Step 4 — compute hybrid confidence for each skill
        # Step 4 — compute hybrid confidence for each skill
    for s in skills_valid:
        sid = str(s.get("skill_id", ""))
        sim = sim_by_skill_id.get(sid)

        # Expose raw similarity for downstream analysis / UI
        if sim is not None:
            s["similarity_score"] = float(sim)

        llm_conf_raw = s.get("confidence", 0.5)
        adjusted_conf = _combine_confidence(sim, llm_conf_raw)

        # Preserve raw and overwrite displayed confidence
        s["confidence_raw"] = llm_conf_raw
        s["confidence"] = adjusted_conf

    return {
        "story_id": story_row.story_id,
        "skills": skills_valid,
        "needs_human_review_skills": needs_human_review_skills,
    }
