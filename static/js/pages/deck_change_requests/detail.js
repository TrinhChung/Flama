import {
  approveRequest,
  fetchRequestDetail,
  rejectRequest,
} from "./api.js";
import {
  getRequestStatusMeta,
  renderChangeItems,
  renderConflicts,
  renderRequestSummary,
} from "./ui.js";

const root = document.getElementById("deck-change-request-detail-root");

if (root) {
  const requestId = root.getAttribute("data-request-id") || "";
  const inboxUrl = root.getAttribute("data-inbox-url") || "/";
  const requesterUrlTemplate = root.getAttribute("data-requester-url-template") || "";

  const backLink = document.getElementById("change-request-detail-back-link");
  const titleEl = document.getElementById("change-request-detail-title");
  const metaEl = document.getElementById("change-request-detail-meta");
  const errorEl = document.getElementById("change-request-detail-error");
  const statusEl = document.getElementById("change-request-detail-status");
  const summaryEl = document.getElementById("change-request-detail-summary");
  const itemsEl = document.getElementById("change-request-detail-items");
  const conflictsEl = document.getElementById("change-request-detail-conflicts");
  const reviewNoteEl = document.getElementById("change-request-review-note");
  const commentEl = document.getElementById("change-request-review-comment");
  const approveBtn = document.getElementById("change-request-approve-btn");
  const rejectBtn = document.getElementById("change-request-reject-btn");
  const decisionPanel = document.getElementById("change-request-decision-panel");

  const state = {
    request: null,
    busy: false,
  };

  function buildRequesterUrl(deckItemId) {
    return requesterUrlTemplate.replace("__DECK_ITEM_ID__", encodeURIComponent(deckItemId || ""));
  }

  function setButtonContent(button, html) {
    if (button) {
      button.innerHTML = html;
    }
  }

  function clearBanner(bannerEl, tone = "info") {
    if (!bannerEl) return;
    bannerEl.textContent = "";
    bannerEl.classList.add("d-none");
    bannerEl.classList.remove("change-request-banner--info", "change-request-banner--success", "change-request-banner--error");
    bannerEl.classList.add(`change-request-banner--${tone}`);
  }

  function showError(message) {
    if (!errorEl) return;
    errorEl.textContent = message || "Không thể tải request detail.";
    errorEl.classList.remove("d-none");
  }

  function clearError() {
    clearBanner(errorEl, "error");
  }

  function showStatus(message, tone = "info") {
    if (!statusEl) return;
    statusEl.textContent = message || "";
    statusEl.classList.remove("d-none");
    statusEl.classList.remove("change-request-banner--info", "change-request-banner--success", "change-request-banner--error");
    statusEl.classList.add(`change-request-banner--${tone}`);
  }

  function clearStatus() {
    clearBanner(statusEl, "info");
  }

  function setBusy(isBusy) {
    state.busy = Boolean(isBusy);
    render();
  }

  function getReviewNote() {
    const requestData = state.request;
    if (!requestData) {
      return "Đang tải request...";
    }

    if (requestData.can_review) {
      return "Approve sẽ merge overlay changes vào source deck. Reject sẽ giữ thay đổi ở local install và yêu cầu requester làm lại.";
    }

    if (requestData.status === "merged") {
      return "Request đã được merge. Panel này hiện ở chế độ read-only để giữ traceability.";
    }

    if (requestData.status === "rejected") {
      return "Request đã bị reject. Overlay edits của requester vẫn còn ở local install cho đến khi họ tạo request mới.";
    }

    return "Request không còn ở trạng thái review. Bạn chỉ có thể xem lại summary, diff và comment đã lưu.";
  }

  function render() {
    renderRequestSummary(summaryEl, state.request, { emptyText: "Không tìm thấy request." });
    renderChangeItems(itemsEl, state.request?.items || []);
    renderConflicts(conflictsEl, state.request?.conflicts || []);

    const canReview = Boolean(state.request?.can_review);
    const statusMeta = getRequestStatusMeta(state.request?.status);
    const deckTitle = state.request?.deck_item?.title || "Unknown deck";
    const requestTitle = state.request?.title || "Change Request";

    if (titleEl) {
      titleEl.textContent = requestTitle;
    }
    if (metaEl) {
      metaEl.textContent = `${deckTitle} · ${statusMeta.description}`;
    }
    if (reviewNoteEl) {
      reviewNoteEl.textContent = getReviewNote();
    }

    if (backLink) {
      if (canReview) {
        backLink.href = inboxUrl;
        backLink.innerHTML = '<i class="bi bi-arrow-left"></i> Quay lại inbox';
      } else {
        backLink.href = state.request?.deck_item_id ? buildRequesterUrl(state.request.deck_item_id) : inboxUrl;
        backLink.innerHTML = '<i class="bi bi-arrow-left"></i> Quay lại request';
      }
    }

    if (commentEl) {
      if (!commentEl.value || state.request?.review_comment) {
        commentEl.value = state.request?.review_comment || "";
      }
      commentEl.readOnly = !canReview || state.busy;
      commentEl.placeholder = canReview
        ? "Lý do approve hoặc reject."
        : "Request không còn ở trạng thái có thể review.";
    }

    if (decisionPanel) {
      decisionPanel.classList.toggle("change-request-panel--readonly", !canReview);
    }

    setButtonContent(approveBtn, '<i class="bi bi-check2-circle"></i> Approve và merge');
    setButtonContent(rejectBtn, '<i class="bi bi-slash-circle"></i> Reject request');

    if (approveBtn) {
      approveBtn.classList.toggle("d-none", !canReview);
      approveBtn.disabled = state.busy || !canReview;
    }
    if (rejectBtn) {
      rejectBtn.classList.toggle("d-none", !canReview);
      rejectBtn.disabled = state.busy || !canReview;
    }

    document.title = `${requestTitle} | Change Request Detail`;
  }

  async function loadRequest() {
    setBusy(true);
    clearError();
    clearStatus();

    try {
      state.request = await fetchRequestDetail(requestId);
      render();
    } catch (error) {
      showError(error.message);
    } finally {
      setBusy(false);
    }
  }

  async function runReviewAction(action, successMessage) {
    setBusy(true);
    clearError();
    clearStatus();

    try {
      state.request = await action();
      render();
      showStatus(successMessage, "success");
    } catch (error) {
      showError(error.message);
    } finally {
      setBusy(false);
    }
  }

  approveBtn?.addEventListener("click", async () => {
    await runReviewAction(
      () => approveRequest(requestId, {
        review_comment: commentEl?.value || "",
      }),
      "Change request đã được approve và merge.",
    );
  });

  rejectBtn?.addEventListener("click", async () => {
    await runReviewAction(
      () => rejectRequest(requestId, {
        review_comment: commentEl?.value || "",
      }),
      "Change request đã bị reject.",
    );
  });

  loadRequest();
}
