"""Queue deployment identity; namespace changes never change DB authority."""

import hashlib
import json
import re

from flask import current_app, has_app_context
from sqlalchemy.engine import make_url


def study_queue_prefix(*, require_namespace: bool = False) -> str:
    namespace = str(current_app.config.get("STUDY_QUEUE_NAMESPACE", "") or "").strip() if has_app_context() else ""
    if not namespace:
        if require_namespace:
            raise ValueError("The continuous Study worker requires STUDY_QUEUE_NAMESPACE.")
        return "flama:study"
    if not re.fullmatch(r"[a-zA-Z0-9_-]{1,64}", namespace):
        raise ValueError("STUDY_QUEUE_NAMESPACE must contain 1-64 letters, digits, underscores or hyphens.")
    url = make_url(current_app.config["SQLALCHEMY_DATABASE_URI"])
    # Credential rotation must not split a pool; different DBs must not consume
    # each other's hints. Endpoints/namespace must match between HTTP and worker.
    identity = [url.get_backend_name(), url.host, url.port, url.database, url.query.get("unix_socket")]
    digest = hashlib.sha256(json.dumps(identity, separators=(",", ":")).encode()).hexdigest()[:32]
    return f"flama:study:{namespace}:{digest}"


def study_queue_key(suffix: str) -> str:
    return f"{study_queue_prefix()}:{suffix}"
