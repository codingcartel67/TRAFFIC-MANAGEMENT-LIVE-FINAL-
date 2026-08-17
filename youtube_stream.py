"""
YouTube Stream Ingestion & Extractor Module
Handles URL validation, direct stream extraction (VOD and HLS Livestreams),
and error recovery using yt-dlp for the OpenCV + YOLOv8 pipeline.
"""

import time
import re
import logging
from typing import Dict, Any, Optional

try:
    import yt_dlp
    HAS_YTDLP = True
except ImportError:
    HAS_YTDLP = False

logger = logging.getLogger("YouTubeStream")

# Cache to avoid re-extracting stream URLs repeatedly within short window
# Format: {url: {"stream_url": str, "title": str, "is_live": bool, "timestamp": float}}
STREAM_CACHE: Dict[str, Dict[str, Any]] = {}
CACHE_TTL = 3600  # 1 hour cache validity

def normalize_youtube_url(url: str) -> str:
    """Normalizes any YouTube or video link format into a clean standard URL."""
    if not url:
        return ""
    url = url.strip()
    if not url.startswith("http://") and not url.startswith("https://"):
        url = "https://" + url
    return url

def is_valid_youtube_url(url: str) -> bool:
    """Checks if the provided string is a valid YouTube or streaming URL."""
    if not url or not isinstance(url, str):
        return False
    url = normalize_youtube_url(url)
    # Match any youtube, youtu.be, direct m3u8/mp4, or streaming link
    if "youtube.com" in url or "youtu.be" in url:
        return True
    if any(url.lower().endswith(ext) for ext in [".m3u8", ".mp4", ".ts", ".flv", ".mov"]):
        return True
    if url.startswith("rtsp://") or url.startswith("rtmp://") or url.startswith("http://") or url.startswith("https://"):
        return True
    return False

def extract_youtube_stream(url: str, force_refresh: bool = False) -> Dict[str, Any]:
    """
    Extracts a playable direct stream URL (MP4 or HLS m3u8) using yt-dlp with multi-client bot bypass.
    """
    if not HAS_YTDLP:
        return {
            "success": False,
            "stream_url": None,
            "title": "YouTube Stream",
            "is_live": False,
            "duration": None,
            "error": "yt-dlp library is not installed on the server."
        }
        
    url = normalize_youtube_url(url)
    if not is_valid_youtube_url(url):
        return {
            "success": False,
            "stream_url": None,
            "title": "Invalid URL",
            "is_live": False,
            "duration": None,
            "error": "Invalid video URL format. Please provide a valid YouTube link or stream."
        }

    now = time.time()
    # Check cache (15 min validity)
    if not force_refresh and url in STREAM_CACHE:
        cached = STREAM_CACHE[url]
        if now - cached.get("timestamp", 0) < 900:
            return {
                "success": True,
                "stream_url": cached["stream_url"],
                "title": cached["title"],
                "is_live": cached["is_live"],
                "duration": cached.get("duration"),
                "error": None
            }

    # Multi-client extraction strategies to bypass YouTube bot detection and 429 rate limits
    client_strategies = [
        # Strategy 1: Android client (most reliable against bot detection)
        {
            'format': 'best[ext=mp4][height<=720]/best[height<=720]/best[ext=mp4]/best',
            'extractor_args': {'youtube': {'player_client': ['android', 'web']}},
            'user_agent': 'com.google.android.youtube/19.09.37 (Linux; U; Android 11; Pixel 5) gzip',
            'quiet': True,
            'no_warnings': True,
            'noplaylist': True,
            'nocheckcertificate': True,
            'socket_timeout': 15,
            'retries': 3
        },
        # Strategy 2: iOS client
        {
            'format': 'best[ext=mp4][height<=720]/best[height<=720]/best[ext=mp4]/best',
            'extractor_args': {'youtube': {'player_client': ['ios']}},
            'user_agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.5 Mobile/15E148 Safari/604.1',
            'quiet': True,
            'no_warnings': True,
            'noplaylist': True,
            'nocheckcertificate': True,
            'socket_timeout': 15,
            'retries': 3
        },
        # Strategy 3: Web / TV Embedded
        {
            'format': 'best[ext=mp4][height<=720]/best[height<=720]/best',
            'extractor_args': {'youtube': {'player_client': ['tv_embedded', 'mweb']}},
            'quiet': True,
            'no_warnings': True,
            'noplaylist': True,
            'nocheckcertificate': True,
            'socket_timeout': 15,
            'retries': 3
        }
    ]

    last_error = "Could not extract video stream."

    for opts in client_strategies:
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False)
                if not info:
                    continue
                    
                is_live = bool(info.get('is_live') or info.get('live_status') == 'is_live')
                raw_title = str(info.get('title') or 'Live Stream')
                # Clean ASCII representation of title to avoid Windows cp1252 print errors
                clean_title = raw_title.encode('ascii', 'ignore').decode('ascii').strip()
                title = clean_title if clean_title else 'Live Stream'
                duration = info.get('duration')
                
                # Find direct playable stream URL
                stream_url = info.get('url')
                if not stream_url and 'formats' in info:
                    formats = info.get('formats', [])
                    for f in reversed(formats):
                        f_url = f.get('url')
                        if f_url and (f.get('vcodec') != 'none' or f.get('ext') == 'mp4' or 'm3u8' in f_url):
                            stream_url = f_url
                            break
                            
                if stream_url:
                    STREAM_CACHE[url] = {
                        "stream_url": stream_url,
                        "title": title,
                        "is_live": is_live,
                        "duration": duration,
                        "timestamp": now
                    }
                    return {
                        "success": True,
                        "stream_url": stream_url,
                        "title": title,
                        "is_live": is_live,
                        "duration": duration,
                        "error": None
                    }
        except Exception as e:
            last_error = str(e)
            continue

    return {
        "success": False,
        "stream_url": None,
        "title": "Stream Unavailable",
        "is_live": False,
        "duration": None,
        "error": f"YouTube stream extraction failed: {last_error[:120]}"
    }

def clear_stream_cache(url: Optional[str] = None):
    """Clears cached streams."""
    global STREAM_CACHE
    if url and url in STREAM_CACHE:
        del STREAM_CACHE[url]
    elif url is None:
        STREAM_CACHE.clear()
