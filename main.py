import os
import shutil
import uuid
import tempfile
import json
import re
import requests
from flask import Flask, render_template_string, request, send_file, jsonify
from ytmusicapi import YTMusic
import yt_dlp

app = Flask(__name__)
ytmusic = YTMusic()

HTML_PAGE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Jet Ski Music Converter</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #0f172a; color: #f8fafc; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }
        .card { background: #1e293b; padding: 2.5rem; border-radius: 1rem; box-shadow: 0 10px 25px rgba(0,0,0,0.3); width: 100%; max-width: 450px; text-align: center; }
        h1 { font-size: 1.5rem; margin-bottom: 0.5rem; color: #38bdf8; }
        p { color: #94a3b8; font-size: 0.9rem; margin-bottom: 1.5rem; }
        input { width: 100%; padding: 0.75rem; border-radius: 0.5rem; border: 1px solid #475569; background: #0f172a; color: #fff; font-size: 1rem; margin-bottom: 1rem; box-sizing: border-box; }
        button { background: #0284c7; color: white; border: none; padding: 0.75rem 1.5rem; border-radius: 0.5rem; font-size: 1rem; font-weight: bold; cursor: pointer; width: 100%; transition: background 0.2s; }
        button:hover { background: #0ea5e9; }
        button:disabled { background: #475569; cursor: not-allowed; }
        #status { margin-top: 1rem; font-size: 0.9rem; color: #38bdf8; }
    </style>
</head>
<body>
    <div class="card">
        <h1>Marine Audio Sync</h1>
        <p>Paste a Spotify playlist link to package tracks with embedded artwork for your app.</p>
        <input type="text" id="playlistUrl" placeholder="https://open.spotify.com/playlist/...">
        <button id="convertBtn" onclick="startConversion()">Convert & Download ZIP</button>
        <div id="status"></div>
    </div>

    <script>
        async function startConversion() {
            const url = document.getElementById('playlistUrl').value.trim();
            const btn = document.getElementById('convertBtn');
            const status = document.getElementById('status');

            if (!url) {
                alert('Please enter a valid Spotify link.');
                return;
            }

            btn.disabled = true;
            btn.innerText = 'Processing...';
            status.innerText = 'Bypassing restrictions & downloading...';

            try {
                const response = await fetch('/convert', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ url })
                });

                const data = await response.json();

                if (response.ok) {
                    status.innerText = 'Success! Downloading your ZIP file...';
                    window.location.href = `/download/${data.download_token}`;
                    btn.innerText = 'Done!';
                    setTimeout(() => { btn.disabled = false; btn.innerText = 'Convert & Download ZIP'; }, 3000);
                } else {
                    status.innerText = 'Error: ' + (data.error || 'Something went wrong');
                    btn.disabled = false;
                    btn.innerText = 'Convert & Download ZIP';
                }
            } catch (err) {
                status.innerText = 'Network error or timeout occurred.';
                btn.disabled = false;
                btn.innerText = 'Convert & Download ZIP';
            }
        }
    </script>
</body>
</html>
"""

@app.route("/")
def index():
    return render_template_string(HTML_PAGE)

def extract_tracks_from_json(data):
    tracks = []
    if isinstance(data, dict):
        if data.get("__typename") == "Track" or ("track" in data and isinstance(data["track"], dict)):
            track_obj = data.get("track", data)
            name = track_obj.get("name")
            artists = track_obj.get("artists")
            if name and artists:
                artist_names = ", ".join([a.get("name", "") for a in artists if isinstance(a, dict)])
                if artist_names:
                    tracks.append(f"{artist_names} - {name}")
        for k, v in data.items():
            tracks.extend(extract_tracks_from_json(v))
    elif isinstance(data, list):
        for item in data:
            tracks.extend(extract_tracks_from_json(item))
    return tracks

@app.route("/convert", methods=["POST"])
def convert_playlist():
    data = request.get_json()
    playlist_url = data.get("url")
    
    if not playlist_url:
        return jsonify({"error": "No URL provided"}), 400

    session_id = str(uuid.uuid4())
    session_dir = os.path.join(tempfile.gettempdir(), session_id)
    os.makedirs(session_dir, exist_ok=True)

    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        resp = requests.get(playlist_url, headers=headers)
        
        track_queries = []
        script_match = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.+?)</script>', resp.text, re.DOTALL)
        if script_match:
            try:
                json_data = json.loads(script_match.group(1))
                track_queries = list(set(extract_tracks_from_json(json_data)))
            except Exception:
                pass

        if not track_queries:
            song_matches = re.findall(r'"name"\s*:\s*"([^"]+)"', resp.text)
            if song_matches:
                track_queries = song_matches[:5]

        if not track_queries:
            return jsonify({"error": "Could not read tracks. Ensure the playlist is public."}), 400

        downloaded_count = 0
        for query in track_queries[:5]:
            try:
                search_results = ytmusic.search(query, filter="songs", limit=1)
                if search_results:
                    video_id = search_results[0]['videoId']
                    video_url = f"https://www.youtube.com/watch?v={video_id}"
                    
                    ydl_opts = {
                        'format': 'bestaudio/best',
                        'outtmpl': os.path.join(session_dir, '%(title)s.%(ext)s'),
                        'postprocessors': [{
                            'key': 'FFmpegExtractAudio',
                            'preferredcodec': 'mp3',
                            'preferredquality': '128',
                        }],
                        'extractor_args': {
                            'youtube': {
                                'player_client': ['android', 'web']
                            }
                        },
                        'quiet': True,
                        'socket_timeout': 10
                    }
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        ydl.download([video_url])
                        downloaded_count += 1
            except Exception:
                continue

        if downloaded_count == 0:
            return jsonify({"error": "Failed to download tracks from search results."}), 404

        zip_base_path = os.path.join(tempfile.gettempdir(), session_id)
        shutil.make_archive(zip_base_path, 'zip', session_dir)

        return jsonify({"success": True, "download_token": session_id})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/download/<token>", methods=["GET"])
def download_zip(token):
    zip_path = os.path.join(tempfile.gettempdir(), f"{token}.zip")
    if os.path.exists(zip_path):
        return send_file(zip_path, as_attachment=True, download_name="marine_playlist.zip")
    return "File not found or expired.", 404

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
