"""Explicit canary admission when an exact analytics projection is pending."""

from flask import current_app


class AnalyticsSummaryNotReady(RuntimeError):
    code = "ANALYTICS_SUMMARY_NOT_READY"
    retry_after_seconds = 60

    def __init__(self, metric):
        super().__init__("Dữ liệu thống kê đang cập nhật. Vui lòng thử lại sau ít phút.")
        self.metric = metric


def require_ready_summary(*, user_id, metric):
    """Only explicit learners opt into pending responses instead of raw scans.

    Readers call this after selecting summary mode and admitting the learner's
    normal read cohort. Raw/shadow remain recovery/oracle modes.
    """
    configured = current_app.config.get("ANALYTICS_REQUIRE_READY_USER_IDS", ())
    configured = configured.split(",") if isinstance(configured, str) else configured
    try:
        selected = int(user_id) in {int(value) for value in configured if str(value).strip()}
    except (TypeError, ValueError):
        selected = False
    if selected:
        raise AnalyticsSummaryNotReady(metric)
