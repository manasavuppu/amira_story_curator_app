from pathlib import Path
import os

from dotenv import load_dotenv

# -------------------------------------------------------------------
# Load environment variables from .env (if present)
# -------------------------------------------------------------------
load_dotenv()

# -------------------------------------------------------------------
# Base paths
# -------------------------------------------------------------------
# BASE_DIR = repo root (src/ is one level below)
BASE_DIR = Path(__file__).resolve().parent.parent

# Data & outputs
DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "outputs"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Core input files
STORIES_PATH = DATA_DIR / "stories.csv"
SKILLS_PATH = DATA_DIR / "skills.csv"
RUBRIC_PATH = DATA_DIR / "content_rubric.md"

# Optional: config file for safety heuristics
# (rubric-aligned categories, keyword lists, weights, etc.)
SAFETY_HEURISTICS_CONFIG_PATH = DATA_DIR / "safety_heuristics.yml"

# -------------------------------------------------------------------
# OpenAI / LLM configuration
# -------------------------------------------------------------------
# API key (also read directly by the OpenAI client via env var)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Models for the two main tasks
OPENAI_MODEL_FLAGS = os.getenv("OPENAI_MODEL_FLAGS", "gpt-4o-mini")
OPENAI_MODEL_SKILLS = os.getenv("OPENAI_MODEL_SKILLS", "gpt-4o-mini")

# Temperatures kept low for determinism / reviewability
LLM_TEMPERATURE_FLAGS = float(os.getenv("LLM_TEMPERATURE_FLAGS", "0.2"))
LLM_TEMPERATURE_SKILLS = float(os.getenv("LLM_TEMPERATURE_SKILLS", "0.2"))

# Simple retry budget for transient failures
LLM_MAX_RETRIES = int(os.getenv("LLM_MAX_RETRIES", "2"))

# -------------------------------------------------------------------
# Embedding model configuration
# -------------------------------------------------------------------
# Used for semantic skill prefiltering and (optionally) semantic heuristics.
EMBED_MODEL = os.getenv("EMBED_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
