from flask import Flask, request, jsonify
from flask_cors import CORS
import yt_dlp

app = Flask(__name__)
CORS(app)

def detect_platform(url):
    u = url.lower()
    if "instagram.com" in u:
        return "Instagram"
    elif "facebook.com" in u or "fb.watch" in u:
        return "Facebook"
    elif "twitter.com" in u or "x.com" in u:
        return "Twitter"
    elif "tiktok.com" in u:
        return "TikTok"
    elif "pin.it" in u or "pinterest.com" in u:
        return "Pinterest"
    elif "reddit.com" in u:
        return "Reddit"
    return "Generic"

@app.route('/download', methods=['GET'])
def download_media():
    target_url = request.args.get('url')
    
    if not target_url:
        return jsonify({
            "status": "error",
            "message": "URL parameter missing. Example: /download?url=<video_link>"
        }), 400

    u = target_url.lower()
    if "youtube.com" in u or "youtu.be" in u:
        return jsonify({
            "status": "error",
            "message": "YouTube downloads are not supported on this endpoint."
        }), 400

    platform = detect_platform(target_url)

    # Progressive direct MP4 streams for native Android MediaPlayer compatibility
    ydl_opts = {
        'format': 'best[ext=mp4]/best',
        'quiet': True,
        'no_warnings': True,
        'skip_download': True,
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(target_url, download=False)

            # Check direct URL
            stream_url = info.get('url')

            # Fallback to formats array if direct URL is not top-level
            if not stream_url and 'formats' in info:
                for fmt in reversed(info['formats']):
                    if fmt.get('url') and fmt.get('ext') == 'mp4':
                        stream_url = fmt['url']
                        break

            if not stream_url:
                return jsonify({
                    "status": "error",
                    "message": "Could not extract direct stream URL."
                }), 404

            return jsonify({
                "status": "success",
                "platform": platform,
                "title": info.get('title', 'Downloaded_Video'),
                "download_url": stream_url,
                "thumbnail": info.get('thumbnail', '')
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
        "service": "Social Media Downloader API",
        "supported": ["Instagram", "Facebook", "Twitter", "TikTok", "Pinterest", "Reddit"]
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
