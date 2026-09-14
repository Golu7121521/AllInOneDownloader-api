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

def extract_highest_quality(info):
    """
    Extracts the absolute highest quality stream or full-res image.
    Handles single posts as well as multi-item carousels.
    """
    media_items = []

    # Multi-item carousel posts
    if 'entries' in info and info['entries']:
        for entry in info['entries']:
            item = parse_media_item(entry)
            if item:
                media_items.append(item)
    else:
        # Single video / single photo
        item = parse_media_item(info)
        if item:
            media_items.append(item)

    return media_items

def parse_media_item(entry):
    if not entry:
        return None

    ext = entry.get('ext', '').lower()
    formats = entry.get('formats', [])

    # 1. Photo Post (Highest resolution original image)
    if ext in ['jpg', 'jpeg', 'png', 'webp'] or not formats:
        img_url = entry.get('url') or entry.get('thumbnail')
        if img_url:
            return {
                "type": "image",
                "url": img_url,
                "thumbnail": img_url
            }

    # 2. Video / Reel (Highest resolution 1080p format)
    # Sort formats strictly by resolution (height/width) and bitrate
    best_stream_url = None
    if formats:
        # Sort by resolution (height) in descending order to get the top quality
        sorted_formats = sorted(
            [f for f in formats if f.get('url')],
            key=lambda x: (x.get('height') or 0, x.get('width') or 0, x.get('tbr') or 0),
            reverse=True
        )
        if sorted_formats:
            best_stream_url = sorted_formats[0]['url']

    # Fallback to direct URL if formats array sorting wasn't applicable
    if not best_stream_url:
        best_stream_url = entry.get('url')

    if best_stream_url:
        return {
            "type": "video",
            "url": best_stream_url,
            "thumbnail": entry.get('thumbnail', '')
        }

    return None

@app.route('/download', methods=['GET'])
def download():
    target_url = request.args.get('url')
    if not target_url:
        return jsonify({"status": "error", "message": "URL parameter missing."}), 400

    u = target_url.lower()
    if "youtube.com" in u or "youtu.be" in u:
        return jsonify({"status": "error", "message": "YouTube is not supported."}), 400

    platform = detect_platform(target_url)

    # yt-dlp options strictly optimized for MAX quality extraction without server overhead
    ydl_opts = {
        'format': 'bestvideo/best',
        'format_sort': ['res:1080', 'res', 'fps', 'size', 'br'],
        'quiet': True,
        'no_warnings': True,
        'skip_download': True,
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
            'Accept-Language': 'en-US,en;q=0.9',
        }
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(target_url, download=False)
            media_items = extract_highest_quality(info)

            if not media_items:
                return jsonify({
                    "status": "error",
                    "message": "Highest quality stream extract nahi ho payi."
                }), 404

            return jsonify({
                "status": "success",
                "platform": platform,
                "title": info.get('title', 'Media_Download'),
                "media": media_items
            })

    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

@app.route('/', methods=['GET'])
def health():
    return jsonify({
        "status": "active",
        "service": "Max Quality Media Downloader API",
        "quality": "Full HD (1080p/Original)"
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
