import gradio as gr
import yt_dlp
import whisper
import json
import os
import re
import subprocess
import base64
import datetime
from groq import Groq
from dotenv import load_dotenv

load_dotenv("/home/s5823597/Desktop/SEM/flavourflow/.env")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
HISTORY_FILE = "outputs/history.json"


# ── history ───────────────────────────────────────────────────────────────────

def load_history():
    if not os.path.exists(HISTORY_FILE):
        return []
    try:
        with open(HISTORY_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return []


def save_history(url, recipe, frames_dir):
    os.makedirs("outputs", exist_ok=True)
    history = load_history()
    history = [h for h in history if h.get("url") != url]
    history.insert(0, {
        "url": url,
        "dish_name": recipe.get("dish_name", "Unknown"),
        "cuisine_type": recipe.get("cuisine_type", ""),
        "frames_dir": os.path.abspath(frames_dir) if frames_dir else "",
        "timestamp": datetime.datetime.now().strftime("%d %b %Y, %H:%M"),
        "recipe": recipe,
    })
    history = history[:10]
    with open(HISTORY_FILE, "w") as f:
        json.dump(history, f, indent=2, ensure_ascii=False)
    return history


def _get_history_choices():
    history = load_history()
    return [
        f"{h['dish_name']}  ·  {h.get('cuisine_type','') or 'Unknown'}  ·  {h['timestamp']}"
        for h in history if h.get("recipe")
    ]


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
        return "", None
    frames_dir = f"outputs/frames_{os.path.basename(video_file).split('.')[0]}"
    os.makedirs(frames_dir, exist_ok=True)
    subprocess.run(
        ["ffmpeg", "-i", video_file, "-vf", "fps=1/3", "-vframes", "5",
         f"{frames_dir}/frame_%02d.jpg", "-y", "-loglevel", "error"]
    )
    frames = sorted([f"{frames_dir}/{f}" for f in os.listdir(frames_dir) if f.endswith(".jpg")])
    if not frames:
        return "", None
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
    return resp.choices[0].message.content, frames_dir


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

def _get_frame_b64(frames_dir):
    if not frames_dir or not os.path.exists(frames_dir):
        return None
    frames = sorted([f for f in os.listdir(frames_dir) if f.endswith(".jpg")])
    if not frames:
        return None
    mid = frames[len(frames) // 2]
    with open(f"{frames_dir}/{mid}", "rb") as f:
        return base64.b64encode(f.read()).decode()


def _get_all_frames_b64(frames_dir):
    if not frames_dir or not os.path.exists(frames_dir):
        return []
    frames = sorted([f for f in os.listdir(frames_dir) if f.endswith(".jpg")])
    result = []
    for fname in frames:
        with open(f"{frames_dir}/{fname}", "rb") as f:
            result.append(base64.b64encode(f.read()).decode())
    return result


def _status(steps_done, current_msg, error=False):
    steps = ["Fetch metadata", "Download video", "Extract speech", "Vision analysis", "Extract recipe"]
    rows = ""
    for i, step in enumerate(steps):
        if i < steps_done:
            icon, color = "✓", "#4ade80"
        elif i == steps_done and not error:
            icon, color = "▶", "#fb923c"
        else:
            icon, color = "○", "#444"
        rows += f'<div style="color:{color};margin:7px 0;font-size:1.05rem;font-weight:500;">{icon} {step}</div>'

    msg_color = "#ff5555" if error else ("#4ade80" if steps_done == len(steps) else "#fb923c")
    msg_icon = "✗" if error else ("✓" if steps_done == len(steps) else "⟳")

    return f"""
    <div style="background:#1a0f05;border:1px solid #3a2010;border-radius:14px;padding:20px;font-family:monospace;">
      <div style="font-size:0.8rem;color:#a16207;margin-bottom:14px;letter-spacing:2px;">PIPELINE STATUS</div>
      {rows}
      <div style="margin-top:14px;padding-top:12px;border-top:1px solid #2a1a08;color:{msg_color};font-size:1rem;">{msg_icon} {current_msg}</div>
    </div>"""


def _render_recipe(recipe, frame_b64=None, all_frames=None):
    if not recipe:
        return ""

    all_frames = all_frames or []
    difficulty = recipe.get('difficulty', '—')
    diff_colors = {"easy": "#4ade80", "medium": "#fb923c", "hard": "#f87171"}
    diff_color = diff_colors.get(str(difficulty).lower(), "#94a3b8")

    # Ingredients list
    ingredients = recipe.get("ingredients", [])
    if ingredients and isinstance(ingredients[0], dict):
        ingr_html = "".join(
            f'<li style="padding:7px 0;font-size:1.1rem;border-bottom:1px solid #1f1208;color:#fef3c7;">'
            f'{i.get("quantity","")}&nbsp;<b style="color:#fff;">{i.get("item","")}</b></li>'
            for i in ingredients
        )
    else:
        ingr_html = "".join(
            f'<li style="padding:7px 0;font-size:1.1rem;color:#fef3c7;border-bottom:1px solid #1f1208;">{i}</li>'
            for i in ingredients
        )

    strip_html = ""

    # Method steps
    steps = recipe.get("steps", [])
    steps_html = ""
    for idx, s in enumerate(steps):
        steps_html += f"""
        <li style="padding:10px 0;line-height:1.7;font-size:1.1rem;color:#fef3c7;
                   border-bottom:1px solid #1f1208;list-style:none;">
          <span style="color:#fb923c;font-weight:700;">Step {idx+1}.</span> {s}
        </li>"""

    # Hero image
    img_html = ""
    if frame_b64:
        img_html = f'<img src="data:image/jpeg;base64,{frame_b64}" style="width:100%;max-height:320px;object-fit:cover;border-radius:16px;margin-bottom:1.5rem;">'

    return f"""
    <div style="font-family:'Segoe UI',sans-serif;color:#fef3c7;padding:0.5rem;">
      {img_html}
      <h1 style="font-size:2.6rem;margin:0 0 0.8rem 0;color:#fff;font-weight:800;">{recipe.get('dish_name','Unknown Dish')}</h1>
      <div style="display:flex;gap:0.6rem;flex-wrap:wrap;margin-bottom:1.4rem;">
        <span style="background:#7c3aed;color:#fff;padding:6px 18px;border-radius:20px;font-size:1rem;font-weight:600;">{recipe.get('cuisine_type','—')}</span>
        <span style="background:{diff_color};color:#000;padding:6px 18px;border-radius:20px;font-size:1rem;font-weight:600;">{difficulty.capitalize()}</span>
      </div>
      <div style="display:flex;gap:2.5rem;margin-bottom:2rem;font-size:1.05rem;">
        <span style="color:#fb923c;">⏱ Prep: <b style="color:#fff;">{recipe.get('prep_time','—')}</b></span>
        <span style="color:#fb923c;">🍳 Cook: <b style="color:#fff;">{recipe.get('cook_time','—')}</b></span>
        <span style="color:#fb923c;">🍽 Serves: <b style="color:#fff;">{recipe.get('servings','—')}</b></span>
      </div>
      <div style="margin-bottom:2.5rem;">
        <h3 style="color:#4ade80;border-bottom:2px solid #4ade80;padding-bottom:0.6rem;margin-top:0;font-size:1.3rem;">🥦 Ingredients</h3>
        <ul style="margin:0;padding-left:1.3rem;list-style:disc;">{ingr_html}</ul>
        {strip_html}
      </div>
      <div>
        <h3 style="color:#fb923c;border-bottom:2px solid #fb923c;padding-bottom:0.6rem;margin-top:0;font-size:1.3rem;">👨‍🍳 Method</h3>
        <ol style="margin:0;padding:0;">{steps_html}</ol>
      </div>
    </div>"""


def _render_history(history):
    if not history:
        return '<div style="color:#a16207;font-size:1rem;padding:0.5rem 0;">No recipes yet — paste a TikTok URL above to get started.</div>'

    by_cuisine = {}
    for h in history:
        cuisine = h.get("cuisine_type") or "Other"
        by_cuisine.setdefault(cuisine, []).append(h)

    cuisine_colors = ["#f97316", "#a855f7", "#22c55e", "#3b82f6", "#ec4899", "#eab308"]
    sections = ""
    for ci, (cuisine, items) in enumerate(by_cuisine.items()):
        color = cuisine_colors[ci % len(cuisine_colors)]
        cards = ""
        for h in items:
            img_html = ""
            frames_dir = h.get("frames_dir", "")
            if frames_dir and os.path.exists(frames_dir):
                b64 = _get_frame_b64(frames_dir)
                if b64:
                    img_html = f'<img src="data:image/jpeg;base64,{b64}" style="width:100%;height:100px;object-fit:cover;border-radius:10px;margin-bottom:0.6rem;">'

            cards += f"""
            <div style="background:#1a0f05;border:1px solid {color}44;border-radius:14px;
                        padding:0.9rem;border-left:3px solid {color};">
              {img_html}
              <div style="font-size:1rem;font-weight:700;color:#fff;margin-bottom:0.2rem;
                          white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">{h.get('dish_name','Unknown')}</div>
              <div style="font-size:0.8rem;color:#a16207;margin-top:0.3rem;">{h.get('timestamp','')}</div>
            </div>"""

        sections += f"""
        <div style="margin-bottom:1.8rem;">
          <div style="font-size:0.9rem;color:{color};letter-spacing:2px;font-weight:700;
                      margin-bottom:0.85rem;font-family:monospace;">▶ {cuisine.upper()}</div>
          <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(160px,1fr));gap:0.85rem;">
            {cards}
          </div>
        </div>"""

    return f"""
    <div style="font-family:'Segoe UI',sans-serif;">
      <div style="font-size:0.85rem;color:#a16207;letter-spacing:2px;
                  margin-bottom:1.2rem;font-family:monospace;font-weight:700;">📚 RECENT RECIPES</div>
      {sections}
    </div>"""


def _meta_display(meta, speech_source):
    return (
        f"Title:    {meta.get('title','')}\n"
        f"Uploader: {meta.get('uploader','')}\n"
        f"Duration: {meta.get('duration','')}s\n"
        f"Views:    {meta.get('view_count','')}\n"
        f"Speech:   {speech_source}"
    )


# ── load history recipe by dropdown selection ─────────────────────────────────

def load_from_dropdown(selection):
    if not selection:
        return ""
    history = load_history()
    for h in history:
        label = f"{h['dish_name']}  ·  {h.get('cuisine_type','') or 'Unknown'}  ·  {h['timestamp']}"
        if label == selection and h.get("recipe"):
            frames_dir = h.get("frames_dir", "")
            frame_b64 = _get_frame_b64(frames_dir)
            all_frames = _get_all_frames_b64(frames_dir)
            return _render_recipe(h["recipe"], frame_b64, all_frames)
    return ""


# ── main generator ────────────────────────────────────────────────────────────

def run_pipeline(url):
    empty_history = _render_history(load_history())
    empty = ("", "", "", "", empty_history, gr.Dropdown(choices=_get_history_choices()))

    if not url or not url.strip():
        yield _status(0, "Enter a TikTok URL above", error=True), *empty
        return

    history_html = _render_history(load_history())
    history_choices = _get_history_choices()

    yield _status(0, "Fetching video metadata…"), "", "", "", "", history_html, gr.Dropdown(choices=history_choices)
    try:
        meta = fetch_metadata(url.strip())
    except Exception as e:
        yield _status(0, f"Metadata error: {e}", error=True), "", "", "", "", history_html, gr.Dropdown(choices=history_choices)
        return

    yield _status(1, "Downloading video and subtitles…"), "", "", "", "", history_html, gr.Dropdown(choices=history_choices)
    try:
        video_file, subtitle_file = download_video(url.strip())
    except Exception as e:
        yield _status(1, f"Download error: {e}", error=True), "", "", "", "", history_html, gr.Dropdown(choices=history_choices)
        return

    yield _status(2, "Extracting speech text…"), "", "", "", "", history_html, gr.Dropdown(choices=history_choices)
    speech_text, speech_source = extract_speech(subtitle_file, video_file)
    meta_text = _meta_display(meta, speech_source)

    yield _status(3, "Analysing frames  (LLaMA 4 Scout Vision)…"), meta_text, "", speech_text, "", history_html, gr.Dropdown(choices=history_choices)
    try:
        visual_desc, frames_dir = extract_frames_and_analyse(video_file) if video_file else ("", None)
    except Exception as e:
        visual_desc, frames_dir = f"[Vision skipped: {e}]", None

    yield _status(4, "Extracting recipe  (LLaMA 3.3 70B)…"), meta_text, "", speech_text, visual_desc, history_html, gr.Dropdown(choices=history_choices)
    try:
        recipe, raw_json = extract_recipe(meta, speech_text, visual_desc)
    except Exception as e:
        yield _status(4, f"Extraction error: {e}", error=True), meta_text, "", speech_text, visual_desc, history_html, gr.Dropdown(choices=history_choices)
        return

    frame_b64 = _get_frame_b64(frames_dir) if frames_dir else None
    all_frames = _get_all_frames_b64(frames_dir) if frames_dir else []
    recipe_html = _render_recipe(recipe, frame_b64, all_frames)
    updated_history = save_history(url, recipe, frames_dir or "")

    yield (
        _status(5, f"Done — speech via {speech_source}"),
        meta_text,
        recipe_html,
        speech_text,
        visual_desc,
        _render_history(updated_history),
        gr.Dropdown(choices=_get_history_choices(), value=None),
    )


# ── UI ────────────────────────────────────────────────────────────────────────

CSS = """
body, .gradio-container {
    background: linear-gradient(135deg, #0f0a05 0%, #1a0f05 100%) !important;
    color: #fef3c7 !important;
    font-size: 1.05rem !important;
}
.gr-button-primary {
    background: linear-gradient(135deg, #f97316, #ea580c) !important;
    border: none !important;
    font-weight: 700 !important;
    font-size: 1.05rem !important;
    color: #fff !important;
    border-radius: 12px !important;
}
.gr-button-primary:hover { background: linear-gradient(135deg, #ea580c, #c2410c) !important; }
footer { display: none !important; }
.tab-nav button {
    background: #1a0f05 !important;
    color: #a16207 !important;
    border: none !important;
    font-size: 1rem !important;
    font-weight: 600 !important;
}
.tab-nav button.selected {
    color: #fb923c !important;
    border-bottom: 2px solid #fb923c !important;
}
textarea, input { font-size: 1.05rem !important; color: #111 !important; background: #fff !important; }
.gr-text-input input, .gr-text-input textarea,
div[data-testid="textbox"] input, div[data-testid="textbox"] textarea,
#url_input input, #url_input textarea { color: #111 !important; background: #fff !important; }
label { font-size: 1.05rem !important; color: #fb923c !important; font-weight: 600 !important; }
select { background: #fff !important; color: #111 !important; font-size: 1rem !important; }
.gradio-dropdown input, .gradio-dropdown ul li { color: #111 !important; }
.gradio-dropdown { background: #fff !important; color: #111 !important; }
"""

HEADER = """
<div style="text-align:center;padding:2.5rem 0 1.5rem;font-family:'Segoe UI',sans-serif;">
  <h1 style="font-size:3.5rem;font-weight:800;margin:0;letter-spacing:-2px;">
    <span>🍳 </span><span style="background:linear-gradient(135deg,#ffffff,#fb923c);
             -webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;">FlavourFlow</span>
  </h1>
  <p style="color:#fb923c;margin:0.6rem 0 0;font-size:1.1rem;font-weight:500;">
    Paste a TikTok cooking video URL — get a structured recipe instantly
  </p>
</div>"""

MODEL_BADGES = """
<div style="display:flex;gap:0.7rem;justify-content:center;flex-wrap:wrap;margin-bottom:1.8rem;font-size:0.9rem;font-weight:600;">
  <span style="background:#1e3a5f;border:1px solid #3b82f6;color:#93c5fd;padding:6px 16px;border-radius:20px;">Whisper base</span>
  <span style="background:#3b1f5e;border:1px solid #a855f7;color:#d8b4fe;padding:6px 16px;border-radius:20px;">LLaMA 4 Scout Vision</span>
  <span style="background:#14532d;border:1px solid #22c55e;color:#86efac;padding:6px 16px;border-radius:20px;">LLaMA 3.3 70B</span>
  <span style="background:#431407;border:1px solid #f97316;color:#fdba74;padding:6px 16px;border-radius:20px;">yt-dlp</span>
  <span style="background:#431407;border:1px solid #f97316;color:#fdba74;padding:6px 16px;border-radius:20px;">ffmpeg</span>
</div>"""

with gr.Blocks(title="FlavourFlow", css=CSS) as demo:
    gr.HTML(HEADER)
    gr.HTML(MODEL_BADGES)

    with gr.Row():
        url_box = gr.Textbox(
            placeholder="https://www.tiktok.com/@.../video/...",
            label="TikTok URL",
            scale=5,
            container=False,
            elem_id="url_input",
        )
        run_btn = gr.Button("Analyse Recipe", variant="primary", scale=1)

    # Dropdown to load a previous recipe — actually works unlike JS onclick
    history_dropdown = gr.Dropdown(
        choices=_get_history_choices(),
        label="📂 Load a Previous Recipe",
        value=None,
        interactive=True,
    )

    history_box = gr.HTML(value=_render_history(load_history()))

    with gr.Row():
        with gr.Column(scale=1):
            status_box = gr.HTML(value=_status(0, "Waiting for URL…"))
            meta_box = gr.Textbox(label="Video Metadata", lines=6, interactive=False)

        with gr.Column(scale=2):
            with gr.Tabs():
                with gr.Tab("Recipe Card"):
                    recipe_box = gr.HTML()
                with gr.Tab("Speech Transcript"):
                    transcript_box = gr.Textbox(lines=14, interactive=False, label="Extracted speech")
                with gr.Tab("Visual Description"):
                    visual_box = gr.Textbox(lines=14, interactive=False, label="LLaMA 4 Scout frame analysis")

    outputs = [status_box, meta_box, recipe_box, transcript_box, visual_box, history_box, history_dropdown]

    run_btn.click(fn=run_pipeline, inputs=[url_box], outputs=outputs)
    url_box.submit(fn=run_pipeline, inputs=[url_box], outputs=outputs)

    # Selecting from dropdown instantly loads the recipe card
    history_dropdown.change(fn=load_from_dropdown, inputs=[history_dropdown], outputs=[recipe_box])

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860, share=True, css=CSS)
