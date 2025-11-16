from typing import List

import pandas as pd
from sentence_transformers import SentenceTransformer, util

from .config import EMBED_MODEL

# -------------------------------------------------------------------
# Global embedding model
# -------------------------------------------------------------------
# Load once at import time so batch runs don’t pay the cost repeatedly.
model = SentenceTransformer(EMBED_MODEL)


def embed_texts(texts: List[str]):
    """
    Batch-encode texts with L2 normalization so cosine similarity
    behaves like a dot product on the unit sphere.

    Returns a torch.Tensor of shape (len(texts), dim).
    """
    if not texts:
        raise ValueError("embed_texts received an empty list of texts.")
    emb = model.encode(
        texts,
        convert_to_tensor=True,
        normalize_embeddings=True,
    )
    return emb


def _combine_skill_text(row: pd.Series) -> str:
    """
    Build a richer embedding representation for each skill.

    We embed:
        "<skill_name>. <skill_description>"

    Including skill_name improves semantic alignment and recall,
    especially for short or generic descriptions.
    """
    name = str(row.skill_name)
    desc = str(row.skill_description)
    return f"{name}. {desc}"


def _embedding_variance(emb_tensor) -> float:
    """
    Compute variance across embedding dimensions as a quality signal.

    If the variance is extremely low, it suggests the embeddings are
    collapsed / not discriminative for this batch, in which case we
    should NOT aggressively prune skills based on cosine scores.
    """
    if emb_tensor.ndim != 2 or emb_tensor.size(0) == 0:
        return 0.0
    return emb_tensor.var(dim=0).mean().item()


def prefilter_skills(
    story_text: str,
    skills_df: pd.DataFrame,
    top_k: int = 10,
    relevance_threshold: float = 0.25,
) -> pd.DataFrame:
    """
    Prefilter skills using semantic similarity BEFORE LLM selection.

    Behavior:
    ---------
    - Embed the story + each skill (name + description).
    - Compute cosine similarity story ↔ skill.
    - Attach a `similarity_score` column to the skills dataframe.
    - If embeddings are not discriminative (very low variance), return ALL skills.
    - If the story is too far from all skills (max cosine < threshold), return ALL skills.
    - Otherwise, return the top_k most similar skills, sorted by similarity.

    This function does NOT make any final decisions about which skills
    are "correct" — it only narrows down the candidate set and provides
    a math-based signal we can later blend with the LLM’s confidence.
    """
    # Basic safety: no story or no skills → nothing to filter
    if not story_text or skills_df.empty:
        return skills_df.copy()

    # --- Build richer embeddings for skills ---
    combined = [_combine_skill_text(row) for _, row in skills_df.iterrows()]

    # --- Embed story + skills in one batch for efficiency ---
    texts_to_encode = [story_text] + combined
    embeddings = embed_texts(texts_to_encode)

    story_emb = embeddings[0]
    skill_embs = embeddings[1:]

    # --- Compute cosine similarity (shape: (num_skills,)) ---
    scores = util.cos_sim(story_emb, skill_embs)[0]

    # Attach raw similarity to the dataframe (numpy array)
    skills_with_scores = skills_df.copy()
    skills_with_scores["similarity_score"] = scores.cpu().numpy()

    # --- Dynamic fallback: low variance means embeddings aren’t discriminative ---
    variance = _embedding_variance(skill_embs)
    if variance < 0.001:
        # Cosine collapsed → let LLM decide freely,
        # but still return similarity_score for transparency.
        return skills_with_scores.reset_index(drop=True)

    # --- Dynamic fallback: story too different from all skills ---
    max_score = float(scores.max().item())
    if max_score < relevance_threshold:
        # We do NOT trust similarity to prune harshly here; again,
        # let the LLM see the full taxonomy and use the scores later
        # only as a soft signal for confidence.
        return skills_with_scores.reset_index(drop=True)

    # --- Select top-k skills deterministically by similarity ---
    k = min(top_k, len(skills_with_scores))
    top_idx = scores.topk(k).indices.cpu().tolist()

    filtered = skills_with_scores.iloc[top_idx].copy()
    # Sort by similarity_score descending for reproducibility & debugging
    filtered.sort_values("similarity_score", ascending=False, inplace=True)
    filtered.reset_index(drop=True, inplace=True)

    return filtered
