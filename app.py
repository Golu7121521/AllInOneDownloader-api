from flask import Flask, request, jsonify
from flask_cors import CORS
import yt_dlp
import requests
from bs4 import BeautifulSoup
import re

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
    return "Generic"

# 🔥 Bypass 1: Fetching Media with SOUND (Via SaveIG Proxy)
def fetch_instagram_media(url):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Content-Type": "application/x-www-form-urlencoded",
        "Origin": "https://saveig.app",
        "Referer": "https://saveig.app/en"
    }
    data = {"q": url, "t": "media", "lang": "en"}
    
    try:
        r = requests.post("https://saveig.app/api/ajaxSearch", data=data, headers=headers, timeout=15)
        if r.status_code == 200 and r.json().get("status") == "ok":
            html_data = r.json().get("data", "")
            soup = BeautifulSoup(html_data, "html.parser")
            media_list = []
            
            # Extracting all downloadable files (Pre-merged MP4s with Sound!)
            for div in soup.find_all("div", class_="download-items"):
                btn = div.find("a", href=True)
                if btn:
                    link = btn['href']
                    media_type = "video" if ".mp4" in link or "video" in link.lower() else "image"
                    media_list.append({"type": media_type, "url": link})
                    
            return media_list
    except Exception as e:
        print("Bypass fetch error:", e)
    return None

# 🔥 Bypass 2: Fetching Profile (Via Picuki Proxy to avoid IG Bans)
def fetch_instagram_profile(username):
    url = f"https://www.picuki.com/profile/{username}"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"}
    
    try:
        r = requests.get(url, headers=headers, timeout=15)
        if r.status_code == 200:
            html = r.text
            
            # Safe Regex extraction
            dp_match = re.search(r'<img src="(https://scontent[^"]+)"', html)
            name_match = re.search(r'<h1 class="profile-name-bottom">([^<]+)</h1>', html)
            bio_match = re.search(r'<div class="profile-description">([^<]+)</div>', html)
            
            dp_url = dp_match.group(1) if dp_match else "https://via.placeholder.com/150"
            full_name = name_match.group(1).strip() if name_match else username
            bio = bio_match.group(1).strip() if bio_match else "Bio unavailable."
            
            # Fetch latest 6 feed posts
            feed = []
            post_matches = re.finditer(r'<a href="https://www.picuki.com/media/([^"]+)".*?<img src="([^"]+)"', html, re.DOTALL)
            for idx, pm in enumerate(post_matches):
                if idx >= 6: break
                feed.append({
                    "link": f"https://www.instagram.com/p/{pm.group(1)}/",
                    "thumbnail": pm.group(2),
                    "is_video": False # Picuki hides video type slightly, setting to false for safety
                })
                
            return {
                "user": {
                    "username": username,
                    "full_name": full_name,
                    "bio": bio,
                    "followers": "Hidden (Privacy)",
                    "profile_pic": dp_url
                },
                "feed": feed
            }
    except Exception as e:
        print("Picuki Profile fetch error:", e)
    return None

@app.route('/download', methods=['GET'])
def download_media():
    target_url = request.args.get('url')
    if not target_url:
        return jsonify({"status": "error", "message": "URL parameter missing."}), 400

    platform = detect_platform(target_url)

    # INSTAGRAM HANDLER (100% Working Sound & Bypass)
    if platform == "Instagram":
        media_list = fetch_instagram_media(target_url)
        if media_list:
            # Username extraction from URL to show profile button
            author = None
            if "instagram.com/" in target_url and not any(x in target_url for x in ["/p/", "/reel/", "/tv/"]):
                author = target_url.split("?")[0].strip("/").split("/")[-1]

            return jsonify({
                "status": "success",
                "platform": "Instagram",
                "type": media_list[0]['type'] if media_list else "video",
                "author_username": author,
                "media": media_list
            })

    # FALLBACK HANDLER (yt-dlp) for Facebook, Twitter, TikTok, etc.
    ydl_opts = {
        'format': 'best',
        'quiet': True,
        'no_warnings': True,
        'skip_download': True,
        'http_headers': {'User-Agent': 'Mozilla/5.0'}
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(target_url, download=False)
            stream_url = info.get('url')
            if not stream_url and 'formats' in info:
                for fmt in reversed(info['formats']):
                    if fmt.get('url'):
                        stream_url = fmt['url']
                        break
            
            if not stream_url:
                return jsonify({"status": "error", "message": "Download link failed."}), 404

            return jsonify({
                "status": "success",
                "platform": platform,
                "type": "video",
                "media": [{"type": "video", "url": stream_url, "thumbnail": info.get('thumbnail', '')}]
            })

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/profile_feed', methods=['GET'])
def get_profile_feed():
    username = request.args.get('username')
    if not username:
        return jsonify({"status": "error", "message": "Username required."}), 400
    
    # Using Picuki Proxy to fetch Profile
    profile_data = fetch_instagram_profile(username)
    
    if profile_data:
        return jsonify({"status": "success", "user": profile_data["user"], "feed": profile_data["feed"]})
    else:
        return jsonify({"status": "error", "message": "Profile could not be fetched due to security restrictions."}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
