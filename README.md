Amira Story Curator – Safety & Skill Tagging Pipeline

A fully reproducible Heuristics + Embeddings + LLM hybrid system built for the
Amira Story Curator Challenge, designed to:
detect safety issues in children’s stories
assign reading skill tags from a 50-skill taxonomy
compute a priority score to triage editorial time
generate outputs for both human review and downstream automation
run locally and via a Streamlit UI

This project balances high recall, interpretability, and LLM efficiency, achieving a safety-first pipeline suitable for children’s content analysis.

1. High-Level System Architecture
┌──────────────────────────────────────────────────────────────┐
│                          Story Input                          │
│                     (data/stories.csv)                        │
└──────────────────────────────────────────────────────────────┘
                 │
                 ▼
┌──────────────────────────────────────────────────────────────┐
│                  STEP 1 — Safety Analysis                     │
│                                                              │
│  Heuristic Layer                LLM Safety Layer              │
│  - keyword patterns             - rubric-grounded JSON flags │
│  - zero-tol. & sensitive        - severity, priority,         │
│  - spans + risk score             evidence_text, rationale    │
└──────────────────────────────────────────────────────────────┘
                 │
                 ▼
┌──────────────────────────────────────────────────────────────┐
│             Evidence Validation + Flag Merging               │
│ - drop LLM flags with invalid evidence                       │
│ - add synthetic “General Safety Review” when needed          │
└──────────────────────────────────────────────────────────────┘
                 │
                 ▼
┌──────────────────────────────────────────────────────────────┐
│                  STEP 2 — Skill Tagging                      │
│                                                              │
│ Embedding Prefilter              LLM Skill Extractor         │
│ - MiniLM story embedding          - support_level            │
│ - cosine similarity               - confidence_raw           │
│ - top-K candidate skills          - evidence + justification │
│                                                              │
│ Hybrid Confidence Scoring                                    │
└──────────────────────────────────────────────────────────────┘
                 │
                 ▼
┌──────────────────────────────────────────────────────────────┐
│                         Final Outputs                        │
│ outputs/story_summary.csv                                     │
│ outputs/story_analysis.jsonl                                  │
│ Streamlit review UI                                           │
└──────────────────────────────────────────────────────────────┘

2. Motivation & Goals

Children’s reading content must be safe, age-appropriate, and educationally aligned.
Traditional single-prompt LLM approaches suffer from:
hallucinated evidence
missing critical safety patterns
poor reproducibility
expensive token consumption

This solution uses a layered hybrid pipeline to ensure:
high safety recall
LLM stability
verifiable evidence
semantic skill matching
interpretable outputs for editors

3. Pipeline Components
3.1 Safety Analysis
Heuristic Layer (safety_heuristics.py)

Deterministic keyword scanning for:
Zero-tolerance (1.0 weight):
profanity
weapons, explicit violence
self-harm
sexual content
hate speech
Sensitive content (0.5 weight):
bullying
fear, emotional harm
unsafe actions
cultural references
frightening scenarios

Produces:

issue_type
start_char, end_char
trigger_text
heuristic_score
LLM Safety Layer (safety_flagging_pipeline.py)

An LLM (GPT-4-mini or o-3-mini) receives:
full story
detailed rubric
JSON-mode schema

Returns:

issue_type  
severity (low/med/high/critical)  
priority  
evidence_text (literal substring required)  
rationale  

Evidence Validation + Merging
reject flags whose evidence_text is not in the story
drop hallucinated or floating evidence
if every LLM flag fails → add:

issue_type = "General Safety Review"
priority ≈ 0.6

This ensures near-zero false negatives.

3.2 Skill Tagging
Embedding Prefilter (skill_prefilter_embeddings.py)

To avoid sending all 50 skills to the LLM:
embed story text with MiniLM-L6-v2
embed each skill (name + description)
compute cosine similarity per skill

Behavior:

if similarity distribution is flat → keep all skills (avoid over-filtering short stories)
otherwise → send Top-K (≈10) skills to LLM
LLM Skill Extraction (skill_tagging_pipeline.py)

LLM returns:

skill_id
skill_name
support_level
confidence_raw
evidence_text
justification


Skills with no valid evidence are removed.

Hybrid Confidence Scoring
llm_conf = min(confidence_raw, 0.9)
sim_norm = clamp(similarity_score, 0.3, 1.0)
confidence = 0.6 * sim_norm + 0.4 * llm_conf


This balances:
semantic closeness (embeddings)
rubric reasoning (LLM)

3.3 Priority Scoring

Final score:

priority =
    0.5 * max_llm_flag_priority +
    0.2 * heuristic_score +
    0.2 * severity_component +
    0.1 * grade_factor


Enforced review conditions ensure:
early grades (K–3)
suspicious stories
missing evidence
any flagged safety issues

→ ALWAYS get human review.

4. Why Not an All-LLM Approach?

Rejected design: one huge prompt per story with full rubric + skills.

Issues:
high false negatives
slow (large context window)
expensive
fragile JSON parsing
no control over evidence grounding

Hybrid = safer + cheaper + more interpretable.

5. Repository Structure
amira_story_curator_app/
│
├── app/
│   └── streamlit_app.py          # Streamlit UI
│
├── src/
│   ├── safety_heuristics.py
│   ├── safety_flagging_pipeline.py
│   ├── skill_prefilter_embeddings.py
│   ├── skill_tagging_pipeline.py
│   ├── llm_clients.py
│   └── config.py
│
├── data/
│   ├── stories.csv
│   ├── skills.csv
│   └── content_rubric.md
│
├── outputs/
│   ├── story_summary.csv
│   └── story_analysis.jsonl
│
├── docs/
│   ├── output_spec.md
│   ├── content_interface.md
│   ├── feedback_proposal.md
│   └── runbook.md
│
├── requirements.txt
└── README.md

6. Installation & Setup
Clone the repo
git clone https://github.com/manasavuppu/amira_story_curator_app.git
cd amira_story_curator_app

Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

Install dependencies
pip install -r requirements.txt

Add OpenAI API Key

Create .env:

OPENAI_API_KEY=your_key_here

7. Run the Pipeline Locally
Batch analysis
python -m src.batch_analyze_stories

Writes:

outputs/story_summary.csv
outputs/story_analysis.jsonl

8. Run the Streamlit App
streamlit run app/streamlit_app.py

Features:
browse stories
highlight evidence spans
inspect safety flags
inspect skills + confidence
view priority explanations

9. Models & Citations
MiniLM-L6-v2 (SentenceTransformers)

Reimers & Gurevych, 2019
https://www.sbert.net/docs/pretrained_models.html

OpenAI GPT-4-mini / o-3-mini

Used for:
safety rubric evaluation
skill extraction
JSON-mode inference

10. Future Enhancements

RAG-based reading skill grounding
fine-tuned classifier for zero-shot safety recall
human-feedback loop storing reviewer corrections
multi-lingual story support
narrative coherence scoring
hallucination-resistant LLM scoring with A/B constraint prompts
