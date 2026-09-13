import os
import uuid
import glob
import time
from flask import Flask, request, jsonify, send_file, Response
from flask_cors import CORS
import yt_dlp

app = Flask(__name__)
CORS(app)

DOWNLOAD_DIR = "/tmp/downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

def cleanup_old_files():
    """Delete files older than 10 minutes to save disk space"""
    now = time.time()
    for f in glob.glob(os.path.join(DOWNLOAD_DIR, "*")):
        if os.stat(f).st_mtime < now - 600:
            try:
                os.remove(f)
            except Exception:
                pass

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
    cleanup_old_files()
    target_url = request.args.get('url')
    if not target_url:
        return jsonify({"status": "error", "message": "URL parameter missing."}), 400

    u = target_url.lower()
    if "youtube.com" in u or "youtu.be" in u:
        return jsonify({"status": "error", "message": "YouTube is not supported."}), 400

    platform = detect_platform(target_url)

    # 1. First probe to detect if it's an image post
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

        # Photo post handling
        if ext in ['jpg', 'jpeg', 'png', 'webp'] or not formats:
            img_url = info.get('url') or info.get('thumbnail')
            return jsonify({
                "status": "success",
                "platform": platform,
                "title": info.get('title', 'Photo_Post'),
                "media": [{
                    "type": "image",
                    "url": img_url,
                    "thumbnail": img_url
                }]
            })

        # Video / Reel handling with FFmpeg merge
        unique_id = str(uuid.uuid4())[:8]
        output_template = os.path.join(DOWNLOAD_DIR, f"{unique_id}.%(ext)s")

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
            title = download_info.get('title', 'Video_Download')

        target_file = os.path.join(DOWNLOAD_DIR, f"{unique_id}.mp4")
        if not os.path.exists(target_file):
            matches = glob.glob(os.path.join(DOWNLOAD_DIR, f"{unique_id}.*"))
            if matches:
                target_file = matches[0]
            else:
                return jsonify({"status": "error", "message": "Failed to merge media streams."}), 500

        file_name = os.path.basename(target_file)
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
        return jsonify({"status": "error", "message": "File expired. Please fetch again."}), 404

    # Direct attachment for download, inline for video streaming
    as_attachment = request.args.get('download', '0') == '1'
    return send_file(
        file_path, 
        mimetype='video/mp4', 
        as_attachment=as_attachment, 
        download_name=filename
    )

@app.route('/', methods=['GET'])
def health():
    return jsonify({"status": "active", "engine": "Docker + FFmpeg Muxer"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
