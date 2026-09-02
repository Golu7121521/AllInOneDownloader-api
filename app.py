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

def get_youtube_download_url(yt_url):
    # Working public cobalt API nodes
    endpoints = [
        "https://api.cobalt.tools/api/json",
        "https://cobalt.api.scip.fun/api/json",
        "https://api.wuk.sh/api/json"
    ]
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0"
    }
    payload = {
        "url": yt_url,
        "vQuality": "720"
    }

    for ep in endpoints:
        try:
            res = requests.post(ep, json=payload, headers=headers, timeout=8)
            if res.status_code == 200:
                data = res.json()
                if "url" in data and data["url"]:
                    return data["url"]
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

    # 1. YOUTUBE ROUTE (yt-dlp se bypass karke direct external node se extract)
    if platform == "YouTube":
        yt_stream = get_youtube_download_url(target_url)
        if yt_stream:
            return jsonify({
                "status": "success",
                "platform": "YouTube",
                "title": "YouTube Video",
                "download_url": yt_stream,
                "thumbnail": ""
            })
        else:
            return jsonify({
                "status": "error",
                "message": "YouTube stream couldn't be extracted right now. Try again in a few seconds."
            }), 500

    # 2. INSTAGRAM / FACEBOOK / TIKTOK / TWITTER ROUTE (yt-dlp works seamlessly)
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
                    "title": info.get('title', 'Downloaded_Video'),
                    "download_url": stream_url,
                    "thumbnail": info.get('thumbnail', '')
                })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

    return jsonify({
        "status": "error",
        "message": "Failed to extract media URL."
    }), 500

@app.route('/', methods=['GET'])
def health_check():
    return jsonify({
        "status": "active",
        "service": "All-in-One Downloader API"
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
