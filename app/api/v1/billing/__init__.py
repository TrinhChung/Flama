"""Billing REST API V1 resources."""

from flask import Blueprint

from .orders import orders_bp
from .support import support_bp


billing_bp = Blueprint("api_v1_billing", __name__)
billing_bp.register_blueprint(orders_bp, url_prefix="/orders")
billing_bp.register_blueprint(support_bp, url_prefix="/support-donation")
