import os
import glob
import yt_dlp
from flask import Flask, request, jsonify

app = Flask(__name__)

DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)


def ydl_opts():
    return {
        "format": "(bestvideo[ext=mp4][height<=720]+bestaudio[ext=m4a])/mp4",
        "outtmpl": f"{DOWNLOAD_DIR}/%(id)s.%(ext)s",
        "merge_output_format": "mp4",
        "quiet": True,
        "nocheckcertificate": True,
        "concurrent_fragment_downloads": 1,
        "ratelimit": 3000000,
        "extractor_args": {
            "youtube": {
                "player_client": ["android"],  # ← IMPORTANT
            }
        },
    }


def cached(vid):
    f = glob.glob(f"{DOWNLOAD_DIR}/{vid}.mp4")
    return f[0] if f else None


def search_video(query: str):
    with yt_dlp.YoutubeDL({"quiet": True}) as ydl:
        info = ydl.extract_info(f"ytsearch1:{query}", download=False)
        return info["entries"][0]["webpage_url"]


def download_mp4(link: str):
    with yt_dlp.YoutubeDL(ydl_opts()) as ydl:
        info = ydl.extract_info(link, download=False)
        vid = info["id"]

        cache = cached(vid)
        if cache:
            return cache, info

        ydl.download([link])
        return f"{DOWNLOAD_DIR}/{vid}.mp4", info


@app.route("/play")
def play_song():
    try:
        query = request.args.get("query")
        if not query:
            return jsonify({"error": "No query"}), 400

        url = search_video(query)
        path, info = download_mp4(url)

        return jsonify({
            "title": info.get("title"),
            "duration": info.get("duration"),
            "thumbnail": info.get("thumbnail"),
            "file": path,
            "video_id": info.get("id"),
        })

    except Exception as e:
        import traceback
        return jsonify({
            "error": str(e),
            "trace": traceback.format_exc()
        }), 500


if __name__ == "__main__":
    PORT = int(os.environ.get("PORT", 5000))  # ← Render fix
    app.run(host="0.0.0.0", port=PORT)
