from fastapi import FastAPI, HTTPException
import yt_dlp
import os

app = FastAPI()

@app.get("/")
def home():
    return {
        "status": "API is Running", 
        "usage": "/stream?query=song_name_or_url"
    }

@app.get("/stream")
def get_video_info(query: str):
    cookie_path = 'cookies.txt'
    
    # yt-dlp configurations
        ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        # 'best' की जगह 'ba/b' (best audio या जो भी बेस्ट हो) यूज़ करें
        'format': 'bestaudio/best', 
        'default_search': 'ytsearch1',
        'nocheckcertificate': True,
        'geo_bypass': True,
    }


    # Cookies check
    if os.path.exists(cookie_path):
        ydl_opts['cookiefile'] = cookie_path

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # Metadata extraction
            info = ydl.extract_info(query, download=False)
            
            # Agar query search hai, toh pehla result uthao
            if 'entries' in info:
                if not info['entries']:
                    raise HTTPException(status_code=404, detail="No results found")
                video_data = info['entries'][0]
            else:
                video_data = info

            # Extracting all necessary fields
            formats = video_data.get('formats', [])
            
            # 1. Direct Video+Audio URL
            video_url = video_data.get('url')
            
            # 2. Extract best Audio-only URL (Filter for formats with no video)
            audio_url = next(
                (f['url'] for f in formats if f.get('vcodec') == 'none' and f.get('acodec') != 'none'), 
                video_url # Fallback to main URL if audio-only not found
            )

            return {
                "title": video_data.get('title'),
                "duration": video_data.get('duration'), # In seconds
                "thumbnail": video_data.get('thumbnail'),
                "video_url": video_url,
                "audio_url": audio_url,
                "uploader": video_data.get('uploader'),
                "views": video_data.get('view_count')
            }
            
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    # Render ke liye port handling
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)
