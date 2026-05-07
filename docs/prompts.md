# FlavourFlow — Prompt Documentation

This document records all prompts, models, and parameters used in the FlavourFlow pipeline.
Required for academic disclosure under the assignment's generative AI usage policy.

---

## Pipeline Overview

```
TikTok URL
    → yt-dlp  (video download + subtitle extraction)
    → Whisper base  (fallback ASR if no subtitles)
    → ffmpeg  (extract 5 frames at fps=1/3)
    → [PROMPT 1] LLaMA 4 Scout 17B  (visual frame analysis)
    → [PROMPT 2] LLaMA 3.3 70B  (recipe extraction)
    → Recipe Card
```

---

## Prompt 1 — Visual Frame Analysis

**Purpose:** Identify visible ingredients, cooking techniques, and dishes from extracted video frames.
This visual context supplements the audio transcript, especially for ingredients shown but not mentioned verbally.

**Model:** `meta-llama/llama-4-scout-17b-16e-instruct` (via Groq API)
**Input type:** Multimodal — 5 JPEG frames (base64-encoded) + text instruction
**Max tokens:** 512
**Temperature:** default (Groq default ≈ 1.0)

**Frame extraction settings:**
- Tool: `ffmpeg`
- Rate: `fps=1/3` (one frame every 3 seconds)
- Count: 5 frames maximum

**User prompt (text portion):**
```
These are frames from a TikTok cooking video.
Describe what ingredients, cooking techniques, and dishes you can see.
Be specific and concise.
```

**Design decisions:**
- "Be specific and concise" prevents verbose descriptions that would bloat the recipe extraction context window.
- 5 frames is a trade-off: enough to cover a 15-second video, but misses briefly-shown ingredients.
- Frames are sampled evenly rather than from the beginning to avoid capturing intro/title cards.

**Known limitations:**
- Only 5 frames are sampled — ingredients shown briefly between sampled points are missed.
- Model may hallucinate ingredients if the frame quality is low.

---

## Prompt 2 — Recipe Extraction

**Purpose:** Synthesise video title, description, speech transcript, and visual description into a
structured JSON recipe. Handles multilingual input by enforcing English output.

**Model:** `llama-3.3-70b-versatile` (via Groq API)
**Input type:** Text only
**Max tokens:** 1024
**Temperature:** 0.1 (near-deterministic — chosen to reduce hallucination of quantities/steps)

### System prompt
```
You are a recipe extraction assistant. Always respond in valid JSON in English only.
```

### User prompt
```
You are a recipe extraction AI. Analyse the following TikTok video data and:

1. Determine if this is a cooking video (YES/NO)
2. If YES, extract a structured recipe in JSON format with these fields:
   - dish_name
   - cuisine_type
   - difficulty (easy/medium/hard)
   - prep_time
   - cook_time
   - servings
   - ingredients (list with quantity and item)
   - steps (numbered list)
   - allergens (list from: Gluten, Dairy, Eggs, Nuts, Peanuts, Soy, Shellfish, Fish, Sesame — only if confident)
   - dietary (list from: Vegetarian, Vegan, Gluten-Free, Dairy-Free, Halal, Contains Nuts — only if confident)

IMPORTANT: The video may be in any language. Translate ALL field values into English.

Video Data:
Video Title: {meta.get('title', '')}
Video Description: {meta.get('description', '')}
Speech Transcript: {speech_text}
Visual Description: {visual_desc}

Respond ONLY in valid JSON.
```

**Design decisions:**
- **Two-step instruction (cooking? → extract):** Prevents hallucinating a recipe from non-cooking videos.
- **"IMPORTANT: Translate ALL field values":** Earlier versions without this produced mixed-language output (e.g., Malay ingredient names). This instruction was added after testing on a Malay-language video.
- **temperature=0.1:** Low temperature is intentional — recipe extraction requires consistent, structured output. Higher values produced inconsistent JSON formatting.
- **JSON-only response:** Reduces post-processing complexity. A regex cleanup (`re.search(r"\{.*\}", ...)`) is applied as a fallback in case the model wraps the JSON in markdown code fences.
- **max_tokens=1024:** Sufficient for most recipes. Complex dishes with 15+ steps may be truncated.

**Known limitations:**
- Prep and cook times are estimated by the model from its training data — not measured from the video. Times can be inaccurate.
- Ingredient quantities are hallucinated when the creator never states them explicitly.
- If the JSON is malformed, the fallback returns an empty dict `{}` and the recipe card will be blank.
- **Allergen detection is inferred, not verified.** The model deduces allergens from ingredient names using training knowledge (e.g., "soy sauce" → Soy). It cannot detect hidden allergens, cross-contamination, or trace amounts. These labels should not be relied upon for clinical dietary decisions.
- Dietary labels (e.g., Halal, Vegan) are estimated from visible ingredients and may be incorrect if unlisted additives or preparation methods affect the classification.

---

## Prompt 3 — Speech Extraction (no LLM involved)

Speech is extracted deterministically, not via an LLM prompt:
- **Primary:** TikTok's embedded `.vtt` subtitle file (downloaded via `yt-dlp`).
  Subtitle lines are filtered to remove WEBVTT headers, timestamps (`-->`), and digit-only lines.
- **Fallback:** OpenAI Whisper `base` model (local, CPU inference) if no subtitle file is found.

No prompt is written for this step — Whisper takes raw audio as input.

**Whisper model:** `base` (74M parameters)
**Known limitation:** Struggles with loud background music (documented in the Arabic video test case where method steps were missed).

---

## AI Tools Disclosure Summary

| Tool | Role | Provider |
|------|------|----------|
| `yt-dlp` | Video download + subtitle extraction | Open source |
| `ffmpeg` | Frame extraction | Open source |
| OpenAI Whisper `base` | Fallback speech-to-text | Open source (local) |
| LLaMA 4 Scout 17B (Groq) | Multimodal visual frame analysis | Meta / Groq |
| LLaMA 3.3 70B (Groq) | Recipe extraction from text context | Meta / Groq |
| Claude Code (Anthropic) | Development assistance (coding, debugging) | Anthropic |

---

*Last updated: 2026-05-06*
