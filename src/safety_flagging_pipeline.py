from typing import Dict, Any, List

import pandas as pd

from .config import STORIES_PATH
from .safety_heuristics import (
    detect_zero_tolerance_candidates,
    detect_sensitive_candidates,
    heuristic_risk_score,
)
from .llm_clients import analyze_flags_with_llm  # fixed import name

# Map severity string to numeric for priority calculation
SEVERITY_MAP = {
    "low": 1,
    "medium": 2,
    "high": 3,
    "critical": 4,
}

FLAG_SEVERITY_PRIORITY = {
    "low": 0.25,
    "medium": 0.5,
    "high": 0.75,
    "critical": 1.0,
}

def load_stories() -> pd.DataFrame:
    """Load the main stories table."""
    return pd.read_csv(STORIES_PATH)


# ---------------------------------------------------------------------
# Heuristic summary for the LLM prompt
# ---------------------------------------------------------------------
def summarize_heuristics(text: str) -> str:
    """
    Build a compact natural-language summary of heuristic hits
    to inject into the LLM prompt. This is intentionally short
    and focused so it nudges the model toward areas of concern.
    """
    zero_hits = detect_zero_tolerance_candidates(text)
    sens_hits = detect_sensitive_candidates(text)
    parts: List[str] = []

    if zero_hits:
        parts.append("Zero-tolerance candidates:")
        for h in zero_hits[:5]:
            parts.append(
                f"- [{h['category']}] '{h['matched_word']}' "
                f"in context: {h['snippet']!r}"
            )

    if sens_hits:
        parts.append("Sensitive candidates:")
        for h in sens_hits[:5]:
            parts.append(
                f"- [{h['category']}] '{h['matched_word']}' "
                f"in context: {h['snippet']!r}"
            )

    return "\n".join(parts)


# ---------------------------------------------------------------------
# Priority computation helpers
# ---------------------------------------------------------------------
def _max_severity(flags: List[Dict[str, Any]]) -> int:
    """Return the numeric max severity across all flags."""
    max_sev = 0
    for f in flags:
        sev = SEVERITY_MAP.get(str(f.get("severity", "")).lower(), 0)
        if sev > max_sev:
            max_sev = sev
    return max_sev


def _grade_sensitivity_factor(grade_level: int) -> float:
    """
    Higher factor for younger grades.

    We deliberately treat K–1 as most sensitive, then taper down.
    """
    if grade_level <= 1:
        return 1.0
    if grade_level <= 3:
        return 0.8
    if grade_level <= 5:
        return 0.5
    return 0.3


def _severity_grade_component(max_severity_num: int, grade_level: int) -> float:
    """
    Compute a severity x grade component that is:
    - 0 if no flagged severity,
    - close to 1.0 for CRITICAL issues in early grades,
    - always clamped to [0, 1].
    """
    if max_severity_num <= 0:
        return 0.0

    base = max_severity_num / 4.0  # critical → 1.0
    grade_factor = _grade_sensitivity_factor(grade_level)
    sev_grade = base * (1.0 + grade_factor)
    return float(min(max(sev_grade, 0.0), 1.0))


def compute_priority(
    llm_priority: float,
    flags: List[Dict[str, Any]],
    heuristic_score: float,
    grade_level: int,
) -> (float, Dict[str, float]):
    """
    Combine LLM priority, heuristic score, and severity x grade into a
    final 0–1 priority score using a monotonic, fail-safe rule:

      final_priority = max(
          llm_priority,
          heuristic_risk_score,
          severity_grade_component
      )

    with a hard fail-safe for critical issues, and a clamp for purely
    synthetic, low-signal cases.

    Returns:
        final_priority (float),
        priority_components (dict) for explainability.
    """
    llm_priority = float(llm_priority)
    heuristic_score = float(heuristic_score)
    grade_level = int(grade_level)

    max_sev = _max_severity(flags)
    sev_grade = _severity_grade_component(max_sev, grade_level)

    # Are all flags synthetic review flags?
    synthetic_only = bool(flags) and all(
        (f.get("source", "").strip().lower() == "synthetic")
        for f in flags
    )

    # Hard fail-safe: critical → force 1.0
    if max_sev == SEVERITY_MAP["critical"]:
        final = 1.0
    else:
        final = max(llm_priority, heuristic_score, sev_grade)

    # Clamp very low-signal synthetic-only cases so they are "High"
    # but not "Critical".
    if synthetic_only and heuristic_score < 0.15 and llm_priority < 0.25:
        final = min(final, 0.6)

    final = round(min(max(final, 0.0), 1.0), 3)

    components = {
        "llm_priority_raw": round(llm_priority, 3),
        "heuristic_risk_score": round(heuristic_score, 3),
        "severity_grade_component": round(sev_grade, 3),
        "max_severity_numeric": float(max_sev),
    }

    return final, components



# ---------------------------------------------------------------------
# Evidence validation & flag post-processing
# ---------------------------------------------------------------------
def validate_evidence_substrings(
    flags: List[Dict[str, Any]],
    story_text: str,
) -> List[Dict[str, Any]]:
    """
    Ensure evidence_text is actually a substring of the story.

    We are more tolerant than a raw "ev in text" check:
    - allow empty evidence_text *only* for synthetic review flags,
    - strip whitespace,
    - case-insensitive match,
    - simple mid-snippet fallback for long evidence strings (and then
      replace evidence_text with that snippet).

    This avoids throwing away useful flags due to small formatting differences,
    while guaranteeing that evidence_text for non-synthetic flags is grounded
    in the story.
    """
    if not flags:
        return []

    if not story_text:
        # Cannot validate without story text
        return flags

    story_raw = story_text
    story_lower = story_raw.lower()

    valid_flags: List[Dict[str, Any]] = []

    for f in flags:
        ev = f.get("evidence_text", "")
        issue_type = (f.get("issue_type") or "").strip().lower()
        source = (f.get("source") or "").strip().lower()

        # Allow empty evidence only for synthetic / general review flags
        if not ev or not str(ev).strip():
            if issue_type == "general safety review" or source == "synthetic":
                valid_flags.append(f)
            # otherwise drop this flag (no grounded snippet)
            continue

        ev_norm = str(ev).strip()
        if not ev_norm:
            continue

        # 1) Direct substring match
        if ev_norm in story_raw:
            valid_flags.append(f)
            continue

        # 2) Case-insensitive match – also normalize evidence_text to story casing
        lower_ev = ev_norm.lower()
        idx = story_lower.find(lower_ev)
        if idx != -1:
            f["evidence_text"] = story_raw[idx : idx + len(ev_norm)]
            valid_flags.append(f)
            continue

        # 3) Fallback: use a mid-snippet slice for long evidence spans
        if len(ev_norm) > 40:
            mid_start = max(0, len(ev_norm) // 2 - 20)
            mid_end = mid_start + 40
            snippet = ev_norm[mid_start:mid_end].strip()
            if snippet:
                # Try exact and case-insensitive against the story
                idx2 = story_raw.find(snippet)
                if idx2 == -1:
                    idx2 = story_lower.find(snippet.lower())
                if idx2 != -1:
                    f["evidence_text"] = story_raw[idx2 : idx2 + len(snippet)]
                    valid_flags.append(f)
                    continue

        # Otherwise, drop as ungrounded
        continue

    return valid_flags

def _dedupe_flags(flags: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Deduplicate flags that use the same evidence_text and very similar
    issue_type, to reduce noise for reviewers.

    Simple rule:
    - Use (evidence_text_lower, issue_type_lower) as a key.
    - Keep the first occurrence; drop subsequent duplicates.
    """
    if not flags:
        return []

    seen = set()
    deduped: List[Dict[str, Any]] = []

    for f in flags:
        ev = (f.get("evidence_text") or "").strip().lower()
        issue = (f.get("issue_type") or "").strip().lower()
        key = (ev, issue)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(f)

    return deduped


# ---------------------------------------------------------------------
# Human-review safeguard & synthetic flag
# ---------------------------------------------------------------------
def _should_force_review(
    flags: List[Dict[str, Any]],
    heuristic_score: float,
    llm_priority: float,
    grade_level: int,
) -> bool:
    """
    Decide if we should force a 'needs_human_review' condition even
    when no valid flags survive. This addresses under-coverage:
    - Heuristics see risk,
    - or LLM priority is non-trivial,
    - or the story is aimed at very young readers.
    """
    if flags:
        return False

    # Heuristic risk alone can justify manual review
    if heuristic_score >= 0.3:
        return True

    # LLM thinks there is some risk, but evidence got filtered out
    if llm_priority >= 0.4:
        return True

    # For K–3, be extra cautious even with low signals
    if int(grade_level) <= 3 and (heuristic_score > 0.0 or llm_priority > 0.0):
        return True

    return False


def _build_forced_review_flag(reason: str) -> Dict[str, Any]:
    """
    Synthetic flag used when we know a story is 'suspicious' but
    didn't get any concrete evidence snippets. This prevents stories
    from silently falling through as 'clean'.
    """
    return {
        "issue_type": "General Safety Review",
        "severity": "medium",
        "rubric_category": "ReviewRequired",
        "evidence_text": "",
        "rationale": reason,
        "source": "synthetic",
    }


# ---------------------------------------------------------------------
# Rubric coverage summary
# ---------------------------------------------------------------------
def _rubric_coverage(flags: List[Dict[str, Any]]) -> Dict[str, bool]:
    """
    Compute a simple coverage report over the main rubric dimensions,
    based on issue_type and rubric_category labels in the flags.
    """
    dimensions = {
        "violence_physical_harm": ["violence", "physical harm"],
        "emotional_safety": ["emotional safety", "bullying"],
        "cultural_sensitivity": ["cultural", "representation"],
        "age_appropriateness": ["age appropriateness"],
        "technical_pedagogical": ["technical", "pedagogical"],
        "physical_safety": ["physical safety"],
    }

    coverage = {k: False for k in dimensions.keys()}

    for f in flags:
        issue = (f.get("issue_type") or "").lower()
        rubric = (f.get("rubric_category") or "").lower()
        label_text = f"{issue} {rubric}"

        for dim_key, keywords in dimensions.items():
            if any(kw in label_text for kw in keywords):
                coverage[dim_key] = True

    return coverage


# ---------------------------------------------------------------------
# Main entry point for safety analysis
# ---------------------------------------------------------------------
def analyze_story_flags(story_row) -> Dict[str, Any]:
    """
    Run the full safety analysis for a single story:
    - Heuristic pre-screen
    - LLM-based flagging
    - Evidence validation and deduplication
    - Force-review safeguard
    - Final priority computation
    - Rubric coverage summary
    """
    text = story_row.story_content
    grade = int(story_row.grade_level)

    # 1) Heuristic pre-screen
    h_summary = summarize_heuristics(text)
    h_score = heuristic_risk_score(text)

    # 2) LLM analysis (multi-dimension handled in llm_client)
    llm_result = analyze_flags_with_llm(story_row, h_summary)

    # Expect keys: story_id, priority_score, flags, risk_summary
    flags_raw = llm_result.get("flags", []) or []
    risk_summary = llm_result.get("risk_summary") or ""

    # 3) Evidence validation (tolerant) + simple dedupe
    flags_valid = validate_evidence_substrings(flags_raw, text)
    flags_valid = _dedupe_flags(flags_valid)

    llm_priority = float(llm_result.get("priority_score", 0.0))

    # 3b) Ensure each flag has a source and per-flag priority
    for f in flags_valid:
        # Default source for model-generated flags
        f.setdefault("source", "llm")

        # Simple per-flag priority for UI (0–1, based only on severity)
        sev = str(f.get("severity", "")).lower()
        f.setdefault("priority", FLAG_SEVERITY_PRIORITY.get(sev, 0.0))


    # 4) Force-review safeguard for under-coverage
    needs_human_review = _should_force_review(
        flags=flags_valid,
        heuristic_score=h_score,
        llm_priority=llm_priority,
        grade_level=grade,
    )

    if needs_human_review:
        # Attach a synthetic flag so the UI and downstream consumers
        # have *something* to show, and so priority isn’t misleadingly low.
        reason_parts = []
        if h_score > 0:
            reason_parts.append(f"heuristic_risk_score={h_score:.2f}")
        if llm_priority > 0:
            reason_parts.append(f"llm_priority={llm_priority:.2f}")
        reason_parts.append(f"grade_level={grade}")
        reason = (
            "Story requires manual review due to signals: "
            + ", ".join(reason_parts)
        )
        flags_valid = flags_valid + [_build_forced_review_flag(reason)]

    # 5) Final priority computation (now including synthetic flag if any)
    final_priority, priority_components = compute_priority(
        llm_priority=llm_priority,
        flags=flags_valid,
        heuristic_score=h_score,
        grade_level=grade,
    )

    # 6) Rubric coverage summary
    coverage = _rubric_coverage(flags_valid)

    return {
        "story_id": story_row.story_id,
        "story_title": story_row.story_title,
        "grade_level": grade,
        "heuristic_risk_score": h_score,
        "flags": flags_valid,
        "llm_priority": round(llm_priority, 3),
        "priority_score_final": final_priority,
        "needs_human_review": needs_human_review,
        "priority_components": priority_components,
        "rubric_coverage": coverage,
        "risk_summary": risk_summary,
    }
