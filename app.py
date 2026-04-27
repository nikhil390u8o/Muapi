from fastapi import FastAPI, HTTPException
import yt_dlp
import os

app = FastAPI()

@app.get("/")
def home():
    return {"status": "API is Running", "endpoint": "/stream?query={your_search}"}

@app.get("/stream")
def get_video_info(query: str):
    # Cookie path handling
    cookie_path = 'cookies.txt'
    
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'format': 'best', # 'best' ya 'b' Render ke liye safe hai
        'default_search': 'ytsearch1',
        'nocheckcertificate': True,
        'geo_bypass': True,
    }

    if os.path.exists(cookie_path):
        ydl_opts['cookiefile'] = cookie_path

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # Info extract karein
            info = ydl.extract_info(query, download=False)
            
            # Agar search hai toh 'entries' list mein hogi
            if 'entries' in info:
                if not info['entries']:
                    raise HTTPException(status_code=404, detail="No results found")
                video_data = info['entries'][0]
            else:
                video_data = info

            # Sabse stable URL nikaalne ka tarika
            video_url = video_data.get('url')
            formats = video_data.get('formats', [])
            
            # Sirf Audio URL filter (m4a/mp3 type)
            audio_url = next(
                (f['url'] for f in formats if f.get('vcodec') == 'none' and f.get('acodec') != 'none'), 
                video_url # Fallback agar audio format na mile
            )

            return {
                "title": video_data.get('title'),
                "duration": video_data.get('duration'), # in seconds
                "thumbnail": video_data.get('thumbnail'),
                "video_url": video_url,
                "audio_url": audio_url,
                "channel": video_data.get('uploader')
            }
    except Exception as e:
        # Pura error message dikhane ke liye
        raise HTTPException(status_code=400, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
