1. High-Level System Architecture

Story Input
Stories load from:
data/stories.csv

STEP 1 — Safety Analysis
1. Heuristic Layer
Detects:
Zero-tolerance issues
Sensitive issues

Produces:
issue_type
evidence span (start_char, end_char)
heuristic_risk_score

2. LLM Safety Layer
LLM evaluates:
emotional safety
cultural sensitivity
age appropriateness

Returns JSON:
issue_type
severity
priority
evidence_text
rationale
Evidence Validation & Merging

Drop LLM flags with invalid evidence
Merge heuristic + LLM flags
Add synthetic “General Safety Review” if evidence missing or story malformed

STEP 2 — Skill Tagging
Embedding Prefilter
Story embedded with MiniLM-L6-v2
Skills (name + description) embedded
Cosine similarity → Top-K skill selection
LLM Skill Extractor

LLM returns:
skill_id, skill_name
support_level
confidence_raw
evidence_text
justification

Skills with missing evidence are dropped.

Hybrid Confidence Scoring
llm_conf = min(confidence_raw, 0.9)
sim_norm = clamp(similarity_score, 0.3, 1.0)
confidence = 0.6 * sim_norm + 0.4 * llm_conf

Combines:
semantic grounding (embeddings)
rubric reasoning (LLM)

STEP 3 — Final Outputs
Structured Files
outputs/story_summary.csv     # Reviewer triage
outputs/story_analysis.jsonl  # Full structured details

Streamlit UI
browse stories
highlight evidence
inspect flags & skills
see priority explanations

2. Motivation & Goals

Children's content must be:
safe
age-appropriate
educationally aligned

Problems with single-prompt LLM approaches:
hallucinations
missed safety issues
high compute costs
low reproducibility

Hybrid Pipeline Fixes This:
heuristics guarantee zero false negatives for critical issues
embeddings improve semantic precision
LLMs add nuance and rubric grounding
evidence validation ensures trustworthy outputs

3. Pipeline Components
3.1 Safety Analysis
Heuristic Layer (safety_heuristics.py)

Detects:
Zero-tolerance (1.0) → profanity, weapons, violence, self-harm
Sensitive (0.5) → bullying, fear, unsafe behavior

Produces deterministic:
spans
trigger texts
heuristic risk score
LLM Safety Layer (safety_flagging_pipeline.py)
LLM receives full story + rubric → returns:
issue type
severity
priority
evidence_text
rationale
Evidence Validation
Drop hallucinated evidence

If ALL evidence fails →
issue_type = "General Safety Review", priority ≈ 0.6

3.2 Skill Tagging
Embedding Prefilter (skill_prefilter_embeddings.py)
Embed story + skills
Compute similarity
Flat distributions → keep all skills
Otherwise → send Top-K

LLM Skill Extraction (skill_tagging_pipeline.py)
Returns:
skill metadata
confidence_raw
justification
Invalid evidence → skill dropped.

3.3 Priority Scoring

Final score:
priority =
  0.5 * max_llm_flag_priority +
  0.2 * heuristic_score +
  0.2 * severity_component +
  0.1 * grade_factor

Stories always reviewed if:
grade ≤ 3
suspicious text
missing evidence
any safety concern

4. Why Not an All-LLM Pipeline?
Because it leads to:
high false negatives
high cost
slow inference
hallucinated evidence
fragile JSON outputs

✔ Hybrid = safer + cheaper + more interpretable + more controllable

5. Repository Structure

amira_story_curator_app/

├── app/
│   └── streamlit_app.py

├── src/
│   ├── safety_heuristics.py
│   ├── safety_flagging_pipeline.py
│   ├── skill_prefilter_embeddings.py
│   ├── skill_tagging_pipeline.py
│   ├── llm_clients.py
│   └── config.py

├── data/
│   ├── stories.csv
│   ├── skills.csv
│   └── content_rubric.md

├── outputs/
│   ├── story_summary.csv
│   └── story_analysis.jsonl

├── docs/
│   ├── output_spec.md
│   ├── content_interface.md
│   ├── feedback_proposal.md
│   └── runbook.md

├── requirements.txt

└── README.md

⚙️ 6. Installation & Setup
git clone https://github.com/manasavuppu/amira_story_curator_app.git
cd amira_story_curator_app
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt


Create .env:

OPENAI_API_KEY=your_key_here

7. Run the Pipeline
Batch processing
python -m src.batch_analyze_stories


Outputs saved to:

outputs/story_summary.csv

outputs/story_analysis.jsonl

8. Run the Streamlit App
streamlit run app/streamlit_app.py

9. Models & Citations
MiniLM-L6-v2 (SentenceTransformers)

Reimers & Gurevych (2019)
https://www.sbert.net/docs/pretrained_models.html

OpenAI GPT-4-mini / o-3-mini

Used for:
safety analysis
skill extraction
JSON-mode reasoning

10. Future Enhancements

RAG grounding for skills
fine-tuned classifiers for safety recall
human-feedback loop
multilingual support
narrative coherence scoring
hallucination-resistant LLM scoring
