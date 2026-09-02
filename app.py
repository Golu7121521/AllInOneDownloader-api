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

def fetch_youtube_via_invidious(video_id):
    # Active public instances jo cloud IP block nahi karte
    instances = [
        "https://inv.tux.pizza",
        "https://invidious.nerdvpn.de",
        "https://invidious.jing.rocks",
        "https://yt.artemislena.eu"
    ]
    for base in instances:
        try:
            res = requests.get(f"{base}/api/v1/videos/{video_id}", timeout=6)
            if res.status_code == 200:
                data = res.json()
                title = data.get("title", "YouTube_Video")
                thumbnail = ""
                if "videoThumbnails" in data and len(data["videoThumbnails"]) > 0:
                    thumbnail = data["videoThumbnails"][0].get("url", "")

                # Combined audio + video MP4 stream (progressive) dhoondo
                formats = data.get("formatStreams", [])
                for f in formats:
                    if "video/mp4" in f.get("type", ""):
                        return {
                            "download_url": f.get("url"),
                            "title": title,
                            "thumbnail": thumbnail
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

    # 1. Non-YouTube platforms (Instagram, Facebook, Twitter, etc.)
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

    # 2. YouTube: Bypass cloud block via Invidious API
    vid = extract_youtube_id(target_url)
    if vid:
        yt_data = fetch_youtube_via_invidious(vid)
        if yt_data:
            return jsonify({
                "status": "success",
                "platform": "YouTube",
                "title": yt_data["title"],
                "download_url": yt_data["download_url"],
                "thumbnail": yt_data["thumbnail"]
            })

    # Agar bypass fail ho toh direct yt-dlp web_embedded fallback
    try:
        ydl_opts = {
            'format': 'best[ext=mp4]/best',
            'quiet': True,
            'skip_download': True,
            'extractor_args': {'youtube': {'player_client': ['web_embedded']}}
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(target_url, download=False)
            return jsonify({
                "status": "success",
                "platform": "YouTube",
                "title": info.get('title', 'YouTube_Video'),
                "download_url": info.get('url'),
                "thumbnail": info.get('thumbnail', '')
            })
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": "YouTube link extract nahi ho paaya. Video private ya age-restricted ho sakti hai."
        }), 500

@app.route('/', methods=['GET'])
def health_check():
    return jsonify({
        "status": "active",
        "service": "All-in-One Downloader"
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
