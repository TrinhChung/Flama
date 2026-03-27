(() => {
    const root = document.getElementById("marketplace-payment-result-root");
    if (!root) return;

    const state = {
        orderId: root.getAttribute("data-payment-order-id") || "",
        productType: root.getAttribute("data-payment-product-type") || "",
        productRefId: root.getAttribute("data-payment-product-ref-id") || "",
        order: null,
    };

    const noteTypeMarketUrl = root.getAttribute("data-note-type-market-url") || "/";
    const deckMarketUrl = root.getAttribute("data-deck-market-url") || "/";
    const noteTypeInstallUrlTemplate = root.getAttribute("data-note-type-install-url-template") || "";
    const deckInstallUrlTemplate = root.getAttribute("data-deck-install-url-template") || "";

    const subtitleEl = document.getElementById("marketplace-payment-subtitle");
    const errorEl = document.getElementById("marketplace-payment-error");
    const cardEl = document.getElementById("marketplace-payment-card");
    const headlineEl = document.getElementById("marketplace-payment-headline");
    const messageEl = document.getElementById("marketplace-payment-message");
    const badgeEl = document.getElementById("marketplace-payment-badge");
    const nextActionEl = document.getElementById("marketplace-payment-next-action");
    const linesEl = document.getElementById("marketplace-payment-lines");
    const instructionsEl = document.getElementById("marketplace-payment-instructions");
    const footerEl = document.getElementById("marketplace-payment-footer");
    const backLinkEl = document.getElementById("marketplace-payment-back-link");
    const backBtnEl = document.getElementById("marketplace-payment-back-btn");
    const retryBtnEl = document.getElementById("marketplace-payment-retry-btn");

    function showError(message) {
        if (!errorEl) return;
        errorEl.textContent = message || "Không thể xử lý yêu cầu lúc này.";
        errorEl.classList.remove("d-none");
    }

    function clearError() {
        if (!errorEl) return;
        errorEl.textContent = "";
        errorEl.classList.add("d-none");
    }

    async function requestJson(url, options = {}) {
        const response = await fetch(url, options);
        const data = await response.json().catch(() => ({}));
        if (!response.ok) {
            const error = new Error(
                data.message
                || (response.status >= 500
                    ? "Máy chủ đang bận hoặc tạm thời không phản hồi. Vui lòng thử lại sau."
                    : "Không thể hoàn tất yêu cầu.")
            );
            error.status = response.status;
            error.code = data.error || "REQUEST_FAILED";
            error.payload = data;
            throw error;
        }
        return data;
    }

    function formatDate(isoString) {
        if (!isoString) return "";
        const date = new Date(isoString);
        if (Number.isNaN(date.getTime())) return "";
        return date.toLocaleString();
    }

    function formatCurrencyMinor(amount) {
        return window.Utils.formatVnd(amount);
    }

    function resolveProductContext(order) {
        const firstItem = Array.isArray(order?.items) ? order.items[0] : null;
        if (!state.productType && firstItem?.product_type) {
            state.productType = firstItem.product_type;
        }
        if (!state.productRefId && firstItem?.product_ref_id) {
            state.productRefId = firstItem.product_ref_id;
        }
    }

    function getMarketplaceLabel(productType) {
        if (productType === "deck_marketplace_item") {
            return "Shared Decks";
        }
        if (productType === "note_type") {
            return "Shared NoteTypes";
        }
        return "Marketplace";
    }

    function getMarketplaceUrl(productType) {
        if (productType === "deck_marketplace_item") {
            return deckMarketUrl;
        }
        return noteTypeMarketUrl;
    }

    function getInstallUrl(productType, productRefId) {
        if (!productRefId) return "";
        if (productType === "deck_marketplace_item") {
            return deckInstallUrlTemplate.replace("__DECK_ITEM_ID__", encodeURIComponent(productRefId));
        }
        if (productType === "note_type") {
            return noteTypeInstallUrlTemplate.replace("__NOTE_TYPE_ID__", encodeURIComponent(productRefId));
        }
        return "";
    }

    function renderBackLinks() {
        const marketplaceUrl = getMarketplaceUrl(state.productType);
        const marketplaceLabel = getMarketplaceLabel(state.productType);
        const buttonText = "Quay lại " + marketplaceLabel;
        if (subtitleEl) {
            subtitleEl.textContent = "Theo dõi trạng thái đơn hàng, quay lại " + marketplaceLabel + " hoặc tạo lại phiên thanh toán khi cần.";
        }
        if (backLinkEl) {
            backLinkEl.href = marketplaceUrl;
            backLinkEl.textContent = buttonText;
        }
        if (backBtnEl) {
            backBtnEl.href = marketplaceUrl;
            backBtnEl.textContent = buttonText;
        }
    }

    function renderPaymentLineValue(line) {
        if (!line) return "N/A";
        if (line.type === "amount_minor") {
            return formatCurrencyMinor(line.value_minor || 0);
        }
        if (line.type === "datetime") {
            return formatDate(line.value) || "N/A";
        }
        return String(line.value || "N/A");
    }

    function renderPaymentLines(lines) {
        if (!linesEl) return;
        linesEl.innerHTML = "";
        const normalized = Array.isArray(lines) ? lines : [];
        if (!normalized.length) {
            const emptyEl = document.createElement("div");
            emptyEl.className = "small text-muted";
            emptyEl.textContent = "Chưa có thêm thông tin chi tiết cho đơn hàng này.";
            linesEl.appendChild(emptyEl);
            return;
        }

        normalized.forEach((line) => {
            const rowEl = document.createElement("div");
            rowEl.className = "marketplace-payment-line";

            const labelEl = document.createElement("div");
            labelEl.className = "marketplace-payment-label";
            labelEl.textContent = line.label || "Thông tin";

            const valueEl = document.createElement("div");
            valueEl.className = "marketplace-payment-value";
            if (line.key === "payment_reference" || line.key === "merchant_order_code") {
                valueEl.classList.add("is-code");
            }

            if (line.type === "url" && line.value) {
                const linkEl = document.createElement("a");
                linkEl.href = line.value;
                linkEl.target = "_blank";
                linkEl.rel = "noopener noreferrer";
                linkEl.textContent = "Mở lại trang thanh toán PayOS";
                valueEl.appendChild(linkEl);
            } else {
                valueEl.textContent = renderPaymentLineValue(line);
            }

            rowEl.appendChild(labelEl);
            rowEl.appendChild(valueEl);
            linesEl.appendChild(rowEl);
        });
    }

    function renderInstructions(instructions) {
        if (!instructionsEl) return;
        instructionsEl.innerHTML = "";
        const normalized = Array.isArray(instructions) ? instructions.filter(Boolean) : [];
        const items = normalized.length ? normalized : ["Theo dõi trạng thái đơn hàng trên màn hình này."];
        items.forEach((instruction) => {
            const itemEl = document.createElement("li");
            itemEl.textContent = instruction;
            instructionsEl.appendChild(itemEl);
        });
    }

    function getActiveCheckoutUrl(order) {
        return order?.active_attempt?.checkout?.checkout_url || order?.active_attempt?.checkout_url || "";
    }

    function resolveRetryConfig(order) {
        const checkoutUrl = getActiveCheckoutUrl(order);
        const status = String(order?.status || "").trim().toLowerCase();
        if (status === "pending_payment") {
            return {
                label: checkoutUrl ? "Tiếp tục thanh toán" : "Đang chờ thanh toán",
                enabled: Boolean(checkoutUrl),
            };
        }
        if (status === "expired" || status === "failed" || status === "canceled") {
            return {
                label: "Mua lại",
                enabled: true,
            };
        }
        return {
            label: "Mua lại",
            enabled: false,
        };
    }

    function renderOrder(order) {
        state.order = order;
        resolveProductContext(order);
        renderBackLinks();

        const statusDisplay = order?.status_display || {};
        if (cardEl) {
            cardEl.setAttribute("data-tone", statusDisplay.tone || "info");
        }
        if (badgeEl) {
            badgeEl.textContent = statusDisplay.label || "Đơn hàng";
        }
        if (headlineEl) {
            headlineEl.textContent = order?.headline || statusDisplay.headline || "Chi tiết đơn hàng";
        }
        if (messageEl) {
            messageEl.textContent = order?.message || statusDisplay.description || "";
        }
        if (nextActionEl) {
            nextActionEl.textContent = order?.next_action ? ("Tiếp theo: " + order.next_action) : "";
        }
        if (footerEl) {
            footerEl.textContent = order?.next_action
                || "Bạn có thể quay lại marketplace hoặc tiếp tục xử lý đơn hàng tại đây.";
        }

        renderPaymentLines(order?.order_detail_lines || []);
        renderInstructions(order?.instructions || []);

        const retryConfig = resolveRetryConfig(order);
        if (retryBtnEl) {
            retryBtnEl.textContent = retryConfig.label;
            retryBtnEl.disabled = !retryConfig.enabled;
            retryBtnEl.classList.toggle("d-none", !getInstallUrl(state.productType, state.productRefId));
        }
    }

    async function loadOrder() {
        if (!state.orderId) {
            renderBackLinks();
            throw new Error("Không tìm thấy mã đơn hàng để hiển thị kết quả thanh toán.");
        }
        const order = await requestJson(`/api/payments/orders/${encodeURIComponent(state.orderId)}`);
        renderOrder(order);
    }

    async function retryPurchase() {
        clearError();
        const currentOrder = state.order || {};
        const currentStatus = String(currentOrder.status || "").trim().toLowerCase();
        const currentCheckoutUrl = getActiveCheckoutUrl(currentOrder);
        if (currentStatus === "pending_payment") {
            if (currentCheckoutUrl) {
                window.location.href = currentCheckoutUrl;
                return;
            }
            throw new Error("Đơn hàng này vẫn đang chờ thanh toán. Vui lòng dùng lại liên kết PayOS hiện tại.");
        }

        const installUrl = getInstallUrl(state.productType, state.productRefId);
        if (!installUrl) {
            throw new Error("Không xác định được sản phẩm để mua lại.");
        }

        const response = await requestJson(installUrl, { method: "POST" });
        if (!response?.payment_required || !response?.order) {
            window.location.href = getMarketplaceUrl(state.productType);
            return;
        }

        const order = response.order;
        state.orderId = order.id || state.orderId;
        renderOrder(order);

        const checkoutUrl = getActiveCheckoutUrl(order);
        if (checkoutUrl && order?.status === "pending_payment") {
            window.location.href = checkoutUrl;
        }
    }

    retryBtnEl?.addEventListener("click", () => {
        retryBtnEl.disabled = true;
        retryPurchase()
            .catch((error) => {
                showError(error.message || "Không thể tạo lại phiên thanh toán lúc này.");
            })
            .finally(() => {
                const retryConfig = state.order
                    ? resolveRetryConfig(state.order)
                    : { enabled: Boolean(getInstallUrl(state.productType, state.productRefId)) };
                retryBtnEl.disabled = !retryConfig.enabled;
            });
    });

    renderBackLinks();
    loadOrder().catch((error) => {
        showError(error.message || "Không thể đồng bộ trạng thái đơn hàng lúc này.");
        if (headlineEl) {
            headlineEl.textContent = "Không thể tải kết quả thanh toán";
        }
        if (messageEl) {
            messageEl.textContent = error.message || "";
        }
        if (retryBtnEl) {
            retryBtnEl.disabled = !getInstallUrl(state.productType, state.productRefId);
        }
    });
})();
