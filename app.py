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

def extract_best_media(info):
    """
    Extracts best media item ensuring video has both video and audio.
    Also handles photo posts and carousels.
    """
    media_list = []

    # Case 1: Multi-media / Carousel (e.g. multiple photos/videos in a post)
    if 'entries' in info and info['entries']:
        for entry in info['entries']:
            item = parse_single_item(entry)
            if item:
                media_list.append(item)
    else:
        # Case 2: Single Video or Single Photo
        item = parse_single_item(info)
        if item:
            media_list.append(item)

    return media_list

def parse_single_item(entry):
    if not entry:
        return None

    # Check if this item is an image post
    ext = entry.get('ext', '').lower()
    formats = entry.get('formats', [])
    
    # Check for direct image URL
    if ext in ['jpg', 'jpeg', 'png', 'webp'] or not formats:
        img_url = entry.get('url') or entry.get('thumbnail')
        if img_url:
            return {
                "type": "image",
                "url": img_url,
                "thumbnail": img_url
            }

    # If it's a video, ensure audio + video are combined (Fix for No Sound)
    stream_url = None
    
    # 1. Filter formats that have BOTH video and audio
    audio_video_formats = [
        f for f in formats 
        if f.get('vcodec') != 'none' and f.get('acodec') != 'none' and f.get('url')
    ]
    
    if audio_video_formats:
        # Highest resolution combined format
        stream_url = audio_video_formats[-1]['url']
    elif entry.get('url'):
        stream_url = entry.get('url')
    elif formats:
        # Fallback to last available format
        stream_url = formats[-1].get('url')

    if stream_url:
        return {
            "type": "video",
            "url": stream_url,
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
        return jsonify({"status": "error", "message": "YouTube downloads are not supported."}), 400

    platform = detect_platform(target_url)

    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'skip_download': True,
        'extract_flat': False,
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
            'Accept-Language': 'en-US,en;q=0.9',
        }
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(target_url, download=False)
            media_items = extract_best_media(info)

            if not media_items:
                return jsonify({
                    "status": "error",
                    "message": "Media extract nahi ho payi. Link check karein."
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
        "service": "All-in-One Media Downloader API",
        "supported": ["Reels", "Posts (Images/Carousels)", "Facebook", "Twitter", "TikTok", "Reddit"]
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
