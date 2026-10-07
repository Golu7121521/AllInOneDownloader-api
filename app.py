import os
import tempfile
from flask import Flask, request, jsonify, send_file
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
def download():
    target_url = request.args.get('url')
    if not target_url:
        return jsonify({"status": "error", "message": "URL parameter missing."}), 400

    u = target_url.lower()
    if "youtube.com" in u or "youtu.be" in u:
        return jsonify({"status": "error", "message": "YouTube is not supported."}), 400

    platform = detect_platform(target_url)

    # Server par ek temporary directory banayenge jahan merged file save hogi
    temp_dir = tempfile.gettempdir()
    
    # yt-dlp Options 
    # 'bestvideo+bestaudio' ensure karta hai ki highest video (1080p/4k) aur highest audio uthaye.
    # 'merge_output_format': 'mp4' un dono ko mila kar ek mp4 file bana dega.
    ydl_opts = {
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        'merge_output_format': 'mp4',
        'outtmpl': os.path.join(temp_dir, '%(id)s.%(ext)s'),  # Temp folder me file save karega
        'quiet': True,
        'no_warnings': True,
        'skip_download': False,  # Merge karne ke liye server par download karna zaroori hai
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
            'Accept-Language': 'en-US,en;q=0.9',
        }
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # Ye step server par video aur audio download karega aur FFmpeg se merge karega
            info = ydl.extract_info(target_url, download=True)
            
            # File ka original naam / path nikalenge
            file_path = ydl.prepare_filename(info)
            base_path, _ = os.path.splitext(file_path)
            
            # Kyunki humne mp4 merge ka option diya hai, final extension .mp4 hoga
            mp4_file_path = base_path + ".mp4"
            
            title = info.get('title', 'Media_Download')
            
            # Agar successfully merge hokar file ban gayi, toh usey user ko bhej do
            if os.path.exists(mp4_file_path):
                return send_file(
                    mp4_file_path, 
                    as_attachment=True, 
                    download_name=f"{title}.mp4",
                    mimetype='video/mp4'
                )
            # Fallback agar direct file wahi rehti hai (merge ki zaroorat nahi padi thi)
            elif os.path.exists(file_path):
                return send_file(
                    file_path, 
                    as_attachment=True, 
                    download_name=f"{title}.mp4",
                    mimetype='video/mp4'
                )
            else:
                return jsonify({"status": "error", "message": "File properly merge nahi ho payi."}), 500

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/', methods=['GET'])
def health():
    return jsonify({"status": "active", "quality": "Highest Video (1080p/2K/4K) + Audio Merged"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
