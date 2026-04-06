import { fetchIncomingRequests } from "./api.js";
import { escapeHtml, formatDate, renderStatusBadge } from "./ui.js";

const root = document.getElementById("deck-change-request-inbox-root");

if (root) {
  const deckItemId = root.getAttribute("data-deck-item-id") || "";
  const requestDetailUrlTemplate = root.getAttribute("data-request-detail-url-template") || "";

  const metaEl = document.getElementById("change-request-inbox-meta");
  const errorEl = document.getElementById("change-request-inbox-error");
  const itemsEl = document.getElementById("change-request-inbox-items");
  const filterTagsEl = document.getElementById("change-request-inbox-filter-tags");
  const searchEl = document.getElementById("change-request-inbox-search");

  const state = {
    rows: [],
    filter: "all",
    search: "",
  };

  function buildDetailUrl(requestId) {
    return requestDetailUrlTemplate.replace("__REQUEST_ID__", encodeURIComponent(requestId || ""));
  }

  function renderChip(label, tone, icon) {
    return `
      <span class="change-request-chip" data-tone="${escapeHtml(tone)}">
        ${icon ? `<i class="bi ${escapeHtml(icon)}"></i>` : ""}
        ${escapeHtml(label)}
      </span>
    `;
  }

  function showError(message) {
    if (!errorEl) return;
    errorEl.textContent = message || "Không thể tải inbox.";
    errorEl.classList.remove("d-none");
  }

  function clearError() {
    if (!errorEl) return;
    errorEl.textContent = "";
    errorEl.classList.add("d-none");
  }

  function matchesFilter(item) {
    if (state.filter === "conflict") {
      return Number(item.unresolved_conflict_count || 0) > 0;
    }
    if (state.filter === "clean") {
      return Number(item.unresolved_conflict_count || 0) === 0;
    }
    return true;
  }

  function matchesSearch(item) {
    const query = state.search.trim().toLowerCase();
    if (!query) {
      return true;
    }

    const haystack = [
      item.title,
      item.requester?.username,
      item.deck_item?.title,
    ]
      .filter(Boolean)
      .join(" ")
      .toLowerCase();

    return haystack.includes(query);
  }

  function getFilteredRows() {
    return state.rows.filter((item) => matchesFilter(item) && matchesSearch(item));
  }

  function updateMeta(rows) {
    if (!metaEl) return;

    const total = state.rows.length;
    const visible = rows.length;
    const totalConflicts = rows.reduce(
      (sum, item) => sum + Number(item.unresolved_conflict_count || 0),
      0,
    );

    if (!total) {
      metaEl.textContent = deckItemId
        ? "Không có request nào đang chờ review cho deck này."
        : "Không có request nào đang chờ owner review.";
      return;
    }

    const filterLabel = state.filter === "conflict"
      ? "đang lọc request có conflict"
      : state.filter === "clean"
        ? "đang lọc request không conflict"
        : "đang hiển thị toàn bộ request";

    metaEl.textContent = `${visible}/${total} request, ${totalConflicts} conflict mở, ${filterLabel}.`;
  }

  function render(rows) {
    updateMeta(rows);

    if (!rows.length) {
      itemsEl.innerHTML = `
        <div class="change-request-empty">
          <div class="change-request-status-list mb-2">
            <span class="change-request-status-badge" data-tone="neutral">
              <i class="bi bi-inbox"></i> Không có kết quả
            </span>
          </div>
          <div>Không có request nào khớp với bộ lọc hiện tại.</div>
        </div>
      `;
      return;
    }

    itemsEl.innerHTML = rows.map((item) => `
      <article class="change-request-inbox-card">
        <div class="change-request-inbox-top">
          <div>
            <h3 class="change-request-inbox-title">${escapeHtml(item.title || "Change Request")}</h3>
            <p class="change-request-item-meta">
              Requester ${escapeHtml(item.requester?.username || "Unknown")}
              · Deck ${escapeHtml(item.deck_item?.title || "Unknown deck")}
              · Submitted ${escapeHtml(formatDate(item.submitted_at))}
            </p>
          </div>
          <div class="change-request-inbox-actions">
            <a class="btn btn-outline-secondary" href="${escapeHtml(buildDetailUrl(item.id))}">
              <i class="bi bi-eye"></i> Review
            </a>
          </div>
        </div>

        <div class="change-request-chip-list">
          ${renderStatusBadge(item.status)}
          ${renderChip(`${item.item_count || 0} changes`, "info", "bi-diagram-3")}
          ${renderChip(
            `${item.unresolved_conflict_count || 0} conflicts`,
            item.unresolved_conflict_count ? "danger" : "success",
            item.unresolved_conflict_count ? "bi-exclamation-diamond" : "bi-check2-all",
          )}
          ${renderChip(`Updated ${formatDate(item.updated_at)}`, "neutral", "bi-clock-history")}
        </div>
      </article>
    `).join("");
  }

  function updateFilterButtons() {
    if (!filterTagsEl) return;
    filterTagsEl.querySelectorAll("[data-filter]").forEach((button) => {
      if (!(button instanceof HTMLElement)) {
        return;
      }
      button.classList.toggle("is-active", button.getAttribute("data-filter") === state.filter);
    });
  }

  function renderCurrentState() {
    updateFilterButtons();
    render(getFilteredRows());
  }

  async function loadInbox() {
    clearError();
    try {
      const payload = await fetchIncomingRequests(deckItemId);
      state.rows = Array.isArray(payload?.items) ? payload.items : [];
      renderCurrentState();
    } catch (error) {
      showError(error.message);
    }
  }

  filterTagsEl?.addEventListener("click", (event) => {
    const target = event.target;
    if (!(target instanceof HTMLElement)) {
      return;
    }
    const button = target.closest("[data-filter]");
    if (!(button instanceof HTMLElement)) {
      return;
    }
    state.filter = button.getAttribute("data-filter") || "all";
    renderCurrentState();
  });

  searchEl?.addEventListener("input", (event) => {
    const target = event.target;
    state.search = target instanceof HTMLInputElement ? target.value : "";
    renderCurrentState();
  });

  loadInbox();
}
