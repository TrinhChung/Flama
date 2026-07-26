(function () {
  "use strict";

  const form = document.getElementById("image-library-form");
  const fileInput = document.getElementById("image-file");
  const chooseButton = document.getElementById("image-file-choose");
  const dropzone = document.getElementById("image-dropzone");
  const emptyState = document.getElementById("image-source-empty");
  const preview = document.getElementById("image-upload-preview");
  const previewImage = preview?.querySelector("img");
  const fileLabel = document.getElementById("image-file-label");
  const fileMeta = document.getElementById("image-file-meta");
  const clearButton = document.getElementById("image-file-clear");
  const sourceUrlInput = document.getElementById("image-source-url");
  const sourceError = document.getElementById("image-source-error");
  const keyInput = document.getElementById("image-key");
  let previewUrl = null;

  function formatBytes(bytes) {
    const value = Number(bytes || 0);
    if (value < 1024) return `${value} B`;
    if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
    return `${(value / 1024 / 1024).toFixed(1)} MB`;
  }

  function showSourceError(message) {
    if (!sourceError) return;
    sourceError.textContent = message || "";
    sourceError.hidden = !message;
  }

  function resetObjectUrl() {
    if (!previewUrl) return;
    URL.revokeObjectURL(previewUrl);
    previewUrl = null;
  }

  function clearFileSelection(options) {
    const preserveUrl = Boolean(options?.preserveUrl);
    resetObjectUrl();
    if (fileInput) fileInput.value = "";
    if (preview) preview.hidden = true;
    if (emptyState) emptyState.hidden = false;
    if (previewImage) previewImage.removeAttribute("src");
    if (fileLabel) fileLabel.textContent = "";
    if (fileMeta) fileMeta.textContent = "";
    dropzone?.classList.remove("has-file", "is-dragover");
    if (!preserveUrl && sourceUrlInput) sourceUrlInput.value = "";
    showSourceError("");
  }

  function clipboardFilename(file) {
    const extensionByMime = {
      "image/gif": "gif",
      "image/jpeg": "jpg",
      "image/png": "png",
      "image/svg+xml": "svg",
      "image/webp": "webp",
    };
    const originalName = String(file?.name || "").trim();
    if (originalName && originalName !== "image.png") return originalName;
    const extension = extensionByMime[String(file?.type || "").toLowerCase()] || "png";
    return `clipboard-image.${extension}`;
  }

  function assignFile(file, sourceLabel) {
    if (!file || !String(file.type || "").toLowerCase().startsWith("image/")) {
      showSourceError("Clipboard hoặc tệp đã chọn không chứa hình ảnh hợp lệ.");
      return false;
    }

    const normalizedFile = file.name
      ? file
      : new File([file], clipboardFilename(file), {
          type: file.type || "image/png",
          lastModified: Date.now(),
        });

    try {
      const transfer = new DataTransfer();
      transfer.items.add(normalizedFile);
      fileInput.files = transfer.files;
    } catch (_error) {
      showSourceError("Trình duyệt không thể nhận ảnh đã dán. Hãy dùng nút Chọn tệp.");
      return false;
    }

    resetObjectUrl();
    previewUrl = URL.createObjectURL(normalizedFile);
    if (previewImage) previewImage.src = previewUrl;
    if (fileLabel) fileLabel.textContent = normalizedFile.name || clipboardFilename(normalizedFile);
    if (fileMeta) {
      fileMeta.textContent = `${sourceLabel || "Tệp hình ảnh"} · ${formatBytes(normalizedFile.size)}`;
    }
    if (emptyState) emptyState.hidden = true;
    if (preview) preview.hidden = false;
    if (sourceUrlInput) sourceUrlInput.value = "";
    dropzone?.classList.add("has-file");
    dropzone?.classList.remove("is-dragover");
    showSourceError("");
    return true;
  }

  function imageFileFromClipboard(clipboardData) {
    return Array.from(clipboardData?.items || [])
      .map(function (item) {
        return item.kind === "file" ? item.getAsFile() : null;
      })
      .find(function (file) {
        return Boolean(file && String(file.type || "").toLowerCase().startsWith("image/"));
      }) || null;
  }

  chooseButton?.addEventListener("click", function (event) {
    event.stopPropagation();
    fileInput?.click();
  });

  dropzone?.addEventListener("click", function (event) {
    if (event.target.closest("#image-file-clear, #image-file-choose")) return;
    fileInput?.click();
  });

  fileInput?.addEventListener("change", function () {
    const file = fileInput.files?.[0];
    if (!file) {
      clearFileSelection({ preserveUrl: true });
      return;
    }
    assignFile(file, "Tệp đã chọn");
  });

  form?.addEventListener("paste", function (event) {
    const file = imageFileFromClipboard(event.clipboardData);
    if (!file) return;
    event.preventDefault();
    assignFile(file, "Ảnh dán từ clipboard");
  });

  dropzone?.addEventListener("dragover", function (event) {
    const hasImage = Array.from(event.dataTransfer?.items || []).some(function (item) {
      return item.kind === "file" && String(item.type || "").toLowerCase().startsWith("image/");
    });
    if (!hasImage) return;
    event.preventDefault();
    dropzone.classList.add("is-dragover");
  });

  dropzone?.addEventListener("dragleave", function (event) {
    if (dropzone.contains(event.relatedTarget)) return;
    dropzone.classList.remove("is-dragover");
  });

  dropzone?.addEventListener("drop", function (event) {
    event.preventDefault();
    dropzone.classList.remove("is-dragover");
    const file = Array.from(event.dataTransfer?.files || []).find(function (candidate) {
      return String(candidate.type || "").toLowerCase().startsWith("image/");
    });
    if (!file) {
      showSourceError("Tệp vừa thả không phải hình ảnh được hỗ trợ.");
      return;
    }
    assignFile(file, "Ảnh kéo thả");
  });

  clearButton?.addEventListener("click", function (event) {
    event.stopPropagation();
    clearFileSelection({ preserveUrl: true });
  });

  sourceUrlInput?.addEventListener("input", function () {
    if (!sourceUrlInput.value.trim()) return;
    clearFileSelection({ preserveUrl: true });
  });

  form?.addEventListener("submit", function (event) {
    const hasFile = Boolean(fileInput?.files?.length);
    const hasUrl = Boolean(sourceUrlInput?.value.trim());
    if (hasFile && hasUrl) {
      event.preventDefault();
      showSourceError("Chỉ chọn tệp hoặc link hình ảnh, không dùng đồng thời cả hai.");
      sourceUrlInput.focus();
    }
  });

  keyInput?.addEventListener("blur", function () {
    if (keyInput.readOnly) return;
    keyInput.value = keyInput.value
      .normalize("NFKC")
      .trim()
      .toLowerCase()
      .replace(/[\s-]+/g, "_")
      .replace(/_+/g, "_")
      .replace(/^_+|_+$/g, "");
  });

  document.querySelectorAll("[data-copy-value]").forEach(function (button) {
    button.addEventListener("click", async function () {
      const value = button.dataset.copyValue;
      if (!value) return;

      try {
        await navigator.clipboard.writeText(new URL(value, window.location.origin).href);
        button.classList.add("is-copied");
        const icon = button.querySelector("i");
        if (icon) icon.className = "bi bi-check2";
        window.setTimeout(function () {
          button.classList.remove("is-copied");
          if (icon) icon.className = "bi bi-copy";
        }, 1600);
      } catch (_error) {
        window.prompt("Sao chép URL hình ảnh:", new URL(value, window.location.origin).href);
      }
    });
  });

  window.addEventListener("beforeunload", resetObjectUrl);
})();
