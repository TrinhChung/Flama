# Flama MCP (Model Context Protocol) on Flama Connect

Giao thức **Model Context Protocol (MCP)** của Flama được tích hợp trực tiếp vào **Flama Connect** (`connect_wsgi.py`, port `4790`) dưới tiền tố đường dẫn `/v1/mcp/`.

---

## 1. Tổng quan Kiến trúc

- **Service Process**: Flama Connect (`connect_wsgi.py` - Port 4790).
- **Protocol**: Model Context Protocol (JSON-RPC 2.0 transport over HTTP).
- **Supported Protocol Version**: `2025-11-25`.
- **Endpoints**:
  - `POST /v1/mcp`: Endpoint tiêu chuẩn nhận Bearer header (`Authorization: Bearer <token>`) hoặc `X-Flama-Connect-Key: <token>`.
  - `POST /v1/mcp/<url_token>`: Endpoint nhận token trực tiếp trong đường dẫn (hỗ trợ các MCP client chỉ cho phép nhập Server URL).
  - `OPTIONS /v1/mcp` & `OPTIONS /v1/mcp/<url_token>`: CORS preflight.

---

## 2. Xác thực (Authentication) & Token

MCP trên Flama Connect chấp nhận cả hai loại token:
1. **`UserApiToken`** (`flama_yt_...`): Token dài hạn tạo từ màn hình API Tokens.
2. **`McpAccessToken`** (`flama_mcp_...`): Token ngắn hạn tạo từ màn hình MCP Tokens.

### Phân quyền theo Scope:
- `deck:read`: Xem danh sách decks, cây thư mục deck, thống kê thẻ due.
- `note-type:read`: Xem danh sách và schema của Note Types.
- `note:check`: Tìm kiếm và kiểm tra trùng lặp thẻ flashcard.
- `note:create`: Tạo thẻ flashcard đơn lẻ hoặc hàng loạt.

---

## 3. Danh sách các MCP Tools được hỗ trợ

| Tên Tool | Scope | Mục đích |
| :--- | :--- | :--- |
| `list_my_decks` | `deck:read` | Liệt kê các flashcard deck mà người dùng sở hữu |
| `get_deck_tree` | `deck:read` | Lấy cấu trúc cây thư mục deck phân cấp đầy đủ |
| `list_note_types` | `note-type:read` | Lấy danh sách các loại Note Type (Model) có sẵn |
| `get_note_type_schema` | `note-type:read` | Lấy chi tiết các field definitions và card templates |
| `find_notes` | `note:check` | Tìm kiếm các thẻ flashcard theo từ khóa hoặc nội dung field |
| `create_note` | `note:create` | Tạo một thẻ flashcard mới với các field và tự sinh Card |
| `batch_create_notes` | `note:create` | Tạo hàng loạt thẻ flashcard trong một batch transaction (tối đa 50 thẻ) |
| `get_due_card_counts` | `deck:read` | Lấy số lượng thẻ đến hạn học hôm nay (due, new, review, learn) |

---

## 4. Các phương thức MCP JSON-RPC (Supported Methods)

- `initialize`
- `notifications/initialized`
- `tools/list`
- `tools/call`
- `resources/list`
- `prompts/list`

---

## 5. Ví dụ Gọi API (Curl / HTTP)

### 1. Initialize

```http
POST /v1/mcp
Content-Type: application/json
Authorization: Bearer <your_token>

{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "initialize",
  "params": {
    "protocolVersion": "2025-11-25",
    "capabilities": {},
    "clientInfo": {
      "name": "cursor-agent",
      "version": "1.0.0"
    }
  }
}
```

### 2. Liệt kê Tools (`tools/list`)

```http
POST /v1/mcp
Content-Type: application/json
MCP-Protocol-Version: 2025-11-25

{
  "jsonrpc": "2.0",
  "id": 2,
  "method": "tools/list",
  "params": {}
}
```

### 3. Tạo thẻ flashcard (`tools/call` - `create_note`)

```http
POST /v1/mcp
Content-Type: application/json
MCP-Protocol-Version: 2025-11-25
Authorization: Bearer <your_token>

{
  "jsonrpc": "2.0",
  "id": 3,
  "method": "tools/call",
  "params": {
    "name": "create_note",
    "arguments": {
      "deck_name": "Tiếng Nhật N5",
      "note_type_name": "Japanese Vocabulary",
      "fields": {
        "Word": "勉強",
        "Reading": "べんきょう",
        "Meaning": "Học tập"
      },
      "tags": ["n5", "noun"]
    }
  }
}
```

### 4. Tìm kiếm thẻ (`tools/call` - `find_notes`)

```http
POST /v1/mcp
Content-Type: application/json
MCP-Protocol-Version: 2025-11-25
Authorization: Bearer <your_token>

{
  "jsonrpc": "2.0",
  "id": 4,
  "method": "tools/call",
  "params": {
    "name": "find_notes",
    "arguments": {
      "query": "勉強",
      "limit": 10
    }
  }
}
```

---

## 6. Cấu hình Client (Claude Desktop / Cursor)

### Cấu hình Claude Desktop (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "flama": {
      "command": "npx",
      "args": [
        "-y",
        "mcp-remote",
        "http://localhost:4790/v1/mcp",
        "--header",
        "Authorization: Bearer <your_token>"
      ]
    }
  }
}
```
