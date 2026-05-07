import streamlit as st
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

# ── Setup ──────────────────────────────────────────────────────────────────────
load_dotenv("/home/s5823597/Desktop/SEM/flavourflow/.env")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
HISTORY_FILE = "outputs/history.json"

st.set_page_config(
    page_title="FlavourFlow",
    page_icon="🍳",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Session state defaults ─────────────────────────────────────────────────────
for _k, _v in {
    "current_recipe": None,
    "current_frame_b64": None,
    "speech_text": "",
    "visual_desc": "",
    "meta_text": "",
}.items():
    if _k not in st.session_state:
        st.session_state[_k] = _v

# ── Global CSS ─────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@700;800&family=Inter:wght@400;500;600;700&display=swap');

/* Page background */
.stApp { background: #FFFBF0 !important; font-family: 'Inter', sans-serif; color: #1C0A00; }

/* Sidebar */
section[data-testid="stSidebar"] > div:first-child { background: #1C0A00 !important; }

/* Hide Streamlit chrome */
#MainMenu { visibility: hidden; }
footer { visibility: hidden; }
header { visibility: hidden; }

/* All buttons */
div[data-testid="stButton"] > button {
    background: linear-gradient(135deg, #EA580C, #C2410C) !important;
    color: white !important;
    border: none !important;
    border-radius: 12px !important;
    font-weight: 700 !important;
    font-size: 0.95rem !important;
    width: 100% !important;
    transition: all 0.2s !important;
}
div[data-testid="stButton"] > button:hover {
    background: linear-gradient(135deg, #C2410C, #9A3412) !important;
    box-shadow: 0 4px 16px rgba(234, 88, 12, 0.4) !important;
    transform: translateY(-1px) !important;
}

/* Sidebar buttons override */
section[data-testid="stSidebar"] div[data-testid="stButton"] > button {
    background: #2A1200 !important;
    border: 1px solid #5C2D00 !important;
    border-radius: 10px !important;
    font-size: 0.82rem !important;
    font-weight: 500 !important;
    text-align: left !important;
    color: #FEF3C7 !important;
}
section[data-testid="stSidebar"] div[data-testid="stButton"] > button:hover {
    background: #3A1800 !important;
    border-color: #EA580C !important;
    box-shadow: none !important;
    transform: none !important;
    color: white !important;
}

/* Text input */
div[data-testid="stTextInput"] input {
    border: 2px solid #F59E0B !important;
    border-radius: 12px !important;
    font-size: 1rem !important;
    background: white !important;
    color: #1C0A00 !important;
    padding: 0.6rem 1rem !important;
}
div[data-testid="stTextInput"] input:focus {
    border-color: #EA580C !important;
    box-shadow: 0 0 0 3px rgba(234, 88, 12, 0.15) !important;
    outline: none !important;
}

/* Tabs */
.stTabs [data-baseweb="tab-list"] { gap: 8px; background: transparent; border-bottom: none; }
.stTabs [data-baseweb="tab"] {
    background: #FEF3C7;
    border-radius: 8px;
    color: #92400E;
    font-weight: 600;
    border: 1px solid #F59E0B;
    padding: 0.4rem 1.2rem;
}
.stTabs [aria-selected="true"] {
    background: #EA580C !important;
    color: white !important;
    border-color: #EA580C !important;
}
.stTabs [data-baseweb="tab-panel"] { padding-top: 1rem; }

/* Text areas */
div[data-testid="stTextArea"] textarea {
    background: white !important;
    border: 1px solid #F59E0B !important;
    border-radius: 8px !important;
    color: #1C0A00 !important;
    font-size: 0.88rem !important;
    font-family: 'Courier New', monospace !important;
}

/* Divider */
hr { border-color: #F59E0B; opacity: 0.25; margin: 1.2rem 0; }

/* Column gap */
div[data-testid="stHorizontalBlock"] { gap: 2rem; }
</style>
""", unsafe_allow_html=True)


# ── History helpers ────────────────────────────────────────────────────────────

def load_history():
    if not os.path.exists(HISTORY_FILE):
        return []
    try:
        with open(HISTORY_FILE) as f:
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


def _get_frame_b64(frames_dir):
    if not frames_dir or not os.path.exists(frames_dir):
        return None
    frames = sorted([f for f in os.listdir(frames_dir) if f.endswith(".jpg")])
    if not frames:
        return None
    mid = frames[len(frames) // 2]
    with open(f"{frames_dir}/{mid}", "rb") as f:
        return base64.b64encode(f.read()).decode()


# ── Pipeline functions ─────────────────────────────────────────────────────────

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
        with open(subtitle_file) as f:
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
    """
    PROMPT 1 — Vision analysis (LLaMA 4 Scout 17B)
    Model: meta-llama/llama-4-scout-17b-16e-instruct via Groq
    Input: 5 JPEG frames extracted at fps=1/3 (one every 3 seconds), base64-encoded
    Purpose: Identify visible ingredients, cooking techniques, and dishes from video frames
    to supplement the audio transcript with visual context.
    """
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
        "text": (
            "These are frames from a TikTok cooking video. "
            "Describe what ingredients, cooking techniques, and dishes you can see. "
            "Be specific and concise."
        ),
    })
    client = Groq(api_key=GROQ_API_KEY)
    resp = client.chat.completions.create(
        model="meta-llama/llama-4-scout-17b-16e-instruct",
        messages=[{"role": "user", "content": content}],
        max_tokens=512,
    )
    return resp.choices[0].message.content, frames_dir


def extract_recipe(meta, speech_text, visual_desc):
    """
    PROMPT 2 — Recipe extraction (LLaMA 3.3 70B Versatile)
    Model: llama-3.3-70b-versatile via Groq
    Input: video title, description, speech transcript, and visual frame description
    Purpose: Synthesise all available context into a structured JSON recipe,
    translating everything to English regardless of the original video language.
    Parameters: temperature=0.1 (low — we want deterministic structured output),
                max_tokens=1024
    """
    client = Groq(api_key=GROQ_API_KEY)
    context = (
        f"Video Title: {meta.get('title', '')}\n"
        f"Video Description: {meta.get('description', '')}\n"
        f"Speech Transcript: {speech_text}\n"
        f"Visual Description: {visual_desc}"
    )
    system_prompt = (
        "You are a recipe extraction assistant. "
        "Always respond in valid JSON in English only."
    )
    user_prompt = f"""You are a recipe extraction AI. Analyse the following TikTok video data and:

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
   - allergens (list of allergens present, chosen from: Gluten, Dairy, Eggs, Nuts, Peanuts, Soy, Shellfish, Fish, Sesame. Only include allergens you are confident are present based on the ingredients.)
   - dietary (list of applicable labels from: Vegetarian, Vegan, Gluten-Free, Dairy-Free, Halal, Contains Nuts. Only include labels you are confident apply.)

IMPORTANT: The video may be in any language. Translate ALL field values into English.

Video Data:
{context}

Respond ONLY in valid JSON."""

    resp = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        max_tokens=1200,
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


# ── UI helpers ─────────────────────────────────────────────────────────────────

def _status_html(steps_done, message, error=False):
    steps = ["Fetch metadata", "Download video", "Extract speech", "Vision analysis", "Extract recipe"]
    rows = ""
    for i, step in enumerate(steps):
        if i < steps_done:
            icon, color = "✓", "#16A34A"
        elif i == steps_done and not error:
            icon, color = "▶", "#EA580C"
        else:
            icon, color = "○", "#92400E"
        rows += (
            f'<div style="padding:5px 0;color:{color};font-size:0.9rem;font-weight:500;">'
            f'{icon}&nbsp; {step}</div>'
        )
    msg_color = "#DC2626" if error else ("#16A34A" if steps_done >= len(steps) else "#EA580C")
    msg_icon = "✗" if error else ("✓" if steps_done >= len(steps) else "⟳")
    return f"""
    <div style="background:#FEF3C7;border:2px solid #F59E0B;border-radius:14px;
                padding:1.2rem;font-family:'Courier New',monospace;">
        <div style="font-size:0.7rem;color:#92400E;letter-spacing:3px;
                    font-weight:700;margin-bottom:0.9rem;">PIPELINE STATUS</div>
        {rows}
        <div style="margin-top:0.9rem;padding-top:0.7rem;border-top:1px solid #FDE68A;
                    color:{msg_color};font-size:0.85rem;font-weight:600;">
            {msg_icon}&nbsp; {message}
        </div>
    </div>"""


def _shopping_list(ingredients):
    lines = []
    for ingr in ingredients:
        if isinstance(ingr, dict):
            qty = ingr.get("quantity", "")
            item = ingr.get("item", "")
            lines.append(f"• {qty} {item}".strip())
        else:
            lines.append(f"• {ingr}")
    return "\n".join(lines)


def _render_recipe(recipe, frame_b64=None):
    if not recipe:
        return

    # Non-cooking video guard
    dish_name = recipe.get("dish_name", "")
    if not dish_name or dish_name.lower() in ("unknown", "n/a", "not a cooking video", ""):
        st.markdown("""
        <div style="text-align:center;padding:3rem 1rem;background:#FEF3C7;
                    border-radius:20px;border:2px dashed #F59E0B;">
            <div style="font-size:3rem;margin-bottom:1rem;">🤔</div>
            <h3 style="font-family:'Playfair Display',serif;color:#1C0A00;margin:0 0 0.5rem;">
                No recipe found
            </h3>
            <p style="color:#92400E;font-size:0.95rem;margin:0;">
                This doesn't look like a cooking video.<br>
                Try a TikTok video that shows someone cooking a dish.
            </p>
        </div>""", unsafe_allow_html=True)
        return

    difficulty = str(recipe.get("difficulty", "—")).lower()
    diff_cfg = {
        "easy":   ("#DCFCE7", "#16A34A"),
        "medium": ("#FEF3C7", "#D97706"),
        "hard":   ("#FEE2E2", "#DC2626"),
    }
    diff_bg, diff_fg = diff_cfg.get(difficulty, ("#F3F4F6", "#6B7280"))
    cuisine = recipe.get("cuisine_type", "—")
    ingredients = recipe.get("ingredients", [])
    steps = recipe.get("steps", [])

    # ── Hero image (full width) ────────────────────────────────────────────────
    if frame_b64:
        st.markdown(f"""
        <div style="border-radius:20px;overflow:hidden;margin-bottom:1.5rem;
                    box-shadow:0 8px 40px rgba(234,88,12,0.2);max-height:360px;">
            <img src="data:image/jpeg;base64,{frame_b64}"
                 style="width:100%;max-height:360px;object-fit:cover;display:block;">
        </div>""", unsafe_allow_html=True)

    # ── Title + badges ─────────────────────────────────────────────────────────
    # Allergen & dietary badge configs
    allergen_style = "background:#FEE2E2;color:#991B1B;border:1px solid #FCA5A5;"
    dietary_style  = "background:#DCFCE7;color:#166534;border:1px solid #86EFAC;"

    allergens = recipe.get("allergens", [])
    dietary   = recipe.get("dietary", [])

    allergen_badges = "".join(
        f'<span style="{allergen_style}padding:4px 12px;border-radius:20px;'
        f'font-size:0.78rem;font-weight:600;">⚠ {a}</span>'
        for a in allergens
    )
    dietary_badges = "".join(
        f'<span style="{dietary_style}padding:4px 12px;border-radius:20px;'
        f'font-size:0.78rem;font-weight:600;">✓ {d}</span>'
        for d in dietary
    )

    st.markdown(f"""
    <h1 style="font-family:'Playfair Display',serif;font-size:2.5rem;font-weight:800;
               color:#1C0A00;margin:0 0 0.5rem 0;line-height:1.2;">{dish_name}</h1>
    <div style="display:flex;gap:0.6rem;flex-wrap:wrap;margin-bottom:0.8rem;">
        <span style="background:#7C3AED;color:white;padding:5px 18px;
                     border-radius:20px;font-size:0.85rem;font-weight:600;">{cuisine}</span>
        <span style="background:{diff_bg};color:{diff_fg};padding:5px 18px;
                     border-radius:20px;font-size:0.85rem;font-weight:600;
                     border:1px solid {diff_fg};">{difficulty.capitalize()}</span>
    </div>""", unsafe_allow_html=True)

    # Allergen row
    if allergens or dietary:
        st.markdown(f"""
        <div style="display:flex;gap:0.5rem;flex-wrap:wrap;margin-bottom:1.1rem;">
            {allergen_badges}{dietary_badges}
        </div>""", unsafe_allow_html=True)

    # ── Stats strip ────────────────────────────────────────────────────────────
    st.markdown(f"""
    <div style="display:flex;gap:2rem;flex-wrap:wrap;margin-bottom:1.8rem;
                padding:1rem 1.5rem;background:#FEF3C7;border-radius:14px;
                border:1px solid #F59E0B;">
        <div style="text-align:center;">
            <div style="font-size:1.3rem;">⏱</div>
            <div style="font-size:0.65rem;color:#92400E;font-weight:700;letter-spacing:1px;">PREP</div>
            <div style="font-size:0.9rem;font-weight:700;color:#1C0A00;">{recipe.get("prep_time","—")}</div>
        </div>
        <div style="text-align:center;">
            <div style="font-size:1.3rem;">🍳</div>
            <div style="font-size:0.65rem;color:#92400E;font-weight:700;letter-spacing:1px;">COOK</div>
            <div style="font-size:0.9rem;font-weight:700;color:#1C0A00;">{recipe.get("cook_time","—")}</div>
        </div>
        <div style="text-align:center;">
            <div style="font-size:1.3rem;">🍽</div>
            <div style="font-size:0.65rem;color:#92400E;font-weight:700;letter-spacing:1px;">SERVES</div>
            <div style="font-size:0.9rem;font-weight:700;color:#1C0A00;">{recipe.get("servings","—")}</div>
        </div>
    </div>""", unsafe_allow_html=True)

    # ── Two-column cookbook layout ─────────────────────────────────────────────
    ingr_col, method_col = st.columns([2, 3])

    with ingr_col:
        st.markdown("""
        <div style="background:white;border-radius:16px;padding:1.3rem 1.5rem;
                    border:1px solid #FDE68A;box-shadow:0 2px 12px rgba(245,158,11,0.1);
                    height:100%;">
        <h2 style="font-family:'Playfair Display',serif;color:#16A34A;font-size:1.2rem;
                   margin:0 0 0.8rem 0;border-bottom:2px solid #16A34A;padding-bottom:0.4rem;">
            🥦 Ingredients
        </h2>""", unsafe_allow_html=True)

        if ingredients:
            items_html = ""
            for ingr in ingredients:
                if isinstance(ingr, dict):
                    qty = ingr.get("quantity", "")
                    item = ingr.get("item", "")
                    items_html += (
                        f'<li style="padding:6px 0;border-bottom:1px solid #FEF3C7;'
                        f'color:#1C0A00;font-size:0.88rem;list-style:none;">'
                        f'<span style="color:#92400E;font-weight:600;">{qty}</span>&nbsp;{item}</li>'
                    )
                else:
                    items_html += (
                        f'<li style="padding:6px 0;border-bottom:1px solid #FEF3C7;'
                        f'color:#1C0A00;font-size:0.88rem;list-style:none;">• {ingr}</li>'
                    )
            st.markdown(f'<ul style="margin:0;padding:0;">{items_html}</ul>',
                        unsafe_allow_html=True)

        st.markdown("</div>", unsafe_allow_html=True)

        # Shopping list copy box
        if ingredients:
            st.markdown("<div style='margin-top:0.8rem;'>", unsafe_allow_html=True)
            with st.expander("📋 Copy as Shopping List"):
                st.code(_shopping_list(ingredients), language=None)
            st.markdown("</div>", unsafe_allow_html=True)

    with method_col:
        st.markdown("""
        <div style="background:white;border-radius:16px;padding:1.3rem 1.5rem;
                    border:1px solid #FDE68A;box-shadow:0 2px 12px rgba(245,158,11,0.1);">
        <h2 style="font-family:'Playfair Display',serif;color:#EA580C;font-size:1.2rem;
                   margin:0 0 0.8rem 0;border-bottom:2px solid #EA580C;padding-bottom:0.4rem;">
            👨‍🍳 Method
        </h2>""", unsafe_allow_html=True)

        for idx, step in enumerate(steps, 1):
            st.markdown(f"""
            <div style="display:flex;gap:0.9rem;padding:0.7rem 0;
                        border-bottom:1px solid #FEF3C7;align-items:flex-start;">
                <div style="background:#EA580C;color:white;border-radius:50%;
                            min-width:26px;height:26px;display:flex;align-items:center;
                            justify-content:center;font-weight:700;font-size:0.8rem;
                            flex-shrink:0;margin-top:2px;">{idx}</div>
                <div style="color:#1C0A00;font-size:0.9rem;line-height:1.7;">{step}</div>
            </div>""", unsafe_allow_html=True)

        st.markdown("</div>", unsafe_allow_html=True)


# ── Sidebar — Recipe Library ───────────────────────────────────────────────────

with st.sidebar:
    st.markdown("""
    <div style="text-align:center;padding:1.5rem 0 0.8rem;">
        <div style="font-size:2.8rem;margin-bottom:0.3rem;">🍳</div>
        <h1 style="font-family:'Playfair Display',serif;color:#FEF3C7;
                   font-size:1.7rem;margin:0;font-weight:800;letter-spacing:-0.5px;">
            FlavourFlow
        </h1>
        <p style="color:#F59E0B;font-size:0.78rem;margin:0.3rem 0 0;letter-spacing:1px;">
            AI RECIPE EXTRACTOR
        </p>
    </div>""", unsafe_allow_html=True)

    st.markdown('<hr style="border-color:#3A1800;margin:0.8rem 0;">', unsafe_allow_html=True)

    # Powered-by badges
    st.markdown("""
    <div style="margin-bottom:1rem;">
        <div style="font-size:0.65rem;color:#92400E;letter-spacing:3px;
                    font-weight:700;margin-bottom:0.5rem;">POWERED BY</div>
        <div style="display:flex;flex-direction:column;gap:0.35rem;">
            <span style="background:#1e3a5f;border:1px solid #3b82f6;color:#93c5fd;
                         padding:3px 10px;border-radius:12px;font-size:0.72rem;font-weight:600;">
                Whisper base ASR
            </span>
            <span style="background:#3b1f5e;border:1px solid #a855f7;color:#d8b4fe;
                         padding:3px 10px;border-radius:12px;font-size:0.72rem;font-weight:600;">
                LLaMA 4 Scout Vision
            </span>
            <span style="background:#14532d;border:1px solid #22c55e;color:#86efac;
                         padding:3px 10px;border-radius:12px;font-size:0.72rem;font-weight:600;">
                LLaMA 3.3 70B
            </span>
            <span style="background:#431407;border:1px solid #f97316;color:#fdba74;
                         padding:3px 10px;border-radius:12px;font-size:0.72rem;font-weight:600;">
                yt-dlp + ffmpeg
            </span>
        </div>
    </div>""", unsafe_allow_html=True)

    st.markdown('<hr style="border-color:#3A1800;margin:0.8rem 0;">', unsafe_allow_html=True)

    # Recipe library
    st.markdown("""
    <div style="font-size:0.65rem;color:#92400E;letter-spacing:3px;
                font-weight:700;margin-bottom:0.8rem;">📚 RECIPE LIBRARY</div>
    """, unsafe_allow_html=True)

    history = load_history()
    if not history:
        st.markdown("""
        <p style="color:#92400E;font-size:0.82rem;font-style:italic;line-height:1.5;">
            No recipes yet.<br>Paste a TikTok URL to get started!
        </p>""", unsafe_allow_html=True)
    else:
        cuisine_colors = ["#F97316", "#A855F7", "#22C55E", "#3B82F6", "#EC4899", "#EAB308"]
        by_cuisine = {}
        for h in history:
            c = h.get("cuisine_type") or "Other"
            by_cuisine.setdefault(c, []).append(h)

        for ci, (cuisine, items) in enumerate(by_cuisine.items()):
            color = cuisine_colors[ci % len(cuisine_colors)]
            st.markdown(
                f'<div style="font-size:0.7rem;color:{color};letter-spacing:2px;'
                f'font-weight:700;margin:0.8rem 0 0.4rem;">▶ {cuisine.upper()}</div>',
                unsafe_allow_html=True,
            )
            for hi, h in enumerate(items):
                frames_dir = h.get("frames_dir", "")
                b64 = _get_frame_b64(frames_dir) if frames_dir else None
                if b64:
                    st.markdown(
                        f'<div style="border-radius:8px;overflow:hidden;margin-bottom:0.3rem;">'
                        f'<img src="data:image/jpeg;base64,{b64}" '
                        f'style="width:100%;height:65px;object-fit:cover;display:block;"></div>',
                        unsafe_allow_html=True,
                    )
                if st.button(
                    f"🍴 {h.get('dish_name', 'Unknown')}",
                    key=f"hist_{ci}_{hi}",
                    use_container_width=True,
                ):
                    st.session_state.current_recipe = h["recipe"]
                    st.session_state.current_frame_b64 = _get_frame_b64(frames_dir)
                    st.session_state.speech_text = ""
                    st.session_state.visual_desc = ""
                    st.session_state.meta_text = ""
                    st.rerun()
                st.markdown(
                    f'<div style="font-size:0.68rem;color:#92400E;margin:-0.2rem 0 0.5rem;'
                    f'padding-left:0.2rem;">{h.get("timestamp","")}</div>',
                    unsafe_allow_html=True,
                )


# ── Main area ──────────────────────────────────────────────────────────────────

# Header
st.markdown("""
<div style="text-align:center;padding:2rem 0 1.2rem;">
    <h1 style="font-family:'Playfair Display',serif;font-size:3.2rem;font-weight:800;
               color:#1C0A00;margin:0;letter-spacing:-1px;">
        🍳 FlavourFlow
    </h1>
    <p style="color:#EA580C;margin:0.5rem 0 0;font-size:1rem;font-weight:500;">
        Paste a TikTok cooking video URL — get a structured recipe instantly
    </p>
</div>""", unsafe_allow_html=True)

# URL input row
url_col, btn_col = st.columns([5, 1])
with url_col:
    url = st.text_input(
        "url",
        placeholder="https://www.tiktok.com/@.../video/...",
        label_visibility="collapsed",
    )
with btn_col:
    analyse = st.button("Analyse", use_container_width=True)

st.markdown("---")

# ── Pipeline execution (runs inline — Streamlit updates placeholders live) ─────
if analyse and url.strip():
    left_col, right_col = st.columns([1, 2])

    with left_col:
        status_ph = st.empty()
        status_ph.markdown(_status_html(0, "Fetching video metadata…"), unsafe_allow_html=True)

    with right_col:
        recipe_ph = st.empty()

    # Step 0 — metadata
    try:
        meta = fetch_metadata(url.strip())
    except Exception as e:
        status_ph.markdown(_status_html(0, f"Metadata error: {e}", error=True), unsafe_allow_html=True)
        st.stop()

    # Step 1 — download
    status_ph.markdown(_status_html(1, "Downloading video and subtitles…"), unsafe_allow_html=True)
    try:
        video_file, subtitle_file = download_video(url.strip())
    except Exception as e:
        status_ph.markdown(_status_html(1, f"Download error: {e}", error=True), unsafe_allow_html=True)
        st.stop()

    # Step 2 — speech
    status_ph.markdown(_status_html(2, "Extracting speech text…"), unsafe_allow_html=True)
    speech_text, speech_source = extract_speech(subtitle_file, video_file)

    # Step 3 — vision
    status_ph.markdown(
        _status_html(3, "Analysing frames (LLaMA 4 Scout Vision)…"), unsafe_allow_html=True
    )
    try:
        visual_desc, frames_dir = (
            extract_frames_and_analyse(video_file) if video_file else ("", None)
        )
    except Exception as e:
        visual_desc, frames_dir = f"[Vision skipped: {e}]", None

    # Step 4 — recipe
    status_ph.markdown(
        _status_html(4, "Extracting recipe (LLaMA 3.3 70B)…"), unsafe_allow_html=True
    )
    try:
        recipe, _ = extract_recipe(meta, speech_text, visual_desc)
    except Exception as e:
        status_ph.markdown(_status_html(4, f"Extraction error: {e}", error=True), unsafe_allow_html=True)
        st.stop()

    frame_b64 = _get_frame_b64(frames_dir) if frames_dir else None

    # Check if a real recipe was extracted
    if not recipe or not recipe.get("dish_name"):
        status_ph.markdown(
            _status_html(5, "Not a cooking video — no recipe found", error=True),
            unsafe_allow_html=True,
        )
        with right_col:
            st.markdown("""
            <div style="text-align:center;padding:3rem 1rem;background:#FEF3C7;
                        border-radius:20px;border:2px dashed #F59E0B;margin-top:1rem;">
                <div style="font-size:3rem;margin-bottom:1rem;">🤔</div>
                <h3 style="font-family:'Playfair Display',serif;color:#1C0A00;margin:0 0 0.5rem;">
                    No recipe found
                </h3>
                <p style="color:#92400E;font-size:0.95rem;margin:0;">
                    This doesn't look like a cooking video.<br>
                    Try a TikTok video that shows someone cooking a dish.
                </p>
            </div>""", unsafe_allow_html=True)
        st.stop()

    save_history(url.strip(), recipe, frames_dir or "")
    status_ph.markdown(
        _status_html(5, f"Done — speech via {speech_source}"), unsafe_allow_html=True
    )

    # Render recipe in right column
    with right_col:
        with recipe_ph.container():
            _render_recipe(recipe, frame_b64)

    # Save to session state for persistence
    st.session_state.current_recipe = recipe
    st.session_state.current_frame_b64 = frame_b64
    st.session_state.speech_text = speech_text
    st.session_state.visual_desc = visual_desc
    st.session_state.meta_text = (
        f"Title:    {meta.get('title', '')}\n"
        f"Uploader: {meta.get('uploader', '')}\n"
        f"Duration: {meta.get('duration', '')}s\n"
        f"Views:    {meta.get('view_count', '')}\n"
        f"Speech:   {speech_source}"
    )

    # Detail tabs
    st.markdown("---")
    tab1, tab2, tab3 = st.tabs(["📝 Speech Transcript", "👁 Visual Description", "📊 Metadata"])
    with tab1:
        st.text_area("Extracted speech", value=speech_text, height=220, disabled=True,
                     label_visibility="collapsed")
    with tab2:
        st.text_area("LLaMA 4 Scout frame analysis", value=visual_desc, height=220, disabled=True,
                     label_visibility="collapsed")
    with tab3:
        st.text_area("Video metadata", value=st.session_state.meta_text, height=220, disabled=True,
                     label_visibility="collapsed")

# ── Show recipe loaded from sidebar history ────────────────────────────────────
elif st.session_state.current_recipe:
    _, recipe_col = st.columns([1, 2])
    with recipe_col:
        _render_recipe(st.session_state.current_recipe, st.session_state.current_frame_b64)

    if st.session_state.speech_text or st.session_state.visual_desc or st.session_state.meta_text:
        st.markdown("---")
        tab1, tab2, tab3 = st.tabs(["📝 Speech Transcript", "👁 Visual Description", "📊 Metadata"])
        with tab1:
            st.text_area("", value=st.session_state.speech_text, height=220, disabled=True)
        with tab2:
            st.text_area("", value=st.session_state.visual_desc, height=220, disabled=True)
        with tab3:
            st.text_area("", value=st.session_state.meta_text, height=220, disabled=True)

# ── Welcome / slide-deck landing page ─────────────────────────────────────────
else:
    st.markdown("""
    <style>
    @keyframes float {
        0%,100% { transform: translateY(0px); }
        50%      { transform: translateY(-8px); }
    }
    .float-emoji { display:inline-block; animation: float 3s ease-in-out infinite; }
    .float-emoji:nth-child(2) { animation-delay: 0.4s; }
    .float-emoji:nth-child(3) { animation-delay: 0.8s; }
    .float-emoji:nth-child(4) { animation-delay: 1.2s; }

    .step-card {
        background: white;
        border-radius: 20px;
        padding: 2rem 1.5rem;
        text-align: center;
        box-shadow: 0 4px 24px rgba(0,0,0,0.07);
        border-top: 4px solid;
        transition: transform 0.2s, box-shadow 0.2s;
        height: 100%;
    }
    .step-card:hover {
        transform: translateY(-4px);
        box-shadow: 0 8px 32px rgba(0,0,0,0.12);
    }
    .step-icon {
        font-size: 3.5rem;
        margin-bottom: 1rem;
        display: block;
    }
    .step-num {
        display: inline-block;
        width: 26px; height: 26px;
        border-radius: 50%;
        font-size: 0.8rem;
        font-weight: 700;
        line-height: 26px;
        margin-bottom: 0.6rem;
        color: white;
    }
    .cuisine-pill {
        display: inline-block;
        padding: 6px 16px;
        border-radius: 20px;
        font-size: 0.82rem;
        font-weight: 600;
        margin: 4px;
    }
    </style>

    <!-- Hero section -->
    <div style="text-align:center;padding:2rem 0 1rem;">
        <div style="margin-bottom:1.2rem;">
            <span class="float-emoji" style="font-size:3rem;">🥘</span>
            <span class="float-emoji" style="font-size:3rem;">🍜</span>
            <span class="float-emoji" style="font-size:3rem;">🍳</span>
            <span class="float-emoji" style="font-size:3rem;">🥗</span>
        </div>
        <h2 style="font-family:'Playfair Display',serif;font-size:2rem;font-weight:800;
                   color:#1C0A00;margin:0 0 0.5rem;">
            Your TikTok recipes, structured instantly.
        </h2>
        <p style="color:#92400E;font-size:1rem;max-width:480px;margin:0 auto 2rem;line-height:1.7;">
            Paste any TikTok cooking video URL above.<br>
            FlavourFlow reads the speech, analyses the visuals,<br>
            and hands you a clean recipe card — in seconds.
        </p>
    </div>
    """, unsafe_allow_html=True)

    # How it works — 4 slide cards
    c1, c2, c3, c4 = st.columns(4)
    cards = [
        ("#EA580C", "🎬", "Paste a URL",
         "Copy any TikTok cooking video link and drop it in the box above."),
        ("#7C3AED", "🎙️", "Speech extracted",
         "yt-dlp grabs subtitles. If none exist, Whisper transcribes the audio automatically."),
        ("#0284C7", "👁️", "AI sees the food",
         "5 frames are pulled from the video and analysed by LLaMA 4 Scout vision model."),
        ("#16A34A", "📋", "Recipe card ready",
         "LLaMA 3.3 70B synthesises everything into ingredients, steps, allergens and timing."),
    ]
    for col, (color, icon, title, desc) in zip([c1, c2, c3, c4], cards):
        with col:
            st.markdown(f"""
            <div class="step-card" style="border-top-color:{color};">
                <span class="step-num" style="background:{color};">
                    {cards.index((color,icon,title,desc))+1}
                </span>
                <span class="step-icon">{icon}</span>
                <h3 style="font-family:'Playfair Display',serif;color:#1C0A00;
                           font-size:1.05rem;margin:0 0 0.5rem;font-weight:700;">{title}</h3>
                <p style="color:#92400E;font-size:0.82rem;line-height:1.6;margin:0;">{desc}</p>
            </div>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # Cuisine coverage strip
    st.markdown("""
    <div style="text-align:center;padding:1.5rem;background:white;border-radius:20px;
                box-shadow:0 2px 12px rgba(0,0,0,0.06);border:1px solid #FDE68A;">
        <p style="font-size:0.75rem;color:#92400E;font-weight:700;letter-spacing:2px;
                  margin:0 0 0.8rem;">WORKS WITH VIDEOS IN ANY LANGUAGE · ALWAYS OUTPUTS IN ENGLISH</p>
        <div>
            <span class="cuisine-pill" style="background:#FEF3C7;color:#92400E;border:1px solid #F59E0B;">🇲🇾 Malaysian</span>
            <span class="cuisine-pill" style="background:#F0FDF4;color:#166534;border:1px solid #86EFAC;">🇯🇵 Japanese</span>
            <span class="cuisine-pill" style="background:#EFF6FF;color:#1D4ED8;border:1px solid #93C5FD;">🇮🇹 Italian</span>
            <span class="cuisine-pill" style="background:#FDF4FF;color:#7E22CE;border:1px solid #D8B4FE;">🇹🇭 Thai</span>
            <span class="cuisine-pill" style="background:#FFF1F2;color:#BE123C;border:1px solid #FDA4AF;">🇨🇳 Chinese</span>
            <span class="cuisine-pill" style="background:#FFFBEB;color:#B45309;border:1px solid #FCD34D;">🇮🇳 Indian</span>
            <span class="cuisine-pill" style="background:#F0FDFA;color:#0F766E;border:1px solid #5EEAD4;">🌍 + more</span>
        </div>
    </div>""", unsafe_allow_html=True)
