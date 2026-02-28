  (() => {
    // Cleanup orphaned modal backdrops on page load
    const cleanupOrphanedBackdrops = () => {
      const backdrops = document.querySelectorAll(".modal-backdrop");
      const activeModals = document.querySelectorAll(".modal.show");

      if (activeModals.length === 0 && backdrops.length > 0) {
        backdrops.forEach((backdrop) => {
          backdrop.remove();
        });
        document.body.classList.remove("modal-open");
        document.body.style.overflow = "";
      }
    };

    // Cleanup on page load
    cleanupOrphanedBackdrops();

    // Also cleanup after a short delay to catch delayed backdrops
    setTimeout(cleanupOrphanedBackdrops, 500);
    const rows = Array.from(document.querySelectorAll(".deck-row[data-node-id]"));
    const rowMap = new Map();
    const toggleMap = new Map();
    let selectedDeckId = null;
    const browseOpenBtn = document.querySelector('[data-browse-open="1"]');
    const statsRoot = document.getElementById("stats-board");
    const statsSummaryEl = document.getElementById("stats-summary");
    const statsYearLabelEl = document.getElementById("stats-year-label");
    const statsHeatmapEl = document.getElementById("stats-heatmap");
    const statsTooltipEl = document.getElementById("stats-tooltip");
    const statsPrevYearBtn = document.getElementById("stats-prev-year");
    const statsNextYearBtn = document.getElementById("stats-next-year");
    const statsDailyAverageEl = document.getElementById("stats-daily-average");
    const statsDaysLearnedEl = document.getElementById("stats-days-learned");
    const statsLongestStreakEl = document.getElementById("stats-longest-streak");
    const statsCurrentStreakEl = document.getElementById("stats-current-streak");

    rows.forEach((row) => {
      rowMap.set(row.dataset.nodeId, row);
    });

    document.querySelectorAll(".tree-toggle[data-node-id]").forEach((toggle) => {
      toggleMap.set(toggle.dataset.nodeId, toggle);
      toggle.addEventListener("click", (event) => {
        event.preventDefault();
        event.stopPropagation();
        const expanded = toggle.dataset.expanded === "true";
        toggle.dataset.expanded = expanded ? "false" : "true";
        toggle.textContent = expanded ? "+" : "-";
        refreshVisibility();
      });
    });

    // ── Study button navigation ──────────────────────────────────────────
    const studyTabBtn = document.getElementById('study-tab-btn');
    const baseStudyUrl = studyTabBtn ? studyTabBtn.dataset.baseStudyUrl : '/vocabulary/study/deck/';
    const statsTabBtn = document.getElementById('stats-tab-btn');
    const baseStatsUrl = statsTabBtn ? statsTabBtn.dataset.baseStatsUrl : '/statistics';
    const importTabBtn = document.getElementById('import-tab-btn');
    const baseImportUrl = importTabBtn ? importTabBtn.dataset.baseImportUrl : '/flashcards/import';

    function getFirstVisibleDeckId() {
      const firstRow = rows.find(r => !r.classList.contains('is-collapsed'));
      return firstRow ? firstRow.dataset.nodeId : null;
    }

    function updateStudyBtn(deckId) {
      const id = deckId || getFirstVisibleDeckId();
      if (studyTabBtn) {
        if (id) {
          studyTabBtn.href = baseStudyUrl + id;
        } else {
          studyTabBtn.href = studyTabBtn.dataset.baseStudyUrl || '#';
        }
      }
      if (statsTabBtn) {
        if (id) {
          statsTabBtn.href = `${baseStatsUrl}?scope=deck&deck_id=${encodeURIComponent(id)}`;
        } else {
          statsTabBtn.href = baseStatsUrl;
        }
      }

      if (importTabBtn) {
        if (id) {
          importTabBtn.href = `${baseImportUrl}?deck_id=${encodeURIComponent(id)}`;
        } else {
          importTabBtn.href = baseImportUrl;
        }
      }

      if (browseOpenBtn) {
        browseOpenBtn.dataset.currentDeckId = deckId || "";
      }
    }

    // Init: point Study to the first deck on load
    updateStudyBtn(null);

    function selectRow(row) {
      if (!row) {
        return;
      }
      rows.forEach((item) => item.classList.toggle("is-selected", item === row));
      selectedDeckId = row.dataset.nodeId || null;
      updateStudyBtn(selectedDeckId);
    }

    function clearSelection() {
      rows.forEach((item) => item.classList.remove("is-selected"));
      selectedDeckId = null;
      updateStudyBtn(null);
    }

    function openRow(row) {
      const url = row?.dataset?.openUrl;
      if (url) {
        window.location.href = url;
      }
    }

    // UI logic for Deck Actions
    const renameModalEl = document.getElementById('renameDeckModal');
    const moveModalEl = document.getElementById('moveDeckModal');
    const renameFormEl = document.getElementById('deck-rename-form');
    const renameInputEl = document.getElementById('deck-rename-input');
    const moveFormEl = document.getElementById('deck-move-form');
    const moveSelectEl = document.getElementById('deck-move-select');
    const moveDeckTokenInputEl = document.getElementById('deck-move-token-input');
    const moveParentTokenInputEl = document.getElementById('deck-parent-token-input');
    const moveParentIdInputEl = document.getElementById('deck-move-parent-id-input');
    const moveDeckNameLabelEl = document.getElementById('move-deck-name-label');
    const moveDeckIdLabelEl = document.getElementById('move-deck-id-label');
    const resetFormEl = document.getElementById('deck-reset-form');
    const deleteFormEl = document.getElementById('deck-delete-form');
    let renameModal = null;
    let moveModal = null;
    const moveAliasToToken = new Map();
    const moveAliasToDeckId = new Map();

    if (renameModalEl && window.bootstrap) renameModal = new bootstrap.Modal(renameModalEl);
    if (moveModalEl && window.bootstrap) moveModal = new bootstrap.Modal(moveModalEl);

    rows.forEach((row) => {
      const alias = (row.dataset.moveAlias || "").trim();
      const token = (row.dataset.moveToken || "").trim();
      const deckId = String(row.dataset.nodeId || "");
      if (alias && token) {
        moveAliasToToken.set(alias, token);
      }
      if (alias && deckId) {
        moveAliasToDeckId.set(alias, deckId);
      }
    });

    function getDescendantDeckIds(rootDeckId) {
      const descendants = new Set();
      if (!rootDeckId) {
        return descendants;
      }
      const queue = [String(rootDeckId)];
      while (queue.length > 0) {
        const currentId = queue.shift();
        rows.forEach((row) => {
          if ((row.dataset.parentId || "") !== currentId) {
            return;
          }
          const childId = row.dataset.nodeId || "";
          if (!childId || descendants.has(childId)) {
            return;
          }
          descendants.add(childId);
          queue.push(childId);
        });
      }
      return descendants;
    }

    function optionExistsByValue(selectEl, value) {
      if (!selectEl) {
        return false;
      }
      return Array.from(selectEl.options).some((opt) => String(opt.value || "") === String(value || ""));
    }

    async function copyText(text) {
      if (!text) {
        return;
      }
      if (navigator.clipboard && navigator.clipboard.writeText) {
        await navigator.clipboard.writeText(text);
      } else {
        const tempInput = document.createElement("input");
        tempInput.type = "text";
        tempInput.value = text;
        document.body.appendChild(tempInput);
        tempInput.select();
        document.execCommand("copy");
        tempInput.remove();
      }
    }

    document.querySelectorAll('.deck-action-btn').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.preventDefault();
        e.stopImmediatePropagation();

        const action = btn.getAttribute('data-action');
        const deckId = btn.getAttribute('data-deck-id');
        const deckName = btn.getAttribute('data-deck-name');
        const parentId = btn.getAttribute('data-parent-id');
        const moveAlias = (btn.getAttribute('data-move-alias') || "").trim();
        const moveToken = (btn.getAttribute('data-move-token') || "").trim();
        const parentMoveAlias = (btn.getAttribute('data-parent-move-alias') || "").trim();
        const parentMoveToken = (btn.getAttribute('data-parent-move-token') || "").trim();
        const normalizedDeckName = (deckName || "").trim() || "Deck";
        const deckIdText = String(deckId || "");

        if (action === 'rename') {
          if (!renameFormEl || !renameInputEl || !deckIdText) {
            window.alert("Bạn không có quyền đổi tên deck này.");
            return;
          }
          renameFormEl.action = `/vocabulary/decks/${deckIdText}/rename`;
          renameInputEl.value = normalizedDeckName;
          if (renameModal) {
            renameModal.show();
            return;
          }
          const promptedName = window.prompt("Nhập tên deck mới", normalizedDeckName);
          if (promptedName === null) {
            return;
          }
          const nextName = promptedName.trim();
          if (!nextName) {
            window.alert("Tên deck không được để trống.");
            return;
          }
          renameInputEl.value = nextName;
          renameFormEl.submit();
        }
        else if (action === 'move') {
          if (
            !moveFormEl ||
            !moveSelectEl ||
            !moveParentIdInputEl ||
            !moveDeckTokenInputEl ||
            !moveParentTokenInputEl ||
            !deckIdText ||
            !moveToken ||
            !moveAlias
          ) {
            window.alert("Bạn không có quyền di chuyển deck này.");
            return;
          }
          const descendantDeckIds = getDescendantDeckIds(deckIdText);
          moveFormEl.dataset.activeDeckId = deckIdText;
          moveFormEl.dataset.activeMoveAlias = moveAlias;
          moveFormEl.action = "/vocabulary/decks/move";
          moveDeckTokenInputEl.value = moveToken;
          moveParentTokenInputEl.value = parentMoveToken || "";
          Array.from(moveSelectEl.options).forEach((opt) => {
            const optionAlias = String(opt.value || "");
            const optionDeckId = moveAliasToDeckId.get(optionAlias) || "";
            opt.disabled = optionAlias === moveAlias || descendantDeckIds.has(optionDeckId);
          });
          moveSelectEl.value = parentMoveAlias || "";
          moveParentIdInputEl.value = parentMoveAlias || "";
          if (moveDeckNameLabelEl) {
            moveDeckNameLabelEl.textContent = normalizedDeckName;
          }
          if (moveDeckIdLabelEl) {
            moveDeckIdLabelEl.textContent = moveAlias;
          }
          if (moveModal) {
            moveModal.show();
            return;
          }
          const fallbackParentAlias = window.prompt(
            "Nhập Move ID tạm của deck cha (để trống = Root)",
            parentMoveAlias || "",
          );
          if (fallbackParentAlias === null) {
            return;
          }
          const nextParentAlias = fallbackParentAlias.trim();
          const nextParentDeckId = moveAliasToDeckId.get(nextParentAlias) || "";
          if (nextParentAlias && !moveAliasToToken.has(nextParentAlias)) {
            window.alert("Parent Move ID không hợp lệ.");
            return;
          }
          if (nextParentAlias && (nextParentAlias === moveAlias || descendantDeckIds.has(nextParentDeckId))) {
            window.alert("Không thể di chuyển deck cha vào deck con.");
            return;
          }
          moveSelectEl.value = nextParentAlias;
          moveParentTokenInputEl.value = nextParentAlias ? (moveAliasToToken.get(nextParentAlias) || "") : "";
          moveFormEl.submit();
        }
        else if (action === 'copy-id') {
          if (!moveAlias) {
            window.alert("Không tìm thấy Move ID.");
            return;
          }
          copyText(moveAlias)
            .then(() => {
              window.alert(`Đã copy Move ID: ${moveAlias}`);
            })
            .catch(() => {
              window.prompt("Copy Move ID", moveAlias);
            });
        }
        else if (action === 'reset') {
          if (!resetFormEl || !deckIdText) {
            window.alert("Bạn không có quyền reset deck này.");
            return;
          }
          if (confirm(`Reset tiến độ học của '${normalizedDeckName}'? (chỉ áp dụng cho tài khoản của bạn)`)) {
            resetFormEl.action = `/vocabulary/decks/${deckIdText}/reset`;
            resetFormEl.submit();
          }
        }
        else if (action === 'delete') {
          if (!deleteFormEl || !deckIdText) {
            window.alert("Bạn không có quyền xóa deck này.");
            return;
          }
          if (confirm(`Xóa vĩnh viễn deck '${normalizedDeckName}' và toàn bộ deck con/nội dung?`)) {
            deleteFormEl.action = `/vocabulary/decks/${deckIdText}/delete`;
            deleteFormEl.submit();
          }
        }
      });
    });

    if (moveSelectEl && moveParentIdInputEl) {
      moveSelectEl.addEventListener("change", () => {
        moveParentIdInputEl.value = moveSelectEl.value || "";
      });

      moveParentIdInputEl.addEventListener("input", () => {
        const inputAlias = (moveParentIdInputEl.value || "").trim();
        if (!inputAlias) {
          moveSelectEl.value = "";
          return;
        }
        if (optionExistsByValue(moveSelectEl, inputAlias)) {
          moveSelectEl.value = inputAlias;
        }
      });
    }

    if (moveFormEl && moveSelectEl && moveParentIdInputEl && moveParentTokenInputEl && moveDeckTokenInputEl) {
      moveFormEl.addEventListener("submit", (event) => {
        const activeDeckId = String(moveFormEl.dataset.activeDeckId || "");
        const activeMoveAlias = String(moveFormEl.dataset.activeMoveAlias || "");
        const typedParentAlias = (moveParentIdInputEl.value || "").trim();
        const selectedParentAlias = String(moveSelectEl.value || "");
        const normalizedParentAlias = typedParentAlias || selectedParentAlias;

        if (!moveDeckTokenInputEl.value) {
          event.preventDefault();
          window.alert("Move token bị thiếu hoặc đã hết hạn. Vui lòng mở lại menu Deck Settings.");
          return;
        }

        if (normalizedParentAlias === activeMoveAlias) {
          event.preventDefault();
          window.alert("Không thể di chuyển deck vào chính nó.");
          return;
        }

        if (activeDeckId) {
          const descendantDeckIds = getDescendantDeckIds(activeDeckId);
          const parentDeckId = moveAliasToDeckId.get(normalizedParentAlias) || "";
          if (normalizedParentAlias && descendantDeckIds.has(parentDeckId)) {
            event.preventDefault();
            window.alert("Không thể di chuyển deck cha vào deck con.");
            return;
          }
        }

        if (normalizedParentAlias && !optionExistsByValue(moveSelectEl, normalizedParentAlias)) {
          event.preventDefault();
          window.alert("Parent Move ID không tồn tại trong cây deck hiện tại.");
          moveParentIdInputEl.focus();
          return;
        }

        const parentMoveToken = normalizedParentAlias ? (moveAliasToToken.get(normalizedParentAlias) || "") : "";
        if (normalizedParentAlias && !parentMoveToken) {
          event.preventDefault();
          window.alert("Parent Move ID không hợp lệ hoặc đã hết hạn.");
          return;
        }

        moveSelectEl.value = normalizedParentAlias;
        moveParentTokenInputEl.value = parentMoveToken;
      });
    }

    rows.forEach((row) => {
      row.addEventListener("click", (event) => {
        // Ngăn chặn các script khác chèn ngang event click chuyển trang ngay lần đầu tiên
        event.stopImmediatePropagation();

        if (event.target.closest(".tree-toggle") || event.target.closest(".deck-settings-wrapper")) {
          return;
        }
        if (row.classList.contains("is-selected")) {
          openRow(row);
          return;
        }
        selectRow(row);
      });
      row.addEventListener("dblclick", (event) => {
        if (event.target.closest(".tree-toggle")) {
          return;
        }
        openRow(row);
      });
    });

    document.addEventListener("click", (event) => {
      if (
        event.target.closest(".deck-row") ||
        event.target.closest(".anki-top-tabs") ||
        event.target.closest(".dash-toolbar") ||
        event.target.closest("#browseModal") ||
        event.target.closest("#browseUnsavedModal")
      ) {
        return;
      }
      clearSelection();
    });

    const createDeckBtn = document.getElementById("create-deck-btn");
    const createDeckForm = document.getElementById("create-deck-form");
    const createDeckParentInput = document.getElementById("create-deck-parent-id");
    const createDeckNameInput = document.getElementById("create-deck-name");
    const createDeckPathInput = document.getElementById("create-deck-path");
    const deckPathInput = document.getElementById("deck-path-input");
    const confirmCreateDeckBtn = document.getElementById("confirm-create-deck-btn");
    const createDeckModalEl = document.getElementById("createDeckModal");

    function buildDeckPathFromSelected() {
      if (!selectedDeckId) {
        return "New Deck";
      }
      const parts = [];
      let currentId = selectedDeckId;
      while (currentId) {
        const row = rowMap.get(currentId);
        if (!row) {
          break;
        }
        const part = (row.dataset.nodeName || "").trim();
        if (part) {
          parts.push(part);
        }
        currentId = row.dataset.parentId || "";
      }
      parts.reverse();
      parts.push("New Deck");
      return parts.join("::");
    }

    if (
      createDeckBtn &&
      createDeckForm &&
      createDeckParentInput &&
      createDeckNameInput &&
      createDeckPathInput &&
      deckPathInput &&
      confirmCreateDeckBtn
    ) {
      createDeckBtn.addEventListener("click", () => {
        const defaultPath = buildDeckPathFromSelected();
        deckPathInput.value = defaultPath;

        if (
          createDeckModalEl &&
          typeof window !== "undefined" &&
          window.bootstrap &&
          window.bootstrap.Modal
        ) {
          const modalInstance = window.bootstrap.Modal.getOrCreateInstance(createDeckModalEl);
          // Reset form when opening
          resetDeckForm();
          deckPathInput.value = defaultPath;
          modalInstance.show();
          return;
        }

        // Fallback when Bootstrap modal JS is unavailable.
        const fallbackPath = window.prompt("New deck name", defaultPath);
        if (fallbackPath === null) {
          return;
        }
        const deckPath = fallbackPath.trim() || "New Deck";
        const leafName = deckPath.split("::").map((item) => item.trim()).filter(Boolean).pop() || "New Deck";
        createDeckParentInput.value = selectedDeckId || "";
        createDeckNameInput.value = leafName;
        createDeckPathInput.value = deckPath;
        createDeckForm.submit();
      });

      confirmCreateDeckBtn.addEventListener("click", () => {
        const deckPath = deckPathInput.value.trim() || "New Deck";

        // Validate input - prevent empty deck path
        if (!deckPath || deckPath === "") {
          alert("Tên deck không được để trống!");
          deckPathInput.focus();
          return;
        }

        const leafName = deckPath.split("::").map((item) => item.trim()).filter(Boolean).pop() || "New Deck";
        createDeckParentInput.value = selectedDeckId || "";
        createDeckNameInput.value = leafName;
        createDeckPathInput.value = deckPath;

        // Get modal instance
        const modalInstance = createDeckModalEl && window.bootstrap && window.bootstrap.Modal
          ? window.bootstrap.Modal.getOrCreateInstance(createDeckModalEl)
          : null;

        // Hide modal before submit
        if (modalInstance) {
          modalInstance.hide();
        }

        // Submit form
        try {
          createDeckForm.submit();
        } catch (error) {
          console.error("Error submitting deck form:", error);
          // Ensure backdrop is removed on error
          if (modalInstance) {
            removeModalBackdrop();
          }
        }
      });

      // Handle modal hidden event to ensure cleanup
      if (createDeckModalEl) {
        createDeckModalEl.addEventListener("hidden.bs.modal", () => {
          removeModalBackdrop();
          resetDeckForm();
        });
      }

      // Function to remove all modal backdrops
      function removeModalBackdrop() {
        const backdrops = document.querySelectorAll(".modal-backdrop");
        backdrops.forEach((backdrop) => {
          backdrop.remove();
        });
        // Also remove modal-open class from body to restore scrolling
        document.body.classList.remove("modal-open");
        document.body.style.overflow = "";
      }

      // Function to reset form
      function resetDeckForm() {
        deckPathInput.value = "New Deck";
        createDeckParentInput.value = "";
        createDeckNameInput.value = "";
        createDeckPathInput.value = "";
      }
    }

    function isVisibleByAncestors(row) {
      let parentId = row.dataset.parentId;
      while (parentId) {
        const parentToggle = toggleMap.get(parentId);
        if (parentToggle && parentToggle.dataset.expanded !== "true") {
          return false;
        }
        const parentRow = rowMap.get(parentId);
        parentId = parentRow ? parentRow.dataset.parentId : "";
      }
      return true;
    }

    function refreshVisibility() {
      rows.forEach((row) => {
        const isRoot = !row.dataset.parentId;
        if (isRoot) {
          row.classList.remove("is-collapsed");
          return;
        }
        row.classList.toggle("is-collapsed", !isVisibleByAncestors(row));
      });
    }

    function parseIsoDate(isoDate) {
      const parts = String(isoDate || "").split("-");
      if (parts.length !== 3) {
        return null;
      }
      const year = Number(parts[0]);
      const month = Number(parts[1]);
      const day = Number(parts[2]);
      if (!Number.isInteger(year) || !Number.isInteger(month) || !Number.isInteger(day)) {
        return null;
      }
      return new Date(Date.UTC(year, month - 1, day));
    }

    function weekdayIndexMonday(dateObj) {
      return (dateObj.getUTCDay() + 6) % 7;
    }

    function buildHeatmapWeeks(days) {
      const weeks = [];
      let week = new Array(7).fill(null);
      days.forEach((item, index) => {
        const parsedDate = parseIsoDate((item && (item.day || item.date)) || "");
        if (!parsedDate) {
          return;
        }
        const weekday = weekdayIndexMonday(parsedDate);
        week[weekday] = item;
        const isLast = index === days.length - 1;
        if (weekday === 6 || isLast) {
          weeks.push(week);
          week = new Array(7).fill(null);
        }
      });
      return weeks;
    }

    function toFixedNumber(rawValue, digits = 2) {
      const value = Number(rawValue || 0);
      if (!Number.isFinite(value)) {
        return (0).toFixed(digits);
      }
      return value.toFixed(digits);
    }

    function toInt(rawValue) {
      const value = Number(rawValue || 0);
      if (!Number.isFinite(value)) {
        return 0;
      }
      return Math.round(value);
    }

    function heatLevel(cards, maxCards) {
      if (!cards || cards <= 0) {
        return 0;
      }
      if (!maxCards || maxCards <= 0) {
        return 1;
      }
      return Math.min(5, Math.max(1, Math.ceil((cards / maxCards) * 5)));
    }

    function updateStatsTooltip(item) {
      if (!statsTooltipEl || !item) {
        return;
      }
      const day = String(item.day || item.date || "");
      const cards = toInt(item.cards);
      const source = String(item.source || "reviewed").toLowerCase();
      if (source === "due") {
        statsTooltipEl.textContent = `${day} · Due: ${cards}`;
        return;
      }
      const studyTime = toInt(item.study_time);
      const minutes = studyTime > 0 ? toFixedNumber(studyTime / 60000, 2) : toFixedNumber(item.minutes, 2);
      const secPerCard = cards > 0 ? toFixedNumber((studyTime / 1000) / cards, 2) : "0.00";
      statsTooltipEl.textContent = `${day} · Reviewed: ${cards} · ${minutes} minutes · ${secPerCard}s/card`;
    }

    function renderStats(payload) {
      if (!payload || typeof payload !== "object") {
        return;
      }

      const today = payload.today || {};
      const metrics = payload.metrics || {};
      const heatmap = Array.isArray(payload.heatmap) ? payload.heatmap : [];

      if (statsYearLabelEl) {
        statsYearLabelEl.textContent = String(payload.year || "");
      }
      if (statsSummaryEl) {
        const cards = toInt(today.cards);
        const minutes = toFixedNumber(today.minutes, 2);
        const secPerCard = toFixedNumber(today.sec_per_card, 2);
        statsSummaryEl.textContent = `Studied ${cards} cards in ${minutes} minutes today (${secPerCard}s/card)`;
      }
      if (statsDailyAverageEl) {
        statsDailyAverageEl.textContent = `${toInt(metrics.daily_average_cards)} cards`;
      }
      if (statsDaysLearnedEl) {
        statsDaysLearnedEl.textContent = `${toInt(metrics.days_learned_percent)}%`;
      }
      if (statsLongestStreakEl) {
        statsLongestStreakEl.textContent = `${toInt(metrics.longest_streak_days)} days`;
      }
      if (statsCurrentStreakEl) {
        statsCurrentStreakEl.textContent = `${toInt(metrics.current_streak_days)} days`;
      }

      if (!statsHeatmapEl) {
        return;
      }
      statsHeatmapEl.innerHTML = "";
      statsHeatmapEl.style.setProperty("--stats-week-count", "1");
      if (heatmap.length === 0) {
        if (statsTooltipEl) {
          statsTooltipEl.textContent = "No data yet.";
        }
        return;
      }

      const maxCards = heatmap.reduce((max, item) => Math.max(max, toInt(item && item.cards)), 0);
      const weeks = buildHeatmapWeeks(heatmap);
      statsHeatmapEl.style.setProperty("--stats-week-count", String(Math.max(1, weeks.length)));
      weeks.forEach((week) => {
        const weekEl = document.createElement("div");
        weekEl.className = "stats-week";
        week.forEach((item) => {
          if (!item) {
            const spacer = document.createElement("span");
            spacer.className = "stats-day stats-day--empty";
            spacer.setAttribute("aria-hidden", "true");
            weekEl.appendChild(spacer);
            return;
          }

          const cards = toInt(item.cards);
          const level = heatLevel(cards, maxCards);
          const day = String(item.day || item.date || "");
          const sourceLabel = String(item.source || "reviewed").toLowerCase() === "due" ? "Due" : "Reviewed";
          const cell = document.createElement("button");
          cell.type = "button";
          cell.className = `stats-day stats-day--level-${level}${item.is_future ? " stats-day--future" : ""}`;
          cell.setAttribute("aria-label", `${day} ${sourceLabel.toLowerCase()} ${cards} cards`);
          cell.title = `${day} · ${sourceLabel}: ${cards} cards`;
          const showTooltip = () => updateStatsTooltip(item);
          cell.addEventListener("mouseenter", showTooltip);
          cell.addEventListener("focus", showTooltip);
          cell.addEventListener("click", showTooltip);
          weekEl.appendChild(cell);
        });
        statsHeatmapEl.appendChild(weekEl);
      });

      if (statsTooltipEl) {
        const firstDay = heatmap.find((item) => toInt(item.cards) > 0) || heatmap[0];
        updateStatsTooltip(firstDay);
      }
    }

    function setStatsLoading(isLoading) {
      if (statsPrevYearBtn) {
        statsPrevYearBtn.disabled = Boolean(isLoading);
      }
      if (statsNextYearBtn) {
        statsNextYearBtn.disabled = Boolean(isLoading);
      }
    }

    let statsYear = Number(statsRoot?.dataset.initialYear || 0);
    if (!Number.isFinite(statsYear) || statsYear <= 0) {
      statsYear = new Date().getFullYear();
    }
    let statsRequestId = 0;

    async function loadStats(year) {
      if (!statsRoot) {
        return;
      }
      statsYear = toInt(year);
      const requestId = ++statsRequestId;
      setStatsLoading(true);
      if (statsYearLabelEl) {
        statsYearLabelEl.textContent = String(statsYear);
      }
      try {
        const response = await fetch(`/api/stats/overview?year=${encodeURIComponent(statsYear)}`);
        const data = await response.json().catch(() => null);
        if (requestId !== statsRequestId) {
          return;
        }
        if (!response.ok || !data) {
          const message = data?.message || "Unable to load statistics.";
          throw new Error(message);
        }
        statsYear = toInt(data.year || statsYear);
        renderStats(data);
      } catch (error) {
        if (requestId !== statsRequestId) {
          return;
        }
        if (statsTooltipEl) {
          statsTooltipEl.textContent = error?.message || "Unable to load statistics.";
        }
      } finally {
        if (requestId === statsRequestId) {
          setStatsLoading(false);
        }
      }
    }

    statsPrevYearBtn?.addEventListener("click", () => {
      loadStats(statsYear - 1);
    });
    statsNextYearBtn?.addEventListener("click", () => {
      loadStats(statsYear + 1);
    });
    if (statsRoot) {
      loadStats(statsYear);
    }

    refreshVisibility();
  })();
