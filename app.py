import os
import uuid
import glob
from flask import Flask, request, jsonify, send_file, after_this_request
from flask_cors import CORS
import yt_dlp

app = Flask(__name__)
CORS(app)

DOWNLOAD_DIR = "/tmp/downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

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
def download():
    target_url = request.args.get('url')
    if not target_url:
        return jsonify({"status": "error", "message": "URL parameter missing."}), 400

    u = target_url.lower()
    if "youtube.com" in u or "youtu.be" in u:
        return jsonify({"status": "error", "message": "YouTube downloads are not supported."}), 400

    platform = detect_platform(target_url)

    # 1. First probe metadata to check if it is an image or video
    probe_opts = {
        'quiet': True,
        'no_warnings': True,
        'skip_download': True,
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
    }

    try:
        with yt_dlp.YoutubeDL(probe_opts) as ydl:
            info = ydl.extract_info(target_url, download=False)

        ext = info.get('ext', '').lower()
        formats = info.get('formats', [])

        # Agar photo post hai (no audio/video streams to merge)
        if ext in ['jpg', 'jpeg', 'png', 'webp'] or not formats:
            img_url = info.get('url') or info.get('thumbnail')
            return jsonify({
                "status": "success",
                "platform": platform,
                "title": info.get('title', 'Media_Photo'),
                "media": [{
                    "type": "image",
                    "url": img_url,
                    "thumbnail": img_url
                }]
            })

        # Agar video/reel hai: Server-side download + FFmpeg merge
        unique_id = str(uuid.uuid4())[:8]
        output_template = os.path.join(DOWNLOAD_DIR, f"{unique_id}_%(title).50s.%(ext)s")

        merge_opts = {
            'format': 'bestvideo+bestaudio/best',
            'outtmpl': output_template,
            'merge_output_format': 'mp4',
            'quiet': True,
            'no_warnings': True,
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
        }

        with yt_dlp.YoutubeDL(merge_opts) as ydl:
            download_info = ydl.extract_info(target_url, download=True)
            title = download_info.get('title', 'video')

        # Find the merged file on disk
        matches = glob.glob(os.path.join(DOWNLOAD_DIR, f"{unique_id}_*"))
        if not matches:
            return jsonify({"status": "error", "message": "File processing failed."}), 500

        file_path = matches[0]
        file_name = os.path.basename(file_path)

        # Host URL generation for stream endpoint
        base_host = request.host_url.rstrip('/')
        stream_link = f"{base_host}/stream/{file_name}"

        return jsonify({
            "status": "success",
            "platform": platform,
            "title": title,
            "media": [{
                "type": "video",
                "url": stream_link,
                "thumbnail": info.get('thumbnail', '')
            }]
        })

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/stream/<filename>', methods=['GET'])
def stream_file(filename):
    file_path = os.path.join(DOWNLOAD_DIR, filename)
    if not os.path.exists(file_path):
        return jsonify({"status": "error", "message": "File not found or expired."}), 404

    @after_this_request
    def remove_file(response):
        # Auto clean up file after serving
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
        except Exception as e:
            app.logger.error(f"Error removing file: {e}")
        return response

    return send_file(file_path, mimetype='video/mp4', as_attachment=False)

@app.route('/', methods=['GET'])
def health():
    return jsonify({"status": "active", "engine": "Docker + FFmpeg Muxer"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
