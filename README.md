# FlavourFlow

A multimodal AI pipeline that extracts structured recipes from TikTok, Instagram Reels, and YouTube Shorts cooking videos. Paste a URL — get a full recipe card with ingredients, steps, allergens, dietary labels, and a UK price estimate. Compare two recipes head-to-head in Battle Mode.

## Run Locally

```bash
git clone git@github.com:s5823597/flavourflow.git
cd flavourflow
pip install streamlit yt-dlp openai-whisper groq python-dotenv
streamlit run streamlit_app.py
```

Then open `http://localhost:8501`.

Create a `.env` file in the project root:

1. Open a text editor (Notepad on Windows, TextEdit on Mac, gedit on Linux)
2. Type exactly this:
```
GROQ_API_KEY=your_key_here
```
3. Save the file as `.env` (no other extension) inside the `flavourflow` folder — same folder as `streamlit_app.py`

Get a free key at https://console.groq.com

The API key is required because FlavourFlow uses two AI models hosted on Groq's servers — LLaMA 4 Scout for visual frame analysis and LLaMA 3.3 70B for recipe extraction. Every request is processed on Groq's infrastructure, and the key is how Groq authenticates your account. Groq has a generous free tier, so running the app for demo purposes costs nothing.

---

## Pipeline

```
Video URL (TikTok / Instagram Reels / YouTube Shorts)
    │
    ├─ yt-dlp ──────────► video + subtitles download
    │
    ├─ subtitles? ──Yes──► extract text directly
    │       └──No────────► Whisper ASR (small model, configurable)
    │
    ├─ ffmpeg ───────────► N frames evenly sampled (5–15, configurable)
    │
    ├─ LLaMA 4 Scout ────► visual description of ingredients & techniques
    │   (Groq Vision API)
    │
    └─ LLaMA 3.3 70B ────► structured JSON recipe
        (Groq API)              dish_name, cuisine_type, difficulty,
                                prep_time, cook_time, servings,
                                ingredients (with confidence scores),
                                steps, allergens, dietary,
                                price_estimate_gbp
```

---

## Features

### Recipe Extractor
- Supports **TikTok**, **Instagram Reels**, and **YouTube Shorts**
- Extracts recipes in any language, outputs in **English**
- Detects **allergens**: Gluten, Dairy, Eggs, Nuts, Peanuts, Soy, Shellfish, Fish, Sesame
- **Dietary labels**: Vegetarian, Vegan, Gluten-Free, Dairy-Free
- **Ingredient confidence scores** — ⚠ CHECK / ⚠ VERIFY badges on uncertain ingredients
- **UK supermarket price estimate** (LLM-estimated range in GBP)
- **Ingredient type cards** — colour-coded by type (Protein, Veggie, Spice, Dairy, Grain, Sauce)
- **Shopping list download** — formatted by ingredient category as `.txt`
- Cinematic hero image from extracted video frames
- Recipe library with thumbnails saved to SQLite database

### Battle Mode ⚔️
- Pick any two saved recipes and compare them side-by-side
- Or paste new URLs to extract and compare on the fly
- Shows ingredients, cooking method, price, and allergens for both recipes simultaneously

### Settings
- **Whisper model**: `base` (fastest) / `small` (default) / `medium` (most accurate)
- **Frames to sample**: 5–15 frames (more frames = richer visual analysis)

---

## Tech Stack

| Tool | Role |
|------|------|
| **yt-dlp** | Multi-platform video and subtitle download |
| **OpenAI Whisper** | Speech-to-text fallback (small model by default) |
| **ffmpeg** | Frame extraction |
| **LLaMA 4 Scout 17B** (Groq) | Visual frame analysis |
| **LLaMA 3.3 70B** (Groq) | Recipe extraction and structuring |
| **Streamlit** | Web interface |
| **SQLite** | Recipe history database |
| **Python 3.9+** | Runtime |

---

## Project Structure

```
streamlit_app.py       → main Streamlit web app (Recipe Extractor + Battle Mode)
app.py                 → original Gradio version (reference only)
__marimo__/            → Marimo notebook prototypes
docs/                  → prompt documentation
outputs/               → downloaded videos, frames, database (gitignored)
.env                   → GROQ_API_KEY (gitignored)
```

---

## Supported Platforms & Languages

**Platforms tested:** TikTok · Instagram Reels · YouTube Shorts

**Languages tested:** English · Malay · Thai · Arabic · Chinese (Mandarin)

---

## Known Limitations

- Whisper struggles with loud background music (use `medium` model for better accuracy)
- Allergen and dietary labels are AI-inferred — not verified against actual ingredient sourcing
- Frame sampling may miss ingredients shown very briefly in the video
- Cannot download private or region-locked videos
- UK price estimates are LLM approximations, not live supermarket data
