"""Canonical source of truth for OAuth and MCP scopes, metadata, and permission evaluation."""

from __future__ import annotations

from typing import Any, Iterable

# --- Granular Functional Scopes ---
SCOPE_DECK_READ = "deck:read"
SCOPE_DECK_WRITE = "deck:write"
SCOPE_NOTE_TYPE_READ = "note-type:read"
SCOPE_NOTE_TYPE_WRITE = "note-type:write"
SCOPE_NOTE_CHECK = "note:check"
SCOPE_NOTE_READ = "note:read"
SCOPE_NOTE_CREATE = "note:create"
SCOPE_NOTE_UPDATE = "note:update"
SCOPE_NOTE_DELETE = "note:delete"
SCOPE_NOTE_SYNC = "note:sync"
SCOPE_STUDY_READ = "study:read"
SCOPE_STUDY_WRITE = "study:write"
SCOPE_STATS_READ = "stats:read"

# --- All Granular Scopes ---
ALL_GRANULAR_SCOPES: frozenset[str] = frozenset(
    {
        SCOPE_DECK_READ,
        SCOPE_DECK_WRITE,
        SCOPE_NOTE_TYPE_READ,
        SCOPE_NOTE_TYPE_WRITE,
        SCOPE_NOTE_CHECK,
        SCOPE_NOTE_READ,
        SCOPE_NOTE_CREATE,
        SCOPE_NOTE_UPDATE,
        SCOPE_NOTE_DELETE,
        SCOPE_NOTE_SYNC,
        SCOPE_STUDY_READ,
        SCOPE_STUDY_WRITE,
        SCOPE_STATS_READ,
    }
)

# --- OIDC / Identity Scopes ---
SCOPE_OPENID = "openid"
SCOPE_PROFILE = "profile"
SCOPE_EMAIL = "email"

ALL_OIDC_SCOPES: frozenset[str] = frozenset(
    {
        SCOPE_OPENID,
        SCOPE_PROFILE,
        SCOPE_EMAIL,
    }
)

# --- Legacy / Broad Wildcard Scopes ---
SCOPE_READ_ALL = "read"
SCOPE_WRITE_ALL = "write"
SCOPE_WILDCARD = "*"

ALL_LEGACY_SCOPES: frozenset[str] = frozenset(
    {
        SCOPE_READ_ALL,
        SCOPE_WRITE_ALL,
        SCOPE_WILDCARD,
    }
)

# --- Allowed OAuth Request Scopes ---
# Only granular scopes and standard OIDC scopes can be requested via OAuth 2.1
ALLOWED_OAUTH_SCOPES: frozenset[str] = frozenset(
    ALL_GRANULAR_SCOPES | ALL_OIDC_SCOPES
)

# --- Allowed MCP Token Scopes (includes legacy for UserApiToken / internal) ---
ALLOWED_MCP_SCOPES: frozenset[str] = frozenset(
    ALL_GRANULAR_SCOPES | ALL_LEGACY_SCOPES | ALL_OIDC_SCOPES
)

# --- Default Scopes (when no scope is specified in OAuth / token creation) ---
DEFAULT_SCOPES: tuple[str, ...] = (
    SCOPE_DECK_READ,
    SCOPE_DECK_WRITE,
    SCOPE_NOTE_TYPE_READ,
    SCOPE_NOTE_TYPE_WRITE,
    SCOPE_NOTE_CHECK,
    SCOPE_NOTE_READ,
    SCOPE_NOTE_CREATE,
    SCOPE_NOTE_UPDATE,
    SCOPE_NOTE_DELETE,
    SCOPE_NOTE_SYNC,
    SCOPE_STUDY_READ,
    SCOPE_STUDY_WRITE,
    SCOPE_STATS_READ,
)

# Read-only granular scopes (satisfied by legacy 'read')
READ_ONLY_GRANULAR_SCOPES: frozenset[str] = frozenset(
    {
        SCOPE_DECK_READ,
        SCOPE_NOTE_TYPE_READ,
        SCOPE_NOTE_CHECK,
        SCOPE_NOTE_READ,
        SCOPE_STUDY_READ,
        SCOPE_STATS_READ,
    }
)

# Mutation granular scopes (satisfied by legacy 'write')
WRITE_GRANULAR_SCOPES: frozenset[str] = frozenset(
    {
        SCOPE_DECK_WRITE,
        SCOPE_NOTE_TYPE_WRITE,
        SCOPE_NOTE_CREATE,
        SCOPE_NOTE_UPDATE,
        SCOPE_NOTE_DELETE,
        SCOPE_NOTE_SYNC,
        SCOPE_STUDY_WRITE,
    }
)

# --- Scope Metadata for Consent UI & Discovery ---
SCOPE_METADATA: dict[str, dict[str, str]] = {
    SCOPE_DECK_READ: {
        "id": SCOPE_DECK_READ,
        "title": "Xem danh mục & cấu trúc bộ thẻ",
        "desc": "Đọc danh sách các bộ thẻ flashcard, cấu trúc thư mục phân cấp và số lượng thẻ.",
        "category": "Bộ thẻ (Decks)",
        "icon": "folder",
    },
    SCOPE_DECK_WRITE: {
        "id": SCOPE_DECK_WRITE,
        "title": "Quản lý & tạo mới bộ thẻ",
        "desc": "Tạo bộ thẻ mới, đổi tên, cập nhật mô tả và tổ chức cây thư mục bộ bài.",
        "category": "Bộ thẻ (Decks)",
        "icon": "folder-plus",
    },
    SCOPE_NOTE_READ: {
        "id": SCOPE_NOTE_READ,
        "title": "Xem & tìm kiếm thẻ ghi nhớ",
        "desc": "Đọc nội dung chi tiết các trường dữ liệu (từ vựng, kanji, nghĩa, ví dụ) và tìm kiếm thẻ.",
        "category": "Thẻ ghi nhớ (Notes)",
        "icon": "file-text",
    },
    SCOPE_NOTE_CHECK: {
        "id": SCOPE_NOTE_CHECK,
        "title": "Kiểm tra trùng lặp thẻ",
        "desc": "Kiểm tra xem từ vựng hay thẻ ghi nhớ đã tồn tại trong bộ bài của bạn chưa.",
        "category": "Thẻ ghi nhớ (Notes)",
        "icon": "check-circle",
    },
    SCOPE_NOTE_CREATE: {
        "id": SCOPE_NOTE_CREATE,
        "title": "Tạo thẻ ghi nhớ flashcard mới",
        "desc": "Thêm từ vựng và thẻ mới vào bộ bài của bạn kèm các trường thông tin tự động.",
        "category": "Thẻ ghi nhớ (Notes)",
        "icon": "plus-circle",
    },
    SCOPE_NOTE_UPDATE: {
        "id": SCOPE_NOTE_UPDATE,
        "title": "Cập nhật thẻ ghi nhớ & nhãn (tags)",
        "desc": "Chỉnh sửa nội dung thẻ, gắn thẻ phân loại (tags) hoặc chuyển thẻ sang bộ bài khác.",
        "category": "Thẻ ghi nhớ (Notes)",
        "icon": "edit",
    },
    SCOPE_NOTE_DELETE: {
        "id": SCOPE_NOTE_DELETE,
        "title": "Xóa thẻ ghi nhớ (Bảo vệ 2 bước)",
        "desc": "Xóa thẻ ghi nhớ và các flashcard liên quan (bắt buộc phải có sự phê duyệt trực tiếp từ bạn).",
        "category": "Thẻ ghi nhớ (Notes)",
        "icon": "trash-2",
    },
    SCOPE_NOTE_SYNC: {
        "id": SCOPE_NOTE_SYNC,
        "title": "Đồng bộ hóa ghi chú từ nguồn bên ngoài",
        "desc": "Tự động tạo, cập nhật, di chuyển thẻ ghi nhớ và tạo bộ bài khi đồng bộ từ các nguồn dữ liệu bên ngoài.",
        "category": "Thẻ ghi nhớ (Notes)",
        "icon": "refresh-cw",
    },
    SCOPE_STUDY_READ: {
        "id": SCOPE_STUDY_READ,
        "title": "Xem hàng đợi ôn tập Spaced Repetition",
        "desc": "Xem danh sách các thẻ đến hạn học hôm nay và dự đoán khoảng cách lặp lại ngắt quãng.",
        "category": "Học tập (SRS Study)",
        "icon": "brain",
    },
    SCOPE_STUDY_WRITE: {
        "id": SCOPE_STUDY_WRITE,
        "title": "Ghi nhận kết quả ôn tập",
        "desc": "Gửi đánh giá kết quả học tập (Again, Hard, Good, Easy) vào thuật toán tính lịch học Flama.",
        "category": "Học tập (SRS Study)",
        "icon": "zap",
    },
    SCOPE_STATS_READ: {
        "id": SCOPE_STATS_READ,
        "title": "Xem thống kê học tập & Streak",
        "desc": "Theo dõi chuỗi ngày học liên tục (streak), số thẻ đã ôn hôm nay và tổng quan tiến độ.",
        "category": "Thống kê (Analytics)",
        "icon": "bar-chart",
    },
    SCOPE_NOTE_TYPE_READ: {
        "id": SCOPE_NOTE_TYPE_READ,
        "title": "Xem cấu trúc mẫu thẻ (Note Types)",
        "desc": "Đọc danh sách mẫu thẻ (Vocabulary, Basic, Cloze) và cấu hình các trường dữ liệu tùy chỉnh.",
        "category": "Mẫu thẻ (Note Types)",
        "icon": "layers",
    },
    SCOPE_NOTE_TYPE_WRITE: {
        "id": SCOPE_NOTE_TYPE_WRITE,
        "title": "Quản lý mẫu thẻ (Note Types)",
        "desc": "Tạo mới, chỉnh sửa trường dữ liệu hoặc mẫu card (bảo vệ preview cho thao tác gây mất dữ liệu).",
        "category": "Mẫu thẻ (Note Types)",
        "icon": "layers",
    },
    SCOPE_OPENID: {
        "id": SCOPE_OPENID,
        "title": "Xác thực danh tính OpenID Connect",
        "desc": "Cung cấp mã định danh người dùng OpenID.",
        "category": "Tài khoản (Account)",
        "icon": "user-check",
    },
    SCOPE_PROFILE: {
        "id": SCOPE_PROFILE,
        "title": "Thông tin tài khoản cơ bản",
        "desc": "Đọc tên hiển thị và thông tin tài khoản cơ bản.",
        "category": "Tài khoản (Account)",
        "icon": "user",
    },
    SCOPE_EMAIL: {
        "id": SCOPE_EMAIL,
        "title": "Địa chỉ Email",
        "desc": "Đọc địa chỉ email của tài khoản Flama.",
        "category": "Tài khoản (Account)",
        "icon": "mail",
    },
}


def parse_scope_tokens(raw_scopes: Any) -> list[str]:
    """Parse string, list, or set into a clean list of scope token strings."""
    if raw_scopes is None:
        return []
    if isinstance(raw_scopes, str):
        return [s.strip() for s in raw_scopes.replace(",", " ").split() if s.strip()]
    if isinstance(raw_scopes, (list, tuple, set)):
        items: list[str] = []
        for s in raw_scopes:
            if isinstance(s, str) and s.strip():
                for part in s.replace(",", " ").split():
                    if part.strip():
                        items.append(part.strip())
        return items
    return []


def validate_and_normalize_oauth_scopes(raw_scopes: Any) -> tuple[str, ...]:
    """Validate requested scopes for OAuth authorization.
    
    If raw_scopes is None or empty:
        Returns DEFAULT_SCOPES.
    If raw_scopes is provided:
        Every scope token MUST be in ALLOWED_OAUTH_SCOPES.
        If any invalid/unknown scope token is found:
            Raises ValueError with details (to be mapped to OAuthError('invalid_scope')).
    """
    tokens = parse_scope_tokens(raw_scopes)
    if not tokens:
        return DEFAULT_SCOPES

    normalized: list[str] = []
    for token in tokens:
        if token not in ALLOWED_OAUTH_SCOPES:
            raise ValueError(f"Unknown or unsupported scope: '{token}'")
        if token not in normalized:
            normalized.append(token)

    return tuple(normalized) if normalized else DEFAULT_SCOPES


def has_scope(granted_scopes: Iterable[str], required_scope: str | None) -> bool:
    """Check if granted scopes satisfy required_scope.
    
    Rules:
    - If required_scope is None or empty -> True
    - Wildcard '*' satisfies any required scope
    - Exact match: required_scope in granted -> True
    - 'note:read' satisfies 'note:check' (reading notes implies checking presence)
    - Legacy 'read' satisfies any read-only granular scope
    - Legacy 'write' satisfies any mutation granular scope and read-only granular scope
    - Granular scopes ('note:create', 'note:update', 'note:delete', 'note:sync')
      are strictly independent and NEVER satisfy each other.
    """
    if not required_scope:
        return True

    granted = set(granted_scopes)
    if SCOPE_WILDCARD in granted:
        return True

    if required_scope in granted:
        return True

    # 'note:read' satisfies 'note:check'
    if required_scope == SCOPE_NOTE_CHECK and SCOPE_NOTE_READ in granted:
        return True

    # Legacy 'write' satisfies all mutation and read scopes
    if SCOPE_WRITE_ALL in granted:
        if required_scope in WRITE_GRANULAR_SCOPES or required_scope in READ_ONLY_GRANULAR_SCOPES:
            return True

    # Legacy 'read' satisfies all read-only scopes
    if SCOPE_READ_ALL in granted:
        if required_scope in READ_ONLY_GRANULAR_SCOPES:
            return True

    return False


def extract_userinfo_claims(user: Any, granted_scopes: Iterable[str]) -> dict[str, Any]:
    """Extract standard OIDC claims from user object based on granted scopes."""
    claims: dict[str, Any] = {
        "sub": str(getattr(user, "id", "")),
    }

    if has_scope(granted_scopes, SCOPE_PROFILE):
        username = getattr(user, "username", "")
        claims["id"] = getattr(user, "id", None)
        claims["username"] = username
        claims["preferred_username"] = username
        display_name = getattr(user, "display_name", None)
        if display_name:
            claims["name"] = display_name

    if has_scope(granted_scopes, SCOPE_EMAIL):
        email = getattr(user, "email", "")
        claims["email"] = email
        # Email is verified if user has email and is active / verified
        claims["email_verified"] = bool(getattr(user, "email_verified", bool(email)))

    return claims
