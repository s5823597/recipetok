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
    import json # lets Python read JSON data (yt-dlp returns data in JSON format)
    import os # lets Phyton interact with the file system — create folders, list files, check if files exist, get file paths.
    from groq import Groq

    return mo, os, yt_dlp


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

    for f in os.listdir("outputs"):  # loop through downloaded files
        if video_id in f and f.endswith(".mp4"):  # find the video file
            video_file = f"outputs/{f}"
        if video_id in f and (".vtt" in f or ".srt" in f):  # find subtitle file
            subtitle_file = f"outputs/{f}"

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
def _(subtitle_file, video_file):
    import whisper

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
        result = whisper_model.transcribe(video_file)
        speech_text = result["text"]
        print("Source: Whisper ASR")
    else:
        print("No video or subtitles found — cannot extract speech")

    print("\nSpeech text:")
    print(speech_text.strip())
    return (speech_text,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Load LLM (Qwen2.5)
    """)
    return


@app.cell
def _():
    from transformers import AutoModelForCausalLM, AutoTokenizer

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
def _(data, model, speech_text, tokenizer):
    context = f"""
    Video Title: {data.get("title", "")}
    Video Description: {data.get("description", "")}
    Speech Transcript: {speech_text.strip()}
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

    Video Data:
    {context}

    Respond ONLY in valid JSON."""

    messages = [
        {"role": "system", "content": "You are a recipe extraction assistant. Always respond in valid JSON only."},
        {"role": "user", "content": prompt}
    ]

    text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    inputs = tokenizer([text], return_tensors="pt").to(model.device)

    output = model.generate(**inputs, max_new_tokens=1024, temperature=0.1, do_sample=True)
    response = tokenizer.decode(output[0][inputs.input_ids.shape[-1]:], skip_special_tokens=True)

    print(response)
    return


@app.cell
def _():
    return


if __name__ == "__main__":
    app.run()
