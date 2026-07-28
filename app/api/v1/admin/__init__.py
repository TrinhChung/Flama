"""Administrative REST API V1 resources."""

from flask import Blueprint

from .image_library import admin_image_library_bp
from .payments import admin_payments_bp
from .support import admin_support_bp
from .tts import admin_tts_bp
from .users import admin_users_bp


admin_bp = Blueprint("api_v1_admin", __name__)
admin_bp.register_blueprint(admin_users_bp, url_prefix="/users")
admin_bp.register_blueprint(admin_tts_bp, url_prefix="/tts-providers")
admin_bp.register_blueprint(admin_support_bp, url_prefix="/support-donation")
admin_bp.register_blueprint(admin_image_library_bp, url_prefix="/image-library")
admin_bp.register_blueprint(admin_payments_bp, url_prefix="/payments")
