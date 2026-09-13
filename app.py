from flask import Flask, request, jsonify
from flask_cors import CORS
import yt_dlp
import instaloader
import re
import requests

app = Flask(__name__)
CORS(app)

# Instaloader setup
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

# Secret API bypass function for Profile if Instaloader is blocked by Instagram
def fallback_profile_fetch(username):
    url = f"https://i.instagram.com/api/v1/users/web_profile_info/?username={username}"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
        'X-IG-App-ID': '936619743392459', # This bypasses basic blocks
        'Accept': '*/*'
    }
    try:
        res = requests.get(url, headers=headers, timeout=10)
        if res.status_code == 200:
            data = res.json()
            user = data['data']['user']
            feed = []
            for edge in user['edge_owner_to_timeline_media']['edges'][:9]:
                node = edge['node']
                feed.append({
                    "shortcode": node['shortcode'],
                    "is_video": node.get('is_video', False),
                    "thumbnail": node.get('display_url'),
                    "link": f"https://www.instagram.com/p/{node['shortcode']}/"
                })
            return {
                "user": {
                    "username": user['username'],
                    "full_name": user['full_name'],
                    "bio": user['biography'],
                    "followers": user['edge_followed_by']['count'],
                    "profile_pic": user['profile_pic_url_hd']
                },
                "feed": feed
            }
    except Exception as e:
        print("Fallback fetch error:", e)
    return None

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
            "media": [{"type": "image", "url": profile.profile_pic_url, "thumbnail": profile.profile_pic_url}]
        }

    # 2. Posts & Carousels
    post_match = re.search(r"/(?:p|reel|tv)/([^/?#&]+)", clean_url)
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
            "title": post.caption[:60] if post.caption else f"Instagram_{shortcode}",
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

    # 1. Try Instaloader for Instagram first
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
            print("Instaloader failed, falling back to yt-dlp:", str(e))
            pass 

    # 2. Fallback / Main Downloader (yt-dlp) - With SOUND FIX ✅
    ydl_opts = {
        'format': 'best', 
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
            
            # SOUND FIX: Filtering only formats that have BOTH Video AND Audio
            if not stream_url and 'formats' in info:
                valid_formats = [fmt for fmt in info['formats'] if fmt.get('vcodec') != 'none' and fmt.get('acodec') != 'none']
                if valid_formats:
                    # Picks the highest quality format that contains sound
                    stream_url = valid_formats[-1].get('url')
                else:
                    # Ultimate fallback
                    for fmt in reversed(info['formats']):
                        if fmt.get('url'):
                            stream_url = fmt['url']
                            break

            if not stream_url:
                return jsonify({"status": "error", "message": "Download link nahi mil payi."}), 404

            # Get Author username from yt-dlp if available
            author = info.get('uploader_id') or info.get('uploader') or info.get('channel')

            return jsonify({
                "status": "success",
                "platform": platform,
                "title": info.get('title', 'Downloaded_Media'),
                "type": "video",
                "author_username": author, # UI ko pata chalega kiski profile hai
                "media": [{"type": "video", "url": stream_url, "thumbnail": info.get('thumbnail', '')}]
            })

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/profile_feed', methods=['GET'])
def get_profile_feed():
    username = request.args.get('username')
    if not username:
        return jsonify({"status": "error", "message": "Username required."}), 400
    
    # METHOD 1: Try Secret API Bypass (Works best on Cloud IPs like Render)
    bypass_data = fallback_profile_fetch(username)
    if bypass_data:
        return jsonify({"status": "success", "user": bypass_data["user"], "feed": bypass_data["feed"]})

    # METHOD 2: Fallback to Instaloader
    try:
        profile = instaloader.Profile.from_username(L.context, username)
        user_info = {
            "username": profile.username,
            "full_name": profile.full_name,
            "bio": profile.biography,
            "followers": profile.followers,
            "profile_pic": profile.profile_pic_url
        }
        recent_posts = []
        try:
            count = 0
            for post in profile.get_posts():
                if count >= 6: break
                recent_posts.append({
                    "shortcode": post.shortcode,
                    "is_video": post.is_video,
                    "thumbnail": post.url,
                    "link": f"https://www.instagram.com/p/{post.shortcode}/"
                })
                count += 1
        except Exception:
            pass # Ignore feed error if blocked
            
        return jsonify({"status": "success", "user": user_info, "feed": recent_posts})
    except Exception as e:
        return jsonify({"status": "error", "message": f"Server IP is blocked by Instagram. {str(e)}"}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
