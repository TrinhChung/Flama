(() => {
    const root = document.getElementById("support-donation-result-root");
    if (!root) return;

    const state = {
        isAuthenticated: root.dataset.isAuthenticated === "true",
        orderUrlTemplate: root.dataset.orderUrlTemplate || "",
        statusUrl: root.dataset.statusUrl || "",
        donateUrl: root.dataset.donateUrl || "/support-donation",
    };

    const errorEl = document.getElementById("supportDonationResultError");
    const subtitleEl = document.getElementById("supportDonationResultSubtitle");
    const cardEl = document.getElementById("supportDonationResultCard");
    const headlineEl = document.getElementById("supportDonationResultHeadline");
    const messageEl = document.getElementById("supportDonationResultMessage");
    const badgeEl = document.getElementById("supportDonationResultBadge");
    const nextActionEl = document.getElementById("supportDonationResultNextAction");
    const linesEl = document.getElementById("supportDonationResultLines");
    const instructionsEl = document.getElementById("supportDonationResultInstructions");
    const footerEl = document.getElementById("supportDonationResultFooter");
    const backBtnEl = document.getElementById("supportDonationBackBtn");
    const checkoutAgainBtn = document.getElementById("supportDonationCheckoutAgainBtn");

    function showError(message) {
        if (!errorEl) return;
        errorEl.textContent = message || "Không thể tải kết quả ủng hộ lúc này.";
        errorEl.classList.remove("d-none");
    }

    function clearError() {
        if (!errorEl) return;
        errorEl.textContent = "";
        errorEl.classList.add("d-none");
    }

    async function requestJson(url, options = {}) {
        const response = await fetch(url, {
            credentials: "same-origin",
            headers: { "Content-Type": "application/json" },
            ...options,
        });
        const payload = await response.json().catch(() => ({}));
        if (!response.ok) {
            const error = new Error(
                payload.message
                || (response.status >= 500
                    ? "Máy chủ đang bận hoặc tạm thời không phản hồi. Vui lòng thử lại sau."
                    : "Không thể hoàn tất yêu cầu.")
            );
            error.status = response.status;
            error.payload = payload;
            throw error;
        }
        return payload;
    }

    function formatAmount(value, currency) {
        const amount = Number(value || 0);
        return new Intl.NumberFormat("vi-VN").format(amount) + " " + (currency || "VND");
    }

    function parseReturnParams() {
        const url = new URL(window.location.href);
        return {
            paymentOrderId: url.searchParams.get("payment_order_id") || "",
            providerOrderCode: url.searchParams.get("support_provider_order_code")
                || url.searchParams.get("orderCode")
                || "",
        };
    }

    function renderLineValue(line) {
        if (!line) return "-";
        if (line.type === "amount_minor") {
            return formatAmount(line.value_minor, line.currency_code);
        }
        return line.value || "-";
    }

    function renderDetailLines(lines) {
        if (!linesEl) return;
        linesEl.innerHTML = "";

        const normalized = Array.isArray(lines) ? lines : [];
        if (!normalized.length) {
            const emptyEl = document.createElement("div");
            emptyEl.className = "support-result-line";
            emptyEl.textContent = "Chưa có thêm chi tiết cho phiên ủng hộ này.";
            linesEl.appendChild(emptyEl);
            return;
        }

        normalized.forEach((line) => {
            const rowEl = document.createElement("div");
            rowEl.className = "support-result-line";

            const labelEl = document.createElement("div");
            labelEl.className = "support-result-line-label";
            labelEl.textContent = line.label || "Chi tiết";

            const valueEl = document.createElement("div");
            valueEl.className = "support-result-line-value";
            if (line.key === "merchant_order_code" || line.key === "payment_reference") {
                valueEl.classList.add("is-code");
            }

            if (line.type === "url" && line.value) {
                const linkEl = document.createElement("a");
                linkEl.href = line.value;
                linkEl.target = "_blank";
                linkEl.rel = "noopener noreferrer";
                linkEl.textContent = "Mở lại trang thanh toán";
                valueEl.appendChild(linkEl);
            } else {
                valueEl.textContent = renderLineValue(line);
            }

            rowEl.appendChild(labelEl);
            rowEl.appendChild(valueEl);
            linesEl.appendChild(rowEl);
        });
    }

    function renderInstructions(instructions) {
        if (!instructionsEl) return;
        instructionsEl.innerHTML = "";

        const items = Array.isArray(instructions) && instructions.length
            ? instructions
            : ["Bạn có thể quay lại màn ủng hộ để bắt đầu một phiên mới khi cần."];

        items.forEach((instruction) => {
            const itemEl = document.createElement("li");
            itemEl.textContent = instruction;
            instructionsEl.appendChild(itemEl);
        });
    }

    function getCheckoutUrl(payload) {
        return payload?.active_attempt?.checkout?.checkout_url
            || payload?.active_attempt?.checkout_url
            || "";
    }

    function renderStatus(payload) {
        const statusDisplay = payload?.status_display || {};
        const checkoutUrl = getCheckoutUrl(payload);
        const isPending = String(payload?.status || "").trim().toLowerCase() === "pending_payment";

        if (cardEl) {
            cardEl.setAttribute("data-tone", statusDisplay.tone || "info");
        }
        if (headlineEl) {
            headlineEl.textContent = payload?.headline || statusDisplay.headline || "Kết quả ủng hộ";
        }
        if (messageEl) {
            messageEl.textContent = payload?.message || statusDisplay.description || "";
        }
        if (badgeEl) {
            badgeEl.textContent = statusDisplay.label || "Trạng thái";
        }
        if (nextActionEl) {
            nextActionEl.textContent = payload?.next_action ? ("Tiếp theo: " + payload.next_action) : "";
        }
        if (subtitleEl) {
            subtitleEl.textContent = isPending
                ? "Phiên ủng hộ của bạn vẫn đang chờ hoàn tất. Bạn có thể tiếp tục thanh toán hoặc quay lại màn donate."
                : "Bạn có thể quay lại màn ủng hộ hoặc mở lịch sử donate để theo dõi các khoản đã ghi nhận.";
        }
        if (footerEl) {
            footerEl.textContent = payload?.next_action
                || "Bạn có thể quay lại màn ủng hộ để thực hiện phiên mới, hoặc mở lịch sử donate nếu muốn xem lại các lần đã ghi nhận.";
        }

        renderDetailLines(payload?.order_detail_lines || []);
        renderInstructions(payload?.instructions || []);

        if (backBtnEl) {
            backBtnEl.href = state.donateUrl;
        }
        if (checkoutAgainBtn) {
            if (checkoutUrl && isPending) {
                checkoutAgainBtn.href = checkoutUrl;
                checkoutAgainBtn.classList.remove("d-none");
            } else {
                checkoutAgainBtn.removeAttribute("href");
                checkoutAgainBtn.classList.add("d-none");
            }
        }
    }

    async function loadStatus() {
        const params = parseReturnParams();

        if (params.paymentOrderId && state.isAuthenticated && state.orderUrlTemplate) {
            try {
                const orderUrl = state.orderUrlTemplate.replace(
                    "__ORDER_ID__",
                    encodeURIComponent(params.paymentOrderId)
                );
                const payload = await requestJson(orderUrl, { method: "GET" });
                renderStatus(payload);
                return;
            } catch (error) {
                if (!(params.providerOrderCode && state.statusUrl)) {
                    throw error;
                }
            }
        }

        if (params.providerOrderCode && state.statusUrl) {
            const statusUrl = new URL(state.statusUrl, window.location.origin);
            statusUrl.searchParams.set("provider_order_code", params.providerOrderCode);
            const payload = await requestJson(statusUrl.toString(), { method: "GET" });
            renderStatus(payload);
            return;
        }

        throw new Error("Không tìm thấy thông tin phiên ủng hộ để hiển thị kết quả.");
    }

    clearError();
    loadStatus().catch((error) => {
        showError(error.message || "Không thể đồng bộ trạng thái ủng hộ.");
        if (headlineEl) {
            headlineEl.textContent = "Không thể tải kết quả ủng hộ";
        }
        if (messageEl) {
            messageEl.textContent = error.message || "";
        }
        if (nextActionEl) {
            nextActionEl.textContent = "";
        }
        if (footerEl) {
            footerEl.textContent = "Bạn vẫn có thể quay lại màn ủng hộ để bắt đầu lại khi sẵn sàng.";
        }
        renderDetailLines([]);
        renderInstructions([]);
        if (checkoutAgainBtn) {
            checkoutAgainBtn.classList.add("d-none");
        }
        if (backBtnEl) {
            backBtnEl.href = state.donateUrl;
        }
    });
})();
