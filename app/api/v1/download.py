"""Download endpoints for desktop applications and local service tools."""

from __future__ import annotations

import os
from flask import Blueprint, current_app, redirect, send_file

DEFAULT_FLAMA_AUDIO_RELEASE_URL = (
    "https://github.com/TrinhChung/Flama/releases/latest/download/FlamaAudio-Setup.exe"
)

download_bp = Blueprint("download", __name__)


@download_bp.route("/download/flama-audio", methods=["GET"])
def download_flama_audio():
    """Download or redirect to the Flama Audio Windows installer executable."""
    custom_url = os.environ.get("FLAMA_AUDIO_DOWNLOAD_URL", "").strip()
    if custom_url:
        return redirect(custom_url, code=302)

    if current_app.static_folder:
        local_installer_path = os.path.join(
            current_app.static_folder, "downloads", "FlamaAudio-Setup.exe"
        )
        if os.path.isfile(local_installer_path):
            return send_file(
                local_installer_path,
                as_attachment=True,
                download_name="FlamaAudio-Setup.exe",
                mimetype="application/x-msdownload",
            )

    system_installer_path = "/var/lib/flama/downloads/FlamaAudio-Setup.exe"
    if os.path.isfile(system_installer_path):
        return send_file(
            system_installer_path,
            as_attachment=True,
            download_name="FlamaAudio-Setup.exe",
            mimetype="application/x-msdownload",
        )

    return redirect(DEFAULT_FLAMA_AUDIO_RELEASE_URL, code=302)
