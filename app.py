from flask import Flask, request, jsonify
from yt_dlp import YoutubeDL

app = Flask(__name__)

YDL_OPTS = {
    "quiet": True,
    "noplaylist": True,
    # IMPORTANT: pre-merged progressive mp4 lo (no JS merge headache)
    "format": "best[ext=mp4][protocol=https]/best",
    # ye 2 options YouTube anti-bot ko avoid karte
    "extractor_args": {
        "youtube": {
            "player_client": ["android", "web"]
        }
    },
}

def extract(query: str):
    with YoutubeDL(YDL_OPTS) as ydl:
        info = ydl.extract_info(f"ytsearch:{query}", download=False)
        v = info["entries"][0]

        return {
            "id": v.get("id"),
            "title": v.get("title"),
            "duration": v.get("duration"),
            "thumbnail": v.get("thumbnail"),
            # progressive mp4 → same URL audio/video dono me chalega
            "audio_url": v.get("url"),
            "video_url": v.get("url"),
        }

@app.route("/")
def home():
    return {"status": "music api running"}

@app.route("/stream")
def stream():
    q = request.args.get("query", "").strip()
    if not q:
        return jsonify({"error": "query required"}), 400
    try:
        return jsonify(extract(q))
    except Exception as e:
        return jsonify({"error": str(e)}), 500
