from flask import Flask, request, jsonify
from flask_cors import CORS
import yt_dlp
import requests

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

def fetch_via_cobalt(target_url):
    """Bypasses YouTube bot/cloud blocks reliably using Cobalt instances"""
    instances = [
        "https://api.cobalt.tools",
        "https://cobalt-api.kwiatekm.tokyo",
        "https://api.wuk.sh"
    ]
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json"
    }
    payload = {
        "url": target_url,
        "videoQuality": "720"
    }
    
    for api_url in instances:
        try:
            res = requests.post(f"{api_url}/", json=payload, headers=headers, timeout=10)
            if res.status_code == 200:
                data = res.json()
                download_url = data.get("url")
                if download_url:
                    return {
                        "download_url": download_url,
                        "title": "YouTube_Video"
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

    # 1. YouTube handling via Cobalt Engine (Bypasses Render Block 100%)
    if platform == "YouTube":
        yt_res = fetch_via_cobalt(target_url)
        if yt_res:
            return jsonify({
                "status": "success",
                "platform": "YouTube",
                "title": yt_res["title"],
                "download_url": yt_res["download_url"],
                "thumbnail": ""
            })

    # 2. Instagram, Facebook, Twitter, TikTok & Others via yt-dlp
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

            if stream_url:
                return jsonify({
                    "status": "success",
                    "platform": platform,
                    "title": info.get('title', 'Media_Video'),
                    "download_url": stream_url,
                    "thumbnail": info.get('thumbnail', '')
                })
    except Exception as e:
        # Fallback to Cobalt for any other platform if yt-dlp fails
        cobalt_fallback = fetch_via_cobalt(target_url)
        if cobalt_fallback:
            return jsonify({
                "status": "success",
                "platform": platform,
                "title": cobalt_fallback["title"],
                "download_url": cobalt_fallback["download_url"],
                "thumbnail": ""
            })
            
        return jsonify({"status": "error", "message": str(e)}), 500

    return jsonify({
        "status": "error",
        "message": "Failed to extract media URL."
    }), 500

@app.route('/', methods=['GET'])
def health_check():
    return jsonify({
        "status": "active",
        "service": "All-in-One Downloader"
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
