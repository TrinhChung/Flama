"""Remote image and page downloads, performed by the media worker (SSRF checks there)."""

from __future__ import annotations

from dataclasses import dataclass
import ipaddress
from pathlib import Path
import socket
from urllib.parse import unquote, urlsplit, urlunsplit

from werkzeug.utils import secure_filename

from app.validators import RequestValidationError


MAX_REMOTE_URL_LENGTH = 2048
MIME_TO_EXTENSION = {
    "image/gif": "gif",
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/svg+xml": "svg",
    "image/webp": "webp",
}


@dataclass(frozen=True)
class RemoteImagePayload:
    content: bytes
    filename: str
    mime_type: str
    source_url: str


@dataclass(frozen=True)
class _ResolvedRemoteTarget:
    url: str
    scheme: str
    hostname: str
    port: int
    host_header: str
    request_target: str
    addresses: tuple[str, ...]


def fetch_remote_image(
    raw_url: str,
    *,
    max_bytes: int,
    timeout_seconds: float,
    max_redirects: int,
) -> RemoteImagePayload:
    """Download a public image through the media worker (redirects capped at 3 there)."""
    url = _normalize_remote_url(raw_url)
    result = _fetch_via_worker(url, kind="image", max_bytes=max_bytes, timeout_seconds=timeout_seconds)
    mime_type = str(result["content_type"]).split(";", 1)[0].strip().lower()
    extension = MIME_TO_EXTENSION.get(mime_type)
    if not extension or not result["content"]:
        raise _remote_error(
            "Link không trả về hình ảnh hợp lệ.",
            code="IMAGE_REMOTE_TYPE_NOT_ALLOWED",
            status=415,
        )
    final_url = str(result["final_url"] or url)
    return RemoteImagePayload(
        content=result["content"],
        filename=_filename_from_url(final_url, extension=extension),
        mime_type=mime_type,
        source_url=final_url,
    )


def fetch_remote_html(
    raw_url: str,
    *,
    max_bytes: int = 512 * 1024,
    timeout_seconds: float = 6.0,
    max_redirects: int = 3,
) -> str:
    """Download a public HTML page through the media worker."""
    url = _normalize_remote_url(raw_url)
    result = _fetch_via_worker(url, kind="html", max_bytes=max_bytes, timeout_seconds=timeout_seconds)
    charset = "utf-8"
    for part in str(result["content_type"]).split(";")[1:]:
        key, _, value = part.strip().partition("=")
        if key.lower() == "charset" and value.strip():
            charset = value.strip().strip('"')
    try:
        return result["content"].decode(charset, errors="replace")
    except LookupError:
        return result["content"].decode("utf-8", errors="replace")


# Worker error codes -> the codes callers and the UI already know.
_WORKER_ERROR_CODES = {
    "URL_NOT_ALLOWED": ("Không cho phép tải từ địa chỉ này.", "IMAGE_REMOTE_HOST_NOT_ALLOWED", 400),
    "PAYLOAD_TOO_LARGE": ("Tệp từ link vượt quá giới hạn dung lượng.", "MEDIA_TOO_LARGE", 413),
    "MEDIA_TYPE_NOT_ALLOWED": ("Link không trả về nội dung được hỗ trợ.", "IMAGE_REMOTE_TYPE_NOT_ALLOWED", 415),
    "FETCH_FAILED": ("Không tải được nội dung từ link.", "IMAGE_REMOTE_FETCH_FAILED", 422),
}


def _fetch_via_worker(url: str, *, kind: str, max_bytes: int, timeout_seconds: float) -> dict:
    # Outbound requests leave from the media worker, never from the app server.
    from app.services import flama_media_client

    try:
        return flama_media_client.fetch_url_via_worker(
            url, kind=kind, max_bytes=int(max_bytes), timeout_seconds=float(timeout_seconds)
        )
    except flama_media_client.FlamaMediaClientError as exc:
        message, code, status = _WORKER_ERROR_CODES.get(exc.error_code, (exc.message, exc.error_code, exc.status_code))
        raise _remote_error(message, code=code, status=status) from exc


def _normalize_remote_url(raw_url: str) -> str:
    value = str(raw_url or "").strip()
    if not value:
        raise _remote_error(
            "Link hình ảnh không được để trống.",
            code="IMAGE_REMOTE_URL_REQUIRED",
            status=400,
        )
    if len(value) > MAX_REMOTE_URL_LENGTH:
        raise _remote_error(
            "Link hình ảnh quá dài.",
            code="IMAGE_REMOTE_URL_INVALID",
            status=400,
        )
    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        raise _remote_error(
            "Link hình ảnh chứa ký tự không hợp lệ.",
            code="IMAGE_REMOTE_URL_INVALID",
            status=400,
        )

    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError as exc:
        raise _remote_error(
            "Link hình ảnh không hợp lệ.",
            code="IMAGE_REMOTE_URL_INVALID",
            status=400,
        ) from exc

    scheme = parsed.scheme.lower()
    if scheme not in {"http", "https"}:
        raise _remote_error(
            "Chỉ hỗ trợ link hình ảnh HTTP hoặc HTTPS.",
            code="IMAGE_REMOTE_SCHEME_NOT_ALLOWED",
            status=400,
        )
    if not parsed.hostname or parsed.username or parsed.password:
        raise _remote_error(
            "Link hình ảnh không được chứa thông tin đăng nhập.",
            code="IMAGE_REMOTE_URL_INVALID",
            status=400,
        )
    expected_port = 443 if scheme == "https" else 80
    if port is not None and port != expected_port:
        raise _remote_error(
            "Link hình ảnh chỉ được dùng cổng HTTP/HTTPS tiêu chuẩn.",
            code="IMAGE_REMOTE_PORT_NOT_ALLOWED",
            status=400,
        )
    return urlunsplit(
        (
            scheme,
            parsed.netloc,
            parsed.path or "/",
            parsed.query,
            "",
        )
    )


def _resolve_remote_target(url: str) -> _ResolvedRemoteTarget:
    parsed = urlsplit(url)
    scheme = parsed.scheme.lower()
    hostname = str(parsed.hostname or "").rstrip(".")
    if not hostname or hostname.lower() == "localhost" or hostname.lower().endswith(".local"):
        raise _remote_error(
            "Không cho phép tải hình ảnh từ địa chỉ nội bộ.",
            code="IMAGE_REMOTE_HOST_NOT_ALLOWED",
            status=400,
        )
    try:
        ascii_hostname = hostname.encode("idna").decode("ascii")
    except UnicodeError as exc:
        raise _remote_error(
            "Tên miền của link hình ảnh không hợp lệ.",
            code="IMAGE_REMOTE_URL_INVALID",
            status=400,
        ) from exc

    port = parsed.port or (443 if scheme == "https" else 80)
    addresses = _resolve_public_addresses(ascii_hostname, port)
    host_token = (
        f"[{ascii_hostname}]"
        if ":" in ascii_hostname and not ascii_hostname.startswith("[")
        else ascii_hostname
    )
    host_header = host_token
    request_target = urlunsplit(("", "", parsed.path or "/", parsed.query, ""))
    return _ResolvedRemoteTarget(
        url=url,
        scheme=scheme,
        hostname=ascii_hostname,
        port=port,
        host_header=host_header,
        request_target=request_target,
        addresses=addresses,
    )


def _resolve_public_addresses(hostname: str, port: int) -> tuple[str, ...]:
    try:
        results = socket.getaddrinfo(
            hostname,
            port,
            type=socket.SOCK_STREAM,
        )
    except OSError as exc:
        raise _remote_error(
            "Không thể phân giải tên miền của link hình ảnh.",
            code="IMAGE_REMOTE_DNS_FAILED",
        ) from exc

    addresses: list[str] = []
    for result in results:
        raw_address = str(result[4][0]).split("%", 1)[0]
        try:
            parsed_address = ipaddress.ip_address(raw_address)
        except ValueError:
            continue
        if not parsed_address.is_global:
            raise _remote_error(
                "Không cho phép tải hình ảnh từ địa chỉ mạng nội bộ.",
                code="IMAGE_REMOTE_HOST_NOT_ALLOWED",
                status=400,
            )
        normalized = str(parsed_address)
        if normalized not in addresses:
            addresses.append(normalized)
    if not addresses:
        raise _remote_error(
            "Tên miền không có địa chỉ mạng công khai hợp lệ.",
            code="IMAGE_REMOTE_DNS_FAILED",
        )
    addresses.sort(
        key=lambda value: 0 if ipaddress.ip_address(value).version == 4 else 1
    )
    return tuple(addresses)


def _filename_from_url(url: str, *, extension: str) -> str:
    raw_name = Path(unquote(urlsplit(url).path)).name
    stem = secure_filename(Path(raw_name).stem)[:200]
    return f"{stem or 'remote-image'}.{extension}"


def _remote_error(
    message: str,
    *,
    code: str,
    status: int = 422,
) -> RequestValidationError:
    return RequestValidationError(
        message,
        field="source_url",
        status=status,
        code=code,
    )
