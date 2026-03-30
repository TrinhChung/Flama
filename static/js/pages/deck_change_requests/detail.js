import {
  approveRequest,
  fetchRequestDetail,
  rejectRequest,
} from "./api.js";
import {
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
  const errorEl = document.getElementById("change-request-detail-error");
  const statusEl = document.getElementById("change-request-detail-status");
  const summaryEl = document.getElementById("change-request-detail-summary");
  const itemsEl = document.getElementById("change-request-detail-items");
  const conflictsEl = document.getElementById("change-request-detail-conflicts");
  const commentEl = document.getElementById("change-request-review-comment");
  const approveBtn = document.getElementById("change-request-approve-btn");
  const rejectBtn = document.getElementById("change-request-reject-btn");
  const decisionPanel = commentEl?.closest(".market-space-panel");

  const state = {
    request: null,
    busy: false,
  };

  function buildRequesterUrl(deckItemId) {
    return requesterUrlTemplate.replace("__DECK_ITEM_ID__", encodeURIComponent(deckItemId || ""));
  }

  function setBusy(isBusy) {
    state.busy = Boolean(isBusy);
    [approveBtn, rejectBtn].forEach((button) => {
      if (button) {
        button.disabled = state.busy;
      }
    });
  }

  function showError(message) {
    errorEl.textContent = message || "Khong the tai request detail.";
    errorEl.classList.remove("d-none");
  }

  function clearError() {
    errorEl.textContent = "";
    errorEl.classList.add("d-none");
  }

  function showStatus(message) {
    statusEl.textContent = message || "";
    statusEl.classList.toggle("d-none", !message);
  }

  function render() {
    renderRequestSummary(summaryEl, state.request, { emptyText: "Khong tim thay request." });
    renderChangeItems(itemsEl, state.request?.items || []);
    renderConflicts(conflictsEl, state.request?.conflicts || []);

    const canReview = Boolean(state.request?.can_review);
    if (backLink) {
      if (canReview) {
        backLink.href = inboxUrl;
        backLink.textContent = "Quay lại inbox";
      } else {
        backLink.href = buildRequesterUrl(state.request?.deck_item_id || "");
        backLink.textContent = "Quay lại request";
      }
    }

    if (commentEl) {
      if (!commentEl.value || state.request?.review_comment) {
        commentEl.value = state.request?.review_comment || "";
      }
      commentEl.readOnly = !canReview;
    }
    if (decisionPanel) {
      decisionPanel.classList.toggle("opacity-75", !canReview);
    }
    if (approveBtn) {
      approveBtn.classList.toggle("d-none", !canReview);
    }
    if (rejectBtn) {
      rejectBtn.classList.toggle("d-none", !canReview);
    }
  }

  async function loadRequest() {
    setBusy(true);
    clearError();
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
    showStatus("");
    try {
      state.request = await action();
      render();
      showStatus(successMessage);
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
      "Change request da duoc approve va merge.",
    );
  });

  rejectBtn?.addEventListener("click", async () => {
    await runReviewAction(
      () => rejectRequest(requestId, {
        review_comment: commentEl?.value || "",
      }),
      "Change request da bi reject.",
    );
  });

  loadRequest();
}
