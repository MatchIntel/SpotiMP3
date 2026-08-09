import os
import shutil
import subprocess
import uuid
import tempfile
from flask import Flask, render_template, request, send_file, jsonify

app = Flask(__name__)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/convert", methods=["POST"])
def convert_playlist():
    data = request.get_json()
    playlist_url = data.get("url")
    
    if not playlist_url:
        return jsonify({"error": "No URL provided"}), 400

    # Use a secure temporary directory for processing
    session_id = str(uuid.uuid4())
    session_dir = os.path.join(tempfile.gettempdir(), session_id)
    os.makedirs(session_dir, exist_ok=True)

    try:
        # Run spotDL command
        cmd = ["spotdl", playlist_url, "--output", session_dir]
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            return jsonify({"error": f"Download failed: {result.stderr}"}), 500

        # Check for generated mp3 files
        mp3_files = [f for f in os.listdir(session_dir) if f.endswith(".mp3")]
        if not mp3_files:
            return jsonify({"error": "No tracks found or downloaded from the link."}), 404

        # Bundle into a zip archive inside temp storage
        zip_base_path = os.path.join(tempfile.gettempdir(), session_id)
        zip_path = shutil.make_archive(zip_base_path, 'zip', session_dir)

        return jsonify({"success": True, "download_token": session_id})

    except Exception as e:
        return jsonify({"error": str(e)}, 500)

@app.route("/download/<token>", methods=["GET"])
def download_zip(token):
    zip_path = os.path.join(tempfile.gettempdir(), f"{token}.zip")
    if os.path.exists(zip_path):
        return send_file(zip_path, as_attachment=True, download_name="marine_playlist.zip")
    return "File not found or expired.", 404

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
