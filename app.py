from flask import Flask, request, jsonify
from flask_cors import CORS
import yt_dlp
import requests
import re

app = Flask(__name__)
CORS(app)

def detect_platform(url):
    if "instagram.com" in url:
        return "Instagram"
    elif "youtube.com" in url or "youtu.be" in url:
        return "YouTube"
    elif "facebook.com" in url or "fb.watch" in url:
        return "Facebook"
    elif "twitter.com" in url or "x.com" in url:
        return "Twitter"
    elif "tiktok.com" in url:
        return "TikTok"
    return "Generic"

def extract_youtube_id(url):
    patterns = [
        r'(?:v=|\/)([0-9A-Za-z_-]{11}).*',
        r'(?:embed\/)([0-9A-Za-z_-]{11})',
        r'(?:shorts\/)([0-9A-Za-z_-]{11})',
        r'^([0-9A-Za-z_-]{11})$'
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None

def fetch_youtube_fallback(video_id):
    """Render/Datacenter IP block bypass karne ke liye public Piped node ka use"""
    instances = [
        "https://pipedapi.kavin.rocks",
        "https://api.piped.privacydev.net",
        "https://piped-api.lunar.icu"
    ]
    for base in instances:
        try:
            res = requests.get(f"{base}/streams/{video_id}", timeout=8)
            if res.status_code == 200:
                data = res.json()
                # 720p/360p progressive MP4 (audio + video combined) dhoondte hain
                streams = data.get("videoStreams", [])
                for s in streams:
                    if s.get("format") == "MPEG_4" and not s.get("videoOnly"):
                        return {
                            "download_url": s.get("url"),
                            "title": data.get("title", "YouTube_Video"),
                            "thumbnail": data.get("thumbnailUrl", "")
                        }
        except Exception:
            continue
    return None

@app.route('/download', methods=['GET'])
def download_media():
    target_url = request.args.get('url')
    
    if not target_url:
        return jsonify({
            "status": "error",
            "message": "URL parameter missing. Use ?url=<video_link>"
        }), 400

    platform = detect_platform(target_url)

    # 1. Instagram, Facebook, TikTok & Standard Platforms via yt-dlp
    if platform != "YouTube":
        ydl_opts = {
            'format': 'best[ext=mp4]/best',
            'quiet': True,
            'no_warnings': True,
            'skip_download': True
        }
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(target_url, download=False)
                stream_url = info.get('url')
                if not stream_url and 'formats' in info:
                    for fmt in reversed(info['formats']):
                        if fmt.get('url') and fmt.get('ext') == 'mp4':
                            stream_url = fmt['url']
                            break

                return jsonify({
                    "status": "success",
                    "platform": platform,
                    "title": info.get('title', 'Media_Video'),
                    "download_url": stream_url,
                    "thumbnail": info.get('thumbnail', '')
                })
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 500

    # 2. YouTube Engine (Special Bypass Mode)
    yt_opts = {
        'format': 'best[ext=mp4]/best',
        'quiet': True,
        'no_warnings': True,
        'skip_download': True,
        'extractor_args': {
            'youtube': {
                'player_client': ['mweb', 'tv_embedded']
            }
        }
    }

    try:
        with yt_dlp.YoutubeDL(yt_opts) as ydl:
            info = ydl.extract_info(target_url, download=False)
            stream_url = info.get('url')
            if not stream_url and 'formats' in info:
                for fmt in reversed(info['formats']):
                    if fmt.get('url') and fmt.get('ext') == 'mp4':
                        stream_url = fmt['url']
                        break
            
            if stream_url:
                return jsonify({
                    "status": "success",
                    "platform": "YouTube",
                    "title": info.get('title', 'YouTube_Video'),
                    "download_url": stream_url,
                    "thumbnail": info.get('thumbnail', '')
                })
    except Exception:
        pass  # Cloud IP bot-block aane par automated fallback trigger hoga

    # Fallback to bypass datacenter restriction
    vid = extract_youtube_id(target_url)
    if vid:
        fallback_data = fetch_youtube_fallback(vid)
        if fallback_data:
            return jsonify({
                "status": "success",
                "platform": "YouTube",
                "title": fallback_data["title"],
                "download_url": fallback_data["download_url"],
                "thumbnail": fallback_data["thumbnail"]
            })

    return jsonify({
        "status": "error",
        "message": "YouTube restricted this video on Cloud IP. Try another link or retry in a moment."
    }), 500

@app.route('/', methods=['GET'])
def health_check():
    return jsonify({
        "status": "active",
        "service": "All-in-One Downloader (Bypass Enabled)"
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
