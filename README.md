Amira Story Curator
Safety Detection + Skill Tagging + Priority Scoring Pipeline

A hybrid AI system that analyzes children’s stories using heuristics, embeddings, and LLMs to produce reliable safety flags, literacy skill tags, and structured review outputs.

⭐ Features

🔒 High-recall safety analysis (zero-tolerance detections)

🧩 LLM-based nuance detection (emotional safety, cultural sensitivity)

🔎 Skill tagging using embeddings + LLM extraction

📊 Priority scoring for human reviewers

🖥️ Streamlit UI for interactive exploration

📁 Structured outputs (CSV + JSONL)

⚡ Hallucination-resistant architecture

🏗️ Architecture Overview
flowchart TD

A[data/stories.csv] --> B[Safety Analysis]

subgraph B[STEP 1 — Safety Analysis]
    B1[Heuristic Layer<br/>• Zero-tolerance checks<br/>• Span detection<br/>• Risk score]
    B2[LLM Safety Layer<br/>• issue_type<br/>• severity<br/>• priority<br/>• evidence + rationale]
    B3[Evidence Validation<br/>Drop hallucinations<br/>Merge flags<br/>Add fallback review]
    B1 --> B2 --> B3
end

B --> C[STEP 2 — Skill Tagging]

subgraph C[Skill Tagging]
    C1[Embedding Prefilter<br/>MiniLM-L6-v2 cosine similarity]
    C2[LLM Skill Extractor<br/>evidence & justification]
    C3[Hybrid Confidence Scoring]
    C1 --> C2 --> C3
end

C --> D[STEP 3 — Final Outputs]

subgraph D[Outputs]
    D1[story_summary.csv]
    D2[story_analysis.jsonl]
    D3[Streamlit UI]
end

🎯 Motivation

LLMs alone are not enough for safety-critical children’s content.
They hallucinate, miss issues, and cost more.

Hybrid = the best of all worlds
Component	Why It Matters
Heuristics	Deterministic. No false negatives for weapons, profanity, violence, self-harm.
Embeddings	Semantic grounding → fewer irrelevant skills.
LLMs	Deep reasoning, rubric alignment, nuance detection.
Validation layer	Prevents hallucinated evidence.
🔍 Pipeline Details
1. Safety Analysis
🔹 Heuristic Layer (safety_heuristics.py)

Detects:

Profanity

Weapons

Violence

Self-harm

Bullying

Unsafe behaviors

Outputs:

issue_type
trigger_text
(start_char, end_char)
heuristic_risk_score

🔹 LLM Safety Layer (safety_flagging_pipeline.py)

Returns:

{
  "issue_type": "",
  "severity": "",
  "priority": "",
  "evidence_text": "",
  "rationale": ""
}

🔹 Evidence Validation

Drops hallucinated evidence

Ensures evidence_text matches the story

If everything fails:

issue_type = "General Safety Review"
priority ≈ 0.6

2. Skill Tagging
🔹 Embedding Prefilter (skill_prefilter_embeddings.py)

MiniLM-L6-v2 embeddings

Compare story → skills

Cosine similarity

Flat distributions → keep all

Otherwise → top-K selected

🔹 LLM Skill Extractor (skill_tagging_pipeline.py)

Returns:

skill_id
skill_name
support_level
confidence_raw
evidence_text
justification


Skills missing valid evidence are removed.

🔹 Hybrid Confidence Score
llm_conf   = min(confidence_raw, 0.9)
sim_norm   = clamp(similarity_score, 0.3, 1.0)

confidence = 0.6 * sim_norm + 0.4 * llm_conf

3. Priority Scoring
priority =
  0.5 * max_llm_flag_priority +
  0.2 * heuristic_score +
  0.2 * severity_component +
  0.1 * grade_factor


Stories are always flagged for review if:

Grade ≤ 3

Suspicious structure

Missing evidence

Any safety concern

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

python3 -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt


Create .env:

OPENAI_API_KEY=your_key_here

▶️ Run Batch Processing
python -m src.batch_analyze_stories


Outputs written to:

outputs/story_summary.csv

outputs/story_analysis.jsonl

🖥️ Launch the Streamlit UI
streamlit run app/streamlit_app.py


Features:

Story browser

Evidence highlighting

Skill + flag inspection

Priority scoring

🤖 Models Used
SentenceTransformers — MiniLM-L6-v2

Semantic similarity for prefiltering

Ref: Reimers & Gurevych (2019)

https://www.sbert.net/docs/pretrained_models.html

OpenAI GPT Models

Used for:

Safety analysis

Skill extraction

JSON-structured reasoning

🔮 Future Enhancements

🔗 RAG grounding for skill tagging

🔥 Fine-tuned classifier for high-recall safety

🧑‍🏫 Reviewer feedback loop

🌍 Multilingual support

🪶 Narrative coherence scoring

🛡️ Hallucination-resistant LLM scoring functions
