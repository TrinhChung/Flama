# MCP `list_my_decks`

Endpoint MCP tối giản nằm tại `POST /api/mcp` và chỉ expose đúng 1 tool: `list_my_decks`.

## Auth

- Tool không nhận `user_id`.
- Backend dùng auth context hiện có của Flask (`current_user` từ session đăng nhập).
- Nếu chưa đăng nhập, route trả về lỗi JSON-RPC `401 Authentication required`.

## Supported MCP Methods

- `initialize`
- `notifications/initialized`
- `tools/list`
- `tools/call`

Protocol version hiện được server trả về: `2025-11-25`.

## Example Requests

### 1. Initialize

```http
POST /api/mcp
Content-Type: application/json

{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "initialize",
  "params": {
    "protocolVersion": "2025-11-25",
    "capabilities": {},
    "clientInfo": {
      "name": "local-test",
      "version": "0.1.0"
    }
  }
}
```

### 2. List tools

```http
POST /api/mcp
Content-Type: application/json
MCP-Protocol-Version: 2025-11-25

{
  "jsonrpc": "2.0",
  "id": 2,
  "method": "tools/list",
  "params": {}
}
```

### 3. Call `list_my_decks`

```http
POST /api/mcp
Content-Type: application/json
MCP-Protocol-Version: 2025-11-25

{
  "jsonrpc": "2.0",
  "id": 3,
  "method": "tools/call",
  "params": {
    "name": "list_my_decks",
    "arguments": {}
  }
}
```

## Example Response

```json
{
  "jsonrpc": "2.0",
  "id": 3,
  "result": {
    "content": [
      {
        "type": "text",
        "text": "{\"decks\": [{\"deck_id\": 12, \"name\": \"JLPT N5\", \"description\": \"Core deck\", \"created_at\": \"2026-03-31T10:00:00\"}]}"
      }
    ],
    "structuredContent": {
      "decks": [
        {
          "deck_id": 12,
          "name": "JLPT N5",
          "description": "Core deck",
          "created_at": "2026-03-31T10:00:00"
        }
      ]
    }
  }
}
```

## Quick Local Test

1. Chạy app như bình thường, ví dụ qua Docker Compose hoặc `flask run`.
2. Đăng nhập để lấy session cookie:

```bash
curl -s -c /tmp/flama.cookies \
  -X POST http://localhost:4789/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  --data "email=your-user@example.com&password=your-password" > /dev/null
```

3. Gọi `initialize`:

```bash
curl -s -b /tmp/flama.cookies \
  -X POST http://localhost:4789/api/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-11-25","capabilities":{},"clientInfo":{"name":"local-test","version":"0.1.0"}}}'
```

4. Gọi tool:

```bash
curl -s -b /tmp/flama.cookies \
  -X POST http://localhost:4789/api/mcp \
  -H "Content-Type: application/json" \
  -H "MCP-Protocol-Version: 2025-11-25" \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"list_my_decks","arguments":{}}}'
```

5. Kiểm tra case bị chặn:

```bash
curl -s -b /tmp/flama.cookies \
  -X POST http://localhost:4789/api/mcp \
  -H "Content-Type: application/json" \
  -H "MCP-Protocol-Version: 2025-11-25" \
  -d '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"list_my_decks","arguments":{"user_id":999}}}'
```

Request trên phải bị reject vì tool không nhận `user_id`.
