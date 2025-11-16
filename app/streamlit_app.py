from pathlib import Path
import sys
import json
import re

import pandas as pd
import streamlit as st

# -------------------------------------------------------------------
# Make sure project root (one level above app/) is on sys.path
# -------------------------------------------------------------------
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.config import OUTPUT_DIR, STORIES_PATH  # noqa: E402


def highlight_evidence(story_text: str, evidence_list: list) -> str:
    """
    Wrap evidence spans in a <mark> tag.
    Evidence must be exact substring matches.
    Escapes regex to avoid injection.
    """
    if not evidence_list:
        return story_text

    highlighted = story_text

    # sort longest first to avoid nested replacements
    evidence_list = sorted(evidence_list, key=len, reverse=True)

    for ev in evidence_list:
        if not ev:
            continue
        pattern = re.escape(ev)
        replacement = f"<mark style='background-color: #ffcccc'>{ev}</mark>"
        highlighted = re.sub(pattern, replacement, highlighted, flags=re.IGNORECASE)

    return highlighted


# -------------------------------------------------------------------
# Data loaders
# -------------------------------------------------------------------
def load_summary() -> pd.DataFrame:
    """Load the triage summary table produced by run_analysis.py."""
    path = OUTPUT_DIR / "story_summary.csv"
    return pd.read_csv(path)


def load_analysis() -> dict:
    """
    Load per-story detailed analysis from JSONL into a dict:
    {story_id: analysis_obj}
    """
    path = OUTPUT_DIR / "story_analysis.jsonl"
    data = {}
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            obj = json.loads(line)
            data[obj["story_id"]] = obj
    return data


def load_story_texts() -> dict:
    """
    Load full story text from stories.csv so reviewers can read
    the entire story in the UI.

    Returns: {story_id: story_content}
    """
    df = pd.read_csv(STORIES_PATH)
    return {row.story_id: row.story_content for _, row in df.iterrows()}


# -------------------------------------------------------------------
# Main app
# -------------------------------------------------------------------
def main():
    st.set_page_config(page_title="Amira Story Curator", layout="wide")
    st.title("Amira Story Curator – Content Specialist View")

    summary_df = load_summary()
    analysis_by_id = load_analysis()
    story_text_by_id = load_story_texts()

    # ---------------- Sidebar filters ----------------
    st.sidebar.header("Filters")

    grades = sorted(summary_df["grade_level"].unique())
    grade_filter = st.sidebar.multiselect(
        "Grade levels",
        options=grades,
        default=grades,
    )

    min_priority, max_priority = st.sidebar.slider(
        "Priority range",
        min_value=0.0,
        max_value=1.0,
        value=(0.0, 1.0),
        step=0.05,
    )

    search_query = st.sidebar.text_input("Search by title or story_id")

    # Base filtering on grade & priority
    filtered = summary_df[
        (summary_df["grade_level"].isin(grade_filter))
        & (summary_df["priority_score_final"] >= min_priority)
        & (summary_df["priority_score_final"] <= max_priority)
    ]

    # Optional search filter
    if search_query:
        mask = (
            filtered["story_title"].str.contains(search_query, case=False, na=False)
            | filtered["story_id"].str.contains(search_query, case=False, na=False)
        )
        filtered = filtered[mask]

    # ---------------- Triage board (with pagination) ----------------
    st.subheader("Story Triage Board")
    st.caption("Sorted by final priority score (highest first).")

    # Legend explaining the scores
    with st.expander("How to read these scores"):
        st.markdown(
            """
**Priority (final)**  
- `0.00–0.19` → Low – likely safe; review only if time allows  
- `0.20–0.39` → Mild – minor or borderline issues  
- `0.40–0.59` → Moderate – should be reviewed  
- `0.60–0.79` → High – review soon; likely real concerns  
- `0.80–1.00` → Critical – must review; serious safety/representation issues  

**Heuristic risk**  
- 0–1 score based on keyword hits (weapons, bullying, death, emotional words, etc.).  
- Higher = more “red flag” words in the raw text.

**LLM priority**  
- 0–1 score based on the AI’s interpretation of the full story against the rubric.  
- Higher = the AI believes the story more urgently needs a human review.

**num_flags**  
- Number of individual issues (violence, bullying, cultural sensitivity, etc.) the AI flagged.

Use **Priority (final)** to triage, then drill into **Flags** and **Skill Tags**
in the detail view for final decisions.
            """
        )

    filtered = filtered.sort_values("priority_score_final", ascending=False)

    total_items = len(filtered)
    if total_items == 0:
        st.info("No stories match the current filters.")
        return

    items_per_page = 20
    total_pages = (total_items - 1) // items_per_page + 1

    page = st.sidebar.number_input(
        "Page number",
        min_value=1,
        max_value=total_pages,
        step=1,
        value=1,
    )

    start = (page - 1) * items_per_page
    end = start + items_per_page
    paged_df = filtered.iloc[start:end]

    st.dataframe(
        paged_df[
            [
                "story_id",
                "story_title",
                "grade_level",
                "priority_score_final",
                "num_flags",
                "top_flag_types",
                "suggested_skills",
            ]
        ],
        use_container_width=True,
        hide_index=True,
    )

    st.markdown(
        f"_Showing {len(paged_df)} of {total_items} stories (page {page}/{total_pages})._"
    )

    st.markdown("---")
    st.subheader("Story Detail & Review")

    # ---------------- Story selection ----------------
    story_ids = filtered["story_id"].tolist()
    selected_id = st.selectbox("Select story_id to inspect", story_ids)
    story_data = analysis_by_id.get(selected_id)

    if not story_data:
        st.warning("No detailed data found for this story.")
        return

    story_text = story_text_by_id.get(selected_id, "")

    col_meta, col_text = st.columns([1, 2])

    # ---------------- Left column: metadata + flags ----------------
    with col_meta:
        st.markdown(f"**Title:** {story_data['story_title']}")
        st.markdown(f"**Grade level:** {story_data['grade_level']}")
        st.markdown(f"**Priority (final):** {story_data['priority_score_final']:.2f}")
        st.markdown(f"**Heuristic risk:** {story_data['heuristic_risk_score']:.2f}")
        st.markdown(f"**LLM priority:** {story_data['llm_priority']:.2f}")
        st.caption(
            "_Priority = combined score; Heuristic risk = keyword-based; "
            "LLM priority = rubric-based AI judgment._"
        )

        st.markdown("### Flags")
        flags = story_data.get("flags", [])
        if not flags:
            st.write("No flags generated.")
        else:
            for i, f in enumerate(flags, start=1):
                with st.expander(f"Flag {i}: {f.get('issue_type', 'Unknown')}"):
                    st.write(f"**Severity:** {f.get('severity', '')}")
                    st.write(f"**Rubric category:** {f.get('rubric_category', '')}")

                    # ---- NEW: smarter evidence display ----
                    evidence = f.get("evidence_text")
                    issue_type = f.get("issue_type", "")
                    source = f.get("source", "")

                    if evidence:
                        st.write("**Evidence:**")
                        st.write(evidence)
                    else:
                        # Synthetic / general review flags have no specific span
                        if issue_type == "General Safety Review" or source == "synthetic":
                            st.write(
                                "**Evidence:** _No specific text span – "
                                "general safety review based on combined signals "
                                "(heuristics, LLM, grade level)._"
                            )
                        else:
                            st.write(
                                "**Evidence:** _No specific text span available._"
                            )

                    st.write(f"**Rationale:** {f.get('rationale', '')}")

    # ---------------- Right column: story text + skills + feedback ----------------
    with col_text:
        st.markdown("### Story Text with Evidence Highlighted")

        skills = story_data.get("skills", [])

        evidence_spans = []
        for f in flags:
            ev = f.get("evidence_text", "")
            if ev:
                evidence_spans.append(ev)
        for s in skills:
            ev = s.get("evidence_text", "")
            if ev:
                evidence_spans.append(ev)

        if story_text:
            highlighted_html = highlight_evidence(story_text, evidence_spans)
            with st.expander("Show full story", expanded=False):
                st.markdown(
                    f"<div style='white-space: pre-wrap; font-size:16px'>{highlighted_html}</div>",
                    unsafe_allow_html=True,
                )
        else:
            st.write("Story text not available (could not find in stories.csv).")

        st.markdown("### Skill Tags")
        if not skills:
            st.write("No skills generated.")
        else:
            for s in skills:
                st.markdown(
                    f"**{s.get('skill_id', '')} – {s.get('skill_name', '')}**"
                )
                st.markdown(
                    f"- Confidence: `{s.get('confidence', 0.0)}`"
                )
                st.markdown(
                    f"- Evidence: “{s.get('evidence_text', '')}”"
                )
                st.markdown(
                    f"- Justification: {s.get('justification', '')}"
                )
                st.markdown("---")

        st.markdown("### Reviewer Feedback")

        reviewed_flags = st.text_area(
            "Revised Flags (optional)",
            value=story_data.get("flags_accepted_revised", ""),
            height=120,
        )
        reviewed_skills = st.text_area(
            "Revised Skill Tags (optional)",
            value=story_data.get("skills_accepted_revised", ""),
            height=120,
        )
        status = st.selectbox(
            "Review Status",
            ["Not Reviewed", "Approved", "Needs Changes"],
            index=0,
        )

        if st.button("Save Review"):
            reviews_dir = OUTPUT_DIR / "reviews"
            reviews_dir.mkdir(parents=True, exist_ok=True)

            review_payload = {
                "story_id": selected_id,
                "story_title": story_data.get("story_title"),
                "grade_level": story_data.get("grade_level"),
                "priority_score_final": story_data.get("priority_score_final"),
                "review_status": status,
                "flags_accepted_revised": reviewed_flags,
                "skills_accepted_revised": reviewed_skills,
            }

            review_path = reviews_dir / f"{selected_id}.json"
            with review_path.open("w", encoding="utf-8") as f:
                json.dump(review_payload, f, indent=2, ensure_ascii=False)

            st.success(f"Review saved to {review_path}")


if __name__ == "__main__":
    main()
