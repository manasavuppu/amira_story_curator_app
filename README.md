Amira Story Curator
Hybrid Safety Detection • Skill Tagging • Priority Scoring for Children’s Stories

This project analyzes children’s stories using a hybrid pipeline combining heuristics, embeddings, and LLMs to produce reliable safety flags, literacy skill tags, and reviewer-ready structured outputs.

✨ Features

High-recall safety detection (zero-tolerance pattern matching)

LLM-based nuance detection
Emotional safety, cultural sensitivity, age appropriateness

Skill tagging using embeddings + LLM extraction

Hybrid confidence scoring (semantic similarity + LLM certainty)

Priority scoring for reviewer triage

Streamlit UI for interactive exploration

Structured outputs (CSV + JSONL)

🔎 Architecture Overview
1. Safety Analysis
🔸 Heuristic Layer

Detects:

profanity

weapons

violence

self-harm

bullying

unsafe behaviors

Produces:

issue_type

trigger_text

start_char, end_char

heuristic_risk_score

🤖 LLM Safety Layer

Structured JSON:

{
  "issue_type": "",
  "severity": "",
  "priority": "",
  "evidence_text": "",
  "rationale": ""
}

🧹 Evidence Validation

Removes hallucinated evidence

Ensures evidence text appears in the story

Falls back to General Safety Review if missing

2. Skill Tagging
🧭 Embedding Prefilter

Uses MiniLM-L6-v2

Embeds story → vector and skills → vectors

Computes cosine similarity

Selects Top-K candidate skills

✍️ LLM Skill Extractor

Returns:

skill_id, skill_name

support_level

confidence_raw

evidence_text

justification

Invalid evidence → skill removed.

📐 Hybrid Confidence Score
llm_conf = min(confidence_raw, 0.9)
sim_norm = clamp(similarity_score, 0.3, 1.0)

confidence = 0.6 * sim_norm + 0.4 * llm_conf

3. Priority Scoring

Priority considers:

max LLM-assigned priority

heuristic risk

severity

grade-level adjustments

Auto-escalated if:

grade ≤ 3

suspicious structure

missing evidence

any safety flag

📁 Repository Structure
amira_story_curator_app/
│
├── app/
│   └── streamlit_app.py
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

⚙️ Installation
git clone https://github.com/manasavuppu/amira_story_curator_app.git
cd amira_story_curator_app


Create virtual environment:

python3 -m venv .venv
source .venv/bin/activate


Install dependencies:

pip install -r requirements.txt


Create .env:

OPENAI_API_KEY=your_key_here

▶️ Run Batch Processing
python -m src.batch_analyze_stories


Outputs:

outputs/story_summary.csv

outputs/story_analysis.jsonl

🖥️ Launch Streamlit UI
streamlit run app/streamlit_app.py


Features:

Story browsing

Evidence highlighting

Safety flags

Skill tags

Priority scoring

🤖 Models Used
MiniLM-L6-v2 (SentenceTransformers)

Used for semantic similarity and Top-K prefiltering.

OpenAI GPT Models

Used for safety analysis, skill extraction, and structured reasoning.

🔮 Future Enhancements

RAG-grounded skill tagging

Fine-tuned safety classifier

Reviewer feedback loop

Multilingual story support

Narrative coherence scoring

More hallucination-resistant scoring
