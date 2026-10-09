"""Standalone stdio JSON-RPC 2.0 Model Context Protocol (MCP) server for Flama.

Enables desktop AI assistants (Claude Desktop, Cursor, Goose) to search published
Flama marketplace decks, look up Japanese vocabulary, preview sample cards,
and access authoritative documentation without authentication barriers.

Configuration in Claude Desktop (`claude_desktop_config.json`):
    {
      "mcpServers": {
        "flama": {
          "command": "python",
          "args": ["d:/Project/nihongo/scripts/flama_mcp_server.py"]
        }
      }
    }
"""

from __future__ import annotations

import io
import json
import logging
import os
import sys
from typing import TextIO

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

logger = logging.getLogger("flama_mcp_server")


def process_mcp_message(client, raw_line: str) -> str | None:
    """Process a single JSON-RPC line and return JSON response string (or None for notifications)."""
    line = raw_line.strip()
    if not line:
        return None

    try:
        req = json.loads(line)
    except json.JSONDecodeError as exc:
        err_resp = {
            "jsonrpc": "2.0",
            "id": None,
            "error": {
                "code": -32700,
                "message": f"Parse error: Invalid JSON ({exc})",
            },
        }
        return json.dumps(err_resp)

    if not isinstance(req, dict):
        err_resp = {
            "jsonrpc": "2.0",
            "id": None,
            "error": {
                "code": -32600,
                "message": "Invalid Request: Expected JSON object.",
            },
        }
        return json.dumps(err_resp)

    # Route through Flask test client on /api/mcp
    response = client.post(
        "/api/mcp",
        json=req,
        headers={"MCP-Protocol-Version": "2025-11-25"},
    )

    if response.status_code == 204:
        return None

    data = response.get_json(silent=True)
    if data is not None:
        return json.dumps(data)
    return None


def run_stdio_server(
    input_stream: TextIO | None = None,
    output_stream: TextIO | None = None,
    app_instance=None,
) -> None:
    """Run the stdio JSON-RPC message loop."""
    if input_stream is None:
        input_stream = sys.stdin
    if output_stream is None:
        output_stream = sys.stdout

    if app_instance is None:
        from wsgi import app as wsgi_app
        app_instance = wsgi_app

    client = app_instance.test_client()

    for line in input_stream:
        response_str = process_mcp_message(client, line)
        if response_str is not None:
            output_stream.write(response_str + "\n")
            output_stream.flush()


if __name__ == "__main__":
    # Log to stderr so stdout is strictly JSON-RPC protocol
    logging.basicConfig(
        stream=sys.stderr,
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    logger.info("Starting Flama stdio MCP server...")
    run_stdio_server()
