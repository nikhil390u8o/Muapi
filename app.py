from flask import Flask, request, jsonify
import yt_dlp
import os
import requests
import threading
import time

app = Flask(__name__)

# Keep-alive for Render
def keep_alive():
    url = os.environ.get("RENDER_URL", "")
    while True:
        time.sleep(840)
        try:
            if url:
                requests.get(url, timeout=10)
        except:
            pass

threading.Thread(target=keep_alive, daemon=True).start()

# ─── yt-dlp se stream URLs nikalo ────────────────────────────────────────────
def get_stream(query: str):
    ydl_opts = {
        "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best",
        "quiet": True,
        "noplaylist": True,
        "geo_bypass": True,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(f"ytsearch:{query}", download=False)
        track = info["entries"][0]

        formats = track.get("requested_formats") or [track]

        if len(formats) >= 2:
            video_url = formats[0]["url"]
            audio_url = formats[1]["url"]
        else:
            video_url = formats[0]["url"]
            audio_url = formats[0]["url"]

        return {
            "id": track["id"],
            "title": track["title"],
            "duration": track.get("duration", 0),
            "thumbnail": track.get("thumbnail", ""),
            "audio_url": audio_url,
            "video_url": video_url,
        }

# ─── Routes ──────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return {"status": "Music API running 🎵"}

@app.route("/stream")
def stream():
    query = request.args.get("query", "").strip()
    if not query:
        return {"error": "query required"}, 400

    try:
        data = get_stream(query)
        return {
            "id": data["id"],
            "title": data["title"],
            "duration": data["duration"],
            "thumbnail": data["thumbnail"],
            "audio_url": data["audio_url"],   # ← AudioPiped() me daalo
            "video_url": data["video_url"],   # ← VideoPiped() me daalo
        }
    except Exception as e:
        return {"error": str(e)}, 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
