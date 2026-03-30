import { fetchIncomingRequests } from "./api.js";
import { escapeHtml, formatDate } from "./ui.js";

const root = document.getElementById("deck-change-request-inbox-root");

if (root) {
  const deckItemId = root.getAttribute("data-deck-item-id") || "";
  const requestDetailUrlTemplate = root.getAttribute("data-request-detail-url-template") || "";

  const metaEl = document.getElementById("change-request-inbox-meta");
  const errorEl = document.getElementById("change-request-inbox-error");
  const itemsEl = document.getElementById("change-request-inbox-items");

  function buildDetailUrl(requestId) {
    return requestDetailUrlTemplate.replace("__REQUEST_ID__", encodeURIComponent(requestId || ""));
  }

  function showError(message) {
    errorEl.textContent = message || "Khong the tai inbox.";
    errorEl.classList.remove("d-none");
  }

  function clearError() {
    errorEl.textContent = "";
    errorEl.classList.add("d-none");
  }

  function render(items) {
    const rows = Array.isArray(items) ? items : [];
    metaEl.textContent = rows.length
      ? `${rows.length} request dang cho owner review.`
      : "Khong co request dang cho review.";
    if (!rows.length) {
      itemsEl.innerHTML = "<div class='market-empty-state'>Khong co incoming request.</div>";
      return;
    }
    itemsEl.innerHTML = rows.map((item) => `
      <article class="market-review-item mb-3">
        <div class="d-flex flex-wrap justify-content-between gap-2 align-items-start">
          <div>
            <div class="fw-semibold">${escapeHtml(item.title || "Change Request")}</div>
            <div class="small text-muted mt-1">
              Requester: ${escapeHtml(item.requester?.username || "Unknown")}
              | Deck: ${escapeHtml(item.deck_item?.title || "Unknown deck")}
            </div>
            <div class="small text-muted mt-1">
              Items: ${escapeHtml(String(item.item_count || 0))}
              | Conflicts: ${escapeHtml(String(item.unresolved_conflict_count || 0))}
              | Submitted: ${escapeHtml(formatDate(item.submitted_at))}
            </div>
          </div>
          <a class="btn btn-outline-secondary" href="${escapeHtml(buildDetailUrl(item.id))}">Open</a>
        </div>
      </article>
    `).join("");
  }

  async function loadInbox() {
    clearError();
    try {
      const payload = await fetchIncomingRequests(deckItemId);
      render(payload?.items || []);
    } catch (error) {
      showError(error.message);
    }
  }

  loadInbox();
}
