export function initDeckModals(rowMap) {
    const rows = Array.from(document.querySelectorAll(".deck-row[data-node-id]"));

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
                if (promptedName === null) return;

                const nextName = promptedName.trim();
                if (!nextName) {
                    window.alert("Tên deck không được để trống.");
                    return;
                }
                renameInputEl.value = nextName;
                renameFormEl.submit();
            }
            else if (action === 'move') {
                if (!moveFormEl || !moveSelectEl || !moveParentIdInputEl || !moveDeckTokenInputEl || !moveParentTokenInputEl || !deckIdText || !moveToken || !moveAlias) {
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

                if (moveDeckNameLabelEl) moveDeckNameLabelEl.textContent = normalizedDeckName;
                if (moveDeckIdLabelEl) moveDeckIdLabelEl.textContent = moveAlias;

                if (moveModal) {
                    moveModal.show();
                    return;
                }

                const fallbackParentAlias = window.prompt("Nhập Move ID tạm của deck cha (để trống = Root)", parentMoveAlias || "");
                if (fallbackParentAlias === null) return;

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
                    .then(() => window.alert(`Đã copy Move ID: ${moveAlias}`))
                    .catch(() => window.prompt("Copy Move ID", moveAlias));
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

    const createDeckBtn = document.getElementById("create-deck-btn");
    const createDeckForm = document.getElementById("create-deck-form");
    const createDeckParentInput = document.getElementById("create-deck-parent-id");
    const createDeckNameInput = document.getElementById("create-deck-name");
    const createDeckPathInput = document.getElementById("create-deck-path");
    const deckPathInput = document.getElementById("deck-path-input");
    const confirmCreateDeckBtn = document.getElementById("confirm-create-deck-btn");
    const createDeckModalEl = document.getElementById("createDeckModal");

    function buildDeckPathFromSelected() {
        // This value needs to somehow access the selected node state from tree.js, we assume it's exposed or window level if not injected
        const selectedDeckId = document.querySelector(".deck-row.is-selected")?.dataset?.nodeId;
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

    if (createDeckBtn && createDeckForm && createDeckParentInput && createDeckNameInput && createDeckPathInput && deckPathInput && confirmCreateDeckBtn) {
        createDeckBtn.addEventListener("click", () => {
            const defaultPath = buildDeckPathFromSelected();
            deckPathInput.value = defaultPath;

            if (createDeckModalEl && typeof window !== "undefined" && window.bootstrap && window.bootstrap.Modal) {
                const modalInstance = window.bootstrap.Modal.getOrCreateInstance(createDeckModalEl);
                resetDeckForm();
                deckPathInput.value = defaultPath;
                modalInstance.show();
                return;
            }

            const fallbackPath = window.prompt("New deck name", defaultPath);
            if (fallbackPath === null) return;

            const deckPath = fallbackPath.trim() || "New Deck";
            const leafName = deckPath.split("::").map((item) => item.trim()).filter(Boolean).pop() || "New Deck";
            const selectedDeckId = document.querySelector(".deck-row.is-selected")?.dataset?.nodeId;
            createDeckParentInput.value = selectedDeckId || "";
            createDeckNameInput.value = leafName;
            createDeckPathInput.value = deckPath;
            createDeckForm.submit();
        });

        confirmCreateDeckBtn.addEventListener("click", () => {
            const deckPath = deckPathInput.value.trim() || "New Deck";

            if (!deckPath || deckPath === "") {
                alert("Tên deck không được để trống!");
                deckPathInput.focus();
                return;
            }

            const leafName = deckPath.split("::").map((item) => item.trim()).filter(Boolean).pop() || "New Deck";
            const selectedDeckId = document.querySelector(".deck-row.is-selected")?.dataset?.nodeId;
            createDeckParentInput.value = selectedDeckId || "";
            createDeckNameInput.value = leafName;
            createDeckPathInput.value = deckPath;

            const modalInstance = createDeckModalEl && window.bootstrap && window.bootstrap.Modal ? window.bootstrap.Modal.getOrCreateInstance(createDeckModalEl) : null;

            if (modalInstance) {
                modalInstance.hide();
            }

            try {
                createDeckForm.submit();
            } catch (error) {
                console.error("Error submitting deck form:", error);
                if (modalInstance) {
                    removeModalBackdrop();
                }
            }
        });

        if (createDeckModalEl) {
            createDeckModalEl.addEventListener("hidden.bs.modal", () => {
                removeModalBackdrop();
                resetDeckForm();
            });
        }

        function removeModalBackdrop() {
            const backdrops = document.querySelectorAll(".modal-backdrop");
            backdrops.forEach((backdrop) => backdrop.remove());
            document.body.classList.remove("modal-open");
            document.body.style.overflow = "";
        }

        function resetDeckForm() {
            deckPathInput.value = "New Deck";
            createDeckParentInput.value = "";
            createDeckNameInput.value = "";
            createDeckPathInput.value = "";
        }
    }
}
