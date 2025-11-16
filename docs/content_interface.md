2. Content Specialist Interface & Review Workflow

This document explains how a non-technical content specialist uses the system, and how the outputs are structured around their day-to-day workflow.

The system surfaces results in two primary forms:
A review-friendly CSV / spreadsheet (outputs/story_summary.csv)
An optional Streamlit web interface (app/streamlit_app.py)
Both are powered by the detailed per-story records in outputs/story_analysis.jsonl.

2.1 Interface Goals

The interface is designed so that a content specialist can:
Quickly see which stories need the most attention
Understand what issues were flagged and where they appear in the text
Inspect and refine skill tags (even if full editing is only designed, not fully implemented)
Provide feedback on flags and tags so the system can improve over time (as described in the feedback proposal)
For this challenge, the feedback loop is specified in design, and the data structures are ready to store those decisions.

2.2 Summary Spreadsheet – outputs/story_summary.csv

Each row corresponds to a single story. Key columns include:
story_id
story_title
grade_level
priority_score_final – overall 0–1 priority score for this story
priority_band – bucketed label such as "Very Low", "Low", "Medium", "High", "Critical"
heuristic_risk_score – risk from deterministic safety heuristics
llm_priority – max priority score from LLM-generated flags
num_flags – number of safety/content flags
num_skills – number of skills tagged
top_flag_types – compact string, e.g. "Violence (high); Bullying (medium)"
top_flag_snippet – short example of a flagged span
suggested_skills – e.g. "SKILL-COMP-003: Character Analysis; SKILL-VOC-002: Tier 2 Vocabulary"
needs_human_review – True/False safety-focused signal
needs_human_review_skills – True/False if skill tagging looks uncertain
review_status – reserved for reviewer decisions, e.g. "not_reviewed", "in_progress", "completed"
flags_accepted_revised, skills_accepted_revised, final_priority – reserved for future feedback logging

How a specialist uses this sheet
Open in Excel or Google Sheets
Sort by priority_score_final (or priority_band) descending → most urgent stories at the top
Filter by grade_level to focus on specific age ranges (e.g., K–2)
Scan top_flag_types, top_flag_snippet, and suggested_skills to see why a story is high priority before opening any detail view

This satisfies the “quick triage” requirement using tools content specialists already use daily.

2.3 Detailed View – Streamlit UI (app/streamlit_app.py)

The Streamlit app gives a story-at-a-time view with context and evidence.
Sidebar

Story selector:
choose by story_id or story_title

Key metadata:
grade_level
priority_score_final and priority_band
needs_human_review flag
Main Panel
Story text
full text of the story shown in a scrollable area
Flags section

list of issues with:
issue_type
severity
per-flag priority
rubric_category
rationale
evidence_text highlighted inline in the story using <mark> tags
(Internally, start_char / end_char from JSONL can be used for precise highlighting)
Skills section

table listing:
skill_id and skill_name
confidence (hybrid score) and confidence_raw
similarity_score from embeddings
evidence_text
justification
Mapping to the challenge requirements
“Understand what issues were flagged and where in the text”
→ the combination of flag list + highlighted evidence spans
“Review, accept, reject, or edit skill tags”
→ current app is read-only, but:
each flag/skill in JSONL is structured with stable fields that are easy to augment with IDs
it is straightforward to add controls (checkboxes/dropdowns) to capture reviewer decisions in a later iteration

2.4 Review, Accept, Reject, Edit – Conceptual Flow
The intended human-in-the-loop workflow is:
Triage in CSV
Specialist sorts story_summary.csv by priority_score_final and picks the top stories.
Inspect in UI
Opens the chosen story in the Streamlit app.
Review flags
Confirms which issues are valid
Optionally adjusts severity or notes additional nuance
Review skills
Confirms skill tags that are helpful
Removes clearly irrelevant ones
Optionally suggests missing skills
Feedback logging (designed)

These actions would be stored as feedback entries (see feedback_proposal.md), e.g.:
decision: accepted / rejected / edited
updated severity/skill/evidence where applicable
optional reviewer comments
The current code is focused on making the decisions easy:
explicit evidence for each flag/skill
clear, numeric priority scores
concise descriptions and justifications

Capturing these decisions as actual write-back is a small incremental step on top of the existing data model and UI.

2.5 Why This Interface Design Works

Spreadsheets
familiar, low-friction
great for sorting, filtering, and bulk triage
Streamlit UI
lightweight, quick to run locally
puts story, flags, and skills in one place
supports evidence highlighting without extra tooling

Together, they provide:
Fast triage (CSV)
Rich per-story understanding (UI)
A clean path to a full feedback loop later (edit controls + feedback logging)

