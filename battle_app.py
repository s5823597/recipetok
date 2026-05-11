import streamlit as st
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

st.set_page_config(
    page_title="FlavourFlow Battle",
    page_icon="⚔️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

for _k, _v in {
    "recipe_left": None,
    "recipe_right": None,
    "frame_left": None,
    "frame_right": None,
}.items():
    if _k not in st.session_state:
        st.session_state[_k] = _v

# ── CSS ────────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Press+Start+2P&family=Inter:wght@400;500;600;700&display=swap');

.stApp {
    background: #0A0A1A !important;
    color: #E8E8E8 !important;
    font-family: 'Inter', sans-serif !important;
}

/* CRT scanlines */
.stApp::before {
    content: '';
    position: fixed;
    top: 0; left: 0; right: 0; bottom: 0;
    background: repeating-linear-gradient(
        0deg, transparent, transparent 3px,
        rgba(0,0,0,0.04) 3px, rgba(0,0,0,0.04) 4px
    );
    pointer-events: none;
    z-index: 9999;
}

/* Pixel button */
div[data-testid="stButton"] > button {
    background: #FFD700 !important;
    color: #0A0A1A !important;
    border: 3px solid #B8860B !important;
    border-radius: 0 !important;
    font-family: 'Press Start 2P', monospace !important;
    font-size: 0.85rem !important;
    box-shadow: 5px 5px 0px #8B6508 !important;
    transition: all 0.08s !important;
    text-transform: uppercase !important;
    padding: 1rem 1.2rem !important;
    width: 100% !important;
    letter-spacing: 1px !important;
    cursor: pointer !important;
}
div[data-testid="stButton"] > button:hover {
    transform: translate(2px, 2px) !important;
    box-shadow: 3px 3px 0px #8B6508 !important;
    background: #FFC400 !important;
}
div[data-testid="stButton"] > button:active {
    transform: translate(5px, 5px) !important;
    box-shadow: 0px 0px 0px #8B6508 !important;
}

/* Text input */
div[data-testid="stTextInput"] input {
    background: #0D0D2B !important;
    border: 2px solid #4A4A8A !important;
    border-radius: 0 !important;
    color: #E8E8FF !important;
    font-family: 'Inter', sans-serif !important;
    font-size: 1rem !important;
    padding: 0.75rem 1.1rem !important;
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
    font-size: 0.65rem !important;
    color: #666 !important;
    letter-spacing: 3px !important;
}

/* Hide chrome */
#MainMenu { visibility: hidden; }
footer    { visibility: hidden; }
header    { visibility: hidden; }

div[data-testid="stHorizontalBlock"] { gap: 1.5rem; }

::-webkit-scrollbar       { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: #0A0A1A; }
::-webkit-scrollbar-thumb { background: #4A4A8A; }
::-webkit-scrollbar-thumb:hover { background: #FFD700; }

hr { border-color: #2A2A4A; }
</style>
""", unsafe_allow_html=True)


# ── Ingredient type system ──────────────────────────────────────────────────────

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
    "garlic": "🧄", "onion": "🧅", "tomato": "🍅", "carrot": "🥕",
    "chilli": "🌶️", "chili": "🌶️", "pepper": "🫑", "egg": "🥚",
    "chicken": "🍗", "beef": "🥩", "pork": "🥩", "fish": "🐟",
    "salmon": "🐟", "tuna": "🐟", "shrimp": "🍤", "prawn": "🍤",
    "rice": "🍚", "noodle": "🍜", "pasta": "🍝", "bread": "🍞",
    "cheese": "🧀", "butter": "🧈", "milk": "🥛", "cream": "🥛",
    "salt": "🧂", "oil": "🫙", "soy": "🫙", "honey": "🍯",
    "lemon": "🍋", "lime": "🍋", "ginger": "🫚", "potato": "🥔",
    "mushroom": "🍄", "corn": "🌽", "broccoli": "🥦", "spinach": "🥬",
    "avocado": "🥑", "cucumber": "🥒", "lettuce": "🥗", "tofu": "🫙",
    "flour": "🌾", "sugar": "🍬", "vinegar": "🫙", "stock": "🥣",
    "broth": "🥣", "wine": "🍷", "water": "💧", "basil": "🌿",
    "coriander": "🌿", "thyme": "🌿", "parsley": "🌿", "mint": "🌿",
    "spring onion": "🌱", "scallion": "🌱", "sesame": "✨",
    "lamb": "🥩", "turkey": "🍗", "bacon": "🥓", "sausage": "🌭",
    "coconut": "🥥", "peanut": "🥜",
}


def _classify(name: str) -> str:
    n = name.lower()
    if any(k in n for k in ["chicken","beef","pork","fish","salmon","tuna","shrimp","prawn","egg","tofu","lamb","meat","turkey","bacon","sausage","mince","steak","cod","seabass"]):
        return "protein"
    if any(k in n for k in ["onion","garlic","tomato","pepper","carrot","broccoli","spinach","ginger","mushroom","potato","celery","leek","chilli","chili","bell","zucchini","cucumber","lettuce","cabbage","kale","spring onion","scallion","bok choy","aubergine","eggplant","courgette","sweet potato","capsicum"]):
        return "vegetable"
    if any(k in n for k in ["salt","cumin","turmeric","paprika","coriander powder","oregano","thyme","bay leaf","cardamom","cinnamon","clove","fennel","nutmeg","curry powder","chilli flake","chili flake","star anise","msg","seasoning","spice","herb"]):
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


# ── Pipeline ────────────────────────────────────────────────────────────────────

def _fetch_meta(url):
    with yt_dlp.YoutubeDL({"quiet": True}) as ydl:
        return ydl.extract_info(url, download=False)


def _download(url):
    os.makedirs("outputs", exist_ok=True)
    opts = {
        "writesubtitles": True, "subtitleslangs": ["all"],
        "writeautomaticsub": True, "outtmpl": "outputs/%(id)s.%(ext)s", "quiet": True,
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        ydl.download([url])
    vid_id = url.split("/")[-1].split("?")[0]
    vf = sf = None
    for fn in os.listdir("outputs"):
        if vid_id in fn and fn.endswith(".mp4"):
            vf = f"outputs/{fn}"
        if vid_id in fn and (".vtt" in fn or ".srt" in fn):
            sf = f"outputs/{fn}"
    return vf, sf


def _speech(sf, vf):
    if sf:
        text = ""
        with open(sf) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("WEBVTT") and "-->" not in line and not line.isdigit():
                    text += line + " "
        return text.strip()
    if vf:
        return whisper.load_model("base").transcribe(vf)["text"].strip()
    return ""


def _vision(vf):
    if not vf or not GROQ_API_KEY:
        return "", None
    fd = f"outputs/frames_{os.path.basename(vf).split('.')[0]}"
    os.makedirs(fd, exist_ok=True)
    subprocess.run(
        ["ffmpeg", "-i", vf, "-vf", "fps=1/3", "-vframes", "5",
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
    content.append({"type": "text", "text": "Describe ingredients, cooking techniques, and dishes visible in these TikTok cooking video frames. Be specific and concise."})
    client = Groq(api_key=GROQ_API_KEY)
    resp = client.chat.completions.create(
        model="meta-llama/llama-4-scout-17b-16e-instruct",
        messages=[{"role": "user", "content": content}],
        max_tokens=512,
    )
    return resp.choices[0].message.content, fd


def _extract_recipe(meta, speech, visual):
    client = Groq(api_key=GROQ_API_KEY)
    ctx = (
        f"Video Title: {meta.get('title','')}\n"
        f"Video Description: {meta.get('description','')}\n"
        f"Speech Transcript: {speech}\n"
        f"Visual Description: {visual}"
    )
    prompt = f"""You are a recipe extraction AI. Analyse this TikTok video data and return a JSON recipe with exactly these fields:
- dish_name
- cuisine_type
- difficulty (easy/medium/hard)
- prep_time
- cook_time
- servings
- ingredients (list of {{"quantity": "...", "item": "..."}} objects)
- steps (list of strings)
- allergens (list from: Gluten, Dairy, Eggs, Nuts, Peanuts, Soy, Shellfish, Fish, Sesame — only if confident)
- dietary (list from: Vegetarian, Vegan, Gluten-Free, Dairy-Free, Halal, Contains Nuts — only if confident)
- price_estimate_gbp: {{"min": <integer>, "max": <integer>}} — estimated total ingredient cost in GBP at a UK supermarket (Tesco/Sainsbury's/ASDA) for the stated quantities

Translate ALL field values to English. Respond ONLY with valid JSON.

Video Data:
{ctx}"""
    resp = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": "You are a recipe extraction assistant. Always respond in valid JSON in English only."},
            {"role": "user", "content": prompt},
        ],
        max_tokens=1400,
        temperature=0.1,
    )
    raw = re.sub(r"```(?:json)?\s*", "", resp.choices[0].message.content).strip()
    try:
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        recipe = json.loads(match.group()) if match else {}
        if "recipe" in recipe and isinstance(recipe["recipe"], dict):
            recipe = recipe["recipe"]
    except Exception:
        recipe = {}
    return recipe


def _frame_b64(fd):
    if not fd or not os.path.exists(fd):
        return None
    frames = sorted([f for f in os.listdir(fd) if f.endswith(".jpg")])
    if not frames:
        return None
    mid = frames[len(frames) // 2]
    with open(f"{fd}/{mid}", "rb") as f:
        return base64.b64encode(f.read()).decode()


def run_pipeline(url: str, player: str):
    ph = st.empty()

    def status(step, total, msg, ok=True):
        pct = int((step / total) * 100)
        bar = "█" * (pct // 5) + "░" * (20 - pct // 5)
        color = "#51CF66" if ok else "#FF6B6B"
        ph.markdown(f"""
        <div style="border:2px solid #2A2A4A;background:#08080F;padding:1.2rem 1.4rem;">
            <div style="font-family:'Press Start 2P',monospace;font-size:0.65rem;
                        color:#555;letter-spacing:2px;margin-bottom:0.7rem;">
                {player} PIPELINE
            </div>
            <div style="font-family:'Press Start 2P',monospace;font-size:0.7rem;
                        color:{color};margin-bottom:0.7rem;">{msg}</div>
            <div style="font-family:'Press Start 2P',monospace;font-size:0.65rem;
                        color:#4A4A8A;">[{bar}] {pct}%</div>
        </div>""", unsafe_allow_html=True)

    try:
        status(0, 5, "FETCHING METADATA...")
        meta = _fetch_meta(url)
        status(1, 5, "DOWNLOADING VIDEO...")
        vf, sf = _download(url)
        status(2, 5, "EXTRACTING SPEECH...")
        speech = _speech(sf, vf)
        status(3, 5, "VISION AI ANALYSIS...")
        visual, fd = _vision(vf) if vf else ("", None)
        status(4, 5, "EXTRACTING RECIPE...")
        recipe = _extract_recipe(meta, speech, visual)
        status(5, 5, "DONE!", ok=True)
        return recipe, _frame_b64(fd) if fd else None
    except Exception as e:
        status(0, 5, f"ERROR: {str(e)[:40]}", ok=False)
        return None, None


# ── Render helpers ──────────────────────────────────────────────────────────────

def _ing_card(ing) -> str:
    if isinstance(ing, dict):
        qty  = ing.get("quantity", "")
        name = ing.get("item", "Unknown")
    else:
        qty  = ""
        name = str(ing)
    t    = _classify(name)
    cfg  = _TYPES[t]
    em   = _emoji(name)
    dname = (name[:14] + "…") if len(name) > 14 else name
    dqty  = (qty[:12]  + "…") if len(qty)  > 12 else qty
    return f"""
    <div style="background:{cfg['bg']};border:2px solid {cfg['color']};
                box-shadow:4px 4px 0px {cfg['color']}44;
                padding:1rem 0.7rem;text-align:center;width:120px;flex-shrink:0;
                display:inline-flex;flex-direction:column;align-items:center;gap:0.4rem;">
        <div style="font-size:2.2rem;line-height:1;">{em}</div>
        <div style="font-family:'Press Start 2P',monospace;font-size:0.5rem;
                    color:{cfg['color']};letter-spacing:1px;">{cfg['label']}</div>
        <div style="font-size:0.85rem;color:#E8E8E8;font-weight:600;
                    line-height:1.3;word-break:break-word;">{dname}</div>
        <div style="font-size:0.78rem;color:#666;">{dqty or "—"}</div>
    </div>"""


def _render_panel(recipe, side: str, frame_b64=None):
    if not recipe:
        st.markdown("""
        <div style="border:2px solid #2A2A4A;padding:5rem;text-align:center;">
            <div style="font-family:'Press Start 2P',monospace;font-size:0.8rem;color:#2A2A4A;">
                NO DATA
            </div>
        </div>""", unsafe_allow_html=True)
        return

    border = "#FF6B35" if side == "left" else "#4D9EFF"
    label  = "◀ PLAYER 1" if side == "left" else "PLAYER 2 ▶"

    dish      = recipe.get("dish_name", "Unknown")
    cuisine   = recipe.get("cuisine_type", "—")
    diff      = str(recipe.get("difficulty", "—")).lower()
    prep_t    = recipe.get("prep_time", "—")
    cook_t    = recipe.get("cook_time", "—")
    servings  = recipe.get("servings", "—")
    ings      = recipe.get("ingredients", [])
    steps     = recipe.get("steps", [])
    price     = recipe.get("price_estimate_gbp", {})
    allergens = recipe.get("allergens", [])
    dietary   = recipe.get("dietary", [])

    diff_col  = {"easy": "#51CF66", "medium": "#FFD43B", "hard": "#FF6B6B"}.get(diff, "#868E96")
    diff_star = {"easy": "★☆☆", "medium": "★★☆", "hard": "★★★"}.get(diff, "?")
    p_min = price.get("min", "?") if isinstance(price, dict) else "?"
    p_max = price.get("max", "?") if isinstance(price, dict) else "?"

    # Thumbnail
    if frame_b64:
        st.markdown(f"""
        <div style="border:3px solid {border};box-shadow:5px 5px 0px {border}44;
                    overflow:hidden;margin-bottom:1rem;height:220px;">
            <img src="data:image/jpeg;base64,{frame_b64}"
                 style="width:100%;height:220px;object-fit:cover;display:block;">
        </div>""", unsafe_allow_html=True)

    # Title card
    st.markdown(f"""
    <div style="border:3px solid {border};box-shadow:5px 5px 0px {border}44;
                background:#0D0D2B;padding:1.3rem;margin-bottom:1rem;">
        <div style="font-family:'Press Start 2P',monospace;font-size:0.65rem;
                    color:{border};letter-spacing:3px;margin-bottom:0.8rem;">{label}</div>
        <div style="font-family:'Press Start 2P',monospace;font-size:1rem;
                    color:#FFD700;text-shadow:2px 2px 0px #8B6508;
                    line-height:1.8;word-break:break-word;">{dish.upper()}</div>
        <div style="font-size:0.95rem;color:#666;margin-top:0.5rem;font-style:italic;">{cuisine}</div>
    </div>""", unsafe_allow_html=True)

    # Stats grid
    st.markdown(f"""
    <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:3px;margin-bottom:1rem;">
        <div style="background:#0D0D2B;border:2px solid #2A2A4A;padding:0.9rem 0.3rem;text-align:center;">
            <div style="font-family:'Press Start 2P',monospace;font-size:0.52rem;color:#555;margin-bottom:0.4rem;">PREP</div>
            <div style="font-size:0.9rem;color:#CCC;font-weight:600;line-height:1.4;">{prep_t}</div>
        </div>
        <div style="background:#0D0D2B;border:2px solid #2A2A4A;padding:0.9rem 0.3rem;text-align:center;">
            <div style="font-family:'Press Start 2P',monospace;font-size:0.52rem;color:#555;margin-bottom:0.4rem;">COOK</div>
            <div style="font-size:0.9rem;color:#CCC;font-weight:600;line-height:1.4;">{cook_t}</div>
        </div>
        <div style="background:#0D0D2B;border:2px solid #2A2A4A;padding:0.9rem 0.3rem;text-align:center;">
            <div style="font-family:'Press Start 2P',monospace;font-size:0.52rem;color:#555;margin-bottom:0.4rem;">SERVES</div>
            <div style="font-size:0.9rem;color:#CCC;font-weight:600;">{servings}</div>
        </div>
        <div style="background:#0D0D2B;border:2px solid #2A2A4A;padding:0.9rem 0.3rem;text-align:center;">
            <div style="font-family:'Press Start 2P',monospace;font-size:0.52rem;color:{diff_col};margin-bottom:0.4rem;">LEVEL</div>
            <div style="font-size:0.9rem;color:{diff_col};font-weight:700;">{diff_star}</div>
        </div>
    </div>""", unsafe_allow_html=True)

    # Price badge
    st.markdown(f"""
    <div style="border:3px solid #FFD700;background:#0D0D00;
                box-shadow:4px 4px 0px #8B6508;
                padding:0.9rem 1.3rem;margin-bottom:1rem;
                display:flex;align-items:center;justify-content:space-between;">
        <div>
            <div style="font-family:'Press Start 2P',monospace;font-size:0.6rem;
                        color:#B8860B;letter-spacing:2px;margin-bottom:0.3rem;">💷 EST. UK COST</div>
            <div style="font-size:0.82rem;color:#555;">supermarket estimate</div>
        </div>
        <div style="font-family:'Press Start 2P',monospace;font-size:1.2rem;
                    color:#FFD700;text-shadow:2px 2px 0px #8B6508;">
            £{p_min}–£{p_max}
        </div>
    </div>""", unsafe_allow_html=True)

    # Allergen & dietary badges
    if allergens or dietary:
        badges = "".join(
            f'<span style="background:#1A0505;border:1px solid #FF6B6B;color:#FF6B6B;'
            f'padding:4px 12px;font-size:0.82rem;font-weight:600;border-radius:2px;">⚠ {a}</span>'
            for a in allergens
        ) + "".join(
            f'<span style="background:#051A08;border:1px solid #51CF66;color:#51CF66;'
            f'padding:4px 12px;font-size:0.82rem;font-weight:600;border-radius:2px;">✓ {d}</span>'
            for d in dietary
        )
        st.markdown(
            f'<div style="display:flex;flex-wrap:wrap;gap:0.4rem;margin-bottom:1rem;">{badges}</div>',
            unsafe_allow_html=True,
        )

    # Ingredient cards
    if ings:
        st.markdown("""
        <div style="font-family:'Press Start 2P',monospace;font-size:0.6rem;
                    color:#555;letter-spacing:3px;margin-bottom:0.8rem;margin-top:0.5rem;">
            ── INGREDIENTS ──
        </div>""", unsafe_allow_html=True)
        cards = '<div style="display:flex;flex-wrap:wrap;gap:0.6rem;margin-bottom:1.2rem;">'
        for ing in ings:
            cards += _ing_card(ing)
        cards += "</div>"
        st.markdown(cards, unsafe_allow_html=True)

    # Cooking steps
    if steps:
        st.markdown("""
        <div style="font-family:'Press Start 2P',monospace;font-size:0.6rem;
                    color:#555;letter-spacing:3px;margin-bottom:0.8rem;">
            ── COOKING METHOD ──
        </div>""", unsafe_allow_html=True)
        rows = "".join(f"""
        <div style="display:flex;gap:1rem;padding:0.8rem 0;
                    border-bottom:1px solid #1A1A2A;align-items:flex-start;">
            <div style="font-family:'Press Start 2P',monospace;font-size:0.65rem;
                        color:{border};min-width:28px;flex-shrink:0;margin-top:4px;">
                {str(i).zfill(2)}
            </div>
            <div style="font-size:0.95rem;color:#CCC;line-height:1.7;">{step}</div>
        </div>""" for i, step in enumerate(steps, 1))
        st.markdown(
            f'<div style="border:2px solid #2A2A4A;background:#08080F;padding:1rem;">{rows}</div>',
            unsafe_allow_html=True,
        )


# ── Main UI ─────────────────────────────────────────────────────────────────────

st.markdown("""
<div style="text-align:center;padding:3rem 0 2rem;">
    <div style="font-family:'Press Start 2P',monospace;font-size:0.8rem;
                color:#3A3A6A;letter-spacing:4px;margin-bottom:1rem;">
        ★ FLAVOURFLOW PRESENTS ★
    </div>
    <div style="font-family:'Press Start 2P',monospace;font-size:2.8rem;
                color:#FFD700;text-shadow:5px 5px 0px #8B6508,10px 10px 0px #3D2B00;
                line-height:1.4;letter-spacing:2px;">
        RECIPE<br>BATTLE!
    </div>
    <div style="font-family:'Press Start 2P',monospace;font-size:0.7rem;
                color:#3A3A6A;letter-spacing:3px;margin-top:1.5rem;line-height:2.5;">
        PASTE 2 TIKTOK URLS · COMPARE RECIPES · FIND YOUR CHAMPION
    </div>
</div>
""", unsafe_allow_html=True)

# URL inputs
c1, vs_c, c2 = st.columns([5, 1, 5])
with c1:
    url1 = st.text_input("PLAYER 1 URL", placeholder="https://tiktok.com/@.../video/...", key="url1")
with vs_c:
    st.markdown("""
    <div style="display:flex;align-items:center;justify-content:center;height:100%;padding-top:2rem;">
        <div style="font-family:'Press Start 2P',monospace;font-size:1.5rem;
                    color:#FF6B6B;text-shadow:4px 4px 0px #8B0000;">VS</div>
    </div>""", unsafe_allow_html=True)
with c2:
    url2 = st.text_input("PLAYER 2 URL", placeholder="https://tiktok.com/@.../video/...", key="url2")

# Buttons
b1, b2, b3 = st.columns([2, 3, 2])
with b2:
    st.markdown("<div style='margin-top:0.6rem;'>", unsafe_allow_html=True)
    battle = st.button("⚔  BATTLE!", use_container_width=True)
    st.markdown("</div>", unsafe_allow_html=True)

has_results = st.session_state.recipe_left or st.session_state.recipe_right
if has_results:
    with b1:
        if st.button("✕  CLEAR", use_container_width=True):
            st.session_state.recipe_left  = None
            st.session_state.recipe_right = None
            st.session_state.frame_left   = None
            st.session_state.frame_right  = None
            st.rerun()

st.markdown('<hr style="border-color:#2A2A4A;margin:1.8rem 0;">', unsafe_allow_html=True)

# ── Validation ──────────────────────────────────────────────────────────────────
if battle and not (url1.strip() and url2.strip()):
    st.markdown("""
    <div style="border:2px solid #FF6B6B;background:#1A0808;padding:1.2rem;text-align:center;">
        <div style="font-family:'Press Start 2P',monospace;font-size:0.8rem;
                    color:#FF6B6B;letter-spacing:2px;">
            ✗ ENTER BOTH URLS TO BATTLE!
        </div>
    </div>""", unsafe_allow_html=True)

# ── Battle execution ────────────────────────────────────────────────────────────
elif battle and url1.strip() and url2.strip():
    left_col, right_col = st.columns(2)
    with left_col:
        r1, f1 = run_pipeline(url1.strip(), "PLAYER 1")
        st.session_state.recipe_left = r1
        st.session_state.frame_left  = f1
    with right_col:
        r2, f2 = run_pipeline(url2.strip(), "PLAYER 2")
        st.session_state.recipe_right = r2
        st.session_state.frame_right  = f2
    st.rerun()

# ── Battle results ──────────────────────────────────────────────────────────────
elif has_results:
    r1 = st.session_state.recipe_left
    r2 = st.session_state.recipe_right
    n1 = (r1.get("dish_name", "???") if r1 else "???").upper()
    n2 = (r2.get("dish_name", "???") if r2 else "???").upper()

    st.markdown(f"""
    <div style="text-align:center;margin-bottom:2rem;">
        <div style="display:flex;align-items:center;justify-content:center;
                    gap:2rem;flex-wrap:wrap;">
            <div style="font-family:'Press Start 2P',monospace;font-size:0.9rem;
                        color:#FF6B35;text-shadow:2px 2px 0px #8B0000;
                        max-width:300px;line-height:1.8;">{n1}</div>
            <div style="font-family:'Press Start 2P',monospace;font-size:1.8rem;
                        color:#FF6B6B;text-shadow:4px 4px 0px #8B0000;">VS</div>
            <div style="font-family:'Press Start 2P',monospace;font-size:0.9rem;
                        color:#4D9EFF;text-shadow:2px 2px 0px #00008B;
                        max-width:300px;line-height:1.8;">{n2}</div>
        </div>
    </div>""", unsafe_allow_html=True)

    lc, rc = st.columns(2)
    with lc:
        _render_panel(r1, "left",  st.session_state.frame_left)
    with rc:
        _render_panel(r2, "right", st.session_state.frame_right)

# ── Welcome screen ──────────────────────────────────────────────────────────────
else:
    st.markdown("""
    <div style="text-align:center;padding:3rem 0 2.5rem;">
        <div style="font-size:3rem;margin-bottom:2rem;">🍳 ⚔️ 🍜</div>
        <div style="font-family:'Press Start 2P',monospace;font-size:0.65rem;
                    color:#3A3A6A;letter-spacing:2px;line-height:3;max-width:560px;margin:0 auto;">
            PASTE TWO TIKTOK COOKING<br>
            VIDEO URLS ABOVE AND<br>
            PRESS BATTLE! TO COMPARE<br>
            RECIPES HEAD-TO-HEAD
        </div>
    </div>

    <div style="display:flex;justify-content:center;flex-wrap:wrap;gap:1rem;
                max-width:800px;margin:0 auto 2rem;">
        <div style="border:2px solid #FF6B6B;background:#1A0808;padding:0.9rem 1.3rem;
                    font-family:'Press Start 2P',monospace;font-size:0.58rem;
                    color:#FF6B6B;letter-spacing:2px;">🥩 PROTEIN</div>
        <div style="border:2px solid #51CF66;background:#081A0A;padding:0.9rem 1.3rem;
                    font-family:'Press Start 2P',monospace;font-size:0.58rem;
                    color:#51CF66;letter-spacing:2px;">🥦 VEGGIE</div>
        <div style="border:2px solid #FFD43B;background:#1A1500;padding:0.9rem 1.3rem;
                    font-family:'Press Start 2P',monospace;font-size:0.58rem;
                    color:#FFD43B;letter-spacing:2px;">✨ SPICE</div>
        <div style="border:2px solid #74C0FC;background:#081020;padding:0.9rem 1.3rem;
                    font-family:'Press Start 2P',monospace;font-size:0.58rem;
                    color:#74C0FC;letter-spacing:2px;">🧀 DAIRY</div>
        <div style="border:2px solid #E8A44A;background:#1A0E00;padding:0.9rem 1.3rem;
                    font-family:'Press Start 2P',monospace;font-size:0.58rem;
                    color:#E8A44A;letter-spacing:2px;">🌾 GRAIN</div>
        <div style="border:2px solid #CC5DE8;background:#120820;padding:0.9rem 1.3rem;
                    font-family:'Press Start 2P',monospace;font-size:0.58rem;
                    color:#CC5DE8;letter-spacing:2px;">🫙 SAUCE</div>
    </div>
    """, unsafe_allow_html=True)
