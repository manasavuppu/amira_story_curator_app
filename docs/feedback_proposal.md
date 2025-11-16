5. Human-in-the-Loop Feedback Proposal

This document describes how content specialist feedback would be captured and integrated to continuously improve the system.
The goal is to turn reviewer decisions into training signals that:
reduce false negatives (missed safety issues)
reduce false positives (annoying or irrelevant flags)
improve the accuracy and coverage of skill tagging
increase trust, usability, and predictability of the system

The focus is on designing the data structures, logging, and improvement loops that make refinement possible.

5.1 Types of Feedback Signals

During review, a content specialist may take actions on flags, skills, and story-level judgments.
These actions form the core feedback signals.

5.1.1 Safety Flags

For each system-generated flag, the reviewer can choose:

Field	Meaning
decision	accepted | rejected | edited
If edited	new values for issue_type, severity, or evidence
issue_type_new	corrected issue category
severity_new	corrected severity
evidence_text_new	corrected evidence span
comment	optional reviewer note

Reviewers may also add new flags that the system missed.
These additions are critical signals for reducing false negatives.

5.1.2 Reading Skills

For each suggested skill:

Field	Meaning
decision	accepted | rejected | edited
If edited	new skill assignment or corrected evidence
skill_id_new	replacement skill ID
evidence_text_new	corrected evidence
justification_new	updated explanation

Reviewers may also add missing skills, indicating areas where the system lacks coverage.

5.1.3 Story-Level Feedback

Optional higher-level reviewer metadata:
story_overall_label: safe | borderline | unsafe
time_to_review_seconds

free-text notes for:
cultural nuance
age-appropriateness context
edge cases not covered by heuristics or LLMs
These story-level annotations help calibrate priority scoring and rubric interpretation.

5.2 Structuring the Feedback Loop

To turn human decisions into improvements, the system needs a consistent feedback log and a periodic analysis → update cycle.

5.2.1 Logging Reviewer Decisions

Extend the outputs folder with a file like:

outputs/feedback_log.jsonl


Each record captures a single reviewer action:

{
  "story_id": "S_012",
  "item_type": "flag",
  "item_id": "flag_3",
  "system_issue_type": "Bullying",
  "system_severity": "medium",
  "human_decision": "rejected",
  "human_comment": "Teasing is brief and resolved immediately.",
  "timestamp": "2025-11-15T10:15:00Z",
  "reviewer_id": "rev_001"
}


Key fields:

story_id — links to the JSONL and CSV
item_type — "flag" or "skill"
item_id — stable identifier from story_analysis.jsonl
system_* fields — what the model originally predicted
human_* fields — the reviewer’s correction
timestamp — for time-series analysis
reviewer_id — optional but useful for calibration and inter-rater reliability

These logs become the ground-truth dataset for ongoing refinement.

5.2.2 Analyzing Feedback

Analysis can be run weekly or monthly. Key metrics:
Safety Flag Metrics
precision / recall per issue_type
severity calibration accuracy
false positives: flags often rejected
false negatives: flags often added by reviewers
evidence disagreements (edit frequency)
Skill Tag Metrics
per-skill precision and recall
skills frequently added by reviewers (missing coverage)
skills frequently rejected (over-tagging or noise)
Story-Level Metrics
reviewer time per story
mismatch between priority_score and reviewer judgment
distribution of borderline vs safe/unsafe calls

This analysis reveals systematic errors, not one-off cases.

5.2.3 Updating the System

Feedback informs improvements in several components:

1. Heuristic Rules
add or refine keywords for recurring missed issues
remove triggers causing frequent false positives
adjust “zero-tolerance” vs “sensitive” classifications

2. LLM Prompts

add few-shot examples from accepted flags
add counter-examples for scenarios where over-flagging occurs
strengthen rubric instructions for cultural or contextual nuance

3. Embedding & Confidence Thresholds

adjust top-K selection for skills
tune minimum similarity floors
tune hybrid confidence weighting (embeddings vs LLM)

4. Priority Scoring Model

Refine weights for:

severity
heuristics
grade factor
LLM priority

5. Optional Calibration Model

Train a small shallow model or score-calibration layer that predicts:
“Will a human accept this flag/skill?”

Based on:

confidence_raw
similarity_score
severity
issue_type
grade_level
flag source (llm vs heuristic vs synthetic)

This gradually makes the system self-correcting.

5.3 Measuring Improvement

Using a held-out, reviewer-labeled dataset, track:

Safety Metrics
precision, recall, and F1 per issue type
reduction in false negatives
reduction in noisy or irrelevant flags
severity calibration accuracy
Skill Tagging Metrics
precision & recall per skill
mean edits per story
proportion of reviewer-added vs system-suggested skills
Workflow Metrics
average review time per story
improvement in priority score’s predictive power

reviewer satisfaction (1–5 scale):

“Flags are helpful and not noisy.”
“Skill suggestions save time.”
These metrics form a quantitative timeline of improvement.

5.4 Scope for the Challenge Submission

For this coding challenge:
The full feedback loop is not implemented (out of scope)

But the system has been architected to support it:
JSONL output is structured to attach human decisions
Summary CSV provides top-level triage signals
Item-level (flag_id, skill_id) fields allow tracking edits
Clear logging format is defined

The proposal outlines:
how feedback would be captured,
how it would be analyzed, and
how the system would be updated over time

