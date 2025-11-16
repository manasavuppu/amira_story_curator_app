1. System Design 
This document describes the architecture, reasoning, and trade-offs behind my solution to the Amira Story Curator Challenge.
The system is a hybrid pipeline (Heuristics + Embeddings + LLMs) that:

detects safety and content issues in children’s stories
assigns reading skill tags from a 50-skill taxonomy
computes a priority score to focus the content specialist’s limited time
outputs results in both human-friendly and machine-readable formats

1.1 High-Level Architecture
For each story in data/stories.csv, the system performs:

Step 1 — Safety Analysis
1. Heuristic Layer: 
Scan the story for curated keyword patterns mapped to rubric categories
Identify zero-tolerance and sensitive content
Produce preliminary flags with:
issue_type
evidence span (start_char, end_char)
heuristic risk score

2. LLM Safety Layer
Use an LLM prompt grounded in the provided rubric
Identify nuanced issues, e.g., emotional safety, cultural sensitivity, age appropriateness
Return structured JSON flags with:
issue_type
severity
priority
evidence_text
rationale

- clamp purely synthetic, low-signal cases to a high but not critical priority, to avoid over-escalating benign decodables, while still forcing review;

- non-synthetic flags and skills now enforce grounded evidence spans, potentially dropping items whose evidence cannot be located in the story.

3. Evidence Validation & Merging
Reject any LLM flag whose evidence is not found in the story
Merge heuristic + LLM flags
If all evidence fails or text is suspicious → add synthetic “General Safety Review” flag
Safety Review Decision
Determine whether needs_human_review = True based on:
heuristic risk
severity of issues
grade level
LLM priority
evidence completeness

Step 2 — Skill Tagging

Embedding Prefilter (skill_prefilter_embeddings.py)
Embed the entire story using MiniLM-L6-v2
Embed each skill (name + description)
Compute cosine similarity

If story has weak similarity distribution → don’t over-filter; keep all skills

Otherwise → send only top-K skills (e.g., top 10) to the LLM

LLM Skill Tagging
LLM receives:
story text,
candidate skills,
instructions to extract supported skill tags

Outputs:
skill_id
skill_name
support_level
confidence_raw
evidence_text
justification

Hybrid Confidence
Compute a blended confidence using both LLM and embeddings:
llm_conf = min(confidence_raw, 0.9)
sim_norm = clamp(similarity_score, 0.3, 1.0)
adjusted_conf = 0.6 * sim_norm + 0.4 * llm_conf

confidence_raw is preserved
confidence uses the hybrid score
Higher similarity increases trust in the tag

Step 3 — Outputs
The system writes:
outputs/story_summary.csv
Spreadsheet-friendly triage table for content specialists
Includes: priority score, flags, skills, grade, human-review fields
outputs/story_analysis.jsonl
Detailed structured output per story
Contains all flags, spans, severities, priorities, skill tags, evidence, and scores
Streamlit App
Browse stories
Highlight evidence
Review flags and skills
Future-ready for human feedback logging

1.2 Key Design Decisions

Hybrid Instead of “All LLM”
Rejected approach:
Call a single large LLM prompt per story containing:
full rubric
all 50 skills
full story text
instruction to output safety, skills, and priority

Why rejected:
High false-negative risk without heuristics
Slow & expensive (large prompts)
Harder to tune or debug
Black-box priority logic
No control over evidence validation or safety recall
Chosen Approach: Hybrid Architecture

Heuristics → deterministic safety net; guarantee recall on critical patterns
Embeddings → semantic filtering; reduce LLM load
LLMs → nuanced, rubric-aware reasoning

This provides:
stronger safety recall
more trustworthy skill tagging
tunable and explainable priority scoring
faster and cheaper execution

1.3 Detecting Safety Issues

Heuristic Layer – safety_heuristics.py
Two signal groups:
Zero-Tolerance (weight 1.0)
profanity
explicit violence, weapons
self-harm
sexual content
hate speech

Sensitive (weight 0.5)
bullying, exclusion
emotional abuse, fear
unsafe behavior
cultural/identity references
frightening scenarios

Each match → a flag with:
issue_type
trigger_text
start_char, end_char

Heuristic risk score:
heuristic_score = min(1.0, (1*num_zero_tol + 0.5*num_sensitive) / 10)

This becomes one of the components of the final priority score.

LLM Safety Layer – safety_flagging_pipeline.py
LLM receives:
full story
full rubric (safety, age, cultural, emotional, technical)
structured JSON instructions

Returns flags containing:
issue_type
severity (low / medium / high / critical)
priority (0–1)
evidence_text (must be literal substring)
rationale

Evidence Validation:
If evidence is not extractable from the story → flag is dropped.
If all evidence fails, story is marked “suspicious” → synthetic safety flag added.

1.4 Assigning Skills

Embedding Prefilter – skill_prefilter_embeddings.py
Embed story text
Embed each skill’s:
name
description

Compute cosine similarity
If similarity variance is tiny (story is short, generic, unclear):
→ return all skills (avoid over-filtering)

Otherwise:
→ return top K (e.g., top 10) skills to send to the LLM

This yields a numeric similarity_score per skill.

LLM Skill Tagging – skill_tagging_pipeline.py
LLM rates each candidate skill with:
support_level
confidence_raw
evidence_text
justification

Skills with no evidence are dropped.

Hybrid Confidence
llm_conf = min(confidence_raw, 0.9)
sim_norm = clamp(similarity_score, 0.3, 1.0)
adjusted_conf = 0.6 * sim_norm + 0.4 * llm_conf

Embeddings provide semantic grounding
LLM confidence refines the semantic signal
Hybrid scoring helps rank skills for the reviewer

1.5 Prioritizing Content Specialist Time
Each story receives:
Final Priority Score
priority =
  0.5 * max_llm_flag_priority  +
  0.2 * heuristic_score         +
  0.2 * severity_component      +
  0.1 * grade_factor

Components:
max_llm_flag_priority → strongest flagged issue
heuristic_score → deterministic safety signals
severity_component → severity mapped to 0–1
grade_factor → younger grades (K–3) boosted

Forced Review Conditions
A synthetic "General Safety Review" is added when:
heuristic risk is non-trivial
any LLM flag suggests concern
grade ≤ 3 (content more sensitive for young readers)
evidence validation fails
story is very short, malformed, or empty

This ensures very low false-negatives for safety and appropriateness.

1.6 Why This Automation + LLM Blend Works
Heuristics
deterministic, cheap, transparent
catch critical patterns reliably
handle obvious unsafe content
Embeddings
semantic filtering
reduce cost and noise
support hybrid confidence
LLMs
interpret rubric nuance
identify emotional/cultural/age issues
provide justifications & evidence

Together, they deliver:
high recall for safety
reasonable precision for skill tagging
consistency across stories
easy debugging and tuning
predictable cost

1.7 Precision, Recall, Cost & Speed
Safety Flags
Prioritize recall (don’t miss dangerous content)
Accept minor over-flagging because humans review final results
Skill Tags

Balanced: slight recall preference
Goal is to surface skills for confirmation, not perfection
Performance
Embeddings reduce LLM token usage
JSON-mode prompts reduce parsing failures
Strict evidence validation improves reliability
Heuristics allow fast triage even before LLM calls

1.8 Design Trade-offs (Summary)

- Safety vs. Convenience**
  - Chosen: Over-flag rather than miss issues.
  - Rationale: False negatives on safety are unacceptable for children’s content.
  - Impact: Some extra reviewer time, but much higher trust in the system.

- Hybrid (Heuristics + LLM) vs. All-LLM**
  - Chosen: Hybrid.
  - Rationale: Heuristics guarantee certain patterns are never missed; LLMs handle nuance.
  - Impact: Better recall, easier debugging, and controllable cost.

- Two-Stage Pipeline vs. One Giant Prompt**
  - Chosen: Separate safety and skill passes.
  - Rationale: Safety and pedagogy have different rubrics and thresholds; separating them makes prompts clearer and tuning easier.
  - Impact: More interpretable outputs, simpler prompt evolution, and more stable behavior.

- Embeddings + LLM vs. LLM-only Skill Tagging**
  - Chosen: Embedding prefilter + LLM decision.
  - Rationale: Embeddings cheaply narrow the candidate skill set and provide a similarity score; LLM focuses on justification and evidence.
  - Impact: Lower token costs and better stability without sacrificing coverage.

- Recall vs. Precision for Skills**
  - Chosen: Slight recall bias.
  - Rationale: It is faster for reviewers to trim a few extra skills than to create missing ones from scratch.
  - Impact: More complete tagging, especially early in system life.
