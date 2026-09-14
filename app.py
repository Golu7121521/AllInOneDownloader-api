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

def extract_original_quality(info):
    media_items = []

    # Carousel/Multiple post items
    if 'entries' in info and info['entries']:
        for entry in info['entries']:
            item = parse_item(entry)
            if item:
                media_items.append(item)
    else:
        item = parse_item(info)
        if item:
            media_items.append(item)

    return media_items

def parse_item(entry):
    if not entry:
        return None

    ext = entry.get('ext', '').lower()
    formats = entry.get('formats', [])

    # Photo post
    if ext in ['jpg', 'jpeg', 'png', 'webp'] or not formats:
        img_url = entry.get('url') or entry.get('thumbnail')
        if img_url:
            return {
                "type": "image",
                "url": img_url,
                "thumbnail": img_url
            }

    # Video: Pick the absolute largest/highest bitrate stream
    best_stream_url = None

    if formats:
        # Filter formats with valid URLs
        valid_formats = [f for f in formats if f.get('url')]

        # Priority 1: Pick format with largest filesize or highest width/height
        def get_quality_score(f):
            # Filesize > Bitrate > Resolution > Height
            size = f.get('filesize') or f.get('filesize_approx') or 0
            tbr = f.get('tbr') or 0
            height = f.get('height') or 0
            width = f.get('width') or 0
            return (size, tbr, height * width)

        valid_formats.sort(key=get_quality_score, reverse=True)
        if valid_formats:
            best_stream_url = valid_formats[0]['url']

    # Fallback to top-level entry URL (original master stream)
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

    # Native sort prioritizing original size & resolution
    ydl_opts = {
        'format': 'bestvideo/best',
        'format_sort': ['filesize', 'res', 'fps', 'tbr'],
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
            media_items = extract_original_quality(info)

            if not media_items:
                return jsonify({"status": "error", "message": "Media extract nahi ho payi."}), 404

            return jsonify({
                "status": "success",
                "platform": platform,
                "title": info.get('title', 'Media_Download'),
                "media": media_items
            })

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/', methods=['GET'])
def health():
    return jsonify({"status": "active", "quality": "Original Master Bitrate (Uncompressed)"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
