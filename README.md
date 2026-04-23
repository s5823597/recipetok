# RecipeTok AI

## Overview
RecipeTok AI is a multimodal AI pipeline that extracts structured recipes from TikTok cooking videos. It combines speech recognition, video analysis, and large language models to transform unstructured cooking content into organised, actionable recipes.

## Features
- Extracts video metadata (title, description, uploader) from TikTok URLs
- Downloads videos and subtitles automatically
- Extracts speech text from subtitles (Whisper fallback coming soon)
- Uses Qwen2.5 LLM to classify cooking videos and structure recipes
- Outputs structured JSON with dish name, ingredients, steps, cuisine type, difficulty, and halal status

## Pipeline

1. User pastes TikTok URL
2. Parse video ID and fetch metadata via yt-dlp
3. Download video and check for subtitles
4. Extract speech text from subtitles (or Whisper ASR fallback)
5. Send metadata + speech text to Qwen2.5 LLM
6. LLM classifies video and extracts structured recipe as JSON
7. Display formatted recipe output

## Tech Stack
- **yt-dlp** — TikTok video metadata and download
- **OpenAI Whisper** — speech-to-text fallback (coming soon)
- **Qwen2.5-1.5B-Instruct** — local LLM for recipe structuring
- **Marimo** — interactive notebook environment
- **Python 3.11**

## Supported Languages (planned)
- English
- Arabic
- Chinese
- Malay

## Upcoming Features
- Whisper ASR fallback for videos without subtitles
- Vision analysis (VLM frame extraction)
- Multi-language translation
- Halal status detection
- Web UI (Gradio/Streamlit)

## Project Structure
```
Recipetok.py    → main marimo notebook with full pipeline
src/            → source code modules
prompts/        → LLM prompt templates and logs
outputs/        → downloaded videos and extracted data
tests/          → test scripts and evaluation
```

## Quick Start
```bash
cd recipetok
uv venv --python python3.11
source .venv/bin/activate
uv pip install marimo yt-dlp openai-whisper requests transformers accelerate
marimo edit Recipetok.py
```
