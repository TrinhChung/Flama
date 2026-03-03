export function initDeckTree(rowMap, toggleMap) {
    const rows = Array.from(document.querySelectorAll(".deck-row[data-node-id]"));
    let selectedDeckId = null;

    // ── Study button navigation ──────────────────────────────────────────
    const studyTabBtn = document.getElementById('study-tab-btn');
    const baseStudyUrl = studyTabBtn ? studyTabBtn.dataset.baseStudyUrl : '/vocabulary/study/deck/';
    const statsTabBtn = document.getElementById('stats-tab-btn');
    const baseStatsUrl = statsTabBtn ? statsTabBtn.dataset.baseStatsUrl : '/statistics';
    const importTabBtn = document.getElementById('import-tab-btn');
    const baseImportUrl = importTabBtn ? importTabBtn.dataset.baseImportUrl : '/flashcards/import';
    const browseOpenBtn = document.querySelector('[data-browse-open="1"]');

    rows.forEach((row) => {
        rowMap.set(row.dataset.nodeId, row);
    });

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

    // Init
    updateStudyBtn(null);

    function openRow(row) {
        const url = row?.dataset?.openUrl;
        if (url) {
            window.location.href = url;
        }
    }

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

    rows.forEach((row) => {
        row.addEventListener("click", (event) => {
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

    return { updateStudyBtn, getFirstVisibleDeckId, getSelectedDeckId: () => selectedDeckId };
}
