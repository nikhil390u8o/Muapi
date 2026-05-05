from flask import Flask, request, jsonify
import requests
import urllib.parse
import re

app = Flask(__name__)

def get_youtube_url(query):
    instances = [
        "https://inv.tux.pizza",
        "https://invidious.nerdvpn.de", 
        "https://invidious.privacydev.net",
        "https://yt.cdaut.de",
    ]
    for instance in instances:
        try:
            resp = requests.get(
                f"{instance}/api/v1/search",
                params={"q": query, "type": "video"},
                timeout=8
            )
            if resp.status_code == 200:
                results = resp.json()
                if results and isinstance(results, list):
                    video_id = results[0].get('videoId')
                    if video_id:
                        return f"https://www.youtube.com/watch?v={video_id}", video_id
        except:
            continue

    # Fallback: YouTube scrape
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        encoded = urllib.parse.quote(query)
        resp = requests.get(
            f"https://www.youtube.com/results?search_query={encoded}",
            headers=headers, timeout=10
        )
        ids = re.findall(r'"videoId":"([a-zA-Z0-9_-]{11})"', resp.text)
        if ids:
            return f"https://www.youtube.com/watch?v={ids[0]}", ids[0]
    except:
        pass

    return None, None

@app.route('/query')
def query():
    q = request.args.get('q', '')
    if not q:
        return jsonify({"error": "q parameter missing"}), 400

    yt_url, video_id = get_youtube_url(q)
    if not yt_url:
        return jsonify({"error": "No video found"}), 404

    # Thumbnail URLs (multiple quality)
    thumbnails = {
        "default": f"https://img.youtube.com/vi/{video_id}/default.jpg",
        "medium":  f"https://img.youtube.com/vi/{video_id}/mqdefault.jpg",
        "high":    f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg",
        "max":     f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg",
    }

    # MP4 (video)
    mp4_data = {}
    try:
        resp = requests.get(
            "https://youtube.anshppt19.workers.dev/anshapi",
            params={"url": yt_url, "format": "mp4hd"},
            timeout=30
        )
        mp4_data = resp.json().get("data", {})
    except:
        pass

    # MP3 (audio)
    mp3_data = {}
    try:
        resp = requests.get(
            "https://youtube.anshppt19.workers.dev/anshapi",
            params={"url": yt_url, "format": "mp3"},
            timeout=30
        )
        mp3_data = resp.json().get("data", {})
    except:
        pass

    return jsonify({
        "success": True,
        "yt_url": yt_url,
        "video_id": video_id,
        "thumbnails": thumbnails,
        "video": mp4_data,
        "audio": mp3_data
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000)
