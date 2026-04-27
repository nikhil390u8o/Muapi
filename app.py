import os
import re
import httpx
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import JSONResponse, StreamingResponse
from typing import Optional, Dict, List, Any
import yt_dlp

app = FastAPI(title="YouTube Media API")

# Proxy configuration (to avoid IP bans)
PROXY_URL = os.getenv("STATIC_PROXY_URL", "")
USE_PROXY = bool(PROXY_URL)

# CORS headers
CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    "Access-Control-Allow-Headers": "*",
}

def extract_video_id(query: str) -> str:
    """Extract YouTube video ID from URL or query"""
    patterns = [
        r'(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/embed\/|youtube\.com\/shorts\/)([a-zA-Z0-9_-]{11})',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, query)
        if match:
            return match.group(1)
    
    if re.match(r'^[a-zA-Z0-9_-]{11}$', query):
        return query
    
    return query

def get_best_audio_stream(info: Dict) -> Optional[str]:
    """Get best audio stream URL"""
    audio_formats = []
    
    for f in info.get('formats', []):
        if f.get('acodec') != 'none' and f.get('vcodec') == 'none':
            audio_formats.append({
                'bitrate': f.get('abr', 0),
                'ext': f.get('ext'),
                'url': f.get('url'),
            })
    
    if not audio_formats:
        return None
    
    audio_formats.sort(key=lambda x: x['bitrate'], reverse=True)
    
    # Prefer m4a or opus
    for fmt in audio_formats:
        if fmt['ext'] in ['m4a', 'opus']:
            return fmt['url']
    
    return audio_formats[0]['url']

def get_best_video_stream(info: Dict, quality: str = "720p") -> Optional[str]:
    """Get best video stream URL"""
    video_formats = []
    
    for f in info.get('formats', []):
        if f.get('vcodec') != 'none' and f.get('acodec') == 'none':
            video_formats.append({
                'height': f.get('height', 0),
                'url': f.get('url'),
            })
    
    if not video_formats:
        return None
    
    video_formats.sort(key=lambda x: x['height'], reverse=True)
    
    quality_map = {"1080p": 1080, "720p": 720, "480p": 480, "360p": 360}
    
    if quality in quality_map:
        target = quality_map[quality]
        for fmt in video_formats:
            if fmt['height'] >= target:
                return fmt['url']
    
    return video_formats[0]['url']

@app.get("/search")
async def search_videos(q: str, limit: int = 10, quality: str = "720p"):
    """
    Search YouTube and return videos with thumbnail + audio + video URLs
    
    Response format:
    {
        "query": "lo safar",
        "count": 5,
        "results": [
            {
                "id": "jcV7i0WM9jU",
                "title": "Lo Safar Song...",
                "duration": 302,
                "channel": "T-Series",
                "thumbnail": "https://i.ytimg.com/vi/jcV7i0WM9jU/maxresdefault.jpg",
                "stream_url": {
                    "audio": "https://...",
                    "video": "https://..."
                }
            }
        ]
    }
    """
    
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': False,  # Get full info for each video
    }
    if USE_PROXY:
        ydl_opts['proxy'] = PROXY_URL
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            search_url = f"ytsearch{limit}:{q}"
            info = ydl.extract_info(search_url, download=False)
            
            results = []
            for entry in info.get('entries', []):
                if entry:
                    video_id = entry.get('id')
                    
                    # Get stream URLs for each video
                    audio_url = get_best_audio_stream(entry)
                    video_url = get_best_video_stream(entry, quality)
                    
                    results.append({
                        "id": video_id,
                        "title": entry.get('title'),
                        "duration": entry.get('duration'),
                        "channel": entry.get('uploader'),
                        "views": entry.get('view_count'),
                        "thumbnail": f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg",
                        "stream_url": {
                            "audio": audio_url,
                            "video": video_url
                        }
                    })
            
            return JSONResponse(
                content={
                    "query": q,
                    "count": len(results),
                    "results": results
                },
                headers=CORS_HEADERS
            )
            
        except Exception as e:
            raise HTTPException(500, f"Search failed: {str(e)}")

@app.get("/stream")
async def get_stream(query: str, quality: str = "720p"):
    """
    Get single video with thumbnail + audio + video URLs
    
    Usage: /stream?query=jcV7i0WM9jU
    """
    
    video_id = extract_video_id(query)
    
    # Search if not a valid ID
    if not re.match(r'^[a-zA-Z0-9_-]{11}$', video_id):
        ydl_opts = {
            'quiet': True,
            'extract_flat': 'in_playlist',
        }
        if USE_PROXY:
            ydl_opts['proxy'] = PROXY_URL
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            try:
                search_url = f"ytsearch1:{query}"
                info = ydl.extract_info(search_url, download=False)
                if info.get('entries'):
                    video_id = info['entries'][0].get('id')
                else:
                    raise HTTPException(404, "No video found")
            except Exception:
                raise HTTPException(404, "No video found")
    
    # Get video info
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': False,
    }
    if USE_PROXY:
        ydl_opts['proxy'] = PROXY_URL
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            video_url = f"https://youtube.com/watch?v={video_id}"
            info = ydl.extract_info(video_url, download=False)
            
            audio_url = get_best_audio_stream(info)
            video_url_stream = get_best_video_stream(info, quality)
            
            response_data = {
                "id": video_id,
                "title": info.get('title'),
                "duration": info.get('duration'),
                "channel": info.get('uploader'),
                "source": video_url,
                "thumbnail": f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg",
                "stream_url": {
                    "audio": audio_url,
                    "video": video_url_stream
                }
            }
            
            return JSONResponse(content=response_data, headers=CORS_HEADERS)
            
        except Exception as e:
            raise HTTPException(500, f"Failed: {str(e)}")

@app.get("/thumbnail")
async def get_thumbnail(query: str, quality: str = "maxres"):
    """Get thumbnail image only"""
    
    video_id = extract_video_id(query)
    
    if not re.match(r'^[a-zA-Z0-9_-]{11}$', video_id):
        ydl_opts = {'quiet': True, 'extract_flat': 'in_playlist'}
        if USE_PROXY:
            ydl_opts['proxy'] = PROXY_URL
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            try:
                search_url = f"ytsearch1:{query}"
                info = ydl.extract_info(search_url, download=False)
                if info.get('entries'):
                    video_id = info['entries'][0].get('id')
            except Exception:
                raise HTTPException(404, "Video not found")
    
    thumbnail_urls = {
        "maxres": f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg",
        "hq": f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg",
    }
    
    url = thumbnail_urls.get(quality, thumbnail_urls["maxres"])
    
    async with httpx.AsyncClient(proxies=PROXY_URL if USE_PROXY else None) as client:
        response = await client.get(url)
        
        if response.status_code == 404 and quality == "maxres":
            response = await client.get(thumbnail_urls["hq"])
        
        return Response(
            content=response.content,
            media_type="image/jpeg",
            headers={**CORS_HEADERS, "Cache-Control": "public, max-age=86400"}
        )

@app.get("/health")
async def health():
    return {"status": "healthy"}

@app.options("/{path:path}")
async def options_handler():
    return Response(headers=CORS_HEADERS)
