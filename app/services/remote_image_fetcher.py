"""Bounded remote image download with DNS pinning and SSRF protection."""

from __future__ import annotations

from dataclasses import dataclass
import http.client
import ipaddress
from pathlib import Path
import socket
import ssl
from urllib.parse import unquote, urljoin, urlsplit, urlunsplit

from werkzeug.utils import secure_filename

from app.validators import RequestValidationError


MAX_REMOTE_URL_LENGTH = 2048
REDIRECT_STATUS_CODES = {301, 302, 303, 307, 308}
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


class _PinnedHTTPSConnection(http.client.HTTPSConnection):
    """HTTPS connection that verifies the URL host while dialing a pinned IP."""

    def __init__(
        self,
        *,
        server_hostname: str,
        connect_host: str,
        port: int,
        timeout: float,
    ) -> None:
        super().__init__(
            server_hostname,
            port=port,
            timeout=timeout,
            context=ssl.create_default_context(),
        )
        self._connect_host = connect_host

    def connect(self) -> None:
        raw_socket = socket.create_connection(
            (self._connect_host, self.port),
            self.timeout,
            self.source_address,
        )
        try:
            self.sock = self._context.wrap_socket(
                raw_socket,
                server_hostname=self.host,
            )
        except Exception:
            raw_socket.close()
            raise


def fetch_remote_image(
    raw_url: str,
    *,
    max_bytes: int,
    timeout_seconds: float,
    max_redirects: int,
) -> RemoteImagePayload:
    current_url = _normalize_remote_url(raw_url)
    redirect_count = 0

    while True:
        target = _resolve_remote_target(current_url)
        connection, response = _request_target(
            target,
            timeout_seconds=timeout_seconds,
        )
        try:
            if response.status in REDIRECT_STATUS_CODES:
                if redirect_count >= int(max_redirects):
                    raise _remote_error(
                        "Link hình ảnh chuyển hướng quá nhiều lần.",
                        code="IMAGE_REMOTE_TOO_MANY_REDIRECTS",
                    )
                location = (response.getheader("Location") or "").strip()
                if not location:
                    raise _remote_error(
                        "Link hình ảnh trả về chuyển hướng không hợp lệ.",
                        code="IMAGE_REMOTE_FETCH_FAILED",
                    )
                next_url = _normalize_remote_url(urljoin(target.url, location))
                next_scheme = urlsplit(next_url).scheme.lower()
                if target.scheme == "https" and next_scheme != "https":
                    raise _remote_error(
                        "Không cho phép chuyển hướng hình ảnh từ HTTPS xuống HTTP.",
                        code="IMAGE_REMOTE_REDIRECT_DOWNGRADE",
                    )
                current_url = next_url
                redirect_count += 1
                continue

            if response.status != 200:
                raise _remote_error(
                    f"Không thể tải hình ảnh từ link (HTTP {response.status}).",
                    code="IMAGE_REMOTE_FETCH_FAILED",
                )

            content_encoding = (
                response.getheader("Content-Encoding") or "identity"
            ).strip().lower()
            if content_encoding not in {"", "identity"}:
                raise _remote_error(
                    "Link hình ảnh dùng kiểu nén phản hồi không được hỗ trợ.",
                    code="IMAGE_REMOTE_ENCODING_NOT_ALLOWED",
                    status=415,
                )

            mime_type = (
                response.getheader("Content-Type") or ""
            ).split(";", 1)[0].strip().lower()
            extension = MIME_TO_EXTENSION.get(mime_type)
            if extension is None:
                raise _remote_error(
                    "Link không trả về định dạng hình ảnh được hỗ trợ.",
                    code="MEDIA_TYPE_NOT_ALLOWED",
                    status=415,
                )

            content_length = _parse_content_length(
                response.getheader("Content-Length")
            )
            if content_length is not None and content_length > int(max_bytes):
                raise _remote_error(
                    f"Hình ảnh từ link vượt quá {int(max_bytes)} bytes.",
                    code="MEDIA_TOO_LARGE",
                    status=413,
                )

            content = _read_bounded(response, max_bytes=int(max_bytes))
            filename = _filename_from_url(
                target.url,
                extension=extension,
            )
            return RemoteImagePayload(
                content=content,
                filename=filename,
                mime_type=mime_type,
                source_url=target.url,
            )
        finally:
            response.close()
            connection.close()


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


def _request_target(
    target: _ResolvedRemoteTarget,
    *,
    timeout_seconds: float,
) -> tuple[http.client.HTTPConnection, http.client.HTTPResponse]:
    last_error: Exception | None = None
    for address in target.addresses:
        connection: http.client.HTTPConnection
        if target.scheme == "https":
            connection = _PinnedHTTPSConnection(
                server_hostname=target.hostname,
                connect_host=address,
                port=target.port,
                timeout=float(timeout_seconds),
            )
        else:
            connection = http.client.HTTPConnection(
                address,
                port=target.port,
                timeout=float(timeout_seconds),
            )
        try:
            connection.request(
                "GET",
                target.request_target,
                headers={
                    "Accept": ", ".join(MIME_TO_EXTENSION),
                    "Host": target.host_header,
                    "User-Agent": "Flama-Image-Library/1.0",
                    "Connection": "close",
                },
            )
            return connection, connection.getresponse()
        except (OSError, ssl.SSLError, http.client.HTTPException) as exc:
            last_error = exc
            connection.close()

    raise _remote_error(
        "Không thể kết nối tới máy chủ hình ảnh.",
        code="IMAGE_REMOTE_FETCH_FAILED",
    ) from last_error


def _read_bounded(
    response: http.client.HTTPResponse,
    *,
    max_bytes: int,
) -> bytes:
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = response.read(min(64 * 1024, max_bytes + 1 - total))
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise _remote_error(
                f"Hình ảnh từ link vượt quá {int(max_bytes)} bytes.",
                code="MEDIA_TOO_LARGE",
                status=413,
            )
        chunks.append(chunk)
    content = b"".join(chunks)
    if not content:
        raise _remote_error(
            "Link hình ảnh trả về tệp rỗng.",
            code="IMAGE_REMOTE_FETCH_FAILED",
        )
    return content


def _parse_content_length(raw_value: str | None) -> int | None:
    if not raw_value:
        return None
    try:
        value = int(raw_value)
    except (TypeError, ValueError):
        return None
    return value if value >= 0 else None


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
