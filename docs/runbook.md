4. Runnable Code & Runbook

This document explains exactly how to install, run, and reproduce the system end-to-end.
It is designed so a reviewer can clone the repo and generate all outputs with a single command.

4.1 Project Layout
.
├── app/
│   └── streamlit_app.py                 # Optional UI for browsing results
├── data/
│   ├── stories.csv                       # Input stories
│   ├── skills.csv                        # Skill taxonomy
│   └── content_rubric.md                 # Safety & quality rubric for LLM prompts
├── outputs/                              # Generated results
├── src/
│   ├── config.py
│   ├── safety_heuristics.py
│   ├── safety_flagging_pipeline.py
│   ├── skill_prefilter_embeddings.py
│   ├── skill_tagging_pipeline.py
│   └── llm_clients.py
├── batch_analyze_stories.py              # Entry point for the entire pipeline
├── requirements.txt
└── README.md


All core logic lives inside src/.

batch_analyze_stories.py runs the full pipeline over every story.

app/streamlit_app.py is an optional exploration UI.

4.2 Environment Setup
1. Create & activate a virtual environment
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install --upgrade pip
pip install -r requirements.txt

2. Set OpenAI API key
export OPENAI_API_KEY="sk-..."       # macOS / Linux
# or
setx OPENAI_API_KEY "sk-..."         # Windows

The code uses the OpenAI Python SDK 1.x (the new client library).

4.3 Running the Full Pipeline
From the repo root, run:
python -m src.batch_analyze_stories
What this command does
For each story in data/stories.csv, it:
Runs heuristic safety checks
Calls LLM-based safety analysis
Validates evidence spans and merges flags
Runs embedding-based skill prefiltering
Calls LLM skill tagging
Computes final priority score & review signals
Aggregates everything into output files
Generated Artifacts
Path	Description
outputs/story_analysis.jsonl	Full, per-story machine-readable output
outputs/story_summary.csv	Reviewer-friendly triage spreadsheet

The entire system is reproducible by running this single module.

4.4 Optional Web Interface (Streamlit)

To browse stories, flags, skills, and evidence in a UI:

cd app
streamlit run streamlit_app.py


Streamlit will print a URL (usually http://localhost:8501
).
Open it in your browser.
What you can do in the UI:
Select a story by ID or title
Read the full story text

Inspect safety flags:
severity
rationale
highlighted evidence text

Inspect skill tags:
confidence scores
similarity scores
evidence snippets

This interface mirrors how a real content specialist would review AI-generated results.

4.5 Reproducibility Notes

All dependencies are pinned in requirements.txt.
Model names and configuration are centralized in src/config.py.
As long as the data directory is present, running the batch script will re-generate all outputs exactly.
No external systems or services are required beyond the OpenAI API.