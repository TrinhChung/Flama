"""Download endpoints for desktop applications and local service tools."""

from __future__ import annotations

import os

from flask import Blueprint, abort, current_app, redirect, send_file

FLAMA_AUDIO_FILENAME = "FlamaAudio-Portable.exe"
SYSTEM_FLAMA_AUDIO_PATH = f"/var/lib/flama/downloads/{FLAMA_AUDIO_FILENAME}"

download_bp = Blueprint("download", __name__)


@download_bp.route("/download/flama-audio", methods=["GET"])
def download_flama_audio():
    """Download the current portable Flama Audio Windows executable."""

    if current_app.static_folder:
        local_executable_path = os.path.join(
            current_app.static_folder, "downloads", FLAMA_AUDIO_FILENAME
        )
        if os.path.isfile(local_executable_path):
            return send_file(
                local_executable_path,
                as_attachment=True,
                download_name=FLAMA_AUDIO_FILENAME,
                mimetype="application/x-msdownload",
            )

    if os.path.isfile(SYSTEM_FLAMA_AUDIO_PATH):
        return send_file(
            SYSTEM_FLAMA_AUDIO_PATH,
            as_attachment=True,
            download_name=FLAMA_AUDIO_FILENAME,
            mimetype="application/x-msdownload",
        )

    custom_url = os.environ.get("FLAMA_AUDIO_DOWNLOAD_URL", "").strip()
    if custom_url:
        return redirect(custom_url, code=302)

    abort(503, description="Flama Audio portable executable is not available yet.")
