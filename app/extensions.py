"""Shared Flask extensions."""

from flask_login import LoginManager
from flask_migrate import Migrate

login_manager = LoginManager()
login_manager.login_view = "auth.login"
login_manager.login_message = "Vui lòng đăng nhập để tiếp tục."
login_manager.login_message_category = "info"

migrate = Migrate()
