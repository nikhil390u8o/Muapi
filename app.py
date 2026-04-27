from fastapi import FastAPI, HTTPException
import yt_dlp
import os

app = FastAPI()
@app.get("/")
def home():
    return {"status": "API is Running", "endpoint": "/stream?query={your_search}"}


@app.get("/stream")
def get_video_info(query: str):
    cookie_path = 'cookies.txt'
    
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        # 'b' use karne se "format not available" ka error nahi aayega
        'format': 'b/bestvideo+bestaudio/best', 
        'default_search': 'ytsearch1',
        'nocheckcertificate': True,
        'geo_bypass': True,
    }

    if os.path.exists(cookie_path):
        ydl_opts['cookiefile'] = cookie_path

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(query, download=False)
            
            if 'entries' in info:
                video_data = info['entries'][0]
            else:
                video_data = info

            # URLs extract karne ka sabse safe tarika
            video_url = video_data.get('url')
            
            # Sirf audio dhoondne ke liye logic
            formats = video_data.get('formats', [])
            audio_url = next((f['url'] for f in formats if f.get('vcodec') == 'none'), video_url)

            return {
                "title": video_data.get('title'),
                "duration": video_data.get('duration'),
                "thumbnail": video_data.get('thumbnail'),
                "video_url": video_url,
                "audio_url": audio_url
            }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
