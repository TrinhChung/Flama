"""Download endpoints for desktop applications and local service tools."""

from __future__ import annotations

import os
from urllib.parse import urlparse

from flask import Blueprint, abort, current_app, redirect, send_file

FLAMA_AUDIO_FILENAME = "FlamaAudio-Portable.exe"
FLAMA_AUDIO_CHECKSUM_FILENAME = f"{FLAMA_AUDIO_FILENAME}.sha256"
SYSTEM_FLAMA_AUDIO_PATH = f"/var/lib/flama/downloads/{FLAMA_AUDIO_FILENAME}"
SYSTEM_FLAMA_AUDIO_CHECKSUM_PATH = (
    f"/var/lib/flama/downloads/{FLAMA_AUDIO_CHECKSUM_FILENAME}"
)

download_bp = Blueprint("download", __name__)


def _send_immutable_release_file(path: str, *, filename: str, mimetype: str):
    response = send_file(
        path,
        as_attachment=True,
        download_name=filename,
        mimetype=mimetype,
    )
    response.headers["Cache-Control"] = "no-cache, no-transform"
    return response


def _https_redirect_from_env(variable_name: str):
    custom_url = os.environ.get(variable_name, "").strip()
    if not custom_url:
        return None

    parsed = urlparse(custom_url)
    if parsed.scheme.lower() != "https" or not parsed.netloc:
        abort(503, description=f"{variable_name} must be an absolute HTTPS URL.")
    return redirect(custom_url, code=302)


@download_bp.route("/download/flama-audio", methods=["GET"])
def download_flama_audio():
    """Download the current portable Flama Audio Windows executable."""

    if current_app.static_folder:
        local_executable_path = os.path.join(
            current_app.static_folder, "downloads", FLAMA_AUDIO_FILENAME
        )
        if os.path.isfile(local_executable_path):
            return _send_immutable_release_file(
                local_executable_path,
                filename=FLAMA_AUDIO_FILENAME,
                mimetype="application/x-msdownload",
            )

    if os.path.isfile(SYSTEM_FLAMA_AUDIO_PATH):
        return _send_immutable_release_file(
            SYSTEM_FLAMA_AUDIO_PATH,
            filename=FLAMA_AUDIO_FILENAME,
            mimetype="application/x-msdownload",
        )

    custom_redirect = _https_redirect_from_env("FLAMA_AUDIO_DOWNLOAD_URL")
    if custom_redirect is not None:
        return custom_redirect

    abort(503, description="Flama Audio portable executable is not available yet.")


@download_bp.route("/download/flama-audio.sha256", methods=["GET"])
def download_flama_audio_checksum():
    """Download SHA-256 metadata generated from the signed production EXE."""

    if current_app.static_folder:
        local_checksum_path = os.path.join(
            current_app.static_folder,
            "downloads",
            FLAMA_AUDIO_CHECKSUM_FILENAME,
        )
        if os.path.isfile(local_checksum_path):
            return _send_immutable_release_file(
                local_checksum_path,
                filename=FLAMA_AUDIO_CHECKSUM_FILENAME,
                mimetype="text/plain",
            )

    if os.path.isfile(SYSTEM_FLAMA_AUDIO_CHECKSUM_PATH):
        return _send_immutable_release_file(
            SYSTEM_FLAMA_AUDIO_CHECKSUM_PATH,
            filename=FLAMA_AUDIO_CHECKSUM_FILENAME,
            mimetype="text/plain",
        )

    custom_redirect = _https_redirect_from_env("FLAMA_AUDIO_CHECKSUM_URL")
    if custom_redirect is not None:
        return custom_redirect

    abort(503, description="Flama Audio SHA-256 metadata is not available yet.")
