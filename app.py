from flask import Flask, request, jsonify
from flask_cors import CORS
import yt_dlp
import re

app = Flask(__name__)
CORS(app)  # Mobile app ya Web browser se access allow karne ke liye

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

@app.route('/download', methods=['GET'])
def download_media():
    target_url = request.args.get('url')
    
    if not target_url:
        return jsonify({
            "status": "error",
            "message": "URL parameter missing. Use ?url=<video_link>"
        }), 400

    platform = detect_platform(target_url)

    # yt-dlp configuration for direct progressive video playback
    ydl_opts = {
        'format': 'best[ext=mp4][vcodec^=avc1]/best[ext=mp4]/best',  # Android MediaPlayer compatible H.264 MP4
        'quiet': True,
        'no_warnings': True,
        'extract_flat': False,
        'skip_download': True,
        # Standard mobile user agent to prevent bot verification blocks
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(target_url, download=False)

            # Direct CDN link
            stream_url = info.get('url')
            
            # If standard url is missing, grab from formats list
            if not stream_url and 'formats' in info:
                for fmt in reversed(info['formats']):
                    if fmt.get('url') and fmt.get('ext') == 'mp4':
                        stream_url = fmt['url']
                        break

            if not stream_url:
                return jsonify({
                    "status": "error",
                    "message": "Could not extract direct stream link."
                }), 404

            return jsonify({
                "status": "success",
                "platform": platform,
                "title": info.get('title', 'Downloaded_Video'),
                "download_url": stream_url,
                "thumbnail": info.get('thumbnail', ''),
                "duration": info.get('duration', 0)
            })

    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

@app.route('/', methods=['GET'])
def health_check():
    return jsonify({
        "status": "active",
        "service": "All-in-One Media Downloader API",
        "usage": "/download?url=<target_link>"
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
