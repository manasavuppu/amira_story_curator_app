import json

import pandas as pd
from tqdm import tqdm

from .config import OUTPUT_DIR
from .safety_flagging_pipeline import load_stories, analyze_story_flags
from .skill_tagging_pipeline import load_skills, analyze_story_skills


def _priority_band(score: float) -> str:
    """
    Map a numeric priority_score_final in [0,1] to a human-readable band.

    This aligns with the UI legend and helps analysts quickly interpret the score:
      - 0.00–0.20   → "Very Low"
      - 0.20–0.40   → "Low"
      - 0.40–0.60   → "Moderate"
      - 0.60–0.80   → "High"
      - 0.80–1.00   → "Critical"
    """
    if score < 0.20:
        return "Very Low"
    if score < 0.40:
        return "Low"
    if score < 0.60:
        return "Moderate"
    if score < 0.80:
        return "High"
    return "Critical"


def main():
    # --------------------------------------------------
    # Load input data
    # --------------------------------------------------
    stories_df = load_stories()
    skills_df = load_skills()

    jsonl_path = OUTPUT_DIR / "story_analysis.jsonl"
    summary_path = OUTPUT_DIR / "story_summary.csv"

    summary_rows = []

    # --------------------------------------------------
    # Core batch loop
    # --------------------------------------------------
    with jsonl_path.open("w", encoding="utf-8") as f_out:
        for _, row in tqdm(
            stories_df.iterrows(),
            total=len(stories_df),
            desc="Analyzing stories",
        ):
            # --------------------------------------------------
            # Run pipelines (safety + skills)
            # --------------------------------------------------
            flags_result = analyze_story_flags(row)
            skills_result = analyze_story_skills(row, skills_df)

            needs_human_review = flags_result.get("needs_human_review", False)
            needs_human_review_skills = skills_result.get(
                "needs_human_review_skills", False
            )

            # Optional extra fields from the safety pipeline
            # (if you add them later, they will flow through transparently)
            priority_components = flags_result.get("priority_components")
            rubric_coverage = flags_result.get("rubric_coverage")
            risk_summary = flags_result.get("risk_summary")

            # --------------------------------------------------
            # Combined per-story object (JSONL)
            # --------------------------------------------------
            priority_score_final = flags_result["priority_score_final"]
            heuristic_risk = flags_result["heuristic_risk_score"]
            llm_priority = flags_result["llm_priority"]

            combined = {
                "story_id": row.story_id,
                "story_title": row.story_title,
                "grade_level": int(row.grade_level),
                "heuristic_risk_score": heuristic_risk,
                "llm_priority": llm_priority,
                "priority_score_final": priority_score_final,
                "priority_band": _priority_band(priority_score_final),
                "flags": flags_result["flags"],
                "skills": skills_result["skills"],
                "needs_human_review": needs_human_review,
                "needs_human_review_skills": needs_human_review_skills,
                # Optional, if provided by the safety pipeline:
                "priority_components": priority_components,
                "rubric_coverage": rubric_coverage,
                "risk_summary": risk_summary,
            }

            # --- Write detailed JSONL line ---
            f_out.write(json.dumps(combined, ensure_ascii=False) + "\n")

            # --------------------------------------------------
            # Build summary row for CSV / UI
            # --------------------------------------------------
            flags = combined["flags"] or []
            skills = combined["skills"] or []

            # Default values
            top_flag_types = ""
            top_flag_snippet = ""
            suggested_skills = ""

            # FLAGS: robust handling
            if flags:
                types = [
                    f.get("issue_type", "")
                    for f in flags
                    if f.get("issue_type")
                ]
                if types:
                    # Truncate for UI readability
                    top_flag_types = "; ".join(types)[:200]

                evidences = [
                    f.get("evidence_text", "")
                    for f in flags
                    if f.get("evidence_text")
                ]
                if evidences:
                    top_flag_snippet = evidences[0][:200]

            # SKILLS: robust handling
            if skills:
                entries = []
                for s in skills:
                    sid = s.get("skill_id")
                    sname = s.get("skill_name")
                    if sid and sname:
                        entries.append(f"{sid}: {sname}")
                if entries:
                    suggested_skills = "; ".join(entries)[:300]

            # Auto-set initial review_status using priority + human-review flags
            # This gives analysts a clear, consistent default triage state.
            if (
                priority_score_final >= 0.6
                or needs_human_review
                or needs_human_review_skills
            ):
                review_status = "Needs Review"
            else:
                review_status = "Not Reviewed"

            summary_rows.append(
                {
                    "story_id": combined["story_id"],
                    "story_title": combined["story_title"],
                    "grade_level": combined["grade_level"],
                    "priority_score_final": priority_score_final,
                    "priority_band": combined["priority_band"],
                    "heuristic_risk_score": heuristic_risk,
                    "llm_priority": llm_priority,
                    "num_flags": len(flags),
                    "num_skills": len(skills),
                    "top_flag_types": top_flag_types,
                    "top_flag_snippet": top_flag_snippet,
                    "suggested_skills": suggested_skills,
                    "needs_human_review": needs_human_review,
                    "needs_human_review_skills": needs_human_review_skills,
                    # Fields for human review / edits later
                    "review_status": review_status,
                    "flags_accepted_revised": "",
                    "skills_accepted_revised": "",
                    "final_priority": "",
                }
            )

    # --------------------------------------------------
    # Create summary CSV for the UI triage board
    # --------------------------------------------------
    summary_df = pd.DataFrame(summary_rows)
    summary_df.sort_values("priority_score_final", ascending=False, inplace=True)
    summary_df.to_csv(summary_path, index=False)

    print(f"Saved detailed analysis to: {jsonl_path}")
    print(f"Saved summary table to:     {summary_path}")


if __name__ == "__main__":
    main()
