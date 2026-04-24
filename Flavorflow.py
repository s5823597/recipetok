import marimo

__generated_with = "0.23.2"
app = marimo.App(width="full", auto_download=["ipynb"])


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Importing libraries
    """)
    return


@app.cell
def _():
    import marimo as mo
    import yt_dlp
    import whisper
    import json
    import os
    import re
    import subprocess
    import base64
    from groq import Groq
    from transformers import AutoModelForCausalLM, AutoTokenizer
    from dotenv import load_dotenv
    load_dotenv()
    return (
        AutoModelForCausalLM,
        AutoTokenizer,
        Groq,
        base64,
        json,
        mo,
        os,
        re,
        subprocess,
        whisper,
        yt_dlp,
    )


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Setting up Tiktok Url
    """)
    return


@app.cell
def _():
    url = "https://www.tiktok.com/@zachsfoods/video/7595255804333149470" # TikTok video URL
    return (url,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Fetching Video Metadata
    """)
    return


@app.cell
def _(url, yt_dlp):
    with yt_dlp.YoutubeDL({'quiet': True}) as ydl_meta:
        data = ydl_meta.extract_info(url, download=False)
    return (data,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Display Metadata
    """)
    return


@app.cell
def _(data):
    print("Title:", data.get("title", "N/A"))  # video title
    print("Uploader:", data.get("uploader", "N/A"))  # creator name
    print("Description:", data.get("description", "N/A")) # video caption
    print("Duration:", data.get("duration", "N/A"), "seconds") # video length
    print("View count:", data.get("view_count", "N/A"))  # total views
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Download Video and Check for Subtitles
    """)
    return


@app.cell
def _(os, url, yt_dlp):
    os.makedirs("outputs", exist_ok=True)  # create outputs folder if it doesn't exist

    ydl_opts = {
        'writesubtitles': True,
        'subtitleslangs': ['all'],
        'writeautomaticsub': True,
        'outtmpl': 'outputs/%(id)s.%(ext)s',
        'quiet': True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl_dl:
        ydl_dl.download([url])

    video_id = url.split("/")[-1].split("?")[0]  # extract video ID from URL
    video_file = None  # will store video file path
    subtitle_file = None  # will store subtitle file path

    for fname in os.listdir("outputs"):  # loop through downloaded files
        if video_id in fname and fname.endswith(".mp4"):  # find the video file
            video_file = f"outputs/{fname}"
        if video_id in fname and (".vtt" in fname or ".srt" in fname):  # find subtitle file
            subtitle_file = f"outputs/{fname}"

    print("Video:", video_file)  # show video path
    print("Subtitles:", subtitle_file)  # show subtitle path (None if no subs)
    return subtitle_file, video_file


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Extract Speech Text from Subtitles
    """)
    return


@app.cell
def _(subtitle_file, video_file, whisper):
    speech_text = ""

    if subtitle_file:  # subtitles found, use them
        with open(subtitle_file, "r") as sub_file:
            lines = sub_file.readlines()
        for line in lines:  # filter out timestamps and metadata
            line = line.strip()
            if line and not line.startswith("WEBVTT") and "-->" not in line and not line.isdigit():
                speech_text += line + " "
        print("Source: TikTok subtitles")
    elif video_file:  # no subtitles — fall back to Whisper ASR
        print("No subtitles found — running Whisper ASR...")
        whisper_model = whisper.load_model("base")
        whisper_result = whisper_model.transcribe(video_file)
        speech_text = whisper_result["text"]
        print("Source: Whisper ASR")
    else:
        print("No video or subtitles found — cannot extract speech")

    print("\nSpeech text:")
    print(speech_text.strip())
    return (speech_text,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Vision Analysis — Frame Extraction
    """)
    return


@app.cell
def _(Groq, base64, os, subprocess, video_file):
    visual_description = ""

    if video_file:
        frames_dir = f"outputs/frames_{os.path.basename(video_file).split('.')[0]}"
        os.makedirs(frames_dir, exist_ok=True)

        # extract 5 evenly spaced frames using ffmpeg
        subprocess.run([
            "ffmpeg", "-i", video_file,
            "-vf", "fps=1/3", "-vframes", "5",
            f"{frames_dir}/frame_%02d.jpg",
            "-y", "-loglevel", "error"
        ])

        frames = sorted([
            f"{frames_dir}/{f}" for f in os.listdir(frames_dir) if f.endswith(".jpg")
        ])
        print(f"Extracted {len(frames)} frames: {frames}")

        # encode frames as base64 and send to Groq vision model
        groq_api_key = os.environ.get("GROQ_API_KEY", "")
        if groq_api_key and frames:
            groq_client = Groq(api_key=groq_api_key)

            image_content = []
            for frame_path in frames:
                with open(frame_path, "rb") as img_file:
                    b64 = base64.b64encode(img_file.read()).decode("utf-8")
                image_content.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{b64}"}
                })
            image_content.append({
                "type": "text",
                "text": "These are frames from a TikTok cooking video. Describe what ingredients, cooking techniques, and dishes you can see. Be specific and concise."
            })

            vision_response = groq_client.chat.completions.create(
                model="meta-llama/llama-4-scout-17b-16e-instruct",
                messages=[{"role": "user", "content": image_content}],
                max_tokens=512,
            )
            visual_description = vision_response.choices[0].message.content
            print("Visual description:")
            print(visual_description)
        else:
            print("No Groq API key or frames — skipping vision analysis")
    else:
        print("No video file — skipping vision analysis")
    return (visual_description,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Load LLM (Qwen2.5)
    """)
    return


@app.cell
def _(AutoModelForCausalLM, AutoTokenizer):
    model_name = "Qwen/Qwen2.5-1.5B-Instruct"
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModelForCausalLM.from_pretrained(
        model_name,
        device_map="auto",
        torch_dtype="auto"
    )

    print("Model loaded!")
    return model, tokenizer


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Extract Structured Recipe
    """)
    return


@app.cell
def _(data, json, model, re, speech_text, tokenizer, visual_description):
    context = f"""
    Video Title: {data.get("title", "")}
    Video Description: {data.get("description", "")}
    Speech Transcript: {speech_text.strip()}
    Visual Description: {visual_description.strip()}
    """

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

    IMPORTANT: The video may be in any language (Arabic, Malay, Chinese, etc.).
    Always translate and respond entirely in English, regardless of the input language.

    Video Data:
    {context}

    Respond ONLY in valid JSON."""

    messages = [
        {"role": "system", "content": "You are a recipe extraction assistant. Always respond in valid JSON in English only, even if the video is in another language."},
        {"role": "user", "content": prompt}
    ]

    text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    inputs = tokenizer([text], return_tensors="pt").to(model.device)

    output = model.generate(**inputs, max_new_tokens=1024, temperature=0.1, do_sample=True)
    response = tokenizer.decode(output[0][inputs.input_ids.shape[-1]:], skip_special_tokens=True)

    # strip markdown fences and parse JSON
    cleaned_single = re.sub(r'```(?:json)?\s*', '', response).strip()
    try:
        json_match_single = re.search(r'\{.*\}', cleaned_single, re.DOTALL)
        recipe = json.loads(json_match_single.group()) if json_match_single else {}
        if "recipe" in recipe and isinstance(recipe["recipe"], dict):
            recipe = recipe["recipe"]
    except Exception:
        recipe = {}

    print(json.dumps(recipe, indent=2, ensure_ascii=False) if recipe else response)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Test Suite — 4 Languages
    """)
    return


@app.cell
def _():
    test_videos = [
        {"language": "English", "url": "https://www.tiktok.com/@zachsfoods/video/7595255804333149470"},
        {"language": "Malay",   "url": "https://www.tiktok.com/@syiqinazrin/video/7608900115130027284"},
        {"language": "Arabic",  "url": "https://www.tiktok.com/@danahnalshaya/video/7059812099437956354"},
        {"language": "Chinese", "url": "https://www.tiktok.com/@hhfghvgfj/video/7435622193951739154"},
    ]
    return (test_videos,)


@app.cell
def _(os, test_videos, whisper, yt_dlp):
    os.makedirs("outputs", exist_ok=True)

    test_results = []

    for video in test_videos:
        lang = video["language"]
        url_t = video["url"]
        print(f"\n--- {lang} ---")

        # fetch metadata
        with yt_dlp.YoutubeDL({'quiet': True}) as ydl_t:
            meta = ydl_t.extract_info(url_t, download=False)

        # download video + subtitles
        ydl_opts_t = {
            'writesubtitles': True,
            'subtitleslangs': ['all'],
            'writeautomaticsub': True,
            'outtmpl': 'outputs/%(id)s.%(ext)s',
            'quiet': True,
        }
        with yt_dlp.YoutubeDL(ydl_opts_t) as ydl_t2:
            ydl_t2.download([url_t])

        video_id_t = url_t.split("/")[-1].split("?")[0]
        video_file_t = None
        subtitle_file_t = None
        for fname_t in os.listdir("outputs"):
            if video_id_t in fname_t and fname_t.endswith(".mp4"):
                video_file_t = f"outputs/{fname_t}"
            if video_id_t in fname_t and (".vtt" in fname_t or ".srt" in fname_t):
                subtitle_file_t = f"outputs/{fname_t}"

        # extract speech
        speech_t = ""
        if subtitle_file_t:
            with open(subtitle_file_t, "r") as sf:
                for line_t in sf.readlines():
                    line_t = line_t.strip()
                    if line_t and not line_t.startswith("WEBVTT") and "-->" not in line_t and not line_t.isdigit():
                        speech_t += line_t + " "
            source_t = "subtitles"
        elif video_file_t:
            whisper_model_t = whisper.load_model("base")
            speech_t = whisper_model_t.transcribe(video_file_t)["text"]
            source_t = "whisper"
        else:
            source_t = "none"

        print(f"Speech source: {source_t}")
        print(f"Title: {meta.get('title', 'N/A')}")
        print(f"Speech preview: {speech_t.strip()[:200]}")

        test_results.append({
            "language": lang,
            "url": url_t,
            "title": meta.get("title", ""),
            "speech_source": source_t,
            "speech_text": speech_t.strip(),
            "description": meta.get("description", ""),
        })

    print("\nAll videos processed.")
    return (test_results,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Evaluation — Scoring Table
    """)
    return


@app.cell
def _(json, mo, model, re, test_results, tokenizer):
    eval_rows = []

    for test_result in test_results:
        context_e = f"""
        Video Title: {test_result['title']}
        Video Description: {test_result['description']}
        Speech Transcript: {test_result['speech_text'][:500]}
        """

        prompt_e = f"""You are a recipe extraction AI. Analyse the following TikTok video data and:

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

        IMPORTANT: The video may be in any language. Always translate and respond entirely in English.

        Video Data:
        {context_e}

        Respond ONLY in valid JSON."""

        messages_e = [
            {"role": "system", "content": "You are a recipe extraction assistant. Always respond in valid JSON in English only."},
            {"role": "user", "content": prompt_e}
        ]

        text_e = tokenizer.apply_chat_template(messages_e, tokenize=False, add_generation_prompt=True)
        inputs_e = tokenizer([text_e], return_tensors="pt").to(model.device)
        output_e = model.generate(**inputs_e, max_new_tokens=1024, temperature=0.1, do_sample=True)
        response_e = tokenizer.decode(output_e[0][inputs_e.input_ids.shape[-1]:], skip_special_tokens=True)

        try:
            cleaned_e = re.sub(r'```(?:json)?\s*', '', response_e).strip()
            json_match_e = re.search(r'\{.*\}', cleaned_e, re.DOTALL)
            recipe_e = json.loads(json_match_e.group()) if json_match_e else {}
            if "recipe" in recipe_e and isinstance(recipe_e["recipe"], dict):
                recipe_e = recipe_e["recipe"]
        except Exception:
            recipe_e = {}

        print(f"[{test_result['language']}] raw response preview: {response_e[:200]}")
        print(f"[{test_result['language']}] parsed recipe keys: {list(recipe_e.keys())}")

        dish_ok  = bool(str(recipe_e.get("dish_name", "")).strip())
        ingr_ok  = len(recipe_e.get("ingredients", [])) >= 2
        steps_ok = len(recipe_e.get("steps", [])) >= 2
        score    = sum([dish_ok, ingr_ok, steps_ok])

        eval_rows.append({
            "Language":      test_result["language"],
            "Dish Name":     recipe_e.get("dish_name", "—"),
            "Dish ✓":        "✓" if dish_ok  else "✗",
            "Ingredients ✓": "✓" if ingr_ok  else "✗",
            "Steps ✓":       "✓" if steps_ok else "✗",
            "Score":         f"{score}/3",
        })

    eval_table = mo.ui.table(eval_rows)
    return (eval_table,)


@app.cell
def _(eval_table):
    eval_table
    return


if __name__ == "__main__":
    app.run()
