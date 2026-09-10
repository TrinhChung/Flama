"""Administrative REST API V1 resources."""

from flask import Blueprint

from .analytics import admin_analytics_bp
from .fees import admin_fees_bp
from .image_library import admin_image_library_bp
from .payments import admin_payments_bp
from .security_alerts import admin_security_alerts_bp
from .support import admin_support_bp
from .taxonomy import admin_taxonomy_bp
from .tts import admin_tts_bp
from .users import admin_users_bp
from .mcp_tokens import admin_mcp_tokens_bp


admin_bp = Blueprint("api_v1_admin", __name__)
admin_bp.register_blueprint(admin_analytics_bp, url_prefix="/analytics")
admin_bp.register_blueprint(admin_users_bp, url_prefix="/users")
admin_bp.register_blueprint(admin_fees_bp, url_prefix="/fees")
admin_bp.register_blueprint(admin_tts_bp, url_prefix="/tts-providers")
admin_bp.register_blueprint(admin_support_bp, url_prefix="/support-donation")
admin_bp.register_blueprint(admin_image_library_bp, url_prefix="/image-library")
admin_bp.register_blueprint(admin_security_alerts_bp, url_prefix="/security-alerts")
admin_bp.register_blueprint(admin_payments_bp, url_prefix="/payments")
admin_bp.register_blueprint(admin_taxonomy_bp, url_prefix="/taxonomy")
admin_bp.register_blueprint(admin_mcp_tokens_bp, url_prefix="/mcp-tokens")


