# Prompt Changelog

Version history for the Arjun's Money Diaries system prompt and user prompt.
Every change that affects generation quality is logged here with the reason and observed outcome.

Treat this file as the contract history between you and the LLM.
If a future change causes quality regression, this log tells you exactly what to revert.

---

## v1.0 — May 2026 (initial n8n build)

**What changed:** Initial system prompt written. Established core series bible.

**Key decisions:**
- Characters defined: Arjun, Rohit, Dev, Vikram with distinct personalities and roles
- POST SKELETON mandated: Episode line → Hook → Scene Setup → Concept → Outcome → Question → Hashtags → Teaser
- TONE RULES: present tense, short paragraphs, Indian context only, one analogy per post
- HARD CONSTRAINTS: 220-260 words, plain text only, no non-Indian instruments
- FY2025-26 tax facts injected as ground truth to prevent LLM hallucination of figures
- Model: Gemini Flash primary, Groq fallback

**Observed outcome:** Good voice consistency. Word count frequently exceeded 260. Gemini Flash occasionally drifted from character voices.

---

## v1.1 — May 2026 (migration to Claude)

**What changed:** Switched primary model from Gemini Flash to Claude Sonnet 4.5.

**Reason:** Claude significantly better at maintaining character voice, story continuity, and structural compliance across episodes. Gemini Flash produced acceptable but inconsistent results.

**Prompt changes:** None — same prompt, different model.

**Observed outcome:** Immediate improvement in character consistency and dialogue quality. Word count issue persisted — identified as prompt design problem, not model compliance.

---

## v1.2 — May 2026 (word count alignment)

**What changed:**
- System prompt hard limit changed from `220-260 words HARD LIMIT` to `target 240-280 words, absolute hard limit 300 words`
- User prompt Rule 3 changed from `220-260 words HARD LIMIT` to `target 240-280 words, hard limit 300 words`
- QC gate updated from binary 220-320 pass/fail to tiered system

**Reason:** Root cause analysis revealed the word count problem was a prompt design bug, not model non-compliance. The POST SKELETON sub-budgets (scene setup 60-80 words + concept 100-130 words + outcome 30-40 words + hashtags/teaser ~20 words) naturally produce 240-280 words. Telling Claude "220-260 hard limit" was asking it to violate its own skeleton — it followed the skeleton correctly and exceeded the stated limit. Aligning the limit to what the skeleton actually produces eliminates the conflict.

**QC gate tiers introduced:**
- Below 200: hard fail
- 200-219: alert + pass
- 220-239: warning + pass
- 240-300: ideal
- 301-319: warning + pass
- 320-339: alert + pass
- 340+: hard fail

**Observed outcome:** Expected reduction in word count QC failures. Human review gate catches edge cases.

---

## v1.3 — May 2026 (temperature tuning)

**What changed:** Added `temperature: 0.85` explicitly to Claude API call. Previously unset (defaulting to 1.0).

**Reason:** Claude was running at temperature 1.0 (default) while Groq fallback was explicitly set to 0.85. Primary model was running hotter than fallback — backwards. Higher temperature increases variance and reduces constraint adherence (word count, structure).

**Observed outcome:** Expected improvement in structural consistency. More predictable word counts. Voice remains creative at 0.85 — not robotic.

---

## v1.4 — May 2026 (QC structural checks added)

**What changed:** Added two new checks to the QC gate:
- `has_correct_opener`: post must start with `Episode N |`
- `has_rs_prefix`: fail if `Rs.` or `INR` used instead of `₹`

**Reason:** Claude occasionally started posts with dialogue or a quote despite the user prompt instruction. No enforcement existed in QC — these slipped through to approval. The Rs./INR check catches currency formatting issues not caught by the existing dollar sign check.

**Observed outcome:** Structural violations now caught at QC gate before reaching Telegram approval. Reduces manual REGENERATE calls.

---

## Prompt engineering principles learned

1. **Skeleton sub-budgets are authoritative.** If the skeleton says "100-130 words for concept section", the total will be ~270 words. The hard limit must match the skeleton math, not fight it.

2. **One constraint, stated once.** Repeating the word count rule in both system prompt and user prompt does not reinforce it — it creates ambiguity. State it once, clearly, in the right place.

3. **Temperature matters more than you think.** At temperature 1.0, Claude takes more creative risks with structure. At 0.85, it follows rules more reliably while remaining creative in content. For constrained creative writing, 0.8-0.9 is the right range.

4. **The QC gate is the real contract.** Whatever the QC gate accepts is what the model learns to target (implicitly, through prompt design reasoning). If QC accepts 320 words, the effective limit is 320 regardless of what the prompt says. Keep QC thresholds tighter than prompt instructions.

5. **Story state injection is load-bearing.** The CHARACTER STATE and STORY CONTINUITY blocks are not optional context — they are the primary mechanism for maintaining a coherent serialised narrative. Without them, every episode reads like a standalone post.

6. **FY facts prevent hallucination.** Without the FY2025-26 facts block, Claude invents plausible-sounding but incorrect Indian tax figures. The facts block acts as a retrieval anchor — Claude quotes from it rather than generating from training data.

---

## How to make a prompt change safely

1. Edit `scripts/prompts.py`
2. Run a manual `Generate Episode` workflow dispatch to test
3. Review the Telegram draft carefully — does it still sound like Arjun?
4. If quality is acceptable: commit, add an entry to this changelog
5. If quality regressed: revert the change, document what failed here

Never change the system prompt and the QC gate simultaneously — you won't know which change caused a quality shift.
