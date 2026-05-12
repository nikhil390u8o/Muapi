import os
import glob
import yt_dlp
from flask import Flask, request, jsonify

app = Flask(__name__)

DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)


def ydl_opts():
    return {
        "format": "best[ext=mp4][height<=720]",
        "outtmpl": f"{DOWNLOAD_DIR}/%(id)s.%(ext)s",
        "quiet": True,
        "nocheckcertificate": True,
        "extractor_args": {
            "youtube": {
                "player_client": ["android"],
                "skip": ["webpage"],
            }
        },
    }


def cached(vid):
    f = glob.glob(f"{DOWNLOAD_DIR}/{vid}.mp4")
    return f[0] if f else None


def search_video(query: str):
    opts = {
        "quiet": True,
        "extractor_args": {
            "youtube": {
                "player_client": ["android"],
                "skip": ["webpage"],
            }
        },
    }

    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(f"ytsearch1:{query}", download=False)

        if "entries" not in info or not info["entries"]:
            raise Exception("No results from ytsearch")

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
    app.run(host="0.0.0.0", port=5000)
