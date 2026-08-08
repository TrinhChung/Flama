import io
import unittest
from app import create_app
from models import db
from models.user import User
from models.user_role import UserRole


class SupportTicketApiTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app(
            {
                "TESTING": True,
                "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
                "WTF_CSRF_ENABLED": False,
            }
        )
        self.client = self.app.test_client()
        with self.app.app_context():
            db.create_all()
            from app.services.user_roles import ensure_default_user_roles
            ensure_default_user_roles(db.session)
            admin_role = UserRole.query.filter_by(code="admin").first()
            user_role = UserRole.query.filter_by(code="regular").first()
            admin = User(
                username="ticket-admin",
                email="admin@example.com",
                is_admin=True,
                role=admin_role,
            )
            admin.set_password("password")
            user = User(
                username="ticket-user",
                email="user@example.com",
                is_admin=False,
                role=user_role,
            )
            user.set_password("password")
            db.session.add_all([admin, user])
            db.session.commit()
            self.user_id = user.id

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def _login(self, email: str):
        self.client.post("/logout")
        response = self.client.post(
            "/api/auth/login",
            json={"email": email, "password": "password"},
        )
        self.assertEqual(response.status_code, 200)

    def test_create_and_manage_ticket_flow(self):
        # 1. User uploads image attachment
        img_bytes = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4"
        upload_resp = self.client.post(
            "/api/tickets/upload-image",
            data={"file": (io.BytesIO(img_bytes), "screenshot.png")},
            content_type="multipart/form-data",
        )
        self.assertEqual(upload_resp.status_code, 200)
        img_url = upload_resp.get_json()["url"]
        self.assertTrue(img_url.startswith("/api/tickets/attachments/"))

        # 2. Login as user and create a ticket
        self._login("user@example.com")
        create_resp = self.client.post(
            "/api/tickets",
            json={
                "category": "bug",
                "title": "Lỗi không hiển thị nút Study",
                "description": "Khi bấm vào deck 'N3 Vocabulary', nút Start Study bị ẩn.",
                "reproduce_steps": "1. Mở trang /browse\n2. Chọn deck N3",
                "screen_url": "http://localhost:5173/browse?deck=12",
                "screen_name": "Duyệt từ vựng & Thẻ ghi nhớ",
                "attachment_urls": [img_url],
            },
        )
        self.assertEqual(create_resp.status_code, 201)
        ticket_data = create_resp.get_json()["item"]
        ticket_id = ticket_data["id"]
        ticket_code = ticket_data["ticket_code"]
        self.assertTrue(ticket_code.startswith("TK-"))
        self.assertEqual(ticket_data["status"], "open")
        self.assertEqual(len(ticket_data["attachment_urls"]), 1)

        # 3. User lists my tickets
        list_resp = self.client.get("/api/tickets/my")
        self.assertEqual(list_resp.status_code, 200)
        my_tickets = list_resp.get_json()["items"]
        self.assertEqual(len(my_tickets), 1)
        self.assertEqual(my_tickets[0]["id"], ticket_id)

        # 4. Login as admin and list admin tickets
        self._login("admin@example.com")
        admin_list_resp = self.client.get("/api/admin/tickets?status=open")
        self.assertEqual(admin_list_resp.status_code, 200)
        admin_data = admin_list_resp.get_json()
        self.assertEqual(admin_data["total"], 1)
        self.assertEqual(admin_data["stats"]["open"], 1)

        # 5. Admin updates status to in_progress and posts a reply
        patch_resp = self.client.patch(
            f"/api/admin/tickets/{ticket_id}",
            json={"status": "in_progress", "priority": "high", "admin_notes": "Đã chuyển team Dev xử lý"},
        )
        self.assertEqual(patch_resp.status_code, 200)
        self.assertEqual(patch_resp.get_json()["item"]["status"], "in_progress")

        admin_reply_resp = self.client.post(
            f"/api/tickets/{ticket_id}/replies",
            json={"message": "Cảm ơn bạn đã báo cáo, đội ngũ đang kiểm tra lỗi này.", "new_status": "in_progress"},
        )
        self.assertEqual(admin_reply_resp.status_code, 201)

        # 6. User reads ticket details and replies back
        self._login("user@example.com")
        detail_resp = self.client.get(f"/api/tickets/{ticket_code}")
        self.assertEqual(detail_resp.status_code, 200)
        item = detail_resp.get_json()["item"]
        self.assertEqual(item["status"], "in_progress")
        self.assertEqual(len(item["replies"]), 1)
        self.assertTrue(item["replies"][0]["is_admin_reply"])

        user_reply_resp = self.client.post(
            f"/api/tickets/{ticket_code}/replies",
            json={"message": "Vâng, em đã thử reset cache nhưng vẫn bị ạ."},
        )
        self.assertEqual(user_reply_resp.status_code, 201)

        # Final check detail
        detail_resp2 = self.client.get(f"/api/tickets/{ticket_code}")
        item2 = detail_resp2.get_json()["item"]
        self.assertEqual(len(item2["replies"]), 2)


if __name__ == "__main__":
    unittest.main()
