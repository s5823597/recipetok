# FlavourFlow

A multimodal AI pipeline that extracts structured recipes from TikTok cooking videos. Paste a URL — get a formatted recipe card with ingredients, steps, allergens, and dietary labels.

## Run Locally

```bash
git clone git@github.com:s5823597/flavourflow.git
cd flavourflow
pip install streamlit yt-dlp openai-whisper groq python-dotenv
streamlit run streamlit_app.py
```

Then open `http://localhost:8501`.

## Pipeline

```
TikTok URL
    │
    ├─ yt-dlp ──────────► video + subtitles download
    │
    ├─ subtitles? ──Yes──► extract text directly
    │       └──No────────► Whisper base (ASR fallback)
    │
    ├─ ffmpeg ───────────► 5 frames at fps=1/3
    │
    ├─ LLaMA 4 Scout ────► visual description of ingredients/techniques
    │   (Groq Vision API)
    │
    └─ LLaMA 3.3 70B ────► structured JSON recipe
        (Groq API)              dish_name, cuisine_type, difficulty,
                                prep_time, cook_time, servings,
                                ingredients, steps, allergens, dietary
```

## Tech Stack

| Tool | Role |
|------|------|
| **yt-dlp** | TikTok video and subtitle download |
| **OpenAI Whisper** (base) | Speech-to-text fallback |
| **ffmpeg** | Frame extraction |
| **LLaMA 4 Scout 17B** (Groq) | Visual frame analysis |
| **LLaMA 3.3 70B** (Groq) | Recipe extraction and structuring |
| **Streamlit** | Web interface |
| **Python 3.9+** | Runtime |

## Features

- Extracts recipes from TikTok videos in any language, outputs in English
- Detects allergens (Gluten, Dairy, Eggs, Nuts, Soy, Shellfish, Fish, Sesame)
- Dietary labels (Vegetarian, Vegan, Halal, Gluten-Free, Dairy-Free)
- Shopping list copy button
- Recipe library grouped by cuisine with thumbnails
- Live pipeline status during extraction

## Project Structure

```
streamlit_app.py    → main Streamlit web interface
app.py              → original Gradio version (reference)
docs/prompts.md     → full prompt documentation
outputs/            → downloaded videos, frames, history (gitignored)
.env                → GROQ_API_KEY (gitignored)
```

## Environment Variables

Create a `.env` file:
```
GROQ_API_KEY=your_key_here
```

Get a free key at https://console.groq.com

## Supported Languages

Tested on: English, Malay, Thai, Arabic, Chinese (Mandarin)

## Known Limitations

- Whisper base struggles with loud background music
- Allergen labels are AI-inferred — not verified against ingredient sourcing
- Only 5 frames sampled — ingredients shown briefly may be missed
- Cannot download private or region-locked TikTok videos
