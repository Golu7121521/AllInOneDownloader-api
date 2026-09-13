from flask import Flask, request, jsonify
from flask_cors import CORS
import yt_dlp
import instaloader
import re

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
    return "Generic"

def extract_instagram_data(url):
    clean_url = url.split("?")[0].rstrip("/")

    # 1. Profile Picture: instagram.com/username
    profile_match = re.search(r"instagram\.com/([a-zA-Z0-9_\.]+)/?$", clean_url)
    if profile_match and not any(x in clean_url for x in ["/p/", "/reel/", "/stories/", "/tv/"]):
        username = profile_match.group(1)
        profile = instaloader.Profile.from_username(L.context, username)
        return {
            "type": "profile",
            "title": f"Profile - @{profile.username}",
            "author_username": profile.username,
            "media": [{
                "type": "image",
                "url": profile.profile_pic_url,
                "thumbnail": profile.profile_pic_url
            }]
        }

    # 2. Posts, Reels: instagram.com/p/CODE
    post_match = re.search(r"/(?:p|reel|tv)/([^/?#&]+)", clean_url)
    if post_match:
        shortcode = post_match.group(1)
        post = instaloader.Post.from_shortcode(L.context, shortcode)
        
        media_list = []
        if post.typename == 'GraphSidecar':
            for node in post.get_sidecar_nodes():
                media_list.append({
                    "type": "video" if node.is_video else "image",
                    "url": node.video_url if node.is_video else node.display_url
                })
        else:
            media_list.append({
                "type": "video" if post.is_video else "image",
                "url": post.video_url if post.is_video else post.url
            })

        return {
            "type": "post" if len(media_list) > 1 else ("video" if post.is_video else "image"),
            "title": post.caption[:60] if post.caption else f"Instagram_{shortcode}",
            "author_username": post.owner_username, # ✅ Yaha se hume user ka pata chalega
            "media": media_list
        }
    return None

@app.route('/download', methods=['GET'])
def download_media():
    target_url = request.args.get('url')
    if not target_url:
        return jsonify({"status": "error", "message": "URL parameter missing."}), 400

    platform = detect_platform(target_url)

    if platform == "Instagram":
        try:
            insta_result = extract_instagram_data(target_url)
            if insta_result:
                return jsonify({
                    "status": "success",
                    "platform": "Instagram",
                    "title": insta_result.get("title", "Instagram Media"),
                    "type": insta_result.get("type"),
                    "author_username": insta_result.get("author_username"),
                    "media": insta_result.get("media")
                })
        except Exception as e:
            pass

    # yt-dlp Fallback for others
    ydl_opts = {'format': 'best', 'quiet': True, 'no_warnings': True, 'skip_download': True}
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(target_url, download=False)
            stream_url = info.get('url')
            if not stream_url and 'formats' in info:
                for fmt in reversed(info['formats']):
                    if fmt.get('url'):
                        stream_url = fmt['url']
                        break
            if stream_url:
                return jsonify({
                    "status": "success",
                    "platform": platform,
                    "title": info.get('title', 'Media'),
                    "type": "video",
                    "media": [{"type": "video", "url": stream_url}]
                })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# ✅ NAYA ENDPOINT: Username se uski Profile aur Latest Feed nikalne ke liye
@app.route('/profile_feed', methods=['GET'])
def get_profile_feed():
    username = request.args.get('username')
    if not username:
        return jsonify({"status": "error", "message": "Username required."}), 400
    
    try:
        profile = instaloader.Profile.from_username(L.context, username)
        
        # Profile ki basic details
        user_info = {
            "username": profile.username,
            "full_name": profile.full_name,
            "bio": profile.biography,
            "followers": profile.followers,
            "profile_pic": profile.profile_pic_url
        }

        # Latest 6-9 posts fetch karna (zyada karne par ban ho sakta hai)
        recent_posts = []
        count = 0
        for post in profile.get_posts():
            if count >= 6: 
                break
            recent_posts.append({
                "shortcode": post.shortcode,
                "is_video": post.is_video,
                "thumbnail": post.url,
                "link": f"https://www.instagram.com/p/{post.shortcode}/"
            })
            count += 1
            
        return jsonify({"status": "success", "user": user_info, "feed": recent_posts})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
