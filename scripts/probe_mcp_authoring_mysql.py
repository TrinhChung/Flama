"""Exercise MCP authoring over HTTP on local MySQL using disposable owned rows.

No DDL, migrations, schema repair or changes to existing users are permitted.
Run from a worktree with --env-file pointing to the existing local .env.
"""

import argparse
import os
from pathlib import Path
import secrets
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path)
    args = parser.parse_args()
    if args.env_file:
        from dotenv import load_dotenv
        load_dotenv(args.env_file)
    os.environ["STARTUP_RUN_MAINTENANCE"] = "false"
    os.environ["STARTUP_RUN_DB_CREATE_ALL"] = "false"
    os.environ["STARTUP_CHECK_DB_CONNECTIVITY"] = "false"
    from sqlalchemy import event
    from app import create_app
    from app.services import flashcard_content_service, template_library_service, user_api_token_service
    from models import db
    from models.deck import Deck
    from models.note import Note
    from models.note_type import NoteType
    from models.template import Template
    from models.user import User
    from tests.study_note_fixtures import create_note_user

    app = create_app({"WTF_CSRF_ENABLED": False, "STARTUP_RUN_MAINTENANCE": False,
        "STARTUP_RUN_DB_CREATE_ALL": False, "STARTUP_CHECK_DB_CONNECTIVITY": False,
        "MCP_PREVIEW_BACKEND": "memory", "MCP_TEMPLATE_PREVIEW_UI_ENABLED": False})
    with app.app_context():
        assert db.engine.dialect.name == "mysql", "Local MySQL required."
        assert db.engine.url.host in {"localhost", "127.0.0.1", "::1"}, "Local host required."
        def no_ddl(_conn, _cursor, statement, _params, _context, _many):
            assert statement.lstrip().split(None, 1)[0].upper() not in {"CREATE", "ALTER", "DROP", "TRUNCATE"}, "DDL is forbidden."
        event.listen(db.engine, "before_cursor_execute", no_ddl)
        username = "mcp-authoring-probe-" + secrets.token_hex(8)
        user_id = None
        try:
            user = create_note_user(db.session, username=username, email=username + "@example.invalid")
            user.set_password(secrets.token_urlsafe(32))
            db.session.commit()
            user_id = user.id
            client = app.test_client()
            with client.session_transaction() as session:
                session["_user_id"], session["_fresh"] = str(user_id), True

            def call(name, arguments, *, error=None):
                response = client.post("/api/mcp", json={"jsonrpc": "2.0", "id": "probe",
                    "method": "tools/call", "params": {"name": name, "arguments": arguments}})
                payload = response.get_json()
                assert response.status_code == 200 and "result" in payload, (name, payload)
                result = payload["result"]
                if error:
                    assert result.get("isError") and result["structuredContent"]["error"]["code"] == error, (name, result)
                else:
                    assert not result.get("isError"), (name, result)
                return result["structuredContent"]

            created = call("create_note_type", {"name": "MCP authoring probe", "fields": [
                {"name": "Word", "field_type": "text", "identity_role": "primary"},
                {"name": "Meaning", "field_type": "richtext"}]})
            nt_id = created["id"]
            schema = call("get_note_type_schema", {"note_type_id": nt_id, "include_templates": True})
            ids = {row["name"]: row["id"] for row in schema["fields"]}
            template = call("create_card_template", {"name": "MCP reusable probe",
                "input_schema": [{"key": "prompt", "label": "Prompt", "type": "text", "required": True},
                    {"key": "definition", "type": "richtext"}],
                "front_html": "<div>{{prompt}}</div>", "back_html": "{{FrontSide}}<hr>{{definition}}"})
            tid = template["id"]
            assert "front_html" not in template
            listing = call("list_card_templates", {"search": "MCP reusable probe"})
            assert tid in {row["id"] for row in listing["items"]} and listing["pagination"]["page"] == 1
            source = call("get_card_template", {"template_id": tid, "include_source": True})
            app_result = call("attach_card_template", {"note_type_id": nt_id, "template_id": tid,
                "input_bindings": {"prompt": ids["Word"], "definition": ids["Meaning"]}, "is_default": True})
            aid = app_result["application_id"]
            assert "template" not in app_result
            removal = {"removed": [schema["templates"][0]["application_id"]]}
            impact = call("preview_note_type_update", {"note_type_id": nt_id, "templates": removal})
            call("update_note_type", {"note_type_id": nt_id, "templates": removal, "preview_id": impact["preview_id"]})

            deck = call("create_deck", {"name": "MCP authoring probe", "default_note_type_id": nt_id})
            call("create_note", {"deck_id": deck["deck_id"], "note_type_id": nt_id,
                "fields": {"Word": "猫", "Meaning": "Cat"}})
            stored_note = Note.query.filter_by(user_id=user_id, note_type_id=nt_id).one()
            samples = {"Word": "猫", "Meaning": "Cat"}
            preview = call("preview_note_type_template", {"note_type_id": nt_id, "application_id": aid,
                "sample_values": samples, "include_server_render": True})
            assert preview["valid"] and "猫" in preview["server_render"]["front_html"]
            assert "Cat" in preview["server_render"]["back_html"]

            changes = {"renamed": [{"old_name": "Meaning", "new_name": "Definition"}]}
            impact = call("preview_note_type_update", {"note_type_id": nt_id, "name": "MCP renamed probe", "fields": changes})
            updated = call("update_note_type", {"note_type_id": nt_id, "name": "MCP renamed probe",
                "fields": changes, "preview_id": impact["preview_id"]})
            db.session.refresh(stored_note)
            assert updated["name"] == "MCP renamed probe" and stored_note.field_values["Definition"] == "Cat"
            assert "Meaning" not in stored_note.field_values
            schema = call("get_note_type_schema", {"note_type_id": nt_id, "include_templates": True})
            assert next(f["id"] for f in schema["fields"] if f["name"] == "Definition") == ids["Meaning"]
            call("update_note_type", {"note_type_id": nt_id,
                "fields": {"modified": [{"name": "Definition", "field_type": "markdown", "required": True, "position": 0}]}})
            renamed = call("update_card_template", {"template_id": tid, "name": "MCP renamed template",
                "shared_css": ".card { color: inherit; }", "input_schema": source["input_schema"],
                "expected_current_version_id": source["current_version_id"]})
            assert renamed["name"] == "MCP renamed template"
            call("update_card_template", {"template_id": tid, "name": "Stale edit",
                "expected_current_version_id": source["current_version_id"]}, error="TEMPLATE_VERSION_STALE")
            impact = call("preview_note_type_update", {"note_type_id": nt_id, "description": "Pending preview"})
            changed_inputs = [dict(item, label="Updated prompt") if item["key"] == "prompt" else item
                for item in source["input_schema"]]
            call("update_card_template", {"template_id": tid, "input_schema": changed_inputs,
                "expected_current_version_id": renamed["current_version_id"]})
            call("update_note_type", {"note_type_id": nt_id, "description": "Pending preview",
                "preview_id": impact["preview_id"]}, error="STALE_PREVIEW_ERROR")
            call("update_template_application", {"note_type_id": nt_id, "application_id": aid,
                "display_name": "Reading", "input_bindings": {"prompt": ids["Word"], "definition": ids["Meaning"]}})
            call("update_template_application", {"note_type_id": nt_id, "application_id": aid,
                "input_bindings": {"prompt": "out-of-scope-field"}}, error="FIELD_OUT_OF_SCOPE")
            call("get_card_template", {"template_id": "not-owned"}, error="TEMPLATE_NOT_FOUND")
            call("update_note_type", {"note_type_id": nt_id,
                "fields": {"added": [{"name": "Hint"}, {"name": "Source"}]}})
            full = call("get_note_type_schema", {"note_type_id": nt_id, "include_templates": True})
            positions = {item["name"]: item["position"] for item in full["fields"]}
            assert positions["Source"] > positions["Hint"]
            full_fields = [{key: item[key] for key in ("id", "name", "field_type", "position", "required", "identity_role")}
                for item in full["fields"]]
            next(item for item in full_fields if item["name"] == "Hint")["required"] = True
            impact = call("preview_note_type_update", {"note_type_id": nt_id, "fields": full_fields})
            assert {"name": "Hint", "required": True} in impact["changes"]["modified_fields"]
            call("update_note_type", {"note_type_id": nt_id, "fields": {"modified": [{"name": "Word", "required": "false"}]}}, error="INVALID_PARAMS")
            removal = {"removed": ["Definition"]}
            impact = call("preview_note_type_update", {"note_type_id": nt_id, "fields": removal})
            assert impact["requires_confirmation"] and impact["data_loss_possible"]
            call("update_note_type", {"note_type_id": nt_id, "fields": removal,
                "preview_id": impact["preview_id"]}, error="CONFIRMATION_REQUIRED")
            db.session.refresh(stored_note)
            assert stored_note.field_values["Definition"] == "Cat"
            invalid = call("preview_note_type_template", {"input_schema": [], "front_html": "<script>const x = ;</script>",
                "back_html": "", "sample_values": {}})
            assert not invalid["valid"] and invalid["checks"]["javascript_syntax"] == "failed"
            token = user_api_token_service.issue_token(user_id=user_id, name="read-only probe", scopes=["note-type:read"])
            guest = app.test_client()
            response = guest.post("/api/mcp", headers={"Authorization": "Bearer " + token.plaintext}, json={
                "jsonrpc": "2.0", "id": "scope", "method": "tools/call", "params": {"name": "create_card_template", "arguments": {"name": "Blocked"}}})
            assert "error" in response.get_json(), "Read-only token was allowed to mutate."
            print("PASS local MySQL HTTP MCP: create, discovery, fields, rename/data preservation, typed inputs, bindings, preview, retirement, versions, ownership, scopes.")
        finally:
            db.session.rollback()
            if user_id:
                user = db.session.get(User, user_id)
                assert user and user.username == username and user.email == username + "@example.invalid"
                for row in Note.query.filter_by(user_id=user_id).all():
                    flashcard_content_service.delete_note(user_id=user_id, note_id=row.id)
                for row in NoteType.query.filter_by(user_id=user_id).all():
                    flashcard_content_service.delete_note_type(user_id=user_id, note_type_id=row.id)
                for row in Template.query.filter_by(owner_user_id=user_id).all():
                    template_library_service.delete_template(user_id=user_id, template_id=row.id)
                for row in Deck.query.filter_by(owner_user_id=user_id).all():
                    db.session.delete(row)
                db.session.flush()
                db.session.delete(user)
                db.session.commit()
                assert db.session.get(User, user_id) is None
                print("Removed the exact disposable user and its owned content.")
            event.remove(db.engine, "before_cursor_execute", no_ddl)


if __name__ == "__main__":
    main()
