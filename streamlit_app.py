import streamlit as st
import yt_dlp
import whisper
import json
import os
import re
import sqlite3
import subprocess
import base64
import datetime
from groq import Groq
from dotenv import load_dotenv

load_dotenv("/home/s5823597/Desktop/SEM/flavourflow/.env")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
DB_FILE      = "outputs/flavourflow.db"

st.set_page_config(
    page_title="FlavourFlow",
    page_icon="🍳",
    layout="wide",
    initial_sidebar_state="expanded",
)

for _k, _v in {
    "current_recipe": None, "current_frame_b64": None,
    "speech_text": "", "visual_desc": "", "meta_text": "",
    "recipe_left": None, "recipe_right": None,
    "frame_left": None, "frame_right": None,
    "p1_hist_idx": None, "p2_hist_idx": None,
    "num_frames": 10, "whisper_model": "small",
}.items():
    if _k not in st.session_state:
        st.session_state[_k] = _v

# ── Global CSS ─────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Press+Start+2P&family=Inter:wght@400;500;600;700&display=swap');

/* ── Base ── */
.stApp {
    background: #0A0A1A !important;
    color: #E8E8E8 !important;
    font-family: 'Inter', sans-serif !important;
}
.stApp::before {
    content: '';
    position: fixed; top:0; left:0; right:0; bottom:0;
    background: repeating-linear-gradient(
        0deg, transparent, transparent 3px,
        rgba(0,0,0,0.04) 3px, rgba(0,0,0,0.04) 4px
    );
    pointer-events: none; z-index: 9999;
}

/* ── Tabs ── */
.stTabs [data-baseweb="tab-list"] {
    gap: 4px;
    background: transparent;
    border-bottom: 2px solid #2A2A4A;
    padding-bottom: 0;
}
.stTabs [data-baseweb="tab"] {
    font-family: 'Press Start 2P', monospace !important;
    font-size: 0.62rem !important;
    background: #0D0D2B !important;
    border: 2px solid #2A2A4A !important;
    border-bottom: none !important;
    border-radius: 0 !important;
    color: #555 !important;
    padding: 0.8rem 1.4rem !important;
    letter-spacing: 2px !important;
}
.stTabs [aria-selected="true"] {
    background: #1A1500 !important;
    border-color: #FFD700 !important;
    color: #FFD700 !important;
}
.stTabs [data-baseweb="tab-panel"] { padding-top: 1.5rem; }

/* ── Buttons ── */
div[data-testid="stButton"] > button {
    background: #FFD700 !important;
    color: #0A0A1A !important;
    border: 3px solid #B8860B !important;
    border-radius: 0 !important;
    font-family: 'Press Start 2P', monospace !important;
    font-size: 0.72rem !important;
    box-shadow: 5px 5px 0px #8B6508 !important;
    transition: all 0.08s !important;
    padding: 0.9rem 1rem !important;
    width: 100% !important;
    letter-spacing: 1px !important;
}
div[data-testid="stButton"] > button:hover {
    transform: translate(2px,2px) !important;
    box-shadow: 3px 3px 0px #8B6508 !important;
    background: #FFC400 !important;
}
div[data-testid="stButton"] > button:active {
    transform: translate(5px,5px) !important;
    box-shadow: 0px 0px 0px #8B6508 !important;
}

/* ── Text input ── */
div[data-testid="stTextInput"] input {
    background: #0D0D2B !important;
    border: 2px solid #4A4A8A !important;
    border-radius: 0 !important;
    color: #E8E8FF !important;
    font-size: 1rem !important;
    padding: 0.75rem 1rem !important;
    caret-color: #FFD700 !important;
}
div[data-testid="stTextInput"] input:focus {
    border-color: #FFD700 !important;
    box-shadow: 3px 3px 0px #B8860B !important;
    outline: none !important;
}
div[data-testid="stTextInput"] input::placeholder { color: #3A3A5A !important; }
div[data-testid="stTextInput"] label p {
    font-family: 'Press Start 2P', monospace !important;
    font-size: 0.55rem !important;
    color: #666 !important;
    letter-spacing: 2px !important;
}

/* ── Radio ── */
div[data-testid="stRadio"] label {
    background: #0D0D2B !important;
    border: 2px solid #2A2A4A !important;
    padding: 0.5rem 0.9rem !important;
    margin-right: 4px !important;
    cursor: pointer !important;
    font-family: 'Press Start 2P', monospace !important;
    font-size: 0.5rem !important;
    color: #666 !important;
    letter-spacing: 1px !important;
    transition: all 0.1s !important;
}
div[data-testid="stRadio"] label:has(input:checked) {
    border-color: #FFD700 !important;
    color: #FFD700 !important;
    background: #1A1500 !important;
}
div[data-testid="stRadio"] > div { gap: 0 !important; }
div[data-testid="stRadio"] input { display: none !important; }

/* ── Sidebar ── */
section[data-testid="stSidebar"] > div:first-child {
    background: #080814 !important;
}
section[data-testid="stSidebar"] p,
section[data-testid="stSidebar"] span,
section[data-testid="stSidebar"] div { color: #888 !important; }

/* sidebar buttons override */
section[data-testid="stSidebar"] div[data-testid="stButton"] > button {
    background: #0D0D2B !important;
    border: 2px solid #2A2A4A !important;
    box-shadow: 3px 3px 0 #1A1A3A !important;
    color: #CCC !important;
    font-size: 0.55rem !important;
    padding: 0.6rem 0.8rem !important;
}
section[data-testid="stSidebar"] div[data-testid="stButton"] > button:hover {
    border-color: #FFD700 !important;
    color: #FFD700 !important;
    background: #1A1500 !important;
    transform: translate(1px,1px) !important;
    box-shadow: 2px 2px 0 #8B6508 !important;
}

/* ── Expander ── */
div[data-testid="stExpander"] {
    border: 2px solid #2A2A4A !important;
    border-radius: 0 !important;
    background: #08080F !important;
}
div[data-testid="stExpander"] summary { color: #888 !important; }

/* ── Text area ── */
div[data-testid="stTextArea"] textarea {
    background: #08080F !important;
    border: 2px solid #2A2A4A !important;
    border-radius: 0 !important;
    color: #CCC !important;
    font-family: 'Courier New', monospace !important;
    font-size: 0.85rem !important;
}

/* ── Hide Streamlit chrome ── */
#MainMenu { visibility: hidden; }
footer    { visibility: hidden; }
header    { visibility: hidden; }

div[data-testid="stHorizontalBlock"] { gap: 1.2rem; }
hr { border-color: #2A2A4A; }

::-webkit-scrollbar       { width: 5px; }
::-webkit-scrollbar-track { background: #0A0A1A; }
::-webkit-scrollbar-thumb { background: #4A4A8A; }
::-webkit-scrollbar-thumb:hover { background: #FFD700; }
</style>
""", unsafe_allow_html=True)


# ── Ingredient type system (shared) ────────────────────────────────────────────
_TYPES = {
    "protein":   {"label": "PROTEIN", "color": "#FF6B6B", "bg": "#1A0808", "emoji": "🥩"},
    "vegetable": {"label": "VEGGIE",  "color": "#51CF66", "bg": "#081A0A", "emoji": "🥦"},
    "spice":     {"label": "SPICE",   "color": "#FFD43B", "bg": "#1A1500", "emoji": "✨"},
    "dairy":     {"label": "DAIRY",   "color": "#74C0FC", "bg": "#081020", "emoji": "🧀"},
    "grain":     {"label": "GRAIN",   "color": "#E8A44A", "bg": "#1A0E00", "emoji": "🌾"},
    "sauce":     {"label": "SAUCE",   "color": "#CC5DE8", "bg": "#120820", "emoji": "🫙"},
    "other":     {"label": "OTHER",   "color": "#868E96", "bg": "#111111", "emoji": "❓"},
}
_EMOJIS = {
    "garlic":"🧄","onion":"🧅","tomato":"🍅","carrot":"🥕","chilli":"🌶️","chili":"🌶️",
    "pepper":"🫑","egg":"🥚","chicken":"🍗","beef":"🥩","pork":"🥩","fish":"🐟",
    "salmon":"🐟","tuna":"🐟","shrimp":"🍤","prawn":"🍤","rice":"🍚","noodle":"🍜",
    "pasta":"🍝","bread":"🍞","cheese":"🧀","butter":"🧈","milk":"🥛","cream":"🥛",
    "salt":"🧂","oil":"🫙","soy":"🫙","honey":"🍯","lemon":"🍋","lime":"🍋",
    "ginger":"🫚","potato":"🥔","mushroom":"🍄","corn":"🌽","broccoli":"🥦",
    "spinach":"🥬","avocado":"🥑","cucumber":"🥒","tofu":"🫙","flour":"🌾",
    "sugar":"🍬","vinegar":"🫙","stock":"🥣","broth":"🥣","wine":"🍷","water":"💧",
    "basil":"🌿","coriander":"🌿","thyme":"🌿","parsley":"🌿","mint":"🌿",
    "spring onion":"🌱","scallion":"🌱","sesame":"✨","lamb":"🥩","turkey":"🍗",
    "bacon":"🥓","sausage":"🌭","coconut":"🥥","peanut":"🥜","lettuce":"🥗",
}

def _classify(name: str) -> str:
    n = name.lower()
    if any(k in n for k in ["chicken","beef","pork","fish","salmon","tuna","shrimp","prawn","egg","tofu","lamb","meat","turkey","bacon","sausage","mince","steak","cod"]):
        return "protein"
    if any(k in n for k in ["onion","garlic","tomato","pepper","carrot","broccoli","spinach","ginger","mushroom","potato","celery","leek","chilli","chili","bell","zucchini","cucumber","lettuce","cabbage","kale","spring onion","scallion","bok choy","aubergine","eggplant","courgette","sweet potato","capsicum"]):
        return "vegetable"
    if any(k in n for k in ["salt","cumin","turmeric","paprika","oregano","thyme","bay leaf","cardamom","cinnamon","clove","fennel","nutmeg","curry powder","chilli flake","star anise","msg","seasoning","spice","herb","coriander powder"]):
        return "spice"
    if any(k in n for k in ["milk","cream","butter","cheese","yogurt","yoghurt","parmesan","mozzarella","cheddar","cream cheese","ricotta","feta"]):
        return "dairy"
    if any(k in n for k in ["flour","rice","pasta","noodle","bread","oat","wheat","cornstarch","starch","vermicelli","dumpling","wonton","tortilla","couscous","quinoa"]):
        return "grain"
    if any(k in n for k in ["sauce","oil","vinegar","soy sauce","stock","broth","wine","beer","juice","syrup","honey","miso","oyster sauce","hoisin","fish sauce","coconut milk","ketchup","mustard","mayo"]):
        return "sauce"
    return "other"

def _emoji(name: str) -> str:
    n = name.lower()
    for key, em in _EMOJIS.items():
        if key in n:
            return em
    return _TYPES[_classify(name)]["emoji"]


# ── SQLite helpers ──────────────────────────────────────────────────────────────
def init_db():
    os.makedirs("outputs", exist_ok=True)
    con = sqlite3.connect(DB_FILE)
    con.execute("""
        CREATE TABLE IF NOT EXISTS recipes (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            url        TEXT UNIQUE,
            dish_name  TEXT,
            cuisine_type TEXT,
            frames_dir TEXT,
            timestamp  TEXT,
            recipe_json TEXT
        )
    """)
    con.commit()
    # One-time migration from old JSON history
    old_json = "outputs/history.json"
    if os.path.exists(old_json):
        try:
            with open(old_json) as f:
                old = json.load(f)
            for h in old:
                try:
                    con.execute(
                        "INSERT OR IGNORE INTO recipes "
                        "(url,dish_name,cuisine_type,frames_dir,timestamp,recipe_json) "
                        "VALUES(?,?,?,?,?,?)",
                        (h.get("url",""), h.get("dish_name",""), h.get("cuisine_type",""),
                         h.get("frames_dir",""), h.get("timestamp",""),
                         json.dumps(h.get("recipe",{})))
                    )
                except Exception:
                    pass
            con.commit()
            os.rename(old_json, old_json + ".migrated")
        except Exception:
            pass
    con.close()

def load_history():
    if not os.path.exists(DB_FILE):
        return []
    try:
        con = sqlite3.connect(DB_FILE)
        rows = con.execute(
            "SELECT url,dish_name,cuisine_type,frames_dir,timestamp,recipe_json "
            "FROM recipes ORDER BY id DESC LIMIT 20"
        ).fetchall()
        con.close()
        return [
            {"url": r[0], "dish_name": r[1], "cuisine_type": r[2],
             "frames_dir": r[3], "timestamp": r[4],
             "recipe": json.loads(r[5] or "{}")}
            for r in rows
        ]
    except Exception:
        return []

def save_history(url, recipe, frames_dir):
    os.makedirs("outputs", exist_ok=True)
    con = sqlite3.connect(DB_FILE)
    con.execute(
        "INSERT OR REPLACE INTO recipes "
        "(url,dish_name,cuisine_type,frames_dir,timestamp,recipe_json) VALUES(?,?,?,?,?,?)",
        (url, recipe.get("dish_name","Unknown"), recipe.get("cuisine_type",""),
         os.path.abspath(frames_dir) if frames_dir else "",
         datetime.datetime.now().strftime("%d %b %Y, %H:%M"),
         json.dumps(recipe, ensure_ascii=False))
    )
    con.commit()
    con.close()

init_db()

# ── Platform detection ──────────────────────────────────────────────────────────
def _detect_platform(url: str) -> str:
    u = url.lower()
    if "tiktok.com"   in u: return "TikTok"
    if "instagram.com" in u: return "Instagram"
    if "youtube.com"  in u or "youtu.be" in u: return "YouTube"
    return "Video"

def _frame_from_dir(frames_dir: str):
    if not frames_dir or not os.path.exists(frames_dir):
        return None
    frames = sorted([f for f in os.listdir(frames_dir) if f.endswith(".jpg")])
    if not frames:
        return None
    mid = frames[len(frames) // 2]
    with open(f"{frames_dir}/{mid}", "rb") as f:
        return base64.b64encode(f.read()).decode()


# ── Pipeline functions ──────────────────────────────────────────────────────────
def fetch_metadata(url):
    with yt_dlp.YoutubeDL({"quiet": True}) as ydl:
        return ydl.extract_info(url, download=False)

def download_video(url):
    os.makedirs("outputs", exist_ok=True)
    opts = {
        "writesubtitles": True, "subtitleslangs": ["all"],
        "writeautomaticsub": True, "outtmpl": "outputs/%(id)s.%(ext)s", "quiet": True,
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)
        video_id = (info or {}).get("id", "") or url.split("/")[-1].split("?")[0]
    vf = sf = None
    for fname in os.listdir("outputs"):
        if video_id and video_id in fname and fname.endswith(".mp4"):
            vf = f"outputs/{fname}"
        if video_id and video_id in fname and (".vtt" in fname or ".srt" in fname):
            sf = f"outputs/{fname}"
    return vf, sf

def extract_speech(sf, vf, model_size="small"):
    if sf:
        text = ""
        with open(sf) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("WEBVTT") and "-->" not in line and not line.isdigit():
                    text += line + " "
        return text.strip(), "Platform subtitles"
    if vf:
        model = whisper.load_model(model_size)
        return model.transcribe(vf)["text"].strip(), f"Whisper {model_size}"
    return "", "none"

def extract_frames_and_analyse(video_file, num_frames=10):
    if not video_file or not GROQ_API_KEY:
        return "", None
    fd = f"outputs/frames_{os.path.basename(video_file).split('.')[0]}"
    os.makedirs(fd, exist_ok=True)
    subprocess.run(
        ["ffmpeg", "-i", video_file, "-vf", "fps=1/3", "-vframes", str(num_frames),
         f"{fd}/frame_%02d.jpg", "-y", "-loglevel", "error"]
    )
    frames = sorted([f"{fd}/{f}" for f in os.listdir(fd) if f.endswith(".jpg")])
    if not frames:
        return "", None
    content = []
    for fp in frames:
        with open(fp, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        content.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}})
    content.append({"type": "text", "text": "Describe what ingredients, cooking techniques, and dishes you can see. Be specific and concise."})
    client = Groq(api_key=GROQ_API_KEY)
    resp = client.chat.completions.create(
        model="meta-llama/llama-4-scout-17b-16e-instruct",
        messages=[{"role": "user", "content": content}], max_tokens=512)
    return resp.choices[0].message.content, fd

def extract_recipe(meta, speech_text, visual_desc):
    client = Groq(api_key=GROQ_API_KEY)
    context = (f"Video Title: {meta.get('title','')}\nVideo Description: {meta.get('description','')}\n"
               f"Speech Transcript: {speech_text}\nVisual Description: {visual_desc}")
    user_prompt = f"""Extract a recipe from this cooking video. Return JSON with exactly these fields:
- dish_name, cuisine_type, difficulty (easy/medium/hard), prep_time, cook_time, servings
- ingredients: list of {{"quantity":"...","item":"...","confidence":"high|medium|low"}} — use low when the ingredient is unclear from the video or audio
- steps: list of strings
- allergens: list from [Gluten,Dairy,Eggs,Nuts,Peanuts,Soy,Shellfish,Fish,Sesame] — only if confident
- dietary: list from [Vegetarian,Vegan,Gluten-Free,Dairy-Free,Halal,Contains Nuts] — only if confident
- price_estimate_gbp: {{"min":<int>,"max":<int>}} — estimated UK supermarket cost in GBP

Translate everything to English. Respond ONLY with valid JSON.

Video Data:\n{context}"""
    resp = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": "You are a recipe extraction assistant. Always respond in valid JSON in English only."},
            {"role": "user", "content": user_prompt},
        ],
        max_tokens=1400, temperature=0.1,
    )
    raw = re.sub(r"```(?:json)?\s*", "", resp.choices[0].message.content).strip()
    try:
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        recipe = json.loads(match.group()) if match else {}
        if "recipe" in recipe and isinstance(recipe["recipe"], dict):
            recipe = recipe["recipe"]
    except Exception:
        recipe = {}
    return recipe, raw


# ── Shared render helpers ───────────────────────────────────────────────────────
def _ing_card(ing) -> str:
    if isinstance(ing, dict):
        qty, name = ing.get("quantity",""), ing.get("item","Unknown")
        conf = ing.get("confidence","high")
    else:
        qty, name, conf = "", str(ing), "high"
    t   = _classify(name)
    cfg = _TYPES[t]
    em  = _emoji(name)
    dn  = (name[:13] + "…") if len(name) > 13 else name
    dq  = (qty[:11]  + "…") if len(qty)  > 11 else qty
    if conf == "low":
        conf_html = '<div style="font-family:\'Press Start 2P\',monospace;font-size:0.4rem;color:#FF6B6B;margin-top:0.1rem;">⚠ CHECK</div>'
    elif conf == "medium":
        conf_html = '<div style="font-family:\'Press Start 2P\',monospace;font-size:0.4rem;color:#FFD43B;margin-top:0.1rem;">⚠ VERIFY</div>'
    else:
        conf_html = ""
    return f"""
    <div style="background:{cfg['bg']};border:2px solid {cfg['color']};
                box-shadow:4px 4px 0 {cfg['color']}44;
                padding:1.2rem 0.8rem;text-align:center;width:135px;flex-shrink:0;
                display:inline-flex;flex-direction:column;align-items:center;gap:0.5rem;">
        <div style="font-size:2.6rem;line-height:1;">{em}</div>
        <div style="font-family:'Press Start 2P',monospace;font-size:0.55rem;
                    color:{cfg['color']};letter-spacing:1px;">{cfg['label']}</div>
        <div style="font-size:1rem;color:#E8E8E8;font-weight:700;
                    line-height:1.3;word-break:break-word;">{dn}</div>
        <div style="font-size:0.88rem;color:#888;">{dq or "—"}</div>
        {conf_html}
    </div>"""

def _pipeline_status(steps_done, message, error=False):
    steps = ["Fetch metadata","Download video","Extract speech","Vision analysis","Extract recipe"]
    rows  = ""
    for i, step in enumerate(steps):
        if i < steps_done:        icon, c = "✓", "#51CF66"
        elif i == steps_done and not error: icon, c = "▶", "#FFD700"
        else:                     icon, c = "○", "#3A3A5A"
        rows += f'<div style="padding:5px 0;color:{c};font-size:0.85rem;font-weight:500;">{icon}&nbsp; {step}</div>'
    mc = "#FF6B6B" if error else ("#51CF66" if steps_done >= len(steps) else "#FFD700")
    mi = "✗" if error else ("✓" if steps_done >= len(steps) else "⟳")
    return f"""
    <div style="background:#08080F;border:2px solid #2A2A4A;padding:1.2rem;">
        <div style="font-family:'Press Start 2P',monospace;font-size:0.55rem;
                    color:#555;letter-spacing:3px;margin-bottom:0.9rem;">PIPELINE STATUS</div>
        {rows}
        <div style="margin-top:0.9rem;padding-top:0.7rem;border-top:1px solid #1A1A2A;
                    color:{mc};font-size:0.88rem;font-weight:600;">{mi}&nbsp; {message}</div>
    </div>"""


def _render_recipe(recipe, frame_b64=None):
    if not recipe:
        return
    dish = recipe.get("dish_name","")
    if not dish or dish.lower() in ("unknown","n/a","not a cooking video",""):
        st.markdown("""
        <div style="text-align:center;padding:3rem;background:#08080F;border:2px solid #2A2A4A;">
            <div style="font-size:3rem;margin-bottom:1rem;">🤔</div>
            <div style="font-family:'Press Start 2P',monospace;font-size:0.8rem;color:#555;margin-bottom:0.8rem;">NO RECIPE FOUND</div>
            <p style="color:#555;font-size:0.95rem;">This doesn't look like a cooking video. Try another URL.</p>
        </div>""", unsafe_allow_html=True)
        return

    cuisine   = recipe.get("cuisine_type","—")
    diff      = str(recipe.get("difficulty","—")).lower()
    prep_t    = recipe.get("prep_time","—")
    cook_t    = recipe.get("cook_time","—")
    servings  = recipe.get("servings","—")
    ings      = recipe.get("ingredients",[])
    steps     = recipe.get("steps",[])
    price     = recipe.get("price_estimate_gbp",{})
    allergens = recipe.get("allergens",[])
    dietary   = recipe.get("dietary",[])

    diff_col  = {"easy":"#51CF66","medium":"#FFD43B","hard":"#FF6B6B"}.get(diff,"#868E96")
    diff_star = {"easy":"★☆☆","medium":"★★☆","hard":"★★★"}.get(diff,"?")
    p_min = price.get("min","?") if isinstance(price,dict) else "?"
    p_max = price.get("max","?") if isinstance(price,dict) else "?"

    if frame_b64:
        st.markdown(f"""
        <div style="border:3px solid #FFD700;box-shadow:5px 5px 0 #8B650844;
                    overflow:hidden;margin-bottom:1.5rem;height:500px;">
            <img src="data:image/jpeg;base64,{frame_b64}"
                 style="width:100%;height:500px;object-fit:cover;object-position:center;display:block;">
        </div>""", unsafe_allow_html=True)

    # Title
    st.markdown(f"""
    <div style="border:3px solid #FFD700;box-shadow:5px 5px 0 #8B6508;
                background:#0D0D2B;padding:1.3rem;margin-bottom:1rem;">
        <div style="font-family:'Press Start 2P',monospace;font-size:1rem;
                    color:#FFD700;text-shadow:2px 2px 0 #8B6508;
                    line-height:1.8;word-break:break-word;">{dish.upper()}</div>
        <div style="font-size:1.15rem;color:#AAA;margin-top:0.6rem;font-style:italic;font-weight:500;">{cuisine}</div>
    </div>""", unsafe_allow_html=True)

    # Stats
    st.markdown(f"""
    <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:3px;margin-bottom:1rem;">
        <div style="background:#0D0D2B;border:2px solid #2A2A4A;padding:0.9rem 0.3rem;text-align:center;">
            <div style="font-family:'Press Start 2P',monospace;font-size:0.5rem;color:#555;margin-bottom:0.4rem;">PREP</div>
            <div style="font-size:0.9rem;color:#CCC;font-weight:600;">{prep_t}</div>
        </div>
        <div style="background:#0D0D2B;border:2px solid #2A2A4A;padding:0.9rem 0.3rem;text-align:center;">
            <div style="font-family:'Press Start 2P',monospace;font-size:0.5rem;color:#555;margin-bottom:0.4rem;">COOK</div>
            <div style="font-size:0.9rem;color:#CCC;font-weight:600;">{cook_t}</div>
        </div>
        <div style="background:#0D0D2B;border:2px solid #2A2A4A;padding:0.9rem 0.3rem;text-align:center;">
            <div style="font-family:'Press Start 2P',monospace;font-size:0.5rem;color:#555;margin-bottom:0.4rem;">SERVES</div>
            <div style="font-size:0.9rem;color:#CCC;font-weight:600;">{servings}</div>
        </div>
        <div style="background:#0D0D2B;border:2px solid #2A2A4A;padding:0.9rem 0.3rem;text-align:center;">
            <div style="font-family:'Press Start 2P',monospace;font-size:0.5rem;color:{diff_col};margin-bottom:0.4rem;">LEVEL</div>
            <div style="font-size:0.9rem;color:{diff_col};font-weight:700;">{diff_star}</div>
        </div>
    </div>""", unsafe_allow_html=True)

    # Price
    st.markdown(f"""
    <div style="border:3px solid #FFD700;background:#0D0D00;box-shadow:4px 4px 0 #8B6508;
                padding:1.1rem 1.4rem;margin-bottom:1rem;
                display:flex;align-items:center;justify-content:space-between;">
        <div>
            <div style="font-family:'Press Start 2P',monospace;font-size:0.72rem;
                        color:#B8860B;letter-spacing:2px;margin-bottom:0.4rem;">💷 EST. UK COST</div>
            <div style="font-size:1rem;color:#888;">supermarket estimate</div>
        </div>
        <div style="font-family:'Press Start 2P',monospace;font-size:1.4rem;
                    color:#FFD700;text-shadow:2px 2px 0 #8B6508;">£{p_min}–£{p_max}</div>
    </div>""", unsafe_allow_html=True)

    # Allergen / dietary badges
    if allergens or dietary:
        badges = "".join(
            f'<span style="background:#1A0505;border:1px solid #FF6B6B;color:#FF6B6B;'
            f'padding:5px 13px;font-size:0.82rem;font-weight:600;">⚠ {a}</span>'
            for a in allergens
        ) + "".join(
            f'<span style="background:#051A08;border:1px solid #51CF66;color:#51CF66;'
            f'padding:5px 13px;font-size:0.82rem;font-weight:600;">✓ {d}</span>'
            for d in dietary
        )
        st.markdown(f'<div style="display:flex;flex-wrap:wrap;gap:0.4rem;margin-bottom:1rem;">{badges}</div>',
                    unsafe_allow_html=True)

    # Ingredients
    ingr_col, method_col = st.columns([2, 3])
    with ingr_col:
        st.markdown("""
        <div style="font-family:'Press Start 2P',monospace;font-size:0.72rem;
                    color:#888;letter-spacing:3px;margin-bottom:1rem;">── INGREDIENTS ──</div>""",
                    unsafe_allow_html=True)
        if ings:
            cards = '<div style="display:flex;flex-wrap:wrap;gap:0.5rem;margin-bottom:1rem;">'
            for ing in ings:
                cards += _ing_card(ing)
            cards += "</div>"
            st.html(cards)
        if ings:
            _type_labels = {
                "protein":"🥩 PROTEINS","vegetable":"🥦 VEGETABLES",
                "spice":"✨ SPICES & HERBS","dairy":"🧀 DAIRY",
                "grain":"🌾 GRAINS & CARBS","sauce":"🫙 SAUCES & OILS","other":"❓ OTHER",
            }
            groups: dict = {}
            for ing in ings:
                if isinstance(ing, dict):
                    item_name = ing.get("item","")
                    line = f"• {ing.get('quantity','')} {item_name}".strip()
                else:
                    item_name, line = str(ing), f"• {ing}"
                groups.setdefault(_classify(item_name), []).append(line)
            shopping_txt = f"SHOPPING LIST — {dish.upper()}\n{'='*40}\n\n"
            for tk, tl in _type_labels.items():
                if tk in groups:
                    shopping_txt += f"{tl}\n"
                    for gl in groups[tk]:
                        shopping_txt += f"  {gl}\n"
                    shopping_txt += "\n"
            shopping_txt += "─"*40 + "\nGenerated by FlavourFlow AI"
            dl_col, pv_col = st.columns([1, 2])
            with dl_col:
                st.download_button(
                    "⬇ SHOPPING LIST",
                    data=shopping_txt,
                    file_name=f"{dish.lower().replace(' ','_')}_shopping.txt",
                    mime="text/plain",
                    use_container_width=True,
                    key=f"dl_shop_{hash(dish)}",
                )
            with pv_col:
                with st.expander("📋 Preview list"):
                    st.code(shopping_txt, language=None)

    with method_col:
        st.markdown("""
        <div style="font-family:'Press Start 2P',monospace;font-size:0.72rem;
                    color:#888;letter-spacing:3px;margin-bottom:1rem;">── COOKING METHOD ──</div>""",
                    unsafe_allow_html=True)
        if steps:
            rows = "".join(f"""
            <div style="display:flex;gap:1.2rem;padding:1rem 0;
                        border-bottom:1px solid #1A1A2A;align-items:flex-start;">
                <div style="font-family:'Press Start 2P',monospace;font-size:0.72rem;
                            color:#FFD700;min-width:32px;flex-shrink:0;margin-top:4px;">
                    {str(i).zfill(2)}</div>
                <div style="font-size:1.05rem;color:#DDD;line-height:1.8;">{step}</div>
            </div>""" for i, step in enumerate(steps, 1))
            st.markdown(f'<div style="border:2px solid #2A2A4A;background:#08080F;padding:1.2rem;">{rows}</div>',
                        unsafe_allow_html=True)


# ── Battle helpers ──────────────────────────────────────────────────────────────
def _render_battle_panel(recipe, side: str, frame_b64=None):
    if not recipe:
        st.markdown("""
        <div style="border:2px solid #2A2A4A;padding:4rem;text-align:center;">
            <div style="font-family:'Press Start 2P',monospace;font-size:0.75rem;color:#2A2A4A;">NO DATA</div>
        </div>""", unsafe_allow_html=True)
        return

    border    = "#FF6B35" if side == "left" else "#4D9EFF"
    label     = "◀ PLAYER 1" if side == "left" else "PLAYER 2 ▶"
    dish      = recipe.get("dish_name","Unknown")
    cuisine   = recipe.get("cuisine_type","—")
    diff      = str(recipe.get("difficulty","—")).lower()
    prep_t    = recipe.get("prep_time","—")
    cook_t    = recipe.get("cook_time","—")
    servings  = recipe.get("servings","—")
    ings      = recipe.get("ingredients",[])
    steps     = recipe.get("steps",[])
    price     = recipe.get("price_estimate_gbp",{})
    allergens = recipe.get("allergens",[])
    dietary   = recipe.get("dietary",[])

    diff_col  = {"easy":"#51CF66","medium":"#FFD43B","hard":"#FF6B6B"}.get(diff,"#868E96")
    diff_star = {"easy":"★☆☆","medium":"★★☆","hard":"★★★"}.get(diff,"?")
    p_min = price.get("min","?") if isinstance(price,dict) else "?"
    p_max = price.get("max","?") if isinstance(price,dict) else "?"

    if frame_b64:
        st.markdown(f"""
        <div style="border:3px solid {border};box-shadow:5px 5px 0 {border}44;
                    overflow:hidden;margin-bottom:1rem;height:210px;">
            <img src="data:image/jpeg;base64,{frame_b64}"
                 style="width:100%;height:220px;object-fit:cover;object-position:center;display:block;">
        </div>""", unsafe_allow_html=True)

    st.markdown(f"""
    <div style="border:3px solid {border};box-shadow:5px 5px 0 {border}44;
                background:#0D0D2B;padding:1.3rem;margin-bottom:1rem;">
        <div style="font-family:'Press Start 2P',monospace;font-size:0.62rem;
                    color:{border};letter-spacing:3px;margin-bottom:0.8rem;">{label}</div>
        <div style="font-family:'Press Start 2P',monospace;font-size:0.9rem;
                    color:#FFD700;text-shadow:2px 2px 0 #8B6508;
                    line-height:1.8;word-break:break-word;">{dish.upper()}</div>
        <div style="font-size:1.1rem;color:#AAA;margin-top:0.6rem;font-style:italic;font-weight:500;">{cuisine}</div>
    </div>""", unsafe_allow_html=True)

    st.markdown(f"""
    <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:3px;margin-bottom:1rem;">
        <div style="background:#0D0D2B;border:2px solid #2A2A4A;padding:0.9rem 0.3rem;text-align:center;">
            <div style="font-family:'Press Start 2P',monospace;font-size:0.48rem;color:#555;margin-bottom:0.4rem;">PREP</div>
            <div style="font-size:0.88rem;color:#CCC;font-weight:600;">{prep_t}</div>
        </div>
        <div style="background:#0D0D2B;border:2px solid #2A2A4A;padding:0.9rem 0.3rem;text-align:center;">
            <div style="font-family:'Press Start 2P',monospace;font-size:0.48rem;color:#555;margin-bottom:0.4rem;">COOK</div>
            <div style="font-size:0.88rem;color:#CCC;font-weight:600;">{cook_t}</div>
        </div>
        <div style="background:#0D0D2B;border:2px solid #2A2A4A;padding:0.9rem 0.3rem;text-align:center;">
            <div style="font-family:'Press Start 2P',monospace;font-size:0.48rem;color:#555;margin-bottom:0.4rem;">SERVES</div>
            <div style="font-size:0.88rem;color:#CCC;font-weight:600;">{servings}</div>
        </div>
        <div style="background:#0D0D2B;border:2px solid #2A2A4A;padding:0.9rem 0.3rem;text-align:center;">
            <div style="font-family:'Press Start 2P',monospace;font-size:0.48rem;color:{diff_col};margin-bottom:0.4rem;">LEVEL</div>
            <div style="font-size:0.88rem;color:{diff_col};font-weight:700;">{diff_star}</div>
        </div>
    </div>""", unsafe_allow_html=True)

    st.markdown(f"""
    <div style="border:3px solid #FFD700;background:#0D0D00;box-shadow:4px 4px 0 #8B6508;
                padding:1.1rem 1.4rem;margin-bottom:1rem;
                display:flex;align-items:center;justify-content:space-between;">
        <div>
            <div style="font-family:'Press Start 2P',monospace;font-size:0.72rem;
                        color:#B8860B;letter-spacing:2px;margin-bottom:0.4rem;">💷 EST. UK COST</div>
            <div style="font-size:1rem;color:#888;">supermarket estimate</div>
        </div>
        <div style="font-family:'Press Start 2P',monospace;font-size:1.4rem;
                    color:#FFD700;text-shadow:2px 2px 0 #8B6508;">£{p_min}–£{p_max}</div>
    </div>""", unsafe_allow_html=True)

    if allergens or dietary:
        badges = "".join(
            f'<span style="background:#1A0505;border:1px solid #FF6B6B;color:#FF6B6B;'
            f'padding:5px 12px;font-size:0.82rem;font-weight:600;">⚠ {a}</span>' for a in allergens
        ) + "".join(
            f'<span style="background:#051A08;border:1px solid #51CF66;color:#51CF66;'
            f'padding:5px 12px;font-size:0.82rem;font-weight:600;">✓ {d}</span>' for d in dietary
        )
        st.markdown(f'<div style="display:flex;flex-wrap:wrap;gap:0.4rem;margin-bottom:1rem;">{badges}</div>',
                    unsafe_allow_html=True)

    if ings:
        st.markdown("""
        <div style="font-family:'Press Start 2P',monospace;font-size:0.72rem;
                    color:#888;letter-spacing:3px;margin-bottom:1rem;">── INGREDIENTS ──</div>""",
                    unsafe_allow_html=True)
        cards = '<div style="display:flex;flex-wrap:wrap;gap:0.55rem;margin-bottom:1.2rem;">'
        for ing in ings:
            cards += _ing_card(ing)
        cards += "</div>"
        st.html(cards)

    if steps:
        st.markdown("""
        <div style="font-family:'Press Start 2P',monospace;font-size:0.72rem;
                    color:#888;letter-spacing:3px;margin-bottom:1rem;">── COOKING METHOD ──</div>""",
                    unsafe_allow_html=True)
        rows = "".join(f"""
        <div style="display:flex;gap:1.2rem;padding:1rem 0;
                    border-bottom:1px solid #1A1A2A;align-items:flex-start;">
            <div style="font-family:'Press Start 2P',monospace;font-size:0.72rem;
                        color:{border};min-width:32px;flex-shrink:0;margin-top:4px;">{str(i).zfill(2)}</div>
            <div style="font-size:1.05rem;color:#DDD;line-height:1.8;">{step}</div>
        </div>""" for i, step in enumerate(steps, 1))
        st.markdown(f'<div style="border:2px solid #2A2A4A;background:#08080F;padding:1.2rem;">{rows}</div>',
                    unsafe_allow_html=True)


def _history_selector(player_key: str, border: str):
    history = load_history()
    if not history:
        st.markdown("""
        <div style="border:2px solid #2A2A4A;background:#08080F;padding:2rem;text-align:center;">
            <div style="font-family:'Press Start 2P',monospace;font-size:0.6rem;color:#3A3A6A;
                        line-height:2;">NO SAVED RECIPES YET</div>
            <div style="font-size:0.9rem;color:#555;margin-top:0.5rem;">
                Extract a recipe first using the Recipe Extractor tab.
            </div>
        </div>""", unsafe_allow_html=True)
        return None, None

    selected_idx = st.session_state.get(f"{player_key}_hist_idx")
    col_a, col_b = st.columns(2)
    for i, h in enumerate(history):
        is_sel      = (selected_idx == i)
        card_border = border if is_sel else "#2A2A4A"
        card_bg     = "#0D0D2B" if is_sel else "#08080F"
        name_col    = border if is_sel else "#888"
        dish        = h.get("dish_name","Unknown")
        cuisine     = h.get("cuisine_type","—")
        ts          = h.get("timestamp","")
        thumb       = _frame_from_dir(h.get("frames_dir",""))
        filt        = "" if is_sel else "filter:brightness(0.5);"
        check       = "✓ " if is_sel else ""
        dname       = dish[:20].upper() + ("…" if len(dish)>20 else "")

        col = col_a if i % 2 == 0 else col_b
        with col:
            if thumb:
                st.markdown(f"""
                <div style="border:2px solid {card_border};border-bottom:none;
                            overflow:hidden;height:90px;">
                    <img src="data:image/jpeg;base64,{thumb}"
                         style="width:100%;height:90px;object-fit:cover;display:block;{filt}">
                </div>""", unsafe_allow_html=True)
            bt = "border-top:none;" if thumb else ""
            st.markdown(f"""
            <div style="background:{card_bg};border:2px solid {card_border};
                        {bt}padding:0.7rem 0.8rem;margin-bottom:0.2rem;">
                <div style="font-family:'Press Start 2P',monospace;font-size:0.46rem;
                            color:{name_col};line-height:1.7;word-break:break-word;">{check}{dname}</div>
                <div style="font-size:0.78rem;color:#555;margin-top:0.2rem;font-style:italic;">{cuisine}</div>
                <div style="font-size:0.7rem;color:#3A3A5A;">{ts}</div>
            </div>""", unsafe_allow_html=True)

            btn_label = "✓ SELECTED" if is_sel else "SELECT"
            if st.button(btn_label, key=f"{player_key}_sel_{i}", use_container_width=True):
                st.session_state[f"{player_key}_hist_idx"] = i
                st.rerun()

    if selected_idx is not None and selected_idx < len(history):
        h = history[selected_idx]
        return h["recipe"], _frame_from_dir(h.get("frames_dir",""))
    return None, None

def run_pipeline(url: str, player: str):
    ph = st.empty()
    def status(step, msg, ok=True):
        pct = int((step / 5) * 100)
        bar = "█" * (pct // 5) + "░" * (20 - pct // 5)
        c = "#51CF66" if ok else "#FF6B6B"
        ph.markdown(f"""
        <div style="border:2px solid #2A2A4A;background:#08080F;padding:1.2rem 1.4rem;">
            <div style="font-family:'Press Start 2P',monospace;font-size:0.6rem;color:#555;
                        letter-spacing:2px;margin-bottom:0.6rem;">{player} PIPELINE</div>
            <div style="font-family:'Press Start 2P',monospace;font-size:0.65rem;
                        color:{c};margin-bottom:0.6rem;">{msg}</div>
            <div style="font-family:'Press Start 2P',monospace;font-size:0.6rem;
                        color:#4A4A8A;">[{bar}] {pct}%</div>
        </div>""", unsafe_allow_html=True)
    try:
        status(0, "FETCHING METADATA...")
        meta = fetch_metadata(url)
        status(1, "DOWNLOADING VIDEO...")
        vf, sf = download_video(url)
        status(2, "EXTRACTING SPEECH...")
        _wm = st.session_state.get("whisper_model", "small")
        speech, _ = extract_speech(sf, vf, model_size=_wm)
        status(3, "VISION AI ANALYSIS...")
        _nf = st.session_state.get("num_frames", 10)
        visual, fd = extract_frames_and_analyse(vf, num_frames=_nf) if vf else ("", None)
        status(4, "EXTRACTING RECIPE...")
        recipe, _ = extract_recipe(meta, speech, visual)
        status(5, "DONE!")
        return recipe, _frame_from_dir(fd) if fd else None
    except Exception as e:
        status(0, f"ERROR: {str(e)[:40]}", ok=False)
        return None, None


# ══════════════════════════════════════════════════════════════════════════════
# ── Sidebar ───────────────────────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown("""
    <div style="text-align:center;padding:1.5rem 0 1rem;">
        <div style="font-size:2.5rem;margin-bottom:0.5rem;">🍳</div>
        <div style="font-family:'Press Start 2P',monospace;font-size:0.9rem;
                    color:#FFD700;text-shadow:2px 2px 0 #8B6508;letter-spacing:1px;">
            FlavourFlow
        </div>
        <div style="font-family:'Press Start 2P',monospace;font-size:0.42rem;
                    color:#3A3A6A;letter-spacing:3px;margin-top:0.5rem;">
            AI RECIPE EXTRACTOR
        </div>
    </div>""", unsafe_allow_html=True)

    st.markdown('<hr style="border-color:#1A1A3A;margin:0.8rem 0;">', unsafe_allow_html=True)

    st.markdown("""
    <div style="font-family:'Press Start 2P',monospace;font-size:0.42rem;
                color:#3A3A6A;letter-spacing:3px;margin-bottom:0.6rem;">POWERED BY</div>
    <div style="display:flex;flex-direction:column;gap:0.4rem;margin-bottom:0.8rem;">
        <span style="background:#08080F;border:1px solid #3b82f6;color:#93c5fd;
                     padding:4px 10px;font-size:0.72rem;font-weight:600;">Whisper ASR</span>
        <span style="background:#08080F;border:1px solid #a855f7;color:#d8b4fe;
                     padding:4px 10px;font-size:0.72rem;font-weight:600;">LLaMA 4 Scout Vision</span>
        <span style="background:#08080F;border:1px solid #22c55e;color:#86efac;
                     padding:4px 10px;font-size:0.72rem;font-weight:600;">LLaMA 3.3 70B</span>
        <span style="background:#08080F;border:1px solid #f97316;color:#fdba74;
                     padding:4px 10px;font-size:0.72rem;font-weight:600;">yt-dlp + ffmpeg</span>
    </div>""", unsafe_allow_html=True)

    with st.expander("⚙ SETTINGS"):
        st.session_state["num_frames"] = st.slider(
            "Frames to sample", min_value=5, max_value=15,
            value=st.session_state.get("num_frames", 10), step=1,
            help="More frames = richer visual analysis, slower processing",
        )
        st.session_state["whisper_model"] = st.radio(
            "Whisper model",
            options=["small", "medium", "base"],
            index=["small","medium","base"].index(st.session_state.get("whisper_model","small")),
            horizontal=True,
            help="small: fast + accurate  |  medium: slower + better  |  base: fastest",
        )

    st.markdown('<hr style="border-color:#1A1A3A;margin:0.8rem 0;">', unsafe_allow_html=True)

    st.markdown("""
    <div style="font-family:'Press Start 2P',monospace;font-size:0.42rem;
                color:#3A3A6A;letter-spacing:3px;margin-bottom:0.8rem;">📚 RECIPE LIBRARY</div>
    """, unsafe_allow_html=True)

    history = load_history()
    if not history:
        st.markdown('<p style="color:#3A3A6A;font-size:0.82rem;font-style:italic;">No recipes yet.</p>',
                    unsafe_allow_html=True)
    else:
        for ci, h in enumerate(history):
            thumb = _frame_from_dir(h.get("frames_dir",""))
            if thumb:
                st.markdown(
                    f'<div style="border:1px solid #2A2A4A;overflow:hidden;margin-bottom:0.2rem;">'
                    f'<img src="data:image/jpeg;base64,{thumb}" '
                    f'style="width:100%;height:60px;object-fit:cover;display:block;filter:brightness(0.7);"></div>',
                    unsafe_allow_html=True)
            if st.button(f"🍴 {h.get('dish_name','Unknown')}", key=f"sb_{ci}", use_container_width=True):
                st.session_state.current_recipe      = h["recipe"]
                st.session_state.current_frame_b64   = _frame_from_dir(h.get("frames_dir",""))
                st.session_state.speech_text         = ""
                st.session_state.visual_desc         = ""
                st.session_state.meta_text           = ""
                st.rerun()
            st.markdown(
                f'<div style="font-size:0.68rem;color:#3A3A5A;margin:-0.2rem 0 0.5rem;padding-left:0.2rem;">'
                f'{h.get("timestamp","")}</div>', unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# ── Main area ─────────────────────────────────────════════════════════════════
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("""
<div style="text-align:center;padding:2rem 0 1.5rem;">
    <div style="font-family:'Press Start 2P',monospace;font-size:2rem;
                color:#FFD700;text-shadow:4px 4px 0 #8B6508,8px 8px 0 #3D2B00;
                line-height:1.4;letter-spacing:2px;">FlavourFlow</div>
    <div style="font-family:'Press Start 2P',monospace;font-size:0.6rem;
                color:#3A3A6A;letter-spacing:3px;margin-top:0.8rem;">
        AI RECIPE EXTRACTOR · BATTLE MODE
    </div>
</div>""", unsafe_allow_html=True)

tab_extract, tab_battle = st.tabs(["🍳  RECIPE EXTRACTOR", "⚔️  BATTLE MODE"])


# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — RECIPE EXTRACTOR
# ══════════════════════════════════════════════════════════════════════════════
with tab_extract:
    url_col, btn_col = st.columns([5, 1])
    with url_col:
        url = st.text_input("url",
                            placeholder="TikTok · Instagram Reels · YouTube Shorts — paste URL here",
                            label_visibility="collapsed")
    with btn_col:
        analyse = st.button("ANALYSE", use_container_width=True)

    st.markdown('<hr style="border-color:#2A2A4A;margin:1rem 0;">', unsafe_allow_html=True)

    if analyse and url.strip():
        left_col, right_col = st.columns([1, 2])
        with left_col:
            status_ph = st.empty()
            status_ph.markdown(_pipeline_status(0, "Fetching video metadata…"), unsafe_allow_html=True)
        with right_col:
            recipe_ph = st.empty()

        try:
            meta = fetch_metadata(url.strip())
        except Exception as e:
            status_ph.markdown(_pipeline_status(0, f"Metadata error: {e}", error=True), unsafe_allow_html=True)
            st.stop()

        status_ph.markdown(_pipeline_status(1, "Downloading video…"), unsafe_allow_html=True)
        try:
            vf, sf = download_video(url.strip())
        except Exception as e:
            status_ph.markdown(_pipeline_status(1, f"Download error: {e}", error=True), unsafe_allow_html=True)
            st.stop()

        status_ph.markdown(_pipeline_status(2, "Extracting speech…"), unsafe_allow_html=True)
        _wm = st.session_state.get("whisper_model", "small")
        speech_text, speech_source = extract_speech(sf, vf, model_size=_wm)

        status_ph.markdown(_pipeline_status(3, "Vision analysis (LLaMA 4 Scout)…"), unsafe_allow_html=True)
        _nf = st.session_state.get("num_frames", 10)
        try:
            visual_desc, frames_dir = extract_frames_and_analyse(vf, num_frames=_nf) if vf else ("", None)
        except Exception as e:
            visual_desc, frames_dir = f"[Vision skipped: {e}]", None

        status_ph.markdown(_pipeline_status(4, "Extracting recipe (LLaMA 3.3 70B)…"), unsafe_allow_html=True)
        try:
            recipe, _ = extract_recipe(meta, speech_text, visual_desc)
        except Exception as e:
            status_ph.markdown(_pipeline_status(4, f"Extraction error: {e}", error=True), unsafe_allow_html=True)
            st.stop()

        frame_b64 = _frame_from_dir(frames_dir) if frames_dir else None

        if not recipe or not recipe.get("dish_name"):
            status_ph.markdown(_pipeline_status(5, "Not a cooking video — no recipe found", error=True),
                                unsafe_allow_html=True)
            st.stop()

        save_history(url.strip(), recipe, frames_dir or "")
        status_ph.markdown(_pipeline_status(5, f"Done — {speech_source}"), unsafe_allow_html=True)

        with right_col:
            with recipe_ph.container():
                _render_recipe(recipe, frame_b64)

        st.session_state.current_recipe    = recipe
        st.session_state.current_frame_b64 = frame_b64
        st.session_state.speech_text       = speech_text
        st.session_state.visual_desc       = visual_desc
        st.session_state.meta_text         = (
            f"Title:    {meta.get('title','')}\n"
            f"Uploader: {meta.get('uploader','')}\n"
            f"Duration: {meta.get('duration','')}s\n"
            f"Views:    {meta.get('view_count','')}\n"
            f"Speech:   {speech_source}"
        )

        st.markdown('<hr style="border-color:#2A2A4A;margin:1rem 0;">', unsafe_allow_html=True)
        t1, t2, t3 = st.tabs(["📝 Speech Transcript", "👁 Visual Description", "📊 Metadata"])
        with t1:
            st.text_area("", value=speech_text,  height=200, disabled=True)
        with t2:
            st.text_area("", value=visual_desc,  height=200, disabled=True)
        with t3:
            st.text_area("", value=st.session_state.meta_text, height=200, disabled=True)

    elif st.session_state.current_recipe:
        _render_recipe(st.session_state.current_recipe, st.session_state.current_frame_b64)

    else:
        st.markdown("""
        <div style="text-align:center;padding:3rem 0 2rem;">
            <div style="font-size:3rem;margin-bottom:1.5rem;">🎬 🎙️ 👁️ 📋</div>
            <div style="font-family:'Press Start 2P',monospace;font-size:0.65rem;
                        color:#3A3A6A;letter-spacing:2px;line-height:3;max-width:500px;margin:0 auto;">
                PASTE A TIKTOK COOKING<br>
                VIDEO URL ABOVE AND<br>
                PRESS ANALYSE
            </div>
        </div>""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — BATTLE MODE
# ══════════════════════════════════════════════════════════════════════════════
with tab_battle:
    st.markdown("""
    <div style="text-align:center;padding:1.5rem 0 1.8rem;">
        <div style="font-family:'Press Start 2P',monospace;font-size:2.2rem;
                    color:#FFD700;text-shadow:5px 5px 0 #8B6508,10px 10px 0 #3D2B00;
                    line-height:1.4;letter-spacing:2px;">RECIPE<br>BATTLE!</div>
        <div style="font-family:'Press Start 2P',monospace;font-size:0.62rem;
                    color:#3A3A6A;letter-spacing:3px;margin-top:1.2rem;line-height:2.5;">
            PICK FROM SAVED RECIPES OR PASTE A NEW URL · COMPARE HEAD-TO-HEAD
        </div>
    </div>""", unsafe_allow_html=True)
    st.markdown('<hr style="border-color:#2A2A4A;margin:0.5rem 0 1.8rem;">', unsafe_allow_html=True)

    p1_col, vs_col, p2_col = st.columns([10, 1, 10])

    with p1_col:
        st.markdown("""
        <div style="font-family:'Press Start 2P',monospace;font-size:0.68rem;
                    color:#FF6B35;letter-spacing:3px;margin-bottom:1rem;">◀ PLAYER 1</div>""",
                    unsafe_allow_html=True)
        p1_mode = st.radio("P1 source", ["📚  From Saved", "🔗  New URL"],
                           horizontal=True, label_visibility="collapsed", key="p1_mode_radio")
        p1_recipe = p1_frame = None
        if "Saved" in p1_mode:
            p1_recipe, p1_frame = _history_selector("p1", "#FF6B35")
        else:
            st.session_state.p1_hist_idx = None
            p1_url = st.text_input("", placeholder="https://tiktok.com/@.../video/...",
                                   key="p1_url_input", label_visibility="collapsed")
            if st.session_state.get("p1_url_input","").strip():
                st.markdown('<div style="font-family:\'Press Start 2P\',monospace;font-size:0.55rem;'
                            'color:#51CF66;letter-spacing:2px;margin-top:0.5rem;">✓ URL READY</div>',
                            unsafe_allow_html=True)

    with vs_col:
        st.markdown("""
        <div style="display:flex;align-items:center;justify-content:center;
                    height:100%;padding-top:3.5rem;">
            <div style="font-family:'Press Start 2P',monospace;font-size:1.3rem;
                        color:#FF6B6B;text-shadow:4px 4px 0 #8B0000;">VS</div>
        </div>""", unsafe_allow_html=True)

    with p2_col:
        st.markdown("""
        <div style="font-family:'Press Start 2P',monospace;font-size:0.68rem;
                    color:#4D9EFF;letter-spacing:3px;margin-bottom:1rem;text-align:right;">PLAYER 2 ▶</div>""",
                    unsafe_allow_html=True)
        p2_mode = st.radio("P2 source", ["📚  From Saved", "🔗  New URL"],
                           horizontal=True, label_visibility="collapsed", key="p2_mode_radio")
        p2_recipe = p2_frame = None
        if "Saved" in p2_mode:
            p2_recipe, p2_frame = _history_selector("p2", "#4D9EFF")
        else:
            st.session_state.p2_hist_idx = None
            p2_url = st.text_input("", placeholder="https://tiktok.com/@.../video/...",
                                   key="p2_url_input", label_visibility="collapsed")
            if st.session_state.get("p2_url_input","").strip():
                st.markdown('<div style="font-family:\'Press Start 2P\',monospace;font-size:0.55rem;'
                            'color:#51CF66;letter-spacing:2px;margin-top:0.5rem;">✓ URL READY</div>',
                            unsafe_allow_html=True)

    st.markdown('<hr style="border-color:#2A2A4A;margin:1.5rem 0;">', unsafe_allow_html=True)

    bb1, bb2, bb3 = st.columns([2, 3, 2])
    with bb2:
        battle = st.button("⚔  BATTLE!", use_container_width=True, key="battle_btn")

    has_results = st.session_state.recipe_left or st.session_state.recipe_right
    if has_results:
        with bb1:
            if st.button("✕  CLEAR", use_container_width=True, key="clear_btn"):
                for k in ("recipe_left","recipe_right","frame_left","frame_right",
                          "p1_hist_idx","p2_hist_idx"):
                    st.session_state[k] = None
                st.rerun()

    if battle:
        p1_url_val = st.session_state.get("p1_url_input","").strip()
        p2_url_val = st.session_state.get("p2_url_input","").strip()
        p1_ok = ("Saved" in p1_mode and p1_recipe is not None) or ("URL" in p1_mode and p1_url_val)
        p2_ok = ("Saved" in p2_mode and p2_recipe is not None) or ("URL" in p2_mode and p2_url_val)

        if not p1_ok or not p2_ok:
            missing = ([" PLAYER 1"] if not p1_ok else []) + (["PLAYER 2"] if not p2_ok else [])
            st.markdown(f"""
            <div style="border:2px solid #FF6B6B;background:#1A0808;padding:1.2rem;text-align:center;margin-top:1rem;">
                <div style="font-family:'Press Start 2P',monospace;font-size:0.68rem;
                            color:#FF6B6B;letter-spacing:2px;">
                    ✗ SELECT OR ENTER URL FOR:{" &".join(missing)}
                </div>
            </div>""", unsafe_allow_html=True)
        else:
            lc, rc = st.columns(2)
            if "Saved" in p1_mode:
                st.session_state.recipe_left = p1_recipe
                st.session_state.frame_left  = p1_frame
            else:
                with lc:
                    r1, f1 = run_pipeline(p1_url_val, "PLAYER 1")
                    st.session_state.recipe_left = r1
                    st.session_state.frame_left  = f1
            if "Saved" in p2_mode:
                st.session_state.recipe_right = p2_recipe
                st.session_state.frame_right  = p2_frame
            else:
                with rc:
                    r2, f2 = run_pipeline(p2_url_val, "PLAYER 2")
                    st.session_state.recipe_right = r2
                    st.session_state.frame_right  = f2
            st.rerun()

    if has_results:
        r1 = st.session_state.recipe_left
        r2 = st.session_state.recipe_right
        n1 = (r1.get("dish_name","???") if r1 else "???").upper()
        n2 = (r2.get("dish_name","???") if r2 else "???").upper()
        st.markdown(f"""
        <div style="text-align:center;padding:2rem 0 1.5rem;">
            <div style="display:flex;align-items:center;justify-content:center;
                        gap:2.5rem;flex-wrap:wrap;">
                <div style="font-family:'Press Start 2P',monospace;font-size:0.85rem;
                            color:#FF6B35;text-shadow:2px 2px 0 #8B0000;
                            max-width:300px;line-height:1.8;">{n1}</div>
                <div style="font-family:'Press Start 2P',monospace;font-size:1.7rem;
                            color:#FF6B6B;text-shadow:4px 4px 0 #8B0000;">VS</div>
                <div style="font-family:'Press Start 2P',monospace;font-size:0.85rem;
                            color:#4D9EFF;text-shadow:2px 2px 0 #00008B;
                            max-width:300px;line-height:1.8;">{n2}</div>
            </div>
        </div>""", unsafe_allow_html=True)
        lc, rc = st.columns(2)
        with lc:
            _render_battle_panel(r1, "left",  st.session_state.frame_left)
        with rc:
            _render_battle_panel(r2, "right", st.session_state.frame_right)
