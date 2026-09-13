from flask import Flask, request, jsonify
from flask_cors import CORS
import yt_dlp
import instaloader
import re
import requests

app = Flask(__name__)
CORS(app)

L = instaloader.Instaloader(
    download_pictures=False,
    download_videos=False,
    download_video_thumbnails=False,
    save_metadata=False
)

def detect_platform(url):
    u = url.lower()
    if "instagram.com" in u:
        return "Instagram"
    elif "facebook.com" in u or "fb.watch" in u:
        return "Facebook"
    elif "twitter.com" in u or "x.com" in u:
        return "Twitter"
    return "Generic"

# 🟢 BYPASS TRICK: WhatsApp/Discord Link Preview Scraper (Never Gets Blocked)
def scrape_profile_html(username):
    url = f"https://www.instagram.com/{username}/"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    try:
        r = requests.get(url, headers=headers, timeout=10)
        # Extracting data from Meta tags (Bypasses API blocks)
        dp_match = re.search(r'"og:image"\s+content="([^"]+)"', r.text)
        desc_match = re.search(r'"og:description"\s+content="([^"]+)"', r.text)
        title_match = re.search(r'"og:title"\s+content="([^"]+)"', r.text)
        
        if dp_match:
            dp_url = dp_match.group(1).replace("&amp;", "&")
            title = title_match.group(1) if title_match else username
            desc = desc_match.group(1) if desc_match else ""
            
            followers = "Hidden"
            if "Followers" in desc:
                followers = desc.split("Followers")[0].strip()
                
            full_name = title.split("(@")[0].strip() if "(@" in title else title
            
            return {
                "username": username,
                "full_name": full_name,
                "bio": "Protected by Instagram API",
                "followers": followers,
                "profile_pic": dp_url
            }
    except Exception as e:
        print("HTML Scrape error:", e)
    return None

def extract_instagram_data(url):
    clean_url = url.split("?")[0].rstrip("/")

    # 🟢 SOUND FIX: Agar Reel/TV hai, to Instaloader SKIP kar do, taki yt-dlp (MP4 with Sound) handle kare!
    if "/reel/" in clean_url or "/tv/" in clean_url:
        return None # Returning None forces the fallback (yt-dlp) to execute below

    # Profile Picture (instagram.com/username)
    profile_match = re.search(r"instagram\.com/([a-zA-Z0-9_\.]+)/?$", clean_url)
    if profile_match and not any(x in clean_url for x in ["/p/", "/reel/", "/stories/", "/tv/"]):
        username = profile_match.group(1)
        profile = instaloader.Profile.from_username(L.context, username)
        return {
            "type": "profile",
            "author_username": profile.username,
            "media": [{"type": "image", "url": profile.profile_pic_url}]
        }

    # Normal Posts / Image Carousels
    post_match = re.search(r"/(?:p)/([^/?#&]+)", clean_url)
    if post_match:
        shortcode = post_match.group(1)
        post = instaloader.Post.from_shortcode(L.context, shortcode)
        
        media_list = []
        if post.typename == 'GraphSidecar':  
            for node in post.get_sidecar_nodes():
                media_list.append({"type": "video" if node.is_video else "image", "url": node.video_url if node.is_video else node.display_url})
        else:
            media_list.append({"type": "video" if post.is_video else "image", "url": post.video_url if post.is_video else post.url})

        return {
            "type": "post" if len(media_list) > 1 else ("video" if post.is_video else "image"),
            "author_username": post.owner_username,
            "media": media_list
        }
    return None

@app.route('/download', methods=['GET'])
def download_media():
    target_url = request.args.get('url')
    if not target_url:
        return jsonify({"status": "error", "message": "URL parameter missing."}), 400

    platform = detect_platform(target_url)
    author_username = None

    if platform == "Instagram":
        try:
            insta_result = extract_instagram_data(target_url)
            if insta_result:
                return jsonify({
                    "status": "success",
                    "platform": "Instagram",
                    "type": insta_result.get("type"),
                    "author_username": insta_result.get("author_username"),
                    "media": insta_result.get("media")
                })
        except Exception:
            pass 

    # 🟢 MAIN VIDEO DOWNLOADER (YT-DLP) - ALWAYS gets Audio + Video Merged
    ydl_opts = {
        'format': 'best[ext=mp4]/best', # Forces pre-merged MP4 for sound guarantee
        'quiet': True,
        'no_warnings': True,
        'skip_download': True,
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(target_url, download=False)
            stream_url = info.get('url')
            
            if not stream_url and 'formats' in info:
                for fmt in reversed(info['formats']):
                    if fmt.get('url') and fmt.get('ext') == 'mp4':
                        stream_url = fmt['url']
                        break

            if not stream_url:
                return jsonify({"status": "error", "message": "Download link nahi mil payi."}), 404

            # Attempt to grab Instagram author from yt-dlp metadata
            author = info.get('uploader_id') or info.get('channel')

            return jsonify({
                "status": "success",
                "platform": platform,
                "type": "video",
                "author_username": author,
                "media": [{"type": "video", "url": stream_url, "thumbnail": info.get('thumbnail', '')}]
            })

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/profile_feed', methods=['GET'])
def get_profile_feed():
    username = request.args.get('username')
    if not username:
        return jsonify({"status": "error", "message": "Username required."}), 400
    
    # 🟢 USE HTML META BYPASS (Never fails on Render)
    html_data = scrape_profile_html(username)
    if html_data:
        # Feed empty rahegi kyunki Instagram cloud par bots ko feed nahi deta, par profile card smoothly dikhega!
        return jsonify({"status": "success", "user": html_data, "feed": []})

    # Ultimate Fallback (If html scraping fails)
    try:
        profile = instaloader.Profile.from_username(L.context, username)
        user_info = {
            "username": profile.username,
            "full_name": profile.full_name,
            "bio": profile.biography,
            "followers": profile.followers,
            "profile_pic": profile.profile_pic_url
        }
        return jsonify({"status": "success", "user": user_info, "feed": []})
    except Exception as e:
        return jsonify({"status": "error", "message": "Profile fetch failed."}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
