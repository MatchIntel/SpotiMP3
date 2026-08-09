import os
import shutil
import subprocess
import uuid
import tempfile
from flask import Flask, render_template_string, request, send_file, jsonify

app = Flask(__name__)

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
            btn.innerText = 'Processing tracks... (This may take a minute)';
            status.innerText = 'Extracting playlist metadata & embedding artwork...';

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
                } else {
                    status.innerText = 'Error: ' + (data.error || 'Something went wrong');
                    btn.disabled = false;
                    btn.innerText = 'Convert & Download ZIP';
                }
            } catch (err) {
                status.innerText = 'Network error occurred.';
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
        # Run spotDL to automatically handle track parsing, conversion, and ID3 artwork embedding
        cmd = ["spotdl", playlist_url, "--output", session_dir]
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            return jsonify({"error": f"Download failed: {result.stderr.strip()}"}), 500

        mp3_files = [f for f in os.listdir(session_dir) if f.endswith(".mp3")]
        if not mp3_files:
            return jsonify({"error": "No tracks found or downloaded from the link."}), 404

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
