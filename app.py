import os
import re
from flask import Flask, request, jsonify
from flask_cors import CORS
import yt_dlp

app = Flask(__name__)
CORS(app)  # Allow cross-origin calls from Flutter app

def sanitize_url(url: str) -> str:
    """Cleans tracking query parameters if needed."""
    return url.strip()

@app.route("/", methods=["GET"])
def health_check():
    return jsonify({
        "status": "online",
        "service": "All Video Downloader API",
        "version": "1.0.0"
    }), 200

@app.route("/api/extract", methods=["POST", "GET"])
def extract_video():
    # Support both GET query param and POST JSON body
    if request.method == "POST":
        data = request.get_json(silent=True) or {}
        video_url = data.get("url")
    else:
        video_url = request.args.get("url")

    if not video_url:
        return jsonify({"success": False, "error": "URL parameter is missing."}), 400

    clean_url = sanitize_url(video_url)

    ydl_opts = {
        "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "extract_flat": False,
        "noplaylist": True,
        "socket_timeout": 15,
        "http_headers": {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(clean_url, download=False)

            if not info:
                return jsonify({"success": False, "error": "Could not extract video info."}), 404

            # Extract available formats
            formats_list = []
            if "formats" in info:
                for f in info["formats"]:
                    direct_url = f.get("url")
                    ext = f.get("ext", "mp4")
                    height = f.get("height")
                    format_note = f.get("format_note", "")

                    # Prioritize formats with both audio/video or standard mp4
                    if direct_url and ext in ["mp4", "webm", "m3u8"]:
                        quality_label = f"{height}p" if height else format_note or "Default"
                        formats_list.append({
                            "quality": quality_label,
                            "format": ext,
                            "url": direct_url,
                            "has_audio": f.get("acodec") != "none",
                            "has_video": f.get("vcodec") != "none",
                            "filesize": f.get("filesize") or f.get("filesize_approx")
                        })

            # Primary direct playback / download URL
            primary_download_url = info.get("url")

            # Fallback to the best playable format if root url is absent
            if not primary_download_url and formats_list:
                # Pick last or best playable format
                primary_download_url = formats_list[-1]["url"]

            response_payload = {
                "success": True,
                "title": info.get("title", "Video"),
                "thumbnail": info.get("thumbnail"),
                "duration": info.get("duration"),
                "uploader": info.get("uploader"),
                "download_url": primary_download_url,
                "formats": formats_list
            }

            return jsonify(response_payload), 200

    except yt_dlp.utils.DownloadError as e:
        return jsonify({
            "success": False,
            "error": "Failed to extract from this link. Video might be private, region-blocked, or removed.",
            "details": str(e)
        }), 422
    except Exception as e:
        return jsonify({
            "success": False,
            "error": "Server error processing stream extraction.",
            "details": str(e)
        }), 500

if __name__ == "__main__":
    # Local run on port 5000
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
