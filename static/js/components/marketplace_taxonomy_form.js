function parseJsonAttribute(value, fallback) {
  if (!value) return fallback;
  try {
    return JSON.parse(value);
  } catch (error) {
    return fallback;
  }
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function optionMap(items = []) {
  return new Map((items || []).map((item) => [String(item.id || ""), item]));
}

function valuesFromRoot(root, name, fallback = []) {
  const checked = Array.from(root.querySelectorAll(`input[name="${name}"]:checked`)).map((input) => input.value);
  return checked.length ? checked : Array.isArray(fallback) ? fallback.slice() : [];
}

function setSelectOptions(selectEl, options, selectedValue, placeholder) {
  if (!selectEl) return;
  const rows = Array.isArray(options) ? options : [];
  const markup = [
    `<option value="">${escapeHtml(placeholder || "Select")}</option>`,
    ...rows.map((option) => `<option value="${escapeHtml(option.id)}">${escapeHtml(option.label || option.id)}</option>`),
  ];
  selectEl.innerHTML = markup.join("");
  selectEl.value = selectedValue || "";
}

function renderCheckboxGroup(container, name, options, selectedValues, maxItems) {
  if (!container) return;
  const selected = new Set((selectedValues || []).map((value) => String(value)));
  const rows = Array.isArray(options) ? options : [];
  if (!rows.length) {
    container.innerHTML = `<div class="text-muted small">No options for this subject yet.</div>`;
    return;
  }
  container.innerHTML = rows.map((option) => `
    <label class="market-filter-check market-filter-check--taxonomy">
      <input
        class="form-check-input"
        type="checkbox"
        name="${escapeHtml(name)}"
        value="${escapeHtml(option.id)}"
        ${selected.has(String(option.id)) ? "checked" : ""}
        ${maxItems ? `data-max-items="${escapeHtml(String(maxItems))}"` : ""}
      >
      <span>${escapeHtml(option.label || option.id)}</span>
    </label>
  `).join("");
}

function normalizeState(root, initial) {
  return {
    domain: root.querySelector('[data-taxonomy-select="domain"]')?.value || initial.domain || "",
    subject: root.querySelector('[data-taxonomy-select="subject"]')?.value || initial.subject || "",
    difficulty_band: root.querySelector('[data-taxonomy-select="difficulty_band"]')?.value || initial.difficulty_band || "",
    audience: root.querySelector('[data-taxonomy-select="audience"]')?.value || initial.audience || "",
    framework: root.querySelector('[data-taxonomy-select="framework"]')?.value || initial.framework || "",
    framework_level: root.querySelector('[data-taxonomy-select="framework_level"]')?.value || initial.framework_level || "",
    framework_track: root.querySelector('[data-taxonomy-select="framework_track"]')?.value || initial.framework_track || "",
    best_used_for: root.querySelector('[data-taxonomy-select="best_used_for"]')?.value || initial.best_used_for || "",
    learning_goals: valuesFromRoot(root, "learning_goals", initial.learning_goals),
    primary_topics: valuesFromRoot(root, "primary_topics", initial.primary_topics),
    format_features: valuesFromRoot(root, "format_features", initial.format_features),
  };
}

function findFramework(subjectPack, frameworkId) {
  const frameworks = Array.isArray(subjectPack?.frameworks) ? subjectPack.frameworks : [];
  return frameworks.find((row) => String(row.id) === String(frameworkId)) || null;
}

function limitChecked(groupEl) {
  const changedInput = groupEl?.querySelector("input:focus");
  if (!changedInput?.checked) return;
  const maxItems = Number(changedInput.getAttribute("data-max-items") || "0");
  if (!maxItems) return;
  const checkedInputs = Array.from(groupEl.querySelectorAll("input:checked"));
  if (checkedInputs.length <= maxItems) return;
  const overflow = checkedInputs.slice(maxItems);
  overflow.forEach((input) => {
    input.checked = false;
  });
}

function initTaxonomyForm(root) {
  const schema = parseJsonAttribute(root.getAttribute("data-taxonomy-schema"), {});
  const initial = parseJsonAttribute(root.getAttribute("data-taxonomy-initial"), {});
  const contentType = root.getAttribute("data-content-type") || "";

  const domainSelect = root.querySelector('[data-taxonomy-select="domain"]');
  const subjectSelect = root.querySelector('[data-taxonomy-select="subject"]');
  const difficultySelect = root.querySelector('[data-taxonomy-select="difficulty_band"]');
  const audienceSelect = root.querySelector('[data-taxonomy-select="audience"]');
  const frameworkSelect = root.querySelector('[data-taxonomy-select="framework"]');
  const frameworkLevelSelect = root.querySelector('[data-taxonomy-select="framework_level"]');
  const frameworkTrackSelect = root.querySelector('[data-taxonomy-select="framework_track"]');
  const bestUsedForSelect = root.querySelector('[data-taxonomy-select="best_used_for"]');
  const bestUsedForWrap = root.querySelector("[data-taxonomy-best-used-for-wrap]");
  const learningGoalsEl = root.querySelector('[data-taxonomy-checkbox-group="learning_goals"]');
  const primaryTopicsEl = root.querySelector('[data-taxonomy-checkbox-group="primary_topics"]');
  const formatFeaturesEl = root.querySelector('[data-taxonomy-checkbox-group="format_features"]');

  const subjectMap = optionMap(schema.subjects || []);
  const goalMap = optionMap(schema.learning_goals || []);
  const topicMap = optionMap(schema.primary_topics || []);
  const featureMap = optionMap(schema.format_features || []);

  function render() {
    const state = normalizeState(root, initial);
    const subjectMeta = subjectMap.get(state.subject);
    const derivedDomain = subjectMeta?.domain || "";
    const activeDomain = derivedDomain || state.domain || "";

    setSelectOptions(domainSelect, schema.domains || [], activeDomain, "Select domain");

    const subjectOptions = (schema.subjects || []).filter((row) => !activeDomain || row.domain === activeDomain);
    const activeSubject = subjectOptions.some((row) => String(row.id) === String(state.subject))
      ? state.subject
      : "";
    setSelectOptions(subjectSelect, subjectOptions, activeSubject, "Select subject");

    setSelectOptions(difficultySelect, schema.difficulty_bands || [], state.difficulty_band, "Select difficulty");
    setSelectOptions(audienceSelect, schema.audiences || [], state.audience, "Select audience");

    const subjectPack = (schema.subject_packs || {})[activeSubject] || null;
    const frameworks = Array.isArray(subjectPack?.frameworks) ? subjectPack.frameworks : [];
    const activeFramework = frameworks.some((row) => String(row.id) === String(state.framework))
      ? state.framework
      : "";
    setSelectOptions(frameworkSelect, frameworks, activeFramework, frameworks.length ? "Select framework" : "No framework");
    frameworkSelect.disabled = frameworks.length === 0;

    const frameworkMeta = findFramework(subjectPack, activeFramework);
    const frameworkLevels = Array.isArray(frameworkMeta?.levels) ? frameworkMeta.levels : [];
    const frameworkTracks = Array.isArray(frameworkMeta?.tracks) ? frameworkMeta.tracks : [];
    const activeLevel = frameworkLevels.some((row) => String(row.id) === String(state.framework_level))
      ? state.framework_level
      : "";
    const activeTrack = frameworkTracks.some((row) => String(row.id) === String(state.framework_track))
      ? state.framework_track
      : "";
    setSelectOptions(frameworkLevelSelect, frameworkLevels, activeLevel, frameworkLevels.length ? "Select level" : "No framework level");
    setSelectOptions(frameworkTrackSelect, frameworkTracks, activeTrack, frameworkTracks.length ? "Select track" : "No track");
    frameworkLevelSelect.disabled = frameworkLevels.length === 0;
    frameworkTrackSelect.disabled = frameworkTracks.length === 0;
    frameworkTrackSelect.closest(".col-md-4")?.classList.toggle("d-none", frameworkTracks.length === 0);

    if (bestUsedForSelect) {
      setSelectOptions(bestUsedForSelect, schema.best_used_for || [], state.best_used_for, "Select note type usage");
    }
    if (bestUsedForWrap) {
      bestUsedForWrap.classList.toggle("d-none", contentType !== "note_type");
    }

    const packGoals = (subjectPack?.learning_goals || [])
      .map((row) => goalMap.get(String(row.id)) || row)
      .filter(Boolean);
    const packTopics = (subjectPack?.primary_topics || [])
      .map((row) => topicMap.get(String(row.id)) || row)
      .filter(Boolean);
    const packFeatures = (subjectPack?.format_features || [])
      .map((row) => featureMap.get(String(row.id)) || row)
      .filter(Boolean);

    renderCheckboxGroup(
      learningGoalsEl,
      "learning_goals",
      packGoals.length ? packGoals : (schema.learning_goals || []),
      state.learning_goals,
      3,
    );
    renderCheckboxGroup(
      primaryTopicsEl,
      "primary_topics",
      packTopics.length ? packTopics : (schema.primary_topics || []),
      state.primary_topics,
      5,
    );
    renderCheckboxGroup(
      formatFeaturesEl,
      "format_features",
      packFeatures.length ? packFeatures : (schema.format_features || []),
      state.format_features,
      4,
    );
  }

  root.addEventListener("change", (event) => {
    const target = event.target;
    if (!(target instanceof HTMLElement)) return;
    const checkboxWrap = target.closest("[data-taxonomy-checkbox-group]");
    if (checkboxWrap) {
      limitChecked(checkboxWrap);
      return;
    }
    if (target.matches("[data-taxonomy-select]")) {
      render();
    }
  });

  render();
}

document.querySelectorAll("[data-taxonomy-form-root]").forEach((root) => initTaxonomyForm(root));
