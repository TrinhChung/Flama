"""JSON validation and wire encoding, independent of persistence and clients."""

import json
from typing import Any

from app.services.connect.registry import ACTIONS, FLAMA_CONNECT_PROTOCOL_VERSION


class ProtocolError(ValueError):
    pass


def _unique_properties(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ProtocolError("duplicate JSON property")
        result[key] = value
    return result


def _invalid_constant(value):
    raise ProtocolError(f"invalid JSON number: {value}")


def _depth(value, depth=0):
    if depth > 12:
        raise ProtocolError("JSON nesting is too deep")
    children = value.values() if isinstance(value, dict) else value if isinstance(value, list) else ()
    for child in children:
        _depth(child, depth + 1)


def validate_payload(payload: Any, *, standard: bool, legacy_web: bool = False) -> dict:
    if not isinstance(payload, dict):
        raise ProtocolError("request body must be a JSON object")
    _depth(payload)
    if set(payload) - {"action", "params", "version", "key"} or "action" not in payload:
        raise ProtocolError("request properties are invalid")
    if not standard and "version" not in payload:
        raise ProtocolError("request properties are invalid")
    action = payload["action"]
    if not isinstance(action, str) or not action.isascii() or not 1 <= len(action) <= 64:
        raise ProtocolError("action is invalid")
    spec = ACTIONS.get(action)
    if spec is None or (spec.legacy_only and (standard or not legacy_web)):
        raise ProtocolError("unsupported action")
    version = payload.get("version", 4)
    if isinstance(version, bool) or not isinstance(version, int) or not 2 <= version <= FLAMA_CONNECT_PROTOCOL_VERSION:
        raise ProtocolError(f"version must be an integer between 2 and {FLAMA_CONNECT_PROTOCOL_VERSION}")
    params = payload.get("params", {})
    if not isinstance(params, dict):
        raise ProtocolError("params must be an object")
    allowed = spec.params
    if action == "storeMediaFile":
        if standard:
            allowed = frozenset({"filename", "data", "deleteExisting"})
        elif not legacy_web:
            allowed = frozenset({"filename", "data"})
    if set(params) - allowed:
        raise ProtocolError("params contains unsupported properties")
    if standard and "key" in payload and not isinstance(payload["key"], str):
        raise ProtocolError("key must be a string")
    return {**payload, "version": version, "params": params}


def parse_body(raw: bytes, *, content_type: str, encoding: str, limit: int, standard: bool, legacy_web: bool = False) -> dict:
    permitted = {"application/json", "text/plain", ""} if standard else {"application/json"}
    if content_type.lower() not in permitted:
        raise ProtocolError("unsupported Content-Type" if standard else "Content-Type must be application/json")
    if encoding.strip().lower() not in {"", "identity"}:
        raise ProtocolError("compressed request bodies are not supported")
    if len(raw) > limit:
        raise ProtocolError("request body is too large")
    if not raw:
        raise ProtocolError("request body is required")
    try:
        payload = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_properties, parse_constant=_invalid_constant)
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as exc:
        raise ProtocolError("request body is not valid JSON") from exc
    return validate_payload(payload, standard=standard, legacy_web=legacy_web)


def encode_result(result=None, error=None, *, version=4, versioned=True):
    if error is not None:
        return {"result": None, "error": str(error)}
    if versioned and version >= 5:
        return {"result": result, "error": None}
    return result
