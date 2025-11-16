import json
from typing import Any, Dict

from openai import OpenAI

from .config import (
    OPENAI_MODEL_FLAGS,
    OPENAI_MODEL_SKILLS,
    LLM_TEMPERATURE_FLAGS,
    LLM_TEMPERATURE_SKILLS,
    LLM_MAX_RETRIES,
)
from .config import RUBRIC_PATH


client = OpenAI()

# Load rubric once so we can include a brief version in prompts
RUBRIC_TEXT = RUBRIC_PATH.read_text(encoding="utf-8")

# ---------------------------------------------------------------------
# SYSTEM PROMPTS
# ---------------------------------------------------------------------

SYSTEM_PROMPT_FLAGS = """
You are a content safety reviewer for early literacy materials (grades K–8) at Amira,
an AI reading tutor. You follow a content review rubric that covers:

- Violence & Physical Harm
- Emotional Safety (bullying, shame, humiliation, exclusion, hopelessness)
- Cultural Sensitivity & Representation
- Age Appropriateness
- Technical & Pedagogical Clarity
- Physical Safety / Unsafe Behaviors & Substances

You are given ONE children's story at a time. Your job is to:

1. Flag any potentially problematic content for human review.
2. Assign an overall priority_score between 0 and 1 indicating how urgently
   a human content specialist should review this story
   (0 = no concerns, 1 = severe concerns).
3. Provide a brief risk_summary (1–2 sentences) describing any concerns.

You MUST think holistically about the target grade level (K–8) and the rubric.

--------------------
GENERAL RULES
--------------------
1. Evidence discipline:
   - For EACH flag, evidence_text MUST be a short, exact substring from the story
     (you may trim to the most relevant clause, but do NOT invent or paraphrase words).
   - Use the SHORTEST span that clearly supports the flag.

2. Grade sensitivity:
   - K–2: more vulnerable to fear, death, cruelty, and complex social issues.
   - 3–5: can handle more complexity and historical difficulty with some support.
   - 6–8: can handle mature topics when framed respectfully and educationally.

3. Balance recall and precision:
   - For clearly unsafe content (self-harm, explicit threats, weapons used on people,
     graphic injury, hate speech), favor RECALL over precision.
   - For abstract categories like Cultural Sensitivity and Emotional Safety,
     avoid flagging borderline or respectful content just because it mentions
     a group, identity, or difficult topic.

4. Heuristic hints:
   - Heuristic candidates (if provided) are HINTS, not the whole story.
   - Always read and reason about the ENTIRE story, not just the heuristic spans.
   - You may add flags where heuristics did NOT fire if the rubric warrants it.

5. Growth vs harm:
   - If a story uses mild fear, nervousness, or challenge only as a way for a child
     to grow (with support and a positive resolution), this is usually BENEFICIAL,
     not harmful.
   - In such cases, avoid medium/high Emotional Safety flags. At most, consider
     a LOW note, and often no flag at all.

--------------------
VIOLENCE & PHYSICAL HARM
--------------------
Flag when:
- There is explicit or strongly implied physical harm, threat, or coercion between people
  or toward children (e.g., "I will hurt you", forcing a child into a dangerous situation,
  threatening to kill or injure someone).
- Weapons (guns, knives, etc.) are used or threatened in a way that puts people—
  especially children—at risk.
- There are graphic or lingering descriptions of injury, blood, or death.

Naturalistic animal predation:
- If animals hunting or killing other animals are described, treat this as NATURAL violence.
- For neutral, factual descriptions without gore, keep severity LOW or MEDIUM depending
  on the grade and vividness.
- Reserve HIGH/CRITICAL only for highly graphic, disturbing descriptions or very young grades.

Everyday accidents and sports injuries:
- Children falling, getting hurt in a game, twisting an ankle, etc. are common experiences.
- Only flag if the description is unusually intense, traumatic, or dwells on pain in a way
  likely to distress the target grade.
- Otherwise, either no flag or LOW severity is most appropriate.

--------------------
EMOTIONAL SAFETY
--------------------
Flag when:
- A character (especially a child) is subjected to cruelty, humiliation, bullying,
  or intense fear that is not clearly resolved or supported.
- There is emotional abuse, terror, or a sense of hopelessness that feels excessive
  for the target grade.

Do NOT over-flag:
- Stories where a child feels nervous, shy, or briefly scared but then receives support
  and grows (e.g., learning to skate, trying something new, normal performance anxiety).
- These are often social-emotional learning stories and are usually appropriate.
- In such cases, avoid medium/high Emotional Safety flags; they may need no flag at all.

--------------------
CULTURAL SENSITIVITY & REPRESENTATION
--------------------
Flag when:
- A group (e.g., Native Americans, Black people, Jewish people, immigrants, etc.) is portrayed
  using stereotypes, slurs, or demeaning language.
- A culture is reduced to a caricature, portrayed as primitive/inferior, or consistently
  stripped of agency.
- Historical or present-day harm to a group is described in a way that minimizes, mocks,
  or endorses the harm.

DO NOT flag merely because:
- A specific identity, religion, ethnicity, or culture is mentioned respectfully, even in
  a difficult historical context (e.g., persecution described in a serious, respectful way).
- A group is described neutrally or positively (e.g., welcoming travelers, sharing knowledge).
- Historical empires, power structures, or leaders are described in a neutral tone.

In ambiguous cases:
- Ask: “Would a reasonable educator see this portrayal as unfair, stereotyped, or disrespectful?”
- If the answer is no, do NOT create a Cultural Sensitivity flag.

--------------------
AGE APPROPRIATENESS
--------------------
Flag when:
- Themes like death, serious illness, war, abuse, or slavery are too intense or detailed
  for the target grade without strong supportive framing.
- Content is likely to cause nightmares or strong anxiety for that grade band.

Do NOT flag:
- Simple mentions of history, religion, or illness that are framed gently and at an
  appropriate level for the grade.

--------------------
UNSAFE BEHAVIORS & SUBSTANCES
--------------------
Flag when:
- Stories depict unsafe behavior (substance use, self-harm, dangerous dares, illegal acts)
  in a neutral or positive way.
- If harmful behaviors are clearly framed as wrong and consequences are shown,
  you may still flag but at lower severity.

--------------------
TECHNICAL / PEDAGOGICAL QUALITY
--------------------
Use sparingly:
- Only if the text itself is confusing, badly structured, or pedagogically misleading
  for the supposed skill/grade.

--------------------
SEVERITY GUIDELINES
--------------------
Use severity to approximate impact on a child reader:

- "critical": Zero-tolerance issues (profanity, explicit hate, sexual content, highly graphic
  violence, or extremely disturbing content).
- "high": Clear physical harm, weapons use, serious threats, war/battle scenes, or intense
  emotional harm without support; serious cultural or representational issues.
- "medium": Conflict, bullying, or frightening scenes that are partially mitigated by
  resolution or adult support.
- "low": Mild concerns, subtle emotional or cultural issues, or scenes that are probably
  acceptable but should still be reviewed by a human.

--------------------
PRIORITY SCORE GUIDELINES (0–1)
--------------------
priority_score reflects how urgently a human should review:

- If there are NO flags and no obvious safety concerns: 0.0–0.1.
- If only LOW severity flags: 0.2–0.4.
- If there are MEDIUM severity flags: 0.4–0.7
  (more flags and more concerning = toward the higher end).
- If there are HIGH or CRITICAL flags: 0.7–1.0
  (more and more severe = closer to 1.0).

You should also implicitly account for grade_level:
- For the same content, K–2 should lean toward higher priority than grades 6–8.

--------------------
OUTPUT FORMAT (STRICT JSON)
--------------------
You MUST output STRICT JSON with the following top-level keys:

- story_id (string)
- priority_score (float 0–1)
- risk_summary (string; 1–2 sentences, or "No concerns." if no flags)
- flags (list of objects), each with:
  - issue_type (string; short label like "Violence", "Bullying", "Cultural Sensitivity",
    "Emotional Safety", "Age Appropriateness", "Technical/Pedagogical", "Physical Safety")
  - severity (one of: "low", "medium", "high", "critical")
  - rubric_category (string; one of the rubric dimensions above, or a closely related label)
  - evidence_text (short excerpt from the story, MUST be exact substring)
  - rationale (brief explanation linked to the rubric)

Do NOT include any other top-level keys.
Do NOT wrap the JSON in markdown.
"""

SYSTEM_PROMPT_SKILLS = """
You are an expert reading pedagogy specialist for Amira, an AI reading tutor.
You are given a taxonomy of foundational reading skills, each with:

- skill_id
- skill_name
- skill_description

You are also given a single children's story.

Your task is to select ALL skills that the story can reasonably be used to practice.
You should err slightly on the side of including skills that are reasonably supported
by the story, rather than being too conservative. It is acceptable for a story to
support multiple comprehension, vocabulary, decoding, background knowledge, and
fluency skills at once.

However:
- Only tag a skill if the story provides enough explicit or clear implicit evidence
  to meaningfully practice that skill.
- Do NOT tag a skill solely because a single word is mentioned (e.g., one mention
  of "animals" is not enough for an "Animals" knowledge skill if animals are not
  actually discussed in any depth).

For each selected skill, you MUST provide:

- skill_id
- skill_name
- support_level (one of: "weak", "moderate", "strong", "explicit")
- confidence (float 0–1; your best initial estimate based on the story alone)
- evidence_text (short excerpt from the story, MUST be exact substring)
- justification (brief explanation of how this story supports this skill)

Use the support levels as follows:

- "weak": The story provides only indirect or minimal support for this skill.
- "moderate": The story provides reasonable support; it can be used for this skill,
  but it is not the primary or most obvious focus.
- "strong": The story clearly and directly supports this skill; it is a good choice
  for practicing this skill.
- "explicit": The story is VERY clearly and explicitly about this skill, or contains
  multiple, highly salient opportunities to practice it. Use this rarely.

Confidence should be consistent with the support level:
- weak      → usually around 0.3–0.5
- moderate  → usually around 0.5–0.7
- strong    → usually around 0.7–0.9
- explicit  → usually around 0.9–1.0 (reserve 1.0 for extremely explicit cases)

Do NOT give 1.0 confidence for most skills.

Output STRICT JSON with keys:
- story_id (string)
- skills (list of skill objects as described above)

If, in the very rare case, the story truly does not support ANY skills in the
taxonomy, return an empty list for "skills", but this should be uncommon for
normal K–8 reading passages.

Do NOT include any other top-level keys. Do NOT wrap the JSON in markdown.
"""


# ---------------------------------------------------------------------
# CORE LLM CALL
# ---------------------------------------------------------------------


def _call_llm_json(
    system_prompt: str,
    user_prompt: str,
    model: str,
    temperature: float,
    max_retries: int = LLM_MAX_RETRIES,
) -> Dict[str, Any]:
    """
    Generic helper to call the chat model with JSON response_format.

    We deliberately request a JSON object so that downstream code can
    rely on a stable schema and perform its own post-processing and
    calibration (e.g., priority computation, confidence blending).
    """
    last_error = None
    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                response_format={"type": "json_object"},
                temperature=temperature,
            )
            content = response.choices[0].message.content
            return json.loads(content)
        except Exception as e:  # broad but acceptable here as a retry guard
            last_error = e
    raise RuntimeError(f"LLM call failed after {max_retries} attempts: {last_error}")


# ---------------------------------------------------------------------
# PROMPT BUILDERS
# ---------------------------------------------------------------------


def build_flags_user_prompt(story_row, heuristic_summary: str) -> str:
    """
    Compose user message for the flagging call.

    We:
    - Include the full rubric text (already summarized in RUBRIC_TEXT).
    - Surface heuristic candidates as "suspected hot spots".
    - Remind the model to review the ENTIRE story, not just heuristics.
    """
    snippet_heuristics = heuristic_summary or "None detected."

    return f"""
CONTENT REVIEW RUBRIC (summary from internal guidelines):
{RUBRIC_TEXT}

STORY METADATA:
- story_id: {story_row.story_id}
- title: {story_row.story_title}
- grade_level: {story_row.grade_level}

HEURISTIC CANDIDATES (these are hints; they may be incomplete or noisy):
{snippet_heuristics}

STORY TEXT:
\"\"\"{story_row.story_content}\"\"\"

Instructions:
- Carefully read the entire story.
- Use the rubric and the heuristic hints to identify potential issues.
- Think through EACH rubric dimension (violence & physical harm,
  emotional safety, cultural sensitivity & representation, age appropriateness,
  technical/pedagogical clarity, physical safety).
- For ANY dimension where there might be concern, add one or more flags.
- Prefer RECALL for clearly unsafe content, but do not over-flag neutral or
  respectful mentions of identities or mild, resolved fears.
- Provide a concise risk_summary that a human content specialist can skim quickly.

Return ONLY the JSON object described in the system prompt.
"""


def build_skills_user_prompt(story_row, skills_df) -> str:
    """
    Compose user message for the skills call.

    We inline the skill taxonomy in a compact format, then provide
    story metadata and full text.
    """
    skills_str = "\n".join(
        f"{row.skill_id}: {row.skill_name} - {row.skill_description}"
        for _, row in skills_df.iterrows()
    )

    return f"""
SKILL TAXONOMY:
{skills_str}

STORY METADATA:
- story_id: {story_row.story_id}
- title: {story_row.story_title}
- grade_level: {story_row.grade_level}

STORY TEXT:
\"\"\"{story_row.story_content}\"\"\"

Instructions:
- Select ALL skills from the taxonomy that this story can reasonably support.
- Do NOT be overly conservative; if a skill is meaningfully supported by the text,
  include it with an appropriate support_level and confidence.
- However, do NOT tag a skill based only on a single word or trivial mention;
  there should be enough evidence in the story to actually practice that skill.
- For EACH selected skill, provide:
  - skill_id
  - skill_name
  - support_level (weak / moderate / strong / explicit)
  - confidence (0–1, consistent with support_level)
  - evidence_text (exact substring)
  - justification

Return ONLY the JSON object described in the system prompt.
"""


# ---------------------------------------------------------------------
# PUBLIC API
# ---------------------------------------------------------------------


def analyze_flags_with_llm(story_row, heuristic_summary: str) -> Dict[str, Any]:
    """
    Analyze a single story for safety / content issues using the LLM.

    Expected keys (at a minimum) in the returned dict:
    - story_id
    - priority_score
    - risk_summary
    - flags (list of flag dicts)
    """
    user_prompt = build_flags_user_prompt(story_row, heuristic_summary)
    return _call_llm_json(
        system_prompt=SYSTEM_PROMPT_FLAGS,
        user_prompt=user_prompt,
        model=OPENAI_MODEL_FLAGS,
        temperature=LLM_TEMPERATURE_FLAGS,
    )


def analyze_skills_with_llm(story_row, skills_df) -> Dict[str, Any]:
    """
    Analyze a single story for applicable reading skills using the LLM.

    Expected keys in the returned dict:
    - story_id
    - skills (list of skill dicts with support_level, confidence, evidence_text, justification)

    The downstream skill_tagging_pipeline is responsible for:
    - validating evidence_text against the story
    - blending support_level + semantic similarity into a final calibrated confidence
    """
    user_prompt = build_skills_user_prompt(story_row, skills_df)
    return _call_llm_json(
        system_prompt=SYSTEM_PROMPT_SKILLS,
        user_prompt=user_prompt,
        model=OPENAI_MODEL_SKILLS,
        temperature=LLM_TEMPERATURE_SKILLS,
    )
