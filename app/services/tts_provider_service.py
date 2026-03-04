from __future__ import annotations

import base64
import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse
from urllib.request import Request, urlopen

from cryptography.fernet import Fernet, InvalidToken
from flask import current_app
from sqlalchemy.exc import SQLAlchemyError

from models.tts_provider_config import TtsProviderConfig
from models.tts_user_provider_profile import TtsUserProviderProfile

VALID_KEY_STATUSES = {"valid", "invalid", "unknown"}
VALID_ACTIVE_FILTERS = {"all", "active", "inactive"}
MAX_PROVIDER_NAME_LEN = 120
MAX_PROVIDER_TYPE_LEN = 64
MAX_BASE_URL_LEN = 500
MAX_LAST_VALIDATION_ERROR_LEN = 500
MAX_VOICEVOX_TEXT_LENGTH = 500
MAX_VOICEVOX_AUDIO_BYTES = 12 * 1024 * 1024

VOICEVOX_PROVIDER_TYPE = "voicevox"
VOICEVOX_AUDIO_BASE_URL = "https://deprecatedapis.tts.quest/v2/voicevox/audio/"
VOICEVOX_SPEAKERS_URL = "https://deprecatedapis.tts.quest/v2/voicevox/speakers/"
VOICEVOX_POINTS_URL = "https://deprecatedapis.tts.quest/v2/api/"
VOICEVOX_DEFAULT_SETTINGS: dict[str, Any] = {
    "character_id": "",
    "volume_scale": 1.0,
    "pitch_scale": 0.0,
    "pitch": 0.0,
    "speed_scale": 1.0,
    "speed": 1.0,
    "intonation_scale": 1.0,
    "initial_silence_scale": 0.1,
    "final_silence_length": 0.1,
}

DEFAULT_TTS_PROVIDER_SEEDS: tuple[dict[str, Any], ...] = (
    {
        "provider_name": "VoiceVox",
        "provider_type": VOICEVOX_PROVIDER_TYPE,
        "base_url": VOICEVOX_AUDIO_BASE_URL,
        "requires_api_key": True,
        "is_active": True,
        "shared_config": {
            "audio_url": VOICEVOX_AUDIO_BASE_URL,
            "speakers_url": VOICEVOX_SPEAKERS_URL,
        },
        "provider_config": {
            "key_validation_url": VOICEVOX_POINTS_URL,
            "key_transport": "query",
            "key_param_name": "key",
            "timeout_seconds": 8,
        },
        "default_settings": {
            "character_id": "",
            "volume_scale": 1.0,
            "pitch_scale": 0.0,
            "pitch": 0.0,
            "speed_scale": 1.0,
            "speed": 1.0,
            "intonation_scale": 1.0,
            "initial_silence_scale": 0.1,
            "final_silence_length": 0.1,
        },
    },
)

UNSET = object()


def _build_fernet() -> Fernet:
    secret = str(current_app.config.get("SECRET_KEY") or "change-me").encode("utf-8")
    digest = hashlib.sha256(secret).digest()
    key = base64.urlsafe_b64encode(digest)
    return Fernet(key)


def encrypt_api_key(raw_value: str) -> str:
    if not raw_value:
        return ""
    token = _build_fernet().encrypt(raw_value.encode("utf-8"))
    return token.decode("utf-8")


def decrypt_api_key(ciphertext: str | None) -> str:
    if not ciphertext:
        return ""
    try:
        plain = _build_fernet().decrypt(ciphertext.encode("utf-8"))
        return plain.decode("utf-8")
    except (InvalidToken, ValueError):
        return ""


def mask_api_key(ciphertext: str | None) -> str:
    raw = decrypt_api_key(ciphertext)
    if not raw:
        return ""
    if len(raw) <= 8:
        return "*" * len(raw)
    return f"{raw[:4]}{'*' * (len(raw) - 8)}{raw[-4:]}"


def normalize_key_status(value: str | None) -> str:
    normalized = str(value or "").strip().lower()
    if normalized in VALID_KEY_STATUSES:
        return normalized
    return "unknown"


def parse_optional_datetime(value: str | None) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def normalize_active_filter(value: str | None) -> str:
    normalized = str(value or "all").strip().lower()
    if normalized in VALID_ACTIVE_FILTERS:
        return normalized
    return "all"


def normalize_provider_type_filter(value: str | None) -> str:
    normalized = str(value or "").strip().lower()
    if not normalized:
        return ""
    # provider_type follows a slug-like convention for stable filtering/querying.
    normalized = re.sub(r"[^a-z0-9_-]+", "-", normalized)
    normalized = re.sub(r"-{2,}", "-", normalized).strip("-_")
    return normalized[:MAX_PROVIDER_TYPE_LEN]


def normalize_search_query(value: str | None) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    return text[:120]


def format_datetime_local(value: datetime | None) -> str:
    if value is None:
        return ""
    return value.strftime("%Y-%m-%dT%H:%M")


def parse_datetime_local(value: str | None) -> tuple[datetime | None, bool]:
    text = str(value or "").strip()
    if not text:
        return None, False
    parsed = parse_optional_datetime(text)
    if parsed is None:
        return None, True
    return parsed, False


def is_truthy(value: Any) -> bool:
    token = str(value or "").strip().lower()
    return token in {"1", "true", "on", "yes", "y"}


def is_valid_http_url(value: str | None) -> bool:
    if not value:
        return True
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def coerce_mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return {str(key): item for key, item in value.items()}
    return {}


def dumps_json_map(value: dict[str, Any] | None) -> str:
    payload = coerce_mapping(value or {})
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def loads_json_map(text: str | None) -> dict[str, Any]:
    raw = str(text or "").strip()
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError):
        return {}
    return coerce_mapping(parsed)


def pretty_json(value: dict[str, Any] | None) -> str:
    payload = coerce_mapping(value or {})
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)


def parse_json_text_field(value: Any, *, field_label: str, errors: list[str]) -> dict[str, Any]:
    text = str(value or "").strip()
    if not text:
        return {}
    try:
        parsed = json.loads(text)
    except (TypeError, ValueError):
        errors.append(f"{field_label} phải là JSON hợp lệ.")
        return {}
    if not isinstance(parsed, dict):
        errors.append(f"{field_label} phải là JSON object.")
        return {}
    return {str(key): item for key, item in parsed.items()}


def _normalize_provider_name(value: Any) -> str:
    text = " ".join(str(value or "").strip().split())
    return text[:MAX_PROVIDER_NAME_LEN]


def _normalize_provider_type(value: Any) -> str:
    normalized = normalize_provider_type_filter(value)
    return normalized[:MAX_PROVIDER_TYPE_LEN]


def _normalize_optional_base_url(value: Any) -> str | None:
    normalized = str(value or "").strip()
    if not normalized:
        return None
    return normalized[:MAX_BASE_URL_LEN]


def _normalize_voicevox_float(
    value: Any,
    *,
    fallback: float,
    minimum: float,
    maximum: float,
) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return fallback
    return max(minimum, min(maximum, parsed))


def _detect_audio_mime_and_extension(
    content: bytes,
    *,
    response_content_type: str | None = None,
) -> tuple[str, str]:
    if len(content) >= 12 and content[:4] == b"RIFF" and content[8:12] == b"WAVE":
        return "audio/wav", "wav"
    if content.startswith(b"OggS"):
        return "audio/ogg", "ogg"
    if content.startswith(b"fLaC"):
        return "audio/flac", "flac"
    if content.startswith(b"ID3") or (len(content) >= 2 and content[0] == 0xFF and (content[1] & 0xE0) == 0xE0):
        return "audio/mpeg", "mp3"

    content_type = str(response_content_type or "").split(";", 1)[0].strip().lower()
    if content_type in {"audio/wav", "audio/x-wav"}:
        return "audio/wav", "wav"
    if content_type in {"audio/ogg", "application/ogg"}:
        return "audio/ogg", "ogg"
    if content_type in {"audio/mpeg", "audio/mp3"}:
        return "audio/mpeg", "mp3"
    return "application/octet-stream", "bin"


def _parse_voicevox_error_message(raw_body: bytes | None) -> str:
    if not raw_body:
        return ""
    try:
        payload = json.loads((raw_body or b"").decode("utf-8", errors="ignore"))
    except (TypeError, ValueError):
        return ""

    if isinstance(payload, dict):
        for key in ("errorMessage", "error", "message", "detail"):
            value = str(payload.get(key) or "").strip()
            if value:
                return value
    if isinstance(payload, list) and payload:
        first = payload[0]
        if isinstance(first, dict):
            for key in ("errorMessage", "error", "message", "detail"):
                value = str(first.get(key) or "").strip()
                if value:
                    return value
    return ""


@dataclass(slots=True)
class ApiKeyValidationResult:
    valid: bool
    status: str
    checked_at: datetime
    message: str


@dataclass(slots=True)
class SynthesizedAudioResult:
    content: bytes
    mime_type: str
    extension: str
    content_type_header: str


class BaseTtsProviderAdapter:
    provider_type = "generic"

    def default_shared_config(self) -> dict[str, Any]:
        return {}

    def default_provider_config(self) -> dict[str, Any]:
        return {}

    def default_user_settings(self) -> dict[str, Any]:
        return {}

    def normalize_user_settings(
        self,
        value: dict[str, Any],
        *,
        default_settings: dict[str, Any],
    ) -> tuple[dict[str, Any], list[str]]:
        normalized = coerce_mapping(default_settings)
        normalized.update(coerce_mapping(value))
        return normalized, []

    def supports_key_validation(self) -> bool:
        return False

    def list_voices(
        self,
        provider: TtsProviderConfig,
        api_key: str,
    ) -> tuple[list[dict[str, Any]], str | None]:
        del provider
        del api_key
        return [], "Provider này chưa hỗ trợ danh sách nhân vật/voice."

    def validate_api_key(self, provider: TtsProviderConfig, api_key: str) -> ApiKeyValidationResult:
        return ApiKeyValidationResult(
            valid=False,
            status="unknown",
            checked_at=datetime.utcnow(),
            message="Provider này chưa hỗ trợ validate API key tự động.",
        )


class VoicevoxTtsProviderAdapter(BaseTtsProviderAdapter):
    provider_type = VOICEVOX_PROVIDER_TYPE

    def default_shared_config(self) -> dict[str, Any]:
        return {
            "audio_url": VOICEVOX_AUDIO_BASE_URL,
            "speakers_url": VOICEVOX_SPEAKERS_URL,
        }

    def default_provider_config(self) -> dict[str, Any]:
        return {
            "key_validation_url": VOICEVOX_POINTS_URL,
            "key_transport": "query",
            "key_param_name": "key",
            "timeout_seconds": 8,
        }

    def default_user_settings(self) -> dict[str, Any]:
        return dict(VOICEVOX_DEFAULT_SETTINGS)

    def normalize_user_settings(
        self,
        value: dict[str, Any],
        *,
        default_settings: dict[str, Any],
    ) -> tuple[dict[str, Any], list[str]]:
        incoming = coerce_mapping(value)
        merged = coerce_mapping(default_settings)
        merged.update(incoming)

        def _pick_first(*keys: str) -> Any:
            for key in keys:
                if key in incoming and incoming.get(key) is not None:
                    return incoming.get(key)
            for key in keys:
                if key in merged and merged.get(key) is not None:
                    return merged.get(key)
            return None

        character_raw = (
            _pick_first("character_id", "speaker_id", "style_id")
        )
        if character_raw is None:
            legacy_speaker = merged.get("speaker")
            if isinstance(legacy_speaker, int):
                character_raw = str(legacy_speaker)
            elif isinstance(legacy_speaker, str) and legacy_speaker.strip().isdigit():
                character_raw = legacy_speaker.strip()

        pitch_raw = _pick_first("pitch_scale", "pitch")
        intonation_raw = _pick_first("intonation_scale", "intonationScale")
        speed_raw = _pick_first("speed_scale", "speed")
        volume_raw = _pick_first("volume_scale", "volumeScale", "volume")
        initial_silence_raw = _pick_first("initial_silence_scale", "pre_phoneme_length", "prePhonemeLength")
        final_silence_raw = _pick_first("final_silence_length", "post_phoneme_length", "postPhonemeLength")

        normalized = {
            "character_id": str(character_raw or "").strip(),
            "volume_scale": _normalize_voicevox_float(
                volume_raw,
                fallback=float(VOICEVOX_DEFAULT_SETTINGS["volume_scale"]),
                minimum=0.0,
                maximum=2.0,
            ),
            "pitch_scale": _normalize_voicevox_float(
                pitch_raw,
                fallback=float(VOICEVOX_DEFAULT_SETTINGS["pitch_scale"]),
                minimum=-0.4,
                maximum=0.4,
            ),
            "speed_scale": _normalize_voicevox_float(
                speed_raw,
                fallback=float(VOICEVOX_DEFAULT_SETTINGS["speed_scale"]),
                minimum=0.1,
                maximum=4.0,
            ),
            "intonation_scale": _normalize_voicevox_float(
                intonation_raw,
                fallback=float(VOICEVOX_DEFAULT_SETTINGS["intonation_scale"]),
                minimum=0.0,
                maximum=2.0,
            ),
            "initial_silence_scale": _normalize_voicevox_float(
                initial_silence_raw,
                fallback=float(VOICEVOX_DEFAULT_SETTINGS["initial_silence_scale"]),
                minimum=0.0,
                maximum=2.0,
            ),
            "final_silence_length": _normalize_voicevox_float(
                final_silence_raw,
                fallback=float(VOICEVOX_DEFAULT_SETTINGS["final_silence_length"]),
                minimum=0.0,
                maximum=2.0,
            ),
        }
        # Legacy aliases kept for compatibility with older clients/tests.
        normalized["pitch"] = normalized["pitch_scale"]
        normalized["speed"] = normalized["speed_scale"]
        return normalized, []

    def supports_key_validation(self) -> bool:
        return True

    def list_voices(
        self,
        provider: TtsProviderConfig,
        api_key: str,
    ) -> tuple[list[dict[str, Any]], str | None]:
        shared_config = shared_config_map(provider)
        provider_config = provider_config_map(provider)

        speakers_url = str(shared_config.get("speakers_url") or VOICEVOX_SPEAKERS_URL).strip()
        if not is_valid_http_url(speakers_url):
            return [], "URL speakers của VoiceVox không hợp lệ."

        key_transport = str(provider_config.get("key_transport") or "query").strip().lower()
        key_param_name = str(provider_config.get("key_param_name") or "key").strip() or "key"
        timeout_seconds = provider_config.get("timeout_seconds", 8)
        try:
            timeout_seconds = float(timeout_seconds)
        except (TypeError, ValueError):
            timeout_seconds = 8
        timeout_seconds = max(2.0, min(20.0, timeout_seconds))

        if provider.requires_api_key and not api_key:
            return [], "Provider yêu cầu API key để tải danh sách nhân vật."

        headers = {"Accept": "application/json"}
        request_url = speakers_url
        if api_key:
            if key_transport == "header":
                headers[key_param_name] = api_key
            else:
                parsed = urlparse(speakers_url)
                params = dict(parse_qsl(parsed.query, keep_blank_values=True))
                params[key_param_name] = api_key
                request_url = urlunparse(parsed._replace(query=urlencode(params)))

        request = Request(request_url, method="GET", headers=headers)
        try:
            with urlopen(request, timeout=timeout_seconds) as response:
                status_code = int(response.getcode() or 0)
                body = response.read(512 * 1024)
        except HTTPError as exc:
            code = int(exc.code or 0)
            if code in {401, 403}:
                return [], "API key VoiceVox không hợp lệ."
            return [], f"Không thể tải danh sách nhân vật (HTTP {code})."
        except URLError as exc:
            return [], f"Không thể kết nối VoiceVox speakers API: {exc.reason}"

        if not (200 <= status_code < 300):
            return [], f"VoiceVox speakers API phản hồi HTTP {status_code}."

        try:
            payload = json.loads(body.decode("utf-8", errors="ignore"))
        except (TypeError, ValueError):
            return [], "Không đọc được danh sách nhân vật VoiceVox."

        if not isinstance(payload, list):
            return [], "Định dạng danh sách nhân vật VoiceVox không hợp lệ."

        voices: list[dict[str, Any]] = []
        for speaker in payload:
            if not isinstance(speaker, dict):
                continue
            speaker_name = str(speaker.get("name") or "").strip() or "Unknown speaker"
            styles = speaker.get("styles")
            if not isinstance(styles, list):
                continue
            for style in styles:
                if not isinstance(style, dict):
                    continue
                style_id = style.get("id")
                if style_id is None:
                    continue
                style_name = str(style.get("name") or "").strip()
                label = f"{speaker_name} - {style_name}" if style_name else speaker_name
                voices.append(
                    {
                        "id": str(style_id),
                        "label": label,
                        "speaker_name": speaker_name,
                        "style_name": style_name,
                    }
                )

        voices.sort(key=lambda item: (str(item.get("speaker_name") or "").lower(), str(item.get("label") or "").lower()))
        return voices, None

    def validate_api_key(self, provider: TtsProviderConfig, api_key: str) -> ApiKeyValidationResult:
        checked_at = datetime.utcnow()
        provider_config = provider_config_map(provider)

        validation_url = str(provider_config.get("key_validation_url") or VOICEVOX_POINTS_URL).strip()
        if not is_valid_http_url(validation_url):
            return ApiKeyValidationResult(
                valid=False,
                status="unknown",
                checked_at=checked_at,
                message="URL validate key không hợp lệ.",
            )

        key_transport = str(provider_config.get("key_transport") or "query").strip().lower()
        key_param_name = str(provider_config.get("key_param_name") or "key").strip() or "key"
        timeout_seconds = provider_config.get("timeout_seconds", 8)
        try:
            timeout_seconds = float(timeout_seconds)
        except (TypeError, ValueError):
            timeout_seconds = 8
        timeout_seconds = max(2.0, min(20.0, timeout_seconds))

        headers = {"Accept": "application/json"}
        request_url = validation_url
        if key_transport == "header":
            headers[key_param_name] = api_key
        else:
            parsed = urlparse(validation_url)
            params = dict(parse_qsl(parsed.query, keep_blank_values=True))
            params[key_param_name] = api_key
            request_url = urlunparse(parsed._replace(query=urlencode(params)))

        request = Request(request_url, method="GET", headers=headers)
        try:
            with urlopen(request, timeout=timeout_seconds) as response:
                status_code = int(response.getcode() or 0)
                body = response.read(4096)
        except HTTPError as exc:
            status_code = int(exc.code or 0)
            if status_code in {401, 403}:
                return ApiKeyValidationResult(
                    valid=False,
                    status="invalid",
                    checked_at=checked_at,
                    message=f"Provider trả về {status_code}: API key không hợp lệ.",
                )
            if 400 <= status_code < 500:
                return ApiKeyValidationResult(
                    valid=False,
                    status="invalid",
                    checked_at=checked_at,
                    message=f"Provider trả về {status_code}: API key bị từ chối.",
                )
            return ApiKeyValidationResult(
                valid=False,
                status="unknown",
                checked_at=checked_at,
                message=f"Không thể validate key (HTTP {status_code}).",
            )
        except URLError as exc:
            return ApiKeyValidationResult(
                valid=False,
                status="unknown",
                checked_at=checked_at,
                message=f"Không thể kết nối provider để validate key: {exc.reason}",
            )

        if not (200 <= status_code < 300):
            return ApiKeyValidationResult(
                valid=False,
                status="unknown",
                checked_at=checked_at,
                message=f"Provider phản hồi HTTP {status_code} khi validate key.",
            )

        message = "API key hợp lệ."
        parsed_body: Any = None
        if body:
            try:
                parsed_body = json.loads(body.decode("utf-8", errors="ignore"))
            except (TypeError, ValueError):
                parsed_body = None

        if isinstance(parsed_body, dict):
            error_message = ""
            for key in ("errorMessage", "error", "errors", "detail", "message"):
                candidate = parsed_body.get(key)
                if isinstance(candidate, list):
                    candidate = candidate[0] if candidate else ""
                if isinstance(candidate, dict):
                    candidate = (
                        candidate.get("errorMessage")
                        or candidate.get("error")
                        or candidate.get("message")
                        or candidate.get("detail")
                        or ""
                    )
                text = str(candidate or "").strip()
                if text:
                    error_message = text
                    break

            normalized_error = error_message.strip().lower().replace(" ", "")
            if normalized_error:
                if normalized_error == "invalidapikey":
                    return ApiKeyValidationResult(
                        valid=False,
                        status="invalid",
                        checked_at=checked_at,
                        message="API key VoiceVox không hợp lệ hoặc đã hết hạn.",
                    )
                if normalized_error == "notenoughpoints":
                    return ApiKeyValidationResult(
                        valid=False,
                        status="invalid",
                        checked_at=checked_at,
                        message="API key VoiceVox không còn đủ points.",
                    )
                if normalized_error == "failed":
                    return ApiKeyValidationResult(
                        valid=False,
                        status="unknown",
                        checked_at=checked_at,
                        message="VoiceVox trả về lỗi khi kiểm tra API key.",
                    )
                return ApiKeyValidationResult(
                    valid=False,
                    status="invalid",
                    checked_at=checked_at,
                    message=error_message[:MAX_LAST_VALIDATION_ERROR_LEN],
                )

            # Heuristic: if payload explicitly marks success=false then treat as invalid.
            if parsed_body.get("success") is False or parsed_body.get("ok") is False:
                return ApiKeyValidationResult(
                    valid=False,
                    status="invalid",
                    checked_at=checked_at,
                    message="VoiceVox từ chối API key.",
                )

            points_value = parsed_body.get("points")
            if points_value is not None:
                try:
                    points = float(points_value)
                except (TypeError, ValueError):
                    points = None
                if points is not None and points <= 0:
                    return ApiKeyValidationResult(
                        valid=False,
                        status="invalid",
                        checked_at=checked_at,
                        message="API key VoiceVox đã hết points.",
                    )

        return ApiKeyValidationResult(
            valid=True,
            status="valid",
            checked_at=checked_at,
            message=message,
        )


TTS_PROVIDER_ADAPTERS: dict[str, BaseTtsProviderAdapter] = {
    VOICEVOX_PROVIDER_TYPE: VoicevoxTtsProviderAdapter(),
}


def get_provider_adapter(provider_type: str | None) -> BaseTtsProviderAdapter:
    normalized = normalize_provider_type_filter(provider_type)
    if normalized in TTS_PROVIDER_ADAPTERS:
        return TTS_PROVIDER_ADAPTERS[normalized]
    return BaseTtsProviderAdapter()


def merge_provider_defaults(
    provider_type: str,
    *,
    shared_config: dict[str, Any] | None,
    provider_config: dict[str, Any] | None,
    default_settings: dict[str, Any] | None,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    adapter = get_provider_adapter(provider_type)

    merged_shared = adapter.default_shared_config()
    merged_shared.update(coerce_mapping(shared_config))

    merged_provider = adapter.default_provider_config()
    merged_provider.update(coerce_mapping(provider_config))

    merged_default_settings = adapter.default_user_settings()
    merged_default_settings.update(coerce_mapping(default_settings))

    normalized_defaults, _ = adapter.normalize_user_settings(
        merged_default_settings,
        default_settings=adapter.default_user_settings(),
    )

    return merged_shared, merged_provider, normalized_defaults


@dataclass(slots=True)
class TtsProviderFormPayload:
    provider_name: str
    provider_type: str
    base_url: str | None
    requires_api_key: bool
    is_active: bool
    shared_config: dict[str, Any]
    provider_config: dict[str, Any]
    default_settings: dict[str, Any]


def parse_provider_form_payload(
    form: dict[str, Any],
    *,
    for_update: bool,
    has_existing_api_key: bool | None = None,
) -> tuple[TtsProviderFormPayload, list[str]]:
    del for_update  # kept for signature stability
    del has_existing_api_key

    errors: list[str] = []

    provider_name = _normalize_provider_name(form.get("provider_name"))
    provider_type = _normalize_provider_type(form.get("provider_type"))
    base_url = _normalize_optional_base_url(form.get("base_url"))
    requires_api_key = is_truthy(form.get("requires_api_key"))
    is_active = is_truthy(form.get("is_active"))

    shared_config = parse_json_text_field(
        form.get("shared_config_json"),
        field_label="Shared config",
        errors=errors,
    )
    provider_config = parse_json_text_field(
        form.get("provider_config_json"),
        field_label="Provider config",
        errors=errors,
    )
    default_settings = parse_json_text_field(
        form.get("default_settings_json"),
        field_label="Default user settings",
        errors=errors,
    )

    if not provider_name:
        errors.append("Tên provider là bắt buộc.")
    if not provider_type:
        errors.append("Loại provider là bắt buộc (chỉ gồm chữ thường, số, '-' hoặc '_').")
    if base_url and not is_valid_http_url(base_url):
        errors.append("Base URL chỉ chấp nhận http/https hợp lệ.")

    merged_shared, merged_provider, merged_default_settings = merge_provider_defaults(
        provider_type,
        shared_config=shared_config,
        provider_config=provider_config,
        default_settings=default_settings,
    )

    payload = TtsProviderFormPayload(
        provider_name=provider_name,
        provider_type=provider_type,
        base_url=base_url,
        requires_api_key=requires_api_key,
        is_active=is_active,
        shared_config=merged_shared,
        provider_config=merged_provider,
        default_settings=merged_default_settings,
    )
    return payload, errors


def shared_config_map(provider: TtsProviderConfig) -> dict[str, Any]:
    return loads_json_map(provider.shared_config_json)


def provider_config_map(provider: TtsProviderConfig) -> dict[str, Any]:
    return loads_json_map(provider.provider_config_json)


def provider_default_settings_map(provider: TtsProviderConfig) -> dict[str, Any]:
    return loads_json_map(provider.default_settings_json)


def normalize_user_settings_for_provider(
    provider: TtsProviderConfig,
    settings: dict[str, Any],
) -> tuple[dict[str, Any], list[str]]:
    adapter = get_provider_adapter(provider.provider_type)
    provider_defaults = provider_default_settings_map(provider)
    merged_defaults = adapter.default_user_settings()
    merged_defaults.update(provider_defaults)
    return adapter.normalize_user_settings(coerce_mapping(settings), default_settings=merged_defaults)


def serialize_provider_row(provider: TtsProviderConfig) -> dict[str, Any]:
    adapter = get_provider_adapter(provider.provider_type)

    shared_config = shared_config_map(provider)
    provider_config = provider_config_map(provider)
    default_settings = provider_default_settings_map(provider)

    if not shared_config:
        shared_config = adapter.default_shared_config()
    if not provider_config:
        provider_config = adapter.default_provider_config()
    if not default_settings:
        default_settings = adapter.default_user_settings()

    normalized_defaults, _ = adapter.normalize_user_settings(default_settings, default_settings=adapter.default_user_settings())

    return {
        "id": provider.id,
        "provider_name": provider.provider_name,
        "provider_type": provider.provider_type,
        "base_url": provider.base_url,
        "requires_api_key": bool(provider.requires_api_key),
        "is_active": bool(provider.is_active),
        "shared_config": shared_config,
        "provider_config": provider_config,
        "default_settings": normalized_defaults,
        "supports_key_validation": adapter.supports_key_validation(),
        "updated_at": provider.updated_at.isoformat() if provider.updated_at else None,
    }


def _provider_order_query(query):
    return query.order_by(
        TtsProviderConfig.id.asc(),
    )


def find_provider_by_type(
    provider_type: str,
    *,
    include_inactive: bool = False,
) -> TtsProviderConfig | None:
    normalized_type = normalize_provider_type_filter(provider_type)
    if not normalized_type:
        return None

    query = TtsProviderConfig.query.filter(TtsProviderConfig.provider_type == normalized_type)
    if not include_inactive:
        query = query.filter(TtsProviderConfig.is_active.is_(True))
    return _provider_order_query(query).first()


def get_or_create_user_provider_profile(
    session,
    *,
    user_id: int,
    provider_id: int,
    create_if_missing: bool,
) -> TtsUserProviderProfile | None:
    row = TtsUserProviderProfile.query.filter_by(user_id=user_id, provider_id=provider_id).first()
    if row is not None or not create_if_missing:
        return row

    row = TtsUserProviderProfile(
        user_id=user_id,
        provider_id=provider_id,
        key_status="unknown",
        settings_json="{}",
    )
    session.add(row)
    session.flush()
    return row


def serialize_user_provider_profile(
    *,
    provider: TtsProviderConfig,
    profile: TtsUserProviderProfile | None,
) -> dict[str, Any]:
    provider_payload = serialize_provider_row(provider)
    adapter = get_provider_adapter(provider.provider_type)

    default_settings = coerce_mapping(provider_payload.get("default_settings"))
    user_settings = loads_json_map(profile.settings_json if profile is not None else "{}")
    normalized_settings, _ = adapter.normalize_user_settings(user_settings, default_settings=default_settings)

    effective_settings = dict(default_settings)
    effective_settings.update(normalized_settings)
    effective_settings, _ = adapter.normalize_user_settings(effective_settings, default_settings=default_settings)

    return {
        "provider": provider_payload,
        "profile": {
            "has_api_key": bool(profile and profile.encrypted_api_key),
            "masked_api_key": mask_api_key(profile.encrypted_api_key) if profile else "",
            "key_status": normalize_key_status(profile.key_status if profile else "unknown"),
            "last_validated_at": profile.last_validated_at.isoformat() if profile and profile.last_validated_at else None,
            "last_validation_error": (profile.last_validation_error or "") if profile else "",
            "settings": normalized_settings,
            "effective_settings": effective_settings,
        },
    }


def list_active_provider_profiles_for_user(user_id: int) -> list[dict[str, Any]]:
    providers = _provider_order_query(TtsProviderConfig.query.filter(TtsProviderConfig.is_active.is_(True))).all()
    provider_ids = [row.id for row in providers if row.id is not None]
    profiles = {}
    if provider_ids:
        rows = TtsUserProviderProfile.query.filter(
            TtsUserProviderProfile.user_id == user_id,
            TtsUserProviderProfile.provider_id.in_(provider_ids),
        ).all()
        profiles = {row.provider_id: row for row in rows}

    return [
        serialize_user_provider_profile(provider=provider, profile=profiles.get(provider.id))
        for provider in providers
    ]


def get_provider_profile_payload_for_user(
    *,
    user_id: int,
    provider_type: str,
    include_inactive: bool = False,
) -> dict[str, Any] | None:
    provider = find_provider_by_type(provider_type, include_inactive=include_inactive)
    if provider is None:
        return None
    profile = get_or_create_user_provider_profile(
        session=TtsUserProviderProfile.query.session,
        user_id=user_id,
        provider_id=provider.id,
        create_if_missing=False,
    )
    return serialize_user_provider_profile(provider=provider, profile=profile)


def validate_provider_api_key(provider: TtsProviderConfig, api_key: str) -> ApiKeyValidationResult:
    adapter = get_provider_adapter(provider.provider_type)
    return adapter.validate_api_key(provider, api_key)


def apply_validation_result_to_profile(
    profile: TtsUserProviderProfile,
    result: ApiKeyValidationResult,
) -> None:
    profile.key_status = normalize_key_status(result.status)
    profile.last_validated_at = result.checked_at
    message = str(result.message or "").strip()
    profile.last_validation_error = message[:MAX_LAST_VALIDATION_ERROR_LEN] if message else None


def update_user_provider_profile(
    session,
    *,
    user_id: int,
    provider: TtsProviderConfig,
    raw_api_key: Any = UNSET,
    clear_api_key: bool = False,
    settings_payload: Any = UNSET,
    validate_key: bool = False,
) -> tuple[TtsUserProviderProfile, ApiKeyValidationResult | None, list[str]]:
    profile = get_or_create_user_provider_profile(
        session,
        user_id=user_id,
        provider_id=provider.id,
        create_if_missing=True,
    )
    if profile is None:
        raise ValueError("Không thể khởi tạo hồ sơ TTS cho user.")

    errors: list[str] = []

    incoming_key = ""
    has_new_key = False
    if raw_api_key is not UNSET:
        incoming_key = str(raw_api_key or "").strip()
        has_new_key = bool(incoming_key)

    if clear_api_key and has_new_key:
        errors.append("Không thể vừa nhập API key mới vừa chọn xoá API key.")

    if not errors:
        if clear_api_key:
            profile.encrypted_api_key = None
            profile.key_status = "unknown"
            profile.last_validated_at = None
            profile.last_validation_error = None
        elif has_new_key:
            profile.encrypted_api_key = encrypt_api_key(incoming_key)
            profile.key_status = "unknown"
            profile.last_validated_at = None
            profile.last_validation_error = None

    if settings_payload is not UNSET:
        if not isinstance(settings_payload, dict):
            errors.append("settings phải là object JSON.")
        else:
            normalized_settings, normalize_errors = normalize_user_settings_for_provider(provider, settings_payload)
            if normalize_errors:
                errors.extend(normalize_errors)
            else:
                profile.settings_json = dumps_json_map(normalized_settings)

    effective_key = decrypt_api_key(profile.encrypted_api_key)
    if provider.requires_api_key and not effective_key:
        errors.append("Provider này yêu cầu API key. Vui lòng lưu API key trước khi sử dụng.")

    if errors:
        return profile, None, errors

    validation_result = None
    if validate_key:
        if not effective_key:
            return profile, None, ["Không có API key để validate."]
        validation_result = validate_provider_api_key(provider, effective_key)
        apply_validation_result_to_profile(profile, validation_result)

    session.add(profile)
    session.flush()
    return profile, validation_result, []


def validate_user_provider_key(
    session,
    *,
    user_id: int,
    provider: TtsProviderConfig,
    api_key_override: str | None = None,
) -> tuple[ApiKeyValidationResult | None, list[str]]:
    key_override = str(api_key_override or "").strip()
    persist_to_profile = not bool(key_override)
    profile = get_or_create_user_provider_profile(
        session,
        user_id=user_id,
        provider_id=provider.id,
        create_if_missing=persist_to_profile,
    )
    if persist_to_profile and profile is None:
        return None, ["Không thể tạo hồ sơ TTS cho user."]

    key_to_validate = key_override
    if not key_to_validate:
        if profile is None:
            return None, ["Không có API key đã lưu để validate."]
        key_to_validate = decrypt_api_key(profile.encrypted_api_key)

    if not key_to_validate:
        return None, ["Không có API key để validate."]

    result = validate_provider_api_key(provider, key_to_validate)
    if persist_to_profile:
        apply_validation_result_to_profile(profile, result)
        session.add(profile)
        session.flush()

    return result, []


def list_provider_voices_for_user(
    session,
    *,
    user_id: int,
    provider: TtsProviderConfig,
    api_key_override: str | None = None,
) -> tuple[list[dict[str, Any]], list[str]]:
    adapter = get_provider_adapter(provider.provider_type)
    raw_key = str(api_key_override or "").strip()
    if raw_key:
        voice_items, error_message = adapter.list_voices(provider, raw_key)
        if error_message:
            return [], [error_message]
        return voice_items, []

    profile = get_or_create_user_provider_profile(
        session,
        user_id=user_id,
        provider_id=provider.id,
        create_if_missing=False,
    )
    saved_key = decrypt_api_key(profile.encrypted_api_key) if profile is not None else ""
    if provider.requires_api_key and not saved_key:
        return [], ["Provider yêu cầu API key. Hãy lưu API key trước khi tải danh sách nhân vật."]

    voice_items, error_message = adapter.list_voices(provider, saved_key)
    if error_message:
        return [], [error_message]
    return voice_items, []


def resolve_provider_api_key_for_user(
    session,
    *,
    user_id: int,
    provider: TtsProviderConfig,
    api_key_override: str | None = None,
) -> tuple[str, list[str]]:
    raw_key = str(api_key_override or "").strip()
    if raw_key:
        return raw_key, []

    profile = get_or_create_user_provider_profile(
        session,
        user_id=user_id,
        provider_id=provider.id,
        create_if_missing=False,
    )
    saved_key = decrypt_api_key(profile.encrypted_api_key) if profile is not None else ""
    if provider.requires_api_key and not saved_key:
        return "", ["Provider yêu cầu API key. Hãy lưu API key trước khi dùng VoiceVox."]
    return saved_key, []


def resolve_user_settings_for_provider(
    session,
    *,
    user_id: int,
    provider: TtsProviderConfig,
    settings_payload: Any = None,
) -> tuple[dict[str, Any], list[str]]:
    profile = get_or_create_user_provider_profile(
        session,
        user_id=user_id,
        provider_id=provider.id,
        create_if_missing=False,
    )
    merged_settings = loads_json_map(profile.settings_json if profile is not None else "{}")

    if settings_payload is not None:
        if not isinstance(settings_payload, dict):
            return {}, ["settings phải là object JSON."]
        merged_settings.update(coerce_mapping(settings_payload))

    normalized, errors = normalize_user_settings_for_provider(provider, merged_settings)
    if errors:
        return {}, errors
    return normalized, []


def synthesize_voicevox_audio_for_user(
    session,
    *,
    user_id: int,
    provider: TtsProviderConfig,
    text: Any,
    character_id: Any = "",
    settings_payload: Any = None,
    api_key_override: str | None = None,
    use_opus: bool = False,
) -> tuple[SynthesizedAudioResult | None, list[str], list[str]]:
    if normalize_provider_type_filter(provider.provider_type) != VOICEVOX_PROVIDER_TYPE:
        return None, ["Provider không hỗ trợ VoiceVox synthesis."], []

    text_value = str(text or "").strip()
    if not text_value:
        return None, ["Text để tạo audio đang trống."], []
    if len(text_value) > MAX_VOICEVOX_TEXT_LENGTH:
        return None, [f"Text vượt quá {MAX_VOICEVOX_TEXT_LENGTH} ký tự."], []

    settings, settings_errors = resolve_user_settings_for_provider(
        session,
        user_id=user_id,
        provider=provider,
        settings_payload=settings_payload,
    )
    if settings_errors:
        return None, settings_errors, []

    character_value = str(character_id or settings.get("character_id") or "0").strip() or "0"
    settings["character_id"] = character_value

    api_key, key_errors = resolve_provider_api_key_for_user(
        session,
        user_id=user_id,
        provider=provider,
        api_key_override=api_key_override,
    )
    if key_errors:
        return None, key_errors, []

    shared_config = shared_config_map(provider)
    provider_config = provider_config_map(provider)

    audio_url = str(
        shared_config.get("audio_url")
        or provider.base_url
        or VOICEVOX_AUDIO_BASE_URL
    ).strip()
    if not is_valid_http_url(audio_url):
        return None, ["URL audio của VoiceVox không hợp lệ."], []

    key_transport = str(provider_config.get("key_transport") or "query").strip().lower()
    key_param_name = str(provider_config.get("key_param_name") or "key").strip() or "key"
    timeout_seconds = provider_config.get("timeout_seconds", 12)
    try:
        timeout_seconds = float(timeout_seconds)
    except (TypeError, ValueError):
        timeout_seconds = 12
    timeout_seconds = max(2.0, min(25.0, timeout_seconds))

    headers = {"Accept": "audio/*,application/octet-stream;q=0.8"}
    parsed = urlparse(audio_url)
    params = dict(parse_qsl(parsed.query, keep_blank_values=True))
    params["text"] = text_value
    params["speaker"] = character_value
    # Match VoiceVox deprecated API documented query params for max compatibility.
    params["pitch"] = str(settings.get("pitch_scale", 0.0))
    params["speed"] = str(settings.get("speed_scale", 1.0))
    params["intonationScale"] = str(settings.get("intonation_scale", 1.0))
    if use_opus:
        # Upstream may ignore this; caller gets warning when content is not opus/ogg.
        params["outputFormat"] = "opus"
        params["format"] = "opus"

    if api_key:
        if key_transport == "header":
            headers[key_param_name] = api_key
        else:
            params[key_param_name] = api_key

    request_url = urlunparse(parsed._replace(query=urlencode(params)))
    request = Request(request_url, method="GET", headers=headers)

    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            status_code = int(response.getcode() or 0)
            content_type_header = str(response.headers.get("Content-Type") or "")
            body = response.read(MAX_VOICEVOX_AUDIO_BYTES + 1)
    except HTTPError as exc:
        code = int(exc.code or 0)
        error_body = b""
        try:
            error_body = exc.read(8192)
        except Exception:
            error_body = b""
        parsed_error = _parse_voicevox_error_message(error_body).lower()
        if parsed_error == "invalidapikey":
            return None, ["API key VoiceVox không hợp lệ hoặc đã hết hạn."], []
        if parsed_error == "notenoughpoints":
            return None, ["VoiceVox API key không đủ points để tổng hợp audio."], []
        if parsed_error == "failed":
            return None, ["VoiceVox tổng hợp âm thanh thất bại."], []
        if code in {401, 403}:
            return None, ["API key VoiceVox không hợp lệ hoặc đã hết hạn."], []
        if parsed_error:
            return None, [f"VoiceVox audio API lỗi: {parsed_error}"], []
        return None, [f"VoiceVox audio API trả về HTTP {code}."], []
    except URLError as exc:
        return None, [f"Không thể kết nối VoiceVox audio API: {exc.reason}"], []

    if not (200 <= status_code < 300):
        return None, [f"VoiceVox audio API phản hồi HTTP {status_code}."], []
    if not body:
        return None, ["VoiceVox trả về audio rỗng."], []
    if len(body) > MAX_VOICEVOX_AUDIO_BYTES:
        return None, ["Audio trả về quá lớn."], []

    if (
        str(content_type_header).split(";", 1)[0].strip().lower() == "application/json"
        or body[:1] in {b"{", b"["}
    ):
        parsed_error = _parse_voicevox_error_message(body).lower()
        if parsed_error == "invalidapikey":
            return None, ["API key VoiceVox không hợp lệ hoặc đã hết hạn."], []
        if parsed_error == "notenoughpoints":
            return None, ["VoiceVox API key không đủ points để tổng hợp audio."], []
        if parsed_error == "failed":
            return None, ["VoiceVox tổng hợp âm thanh thất bại."], []
        if parsed_error:
            return None, [f"VoiceVox audio API lỗi: {parsed_error}"], []
        return None, ["VoiceVox audio API trả về JSON thay vì audio."], []

    mime_type, extension = _detect_audio_mime_and_extension(
        body,
        response_content_type=content_type_header,
    )
    if extension == "bin":
        return None, ["VoiceVox audio API trả dữ liệu không nhận diện được định dạng âm thanh."], []
    warnings: list[str] = []
    if use_opus and extension not in {"ogg", "opus"}:
        warnings.append("VoiceVox API không trả định dạng opus, hệ thống đã lưu theo định dạng thực tế.")

    return (
        SynthesizedAudioResult(
            content=body,
            mime_type=mime_type,
            extension=extension,
            content_type_header=content_type_header,
        ),
        [],
        warnings,
    )


def ensure_default_tts_providers(session) -> dict[str, int]:
    """Create default global TTS providers without duplicating existing rows."""
    created = 0
    updated = 0

    try:
        for seed in DEFAULT_TTS_PROVIDER_SEEDS:
            provider_type = normalize_provider_type_filter(seed.get("provider_type"))
            existing = (
                TtsProviderConfig.query.filter(
                    TtsProviderConfig.provider_type == provider_type,
                )
                .order_by(TtsProviderConfig.id.asc())
                .first()
            )

            merged_shared, merged_provider, merged_defaults = merge_provider_defaults(
                provider_type,
                shared_config=coerce_mapping(seed.get("shared_config")),
                provider_config=coerce_mapping(seed.get("provider_config")),
                default_settings=coerce_mapping(seed.get("default_settings")),
            )

            if existing is None:
                row = TtsProviderConfig(
                    provider_name=str(seed.get("provider_name") or "VoiceVox"),
                    provider_type=provider_type or VOICEVOX_PROVIDER_TYPE,
                    base_url=str(seed.get("base_url") or "").strip() or None,
                    requires_api_key=bool(seed.get("requires_api_key", True)),
                    is_active=bool(seed.get("is_active", True)),
                    shared_config_json=dumps_json_map(merged_shared),
                    provider_config_json=dumps_json_map(merged_provider),
                    default_settings_json=dumps_json_map(merged_defaults),
                    created_by_admin_id=None,
                    updated_by_admin_id=None,
                )
                session.add(row)
                created += 1
                continue

            changed = False
            if not existing.base_url and seed.get("base_url"):
                existing.base_url = str(seed.get("base_url")).strip()
                changed = True

            if not loads_json_map(existing.shared_config_json):
                existing.shared_config_json = dumps_json_map(merged_shared)
                changed = True
            if not loads_json_map(existing.provider_config_json):
                existing.provider_config_json = dumps_json_map(merged_provider)
                changed = True
            existing_defaults = loads_json_map(existing.default_settings_json)
            if not existing_defaults:
                existing.default_settings_json = dumps_json_map(merged_defaults)
                changed = True
            elif normalize_provider_type_filter(existing.provider_type) == VOICEVOX_PROVIDER_TYPE:
                missing_key = any(key not in existing_defaults for key in VOICEVOX_DEFAULT_SETTINGS.keys())
                legacy_pitch = _normalize_voicevox_float(
                    existing_defaults.get("pitch"),
                    fallback=0.0,
                    minimum=-10.0,
                    maximum=10.0,
                )
                legacy_speed = _normalize_voicevox_float(
                    existing_defaults.get("speed"),
                    fallback=0.0,
                    minimum=-10.0,
                    maximum=10.0,
                )
                legacy_intonation = _normalize_voicevox_float(
                    existing_defaults.get("intonation_scale"),
                    fallback=0.0,
                    minimum=-10.0,
                    maximum=10.0,
                )
                has_legacy_half_defaults = (
                    "pitch_scale" not in existing_defaults
                    and "speed_scale" not in existing_defaults
                    and legacy_pitch == 0.5
                    and legacy_speed == 0.5
                    and legacy_intonation == 0.5
                )
                if missing_key or has_legacy_half_defaults:
                    existing.default_settings_json = dumps_json_map(merged_defaults)
                    changed = True

            if changed:
                updated += 1
    except SQLAlchemyError:
        session.rollback()
        return {"created": 0, "updated": 0}

    return {"created": created, "updated": updated}
