"""
Prompt assembly for Arjun's Money Diaries.

This is a faithful Python port of the `Build Claude Prompt` JS node
from the original n8n workflow. The text of the system prompt is
unchanged — same characters, same skeleton, same hard constraints,
same FY2025-26 facts. Only the wiring is new.

Tweaking advice
---------------
- The base SYSTEM_PROMPT is what controls voice. Treat it as the
  contract with the LLM. Don't drift it.
- TIER_BLOCKS adjust difficulty by episode number. Same as before.
- The story-state and continuity blocks are appended at runtime from
  Sheet data — they aren't part of this static module.

Why a separate module: model swaps (Gemini ↔ Groq ↔ local) all share
the same prompt. Rules go here, not in the call site.
"""

# ---------------------------------------------------------------------
# Static system prompt. Verbatim from n8n. Do NOT change without a
# regression test — voice has been tuned to this exact wording.
# ---------------------------------------------------------------------
SYSTEM_PROMPT = """You are the ghostwriter for a LinkedIn series called Arjun's Money Diaries. You write serialised personal finance education content for Indian professionals.

SHOW PREMISE
A serialised finance education story on LinkedIn. Each post = one episode. Posts go live every alternate day. The reader follows Arjun — a 25-year-old who just moved to Bengaluru — as he learns personal finance the hard way, one real-life situation at a time.

CHARACTERS

Arjun Sharma (protagonist)
- Age: 25. Junior analyst at a consulting firm, Bengaluru. Salary: 8.4 LPA (57,000 in-hand).
- From Indore. First job, first city, first time paying rent.
- Smart but financially clueless. Self-deprecating. Uses yaar, bhai, bro with Dev. More formal with Vikram.
- NEVER has all the answers. NEVER sounds like a finance textbook.
- Season 2 arc: Now2 years in, got a 30% raise to 10.9 LPA. Stakes are higher.

Rohit Mehra (the explainer)
- Age 28. Qualified CA, Big4. College friend.
- Patient, slightly nerdy. Always has a real rupee number ready.
- Uses analogies. Short clear sentences. Cricket analogies.
- NEVER gives vague answers. NEVER makes Arjun feel stupid.
- Signature move: pulls out phone calculator.

Vikram Nair (the mentor)
- Age 34. Senior manager at Arjun's firm. Ex-IIM.
- Reserved. Does not give unsolicited advice. When he speaks, it lands.
- Short sentences. Dry humour. Often asks a question instead of giving an answer.
- In Season 2: genuinely mentoring Arjun now.

Dev Malhotra (the cautionary mirror)
- Age 25. Arjun's flatmate. Works in sales at a startup.
- Fun, impulsive, always optimistic about money he does not have.
- NEVER learns from a mistake early on. Every bad financial decision belongs to Dev first.
- In Season 2: starting to feel consequences of earlier mistakes.

TONE RULES
1. One concept per post. Fully explained. No cliffhangers on the concept.
2. Present tense always.
3. Short paragraphs. Max 2 lines per paragraph.
4. Indian context only. Use rupee symbol not dollar. CIBIL not credit score. ITR not tax return. EPF not 401k. Nifty not S&P 500.
5. One Indian analogy per post. Cricket, kirana store, tiffin dabba, chai break etc.
6. Funny when light, real when stakes are high.
7. Never moralize. Lesson emerges from what happens.
8. Finance principle lands as one plain-language sentence at end of concept section.

POST SKELETON (mandatory every episode)
Line 1: Episode X | Arjun's Money Diaries
Line 2: HOOK — one sentence max12 words. Human moment not a definition. Never starts with Did you know or Today we learn.
Lines 3-5: SCENE SETUP — 3 short paragraphs 60-80 words total. Dialogue mandatory. Present tense. Max 1 supporting character.
Lines 6-9: CONCEPT THROUGH SCENE — 100-130 words. Finance lesson through dialogue or action never as lecture. One Indian analogy. At least one real rupee figure or percentage. Ends with concept as one plain-language principle sentence.
Lines 10-11: OUTCOME + TEASER — 30-40 words. What Arjun does. Then teaser for next episode.
Line 12: ENGAGEMENT QUESTION — specific question reader can answer from their own life. Never what do you think.
Line 13: #PersonalFinance #MoneyInIndia #FinanceForAll #ArjunSeries #LearnWithStories
Line 14: Follow for Episode [N+1] — dropping in2 days.

HARD CONSTRAINTS
- Total word count target 240-280 words. Absolute hard limit 300 words. Count every word. Cut ruthlessly if over 280. Never exceed 300 words.
- No bullet points inside the story.
- Max 1 rupee figure or number per paragraph.
- Always ends on question or teaser.
- One supporting character per episode maximum.
- Every jargon term explained immediately.
- Never write in past tense.
- Never use dollar sign instead of rupee symbol.
- Never reference401k IRA Roth S&P 500 or non-Indian instruments.
- Output PLAIN TEXT only. No markdown. No **bold**. No *italics*. No headers.

FY2025-26 TAX AND FINANCE FACTS
- New regime is default for salaried from FY2025-26
- Zero tax up to 12,00,000 under Section 87A (new regime)
- Standard deduction 75,000 under new regime
- Effective zero-tax limit 12,75,000
- New regime slabs: up to 3L nil, 3L-7L 5%, 7L-10L 10%, 10L-12L 15%, 12L-15L 20%, above 15L 30%
- 80C limit1,50,000 old regime only
- EPF employee contribution 12% of basic salary
- EPF interest rate 8.25% FY2024-25
- STCG on equity mutual funds 20%
- LTCG on equity mutual funds 12.5% exemption 1,25,000
- PPF interest rate 7.1% per annum
- Liquid mutual funds approximately 6.5-7.0% per annum indicative
- Inflation assumption 5% per annum
- F and O: 90%+ retail traders lose money per SEBI data
- LRS: RBI allows up to USD 2,50,000 per year overseas
- REITs listed on NSE/BSE minimum investment approximately 10,000-15,000
- Sovereign Gold Bond: RBI issued2.5% annual interest8-year tenure
- Never invent figures not listed above. Use (example only) if needed."""


TIER_BLOCK_BASIC = """

DIFFICULTY TIER: BASIC (Episodes 1-5)
- Reader is brand new to finance. Explain like they have never heard the concept.
- Arjun is confused and surprised — learning for the first time.
- Use extremely simple language and everyday analogies.
- Stakes are personal and immediate: rent, food, daily expenses.
- Zero jargon without instant plain-language explanation.
"""

TIER_BLOCK_INTERMEDIATE = """

DIFFICULTY TIER: INTERMEDIATE (Episodes 6-15)
- Arjun now understands budgeting, saving, credit basics. Can reference them without re-explaining.
- Introduce moderately complex ideas: SIPs, tax, insurance, credit scores.
- Arjun asks smarter questions. He has context from past episodes.
- Stakes grow: career decisions, long-term goals, protecting what he has built.
- Some jargon okay if explained naturally through dialogue.
"""

TIER_BLOCK_ADVANCED = """

DIFFICULTY TIER: ADVANCED (Episodes 16-44)
- Arjun is financially literate. He has SIPs, emergency fund, insurance, tax knowledge.
- He uses financial terms naturally in thought and conversation.
- New concepts are sophisticated: tax harvesting, ESOPs, factor investing, debt funds, PMS.
- He occasionally helps Dev — showing growth.
- Vikram treats him more as a peer.
- Stakes are strategic: wealth building, career moves, long-term portfolio design.
"""


def tier_for(episode_no: int, override: str | None = None) -> str:
    """Pick the right difficulty block. Override comes from the Sheet's
    Difficulty_Tier column when set, otherwise inferred from episode #."""
    if override:
        override = override.strip().lower()
        if override == "basic":
            return TIER_BLOCK_BASIC
        if override == "intermediate":
            return TIER_BLOCK_INTERMEDIATE
        if override == "advanced":
            return TIER_BLOCK_ADVANCED
    if episode_no <= 5:
        return TIER_BLOCK_BASIC
    if episode_no <= 15:
        return TIER_BLOCK_INTERMEDIATE
    return TIER_BLOCK_ADVANCED


def tier_label_for(episode_no: int, override: str | None = None) -> str:
    """Human-readable tier name for telemetry / Telegram drafts."""
    if override:
        norm = override.strip().capitalize()
        if norm in ("Basic", "Intermediate", "Advanced"):
            return norm
    if episode_no <= 5:
        return "Basic"
    if episode_no <= 15:
        return "Intermediate"
    return "Advanced"


def build_continuity_block(posted_episodes: list[dict]) -> str:
    """Build the STORY CONTINUITY block from the last 2 posted episodes.
    posted_episodes is a list of dicts in any order — we sort and slice."""
    if not posted_episodes:
        return ""
    filtered = [
        ep
        for ep in posted_episodes
        if ep.get("Episode_No") and (ep.get("post_text") or "").strip()
    ]
    if not filtered:
        return ""
    filtered.sort(key=lambda r: float(r["Episode_No"]), reverse=True)
    last2 = list(reversed(filtered[:2]))
    parts = []
    for ep in last2:
        parts.append(
            f"--- Episode {ep['Episode_No']} | {ep.get('Title', '')}"
            f"({ep.get('Concept', 'unknown')}) ---\n{ep['post_text']}"
        )
    snippets = "\n\n".join(parts)
    return (
        "\n\n=== STORY CONTINUITY (MANDATORY) ===\n"
        "The most recent posted episodes are below. You MUST:\n"
        "1. Continue directly from where the story left off. Reference specific events, decisions, or dialogue from these episodes.\n"
        "2. Maintain ALL established facts — apartment location, salary, relationships, past lessons.\n"
        "3. If the previous episode ended with a teaser about this episode, DELIVER on that teaser.\n"
        "4. Characters remember everything. No amnesia. No contradictions.\n"
        "5. The story is one continuous narrative — each episode is a chapter, not a standalone post.\n\n"
        f"{snippets}\n=== END STORY CONTINUITY ===\n"
    )


def build_story_state_block(story_rows: list[dict]) -> str:
    """Build CHARACTER STATE block from Story_State sheet rows."""
    lines = []
    for sr in story_rows:
        char = sr.get("Character")
        state = sr.get("Current_State")
        if char and state:
            lines.append(f"- {char}: {state}")
    if not lines:
        return ""
    return (
        "\n\n=== CHARACTER STATE (ground truth — do NOT contradict) ===\n"
        + "\n".join(lines)
        + "\n=== END CHARACTER STATE ===\n"
    )


def build_full_system_prompt(
    episode_no: int,
    difficulty_override: str | None,
    posted_episodes: list[dict],
    story_rows: list[dict],
) -> str:
    """Assemble the complete system prompt for one generation call."""
    return (
        SYSTEM_PROMPT
        + tier_for(episode_no, difficulty_override)
        + build_story_state_block(story_rows)
        + build_continuity_block(posted_episodes)
    )


def build_user_prompt(
    episode_no: int,
    title: str,
    hook_line: str,
    supporting_character: str,
    concept: str,
    difficulty_tier: str,
    concepts_used_so_far: str,
) -> str:
    """The per-episode user message. Same structure as before."""
    if not concepts_used_so_far or not concepts_used_so_far.strip():
        concepts_used_so_far = "None yet"
    return (
        f"Write Episode {episode_no} of the Arjun Money Diaries series.\n\n"
        "EPISODE METADATA (you MUST use all of this):\n"
        f"- Title: {title}\n"
        f"- Hook line (use this as your opening beat — capture this exact moment and energy): {hook_line}\n"
        f"- Supporting character for this episode (use ONLY this character): {supporting_character}\n"
        f"- Financial concept to teach: {concept}\n"
        f"- Difficulty tier: {difficulty_tier}\n\n"
        "CONCEPTS ALREADY COVERED (do NOT repeat as main lesson but you may briefly reference as established knowledge Arjun already has):\n"
        f"{concepts_used_so_far}\n\n"
        "RULES:\n"
        "1. Your hook MUST be inspired by the hook line above. Capture that specific moment.\n"
        "2. Use ONLY the supporting character listed. No other named characters.\n"
        "3. CRITICAL word count: target 240-280 words. Hard limit 300 words. Count every single word including hashtags. If over 280, cut before responding. Never exceed 300 words.\n"
        "4. First person as Arjun. Story-first. One core financial lesson woven naturally.\n"
        "5. End with a teaser that connects naturally to the next episode in the series.\n"
        "6. PLAIN TEXT ONLY. No markdown, no bold, no italics, no headers.\n"
        "7. Do NOT start the post with a quote or dialogue. Start with the Episode X | line.\n"
    )


# ---------------------------------------------------------------------
# Story-state updater prompt (used after a successful post)
# ---------------------------------------------------------------------
STORY_STATE_SYSTEM = (
    "You update a character state tracker for a serialised fiction series. "
    "Given the latest posted episode text, update each character state to "
    "reflect what happened. Keep each state to 2-3 sentences max. Only "
    "update characters who appeared or were meaningfully affected. Return "
    'ONLY a valid JSON array with format: [{"Character":"name",'
    '"Current_State":"updated state","Last_Updated_Episode":"number"}]. '
    "No extra text outside the JSON."
)


def build_story_state_user_prompt(
    episode_no: int, final_text: str, story_rows: list[dict]
) -> str:
    state_lines = []
    for sr in story_rows:
        if sr.get("Character") and sr.get("Current_State"):
            state_lines.append(f"- {sr['Character']}: {sr['Current_State']}")
    current_states = "\n".join(state_lines)
    return (
        f"Episode {episode_no} was just posted. Here is the text:\n\n"
        f"{final_text}\n\n"
        f"Current character states:\n{current_states}\n"
        "Update the states based on what happened in this episode. Only "
        "include characters whose state changed."
    )
