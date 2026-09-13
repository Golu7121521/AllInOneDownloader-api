from flask import Flask, request, jsonify
from flask_cors import CORS
import yt_dlp
import instaloader
import re

app = Flask(__name__)
CORS(app)

# Instaloader setup without saving files locally
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
    elif "tiktok.com" in u:
        return "TikTok"
    elif "pin.it" in u or "pinterest.com" in u:
        return "Pinterest"
    elif "reddit.com" in u:
        return "Reddit"
    return "Generic"

def extract_instagram_data(url):
    """
    Handles Instagram Post, Reel, Carousel, and Profile Pic extraction
    """
    clean_url = url.split("?")[0].rstrip("/")

    # 1. Profile Picture: instagram.com/username
    profile_match = re.search(r"instagram\.com/([a-zA-Z0-9_\.]+)/?$", clean_url)
    if profile_match and not any(x in clean_url for x in ["/p/", "/reel/", "/stories/", "/tv/"]):
        username = profile_match.group(1)
        profile = instaloader.Profile.from_username(L.context, username)
        return {
            "type": "profile",
            "title": f"Profile - @{profile.username}",
            "media": [{
                "type": "image",
                "url": profile.profile_pic_url,
                "thumbnail": profile.profile_pic_url
            }],
            "bio": profile.biography
        }

    # 2. Posts, Multi-image Posters, Reels: instagram.com/p/CODE or /reel/CODE
    post_match = re.search(r"/(?:p|reel|tv)/([^/?#&]+)", clean_url)
    if post_match:
        shortcode = post_match.group(1)
        post = instaloader.Post.from_shortcode(L.context, shortcode)
        
        media_list = []
        if post.typename == 'GraphSidecar':  # Multi-media / Carousel
            for node in post.get_sidecar_nodes():
                media_list.append({
                    "type": "video" if node.is_video else "image",
                    "url": node.video_url if node.is_video else node.display_url,
                    "thumbnail": node.display_url
                })
        else:
            media_list.append({
                "type": "video" if post.is_video else "image",
                "url": post.video_url if post.is_video else post.url,
                "thumbnail": post.url
            })

        return {
            "type": "post" if len(media_list) > 1 else ("video" if post.is_video else "image"),
            "title": post.caption[:60] if post.caption else f"Instagram_{shortcode}",
            "media": media_list
        }

    return None

@app.route('/download', methods=['GET'])
def download_media():
    target_url = request.args.get('url')
    
    if not target_url:
        return jsonify({
            "status": "error",
            "message": "URL parameter missing. Example: /download?url=<link>"
        }), 400

    u = target_url.lower()
    if "youtube.com" in u or "youtu.be" in u:
        return jsonify({
            "status": "error",
            "message": "YouTube downloads are not supported on this endpoint."
        }), 400

    platform = detect_platform(target_url)

    # 1. Instagram Custom Handler (Photos, Profile, Reels, Multi-items)
    if platform == "Instagram":
        try:
            insta_result = extract_instagram_data(target_url)
            if insta_result:
                return jsonify({
                    "status": "success",
                    "platform": "Instagram",
                    "title": insta_result.get("title", "Instagram Media"),
                    "type": insta_result.get("type"),
                    "media": insta_result.get("media")
                })
        except Exception as e:
            # Agar instaloader fail ho to yt-dlp fallback chalne de
            pass

    # 2. General / Video Handler with yt-dlp (Reels, FB, Twitter, Reddit)
    ydl_opts = {
        'format': 'best[ext=mp4]/best',
        'quiet': True,
        'no_warnings': True,
        'skip_download': True,
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
        }
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
                return jsonify({
                    "status": "error",
                    "message": "Direct download link nahi mil payi."
                }), 404

            return jsonify({
                "status": "success",
                "platform": platform,
                "title": info.get('title', 'Downloaded_Media'),
                "type": "video",
                "media": [{
                    "type": "video",
                    "url": stream_url,
                    "thumbnail": info.get('thumbnail', '')
                }]
            })

    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

@app.route('/', methods=['GET'])
def health_check():
    return jsonify({
        "status": "active",
        "service": "All Media & Profile Downloader API",
        "supported": ["Instagram (Reels, Posts, Profile)", "Facebook", "Twitter", "TikTok", "Pinterest", "Reddit"]
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
