import os
import uuid
import glob
import time
import re
from flask import Flask, request, jsonify, Response
from flask_cors import CORS
import yt_dlp

app = Flask(__name__)
CORS(app)

DOWNLOAD_DIR = "/tmp/downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

def cleanup_old_files():
    """Delete files older than 15 minutes to save disk space"""
    now = time.time()
    for f in glob.glob(os.path.join(DOWNLOAD_DIR, "*")):
        try:
            if os.stat(f).st_mtime < now - 900:
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

    # 1. Probe metadata (Check for image posts)
    probe_opts = {
        'quiet': True,
        'no_warnings': True,
        'skip_download': True,
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
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

        # Video / Reel handling (FORCING AUDIO PRIORITY)
        unique_id = str(uuid.uuid4())[:8]
        output_template = os.path.join(DOWNLOAD_DIR, f"{unique_id}.%(ext)s")

        download_opts = {
            # Priority: Video+Audio merge -> Best format that HAS audio -> Fallback
            'format': 'bestvideo+bestaudio/best[acodec!=none]/best',
            # Force audio presence BEFORE checking resolution
            'format_sort': ['hasaud', 'res', 'fps'],
            'outtmpl': output_template,
            'merge_output_format': 'mp4',
            'quiet': True,
            'no_warnings': True,
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
            }
        }

        with yt_dlp.YoutubeDL(download_opts) as ydl:
            download_info = ydl.extract_info(target_url, download=True)
            title = download_info.get('title', 'Video_Download')

        target_file = os.path.join(DOWNLOAD_DIR, f"{unique_id}.mp4")
        if not os.path.exists(target_file):
            matches = glob.glob(os.path.join(DOWNLOAD_DIR, f"{unique_id}.*"))
            if matches:
                target_file = matches[0]
            else:
                return jsonify({"status": "error", "message": "Failed to process video."}), 500

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

    if request.args.get('download', '0') == '1':
        with open(file_path, 'rb') as f:
            data = f.read()
        return Response(
            data,
            mimetype="video/mp4",
            headers={
                "Content-Disposition": f"attachment; filename={filename}",
                "Content-Length": str(len(data))
            }
        )

    file_size = os.path.getsize(file_path)
    range_header = request.headers.get('Range', None)

    if not range_header:
        with open(file_path, 'rb') as f:
            data = f.read()
        return Response(data, mimetype='video/mp4', headers={"Content-Length": str(file_size), "Accept-Ranges": "bytes"})

    byte1, byte2 = 0, None
    m = re.search(r'bytes=(\d+)-(\d*)', range_header)
    if m:
        g = m.groups()
        byte1 = int(g[0])
        if g[1]:
            byte2 = int(g[1])

    length = file_size - byte1 if byte2 is None else byte2 - byte1 + 1

    with open(file_path, 'rb') as f:
        f.seek(byte1)
        data = f.read(length)

    rv = Response(data, 206, mimetype='video/mp4', direct_passthrough=True)
    rv.headers.add('Content-Range', f'bytes {byte1}-{byte1 + len(data) - 1}/{file_size}')
    rv.headers.add('Accept-Ranges', 'bytes')
    rv.headers.add('Content-Length', str(len(data)))
    return rv

@app.route('/', methods=['GET'])
def health():
    return jsonify({"status": "active", "engine": "Docker + FFmpeg (Audio-First Muxer)"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
