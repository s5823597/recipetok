import gradio as gr
import yt_dlp
import whisper
import json
import os
import re
import subprocess
import base64
from groq import Groq
from dotenv import load_dotenv

load_dotenv("/home/s5823597/Desktop/SEM/flavourflow/.env")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")

# ── pipeline steps ────────────────────────────────────────────────────────────

def fetch_metadata(url):
    with yt_dlp.YoutubeDL({"quiet": True}) as ydl:
        return ydl.extract_info(url, download=False)


def download_video(url):
    os.makedirs("outputs", exist_ok=True)
    opts = {
        "writesubtitles": True,
        "subtitleslangs": ["all"],
        "writeautomaticsub": True,
        "outtmpl": "outputs/%(id)s.%(ext)s",
        "quiet": True,
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        ydl.download([url])
    video_id = url.split("/")[-1].split("?")[0]
    video_file = subtitle_file = None
    for fname in os.listdir("outputs"):
        if video_id in fname and fname.endswith(".mp4"):
            video_file = f"outputs/{fname}"
        if video_id in fname and (".vtt" in fname or ".srt" in fname):
            subtitle_file = f"outputs/{fname}"
    return video_file, subtitle_file


def extract_speech(subtitle_file, video_file):
    text = ""
    if subtitle_file:
        with open(subtitle_file, "r") as f:
            for line in f.readlines():
                line = line.strip()
                if line and not line.startswith("WEBVTT") and "-->" not in line and not line.isdigit():
                    text += line + " "
        return text.strip(), "TikTok subtitles"
    elif video_file:
        model = whisper.load_model("base")
        text = model.transcribe(video_file)["text"]
        return text.strip(), "Whisper ASR (base)"
    return "", "none"


def extract_frames_and_analyse(video_file):
    if not video_file or not GROQ_API_KEY:
        return ""
    frames_dir = f"outputs/frames_{os.path.basename(video_file).split('.')[0]}"
    os.makedirs(frames_dir, exist_ok=True)
    subprocess.run(
        ["ffmpeg", "-i", video_file, "-vf", "fps=1/3", "-vframes", "5",
         f"{frames_dir}/frame_%02d.jpg", "-y", "-loglevel", "error"]
    )
    frames = sorted([f"{frames_dir}/{f}" for f in os.listdir(frames_dir) if f.endswith(".jpg")])
    if not frames:
        return ""
    content = []
    for fp in frames:
        with open(fp, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        content.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}})
    content.append({
        "type": "text",
        "text": "These are frames from a TikTok cooking video. Describe what ingredients, cooking techniques, and dishes you can see. Be specific and concise."
    })
    client = Groq(api_key=GROQ_API_KEY)
    resp = client.chat.completions.create(
        model="meta-llama/llama-4-scout-17b-16e-instruct",
        messages=[{"role": "user", "content": content}],
        max_tokens=512,
    )
    return resp.choices[0].message.content


def extract_recipe(meta, speech_text, visual_desc):
    client = Groq(api_key=GROQ_API_KEY)
    context = f"""Video Title: {meta.get('title', '')}
Video Description: {meta.get('description', '')}
Speech Transcript: {speech_text}
Visual Description: {visual_desc}"""

    prompt = f"""You are a recipe extraction AI. Analyse the following TikTok video data and:

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
   - halal_status (halal/not_halal/uncertain with reason)

IMPORTANT: The video may be in any language. Translate ALL field values into English.

Video Data:
{context}

Respond ONLY in valid JSON."""

    resp = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": "You are a recipe extraction assistant. Always respond in valid JSON in English only."},
            {"role": "user", "content": prompt},
        ],
        max_tokens=1024,
        temperature=0.1,
    )
    raw = resp.choices[0].message.content
    cleaned = re.sub(r"```(?:json)?\s*", "", raw).strip()
    try:
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        recipe = json.loads(match.group()) if match else {}
        if "recipe" in recipe and isinstance(recipe["recipe"], dict):
            recipe = recipe["recipe"]
    except Exception:
        recipe = {}
    return recipe, raw


# ── rendering helpers ─────────────────────────────────────────────────────────

def _status(steps_done, current_msg, error=False):
    steps = [
        "Fetch metadata",
        "Download video",
        "Extract speech",
        "Vision analysis",
        "Extract recipe",
    ]
    rows = ""
    for i, step in enumerate(steps):
        if i < steps_done:
            icon = "✓"
            color = "#00cc88"
        elif i == steps_done and not error:
            icon = "▶"
            color = "#4a9eff"
        else:
            icon = "○"
            color = "#555"
        rows += f'<div style="color:{color};margin:4px 0;font-size:0.9rem;">{icon} {step}</div>'

    if error:
        msg_color = "#ff5555"
        msg_icon = "✗"
    elif steps_done == len(steps):
        msg_color = "#00cc88"
        msg_icon = "✓"
    else:
        msg_color = "#4a9eff"
        msg_icon = "⟳"

    return f"""
    <div style="background:#111;border:1px solid #222;border-radius:10px;padding:16px;font-family:monospace;">
      <div style="font-size:0.75rem;color:#666;margin-bottom:10px;letter-spacing:1px;">PIPELINE STATUS</div>
      {rows}
      <div style="margin-top:12px;padding-top:10px;border-top:1px solid #222;color:{msg_color};font-size:0.85rem;">{msg_icon} {current_msg}</div>
    </div>"""


def _render_recipe(recipe):
    if not recipe:
        return ""

    halal_raw = recipe.get("halal_status", "uncertain")
    halal_str = str(halal_raw).lower() if isinstance(halal_raw, str) else json.dumps(halal_raw).lower()
    if "not_halal" in halal_str or "not halal" in halal_str:
        halal_color, halal_label = "#ff4444", "Not Halal"
    elif "uncertain" in halal_str:
        halal_color, halal_label = "#ff9900", "Uncertain"
    else:
        halal_color, halal_label = "#00cc88", "Halal"

    ingredients = recipe.get("ingredients", [])
    if ingredients and isinstance(ingredients[0], dict):
        ingr_html = "".join(
            f'<li style="padding:4px 0;">{i.get("quantity","")}&nbsp;{i.get("item","")}</li>'
            for i in ingredients
        )
    else:
        ingr_html = "".join(f'<li style="padding:4px 0;">{i}</li>' for i in ingredients)

    steps = recipe.get("steps", [])
    steps_html = "".join(f'<li style="padding:6px 0;line-height:1.5;">{s}</li>' for s in steps)

    tag = lambda text, bg="#2a2a2a": f'<span style="background:{bg};color:#fff;padding:4px 14px;border-radius:20px;font-size:0.82rem;white-space:nowrap;">{text}</span>'

    return f"""
    <div style="font-family:'Segoe UI',sans-serif;color:#e0e0e0;max-width:860px;">
      <h1 style="font-size:2rem;margin:0 0 0.6rem 0;color:#fff;">{recipe.get('dish_name','Unknown Dish')}</h1>
      <div style="display:flex;gap:0.5rem;flex-wrap:wrap;margin-bottom:1.2rem;">
        {tag(recipe.get('cuisine_type','—'))}
        {tag(recipe.get('difficulty','—').capitalize())}
        {tag(halal_label, halal_color)}
      </div>
      <div style="display:flex;gap:2.5rem;margin-bottom:1.8rem;color:#888;font-size:0.9rem;">
        <span>⏱ Prep: <b style="color:#ccc;">{recipe.get('prep_time','—')}</b></span>
        <span>🍳 Cook: <b style="color:#ccc;">{recipe.get('cook_time','—')}</b></span>
        <span>🍽 Serves: <b style="color:#ccc;">{recipe.get('servings','—')}</b></span>
      </div>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:2rem;">
        <div>
          <h3 style="color:#fff;border-bottom:1px solid #333;padding-bottom:0.5rem;margin-top:0;">Ingredients</h3>
          <ul style="margin:0;padding-left:1.2rem;color:#ccc;">{ingr_html}</ul>
        </div>
        <div>
          <h3 style="color:#fff;border-bottom:1px solid #333;padding-bottom:0.5rem;margin-top:0;">Method</h3>
          <ol style="margin:0;padding-left:1.2rem;color:#ccc;">{steps_html}</ol>
        </div>
      </div>
    </div>"""


def _meta_display(meta, speech_source):
    return (
        f"Title:    {meta.get('title','')}\n"
        f"Uploader: {meta.get('uploader','')}\n"
        f"Duration: {meta.get('duration','')}s\n"
        f"Views:    {meta.get('view_count','')}\n"
        f"Speech:   {speech_source}"
    )


# ── main generator ────────────────────────────────────────────────────────────

def run_pipeline(url):
    empty = ("", "", "", "")

    if not url or not url.strip():
        yield _status(0, "Enter a TikTok URL above", error=True), *empty
        return

    # Step 0 → fetch metadata
    yield _status(0, "Fetching video metadata…"), *empty
    try:
        meta = fetch_metadata(url.strip())
    except Exception as e:
        yield _status(0, f"Metadata error: {e}", error=True), *empty
        return

    # Step 1 → download
    yield _status(1, "Downloading video and subtitles…"), *empty
    try:
        video_file, subtitle_file = download_video(url.strip())
    except Exception as e:
        yield _status(1, f"Download error: {e}", error=True), *empty
        return

    # Step 2 → speech
    yield _status(2, "Extracting speech text…"), *empty
    speech_text, speech_source = extract_speech(subtitle_file, video_file)
    meta_text = _meta_display(meta, speech_source)

    # Step 3 → vision
    yield _status(3, "Analysing frames  (LLaMA 4 Scout Vision)…"), meta_text, "", speech_text, ""
    try:
        visual_desc = extract_frames_and_analyse(video_file) if video_file else ""
    except Exception as e:
        visual_desc = f"[Vision skipped: {e}]"

    # Step 4 → recipe
    yield _status(4, "Extracting recipe  (LLaMA 3.3 70B)…"), meta_text, "", speech_text, visual_desc
    try:
        recipe, raw_json = extract_recipe(meta, speech_text, visual_desc)
    except Exception as e:
        yield _status(4, f"Extraction error: {e}", error=True), meta_text, "", speech_text, visual_desc
        return

    recipe_html = _render_recipe(recipe)
    json_str = json.dumps(recipe, indent=2, ensure_ascii=False)

    yield (
        _status(5, f"Done — speech via {speech_source}"),
        meta_text,
        recipe_html,
        speech_text,
        visual_desc,
    )


# ── UI ────────────────────────────────────────────────────────────────────────

CSS = """
body, .gradio-container { background:#0d0d0d !important; color:#e0e0e0 !important; }
.gr-button-primary { background:#4a9eff !important; border:none !important; font-weight:600 !important; }
.gr-button-primary:hover { background:#2a7edf !important; }
footer { display:none !important; }
.tab-nav button { background:#1a1a1a !important; color:#888 !important; border:none !important; }
.tab-nav button.selected { color:#fff !important; border-bottom:2px solid #4a9eff !important; }
"""

HEADER = """
<div style="text-align:center;padding:2rem 0 1.5rem;font-family:'Segoe UI',sans-serif;">
  <h1 style="font-size:2.8rem;font-weight:700;color:#fff;margin:0;letter-spacing:-1px;">
    🍳 FlavourFlow
  </h1>
  <p style="color:#888;margin:0.5rem 0 0;font-size:1rem;">
    Paste a TikTok cooking video URL — get a structured recipe using Whisper + Vision LLM + LLaMA 3.3
  </p>
</div>"""

MODEL_BADGES = """
<div style="display:flex;gap:0.6rem;justify-content:center;flex-wrap:wrap;margin-bottom:1.5rem;font-family:monospace;font-size:0.78rem;">
  <span style="background:#1a1a1a;border:1px solid #333;color:#4a9eff;padding:4px 12px;border-radius:20px;">Whisper base</span>
  <span style="background:#1a1a1a;border:1px solid #333;color:#a78bfa;padding:4px 12px;border-radius:20px;">LLaMA 4 Scout Vision</span>
  <span style="background:#1a1a1a;border:1px solid #333;color:#34d399;padding:4px 12px;border-radius:20px;">LLaMA 3.3 70B</span>
  <span style="background:#1a1a1a;border:1px solid #333;color:#fb923c;padding:4px 12px;border-radius:20px;">yt-dlp</span>
  <span style="background:#1a1a1a;border:1px solid #333;color:#fb923c;padding:4px 12px;border-radius:20px;">ffmpeg</span>
</div>"""

with gr.Blocks(title="FlavourFlow") as demo:
    gr.HTML(HEADER)
    gr.HTML(MODEL_BADGES)

    with gr.Row():
        url_box = gr.Textbox(
            placeholder="https://www.tiktok.com/@.../video/...",
            label="TikTok URL",
            scale=5,
            container=False,
        )
        run_btn = gr.Button("Analyse Recipe", variant="primary", scale=1)

    with gr.Row():
        with gr.Column(scale=1):
            status_box = gr.HTML(
                value=_status(0, "Waiting for URL…"),
                label="Pipeline",
            )
            meta_box = gr.Textbox(
                label="Video Metadata",
                lines=5,
                interactive=False,
            )

        with gr.Column(scale=2):
            with gr.Tabs():
                with gr.Tab("Recipe Card"):
                    recipe_box = gr.HTML()
                with gr.Tab("Speech Transcript"):
                    transcript_box = gr.Textbox(
                        lines=12,
                        interactive=False,
                        label="Extracted speech",
                    )
                with gr.Tab("Visual Description"):
                    visual_box = gr.Textbox(
                        lines=12,
                        interactive=False,
                        label="LLaMA 4 Scout frame analysis",
                    )

    run_btn.click(
        fn=run_pipeline,
        inputs=[url_box],
        outputs=[status_box, meta_box, recipe_box, transcript_box, visual_box],
    )
    url_box.submit(
        fn=run_pipeline,
        inputs=[url_box],
        outputs=[status_box, meta_box, recipe_box, transcript_box, visual_box],
    )

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860, share=False, css=CSS)
