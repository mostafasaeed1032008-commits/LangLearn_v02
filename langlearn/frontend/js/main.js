// frontend/js/main.js

const state = {
  locale: "ar",
  courses: [],
  currentCourseId: null,
  levels: [],
  currentLevelId: null,
  units: [],
  currentUnitId: null,
  lessons: [],
  currentLessonId: null,
  stages: [],
};

function t(key) {
  return (UI_STRINGS[state.locale] && UI_STRINGS[state.locale][key]) || key;
}

function dirFor(locale) {
  const l = LOCALES.find((x) => x.code === locale);
  return l ? l.dir : "ltr";
}

// ----------------------------------------------------------------
// Bootstrapping
// ----------------------------------------------------------------
async function init() {
  renderLocaleSwitch();
  applyDocumentDirection();
  await loadCourses();
  attachStaticHandlers();
}

function applyDocumentDirection() {
  document.documentElement.lang = state.locale;
  document.body.dir = dirFor(state.locale);
  document.getElementById("app-title").textContent = t("app_title");
}

function attachStaticHandlers() {
  document.getElementById("btn-add-unit").addEventListener("click", () => openAddUnitModal());
  document.getElementById("btn-add-lesson").addEventListener("click", () => openAddLessonModal());
}

// ----------------------------------------------------------------
// Locale switching
// ----------------------------------------------------------------
function renderLocaleSwitch() {
  const el = document.getElementById("locale-switch");
  el.innerHTML = "";
  LOCALES.forEach((loc) => {
    const btn = document.createElement("button");
    btn.textContent = loc.label;
    btn.className = loc.code === state.locale ? "active" : "";
    btn.addEventListener("click", () => {
      state.locale = loc.code;
      applyDocumentDirection();
      renderLocaleSwitch();
      renderLevels();
      renderUnits();
      renderLessons();
      renderStages();
      renderCefrPanel();
    });
    el.appendChild(btn);
  });
}

// ----------------------------------------------------------------
// Error handling
// ----------------------------------------------------------------
function showError(msg) {
  const el = document.getElementById("error-banner");
  el.textContent = msg;
  el.style.display = "block";
  setTimeout(() => (el.style.display = "none"), 6000);
}

// ----------------------------------------------------------------
// Loaders
// ----------------------------------------------------------------
async function loadCourses() {
  try {
    state.courses = await Api.listCourses();
    if (state.courses.length > 0) {
      state.currentCourseId = state.courses[0].id;
      await loadLevels();
    }
  } catch (e) {
    showError(t("error_generic"));
    console.error(e);
  }
}

async function loadLevels() {
  state.levels = await Api.listLevels(state.currentCourseId);
  renderLevels();
}

async function loadUnits(levelId) {
  state.currentLevelId = levelId;
  state.currentUnitId = null;
  state.currentLessonId = null;
  state.units = await Api.listUnits(levelId);
  state.lessons = [];
  state.stages = [];
  renderLevels();
  renderUnits();
  renderLessons();
  renderStages();
  renderCefrPanel();
}

async function loadLessons(unitId) {
  state.currentUnitId = unitId;
  state.currentLessonId = null;
  state.lessons = await Api.listLessons(unitId);
  state.stages = [];
  renderUnits();
  renderLessons();
  renderStages();
}

async function loadStages(lessonId) {
  state.currentLessonId = lessonId;
  state.stages = await Api.listStages(lessonId);
  renderLessons();
  renderStages();
}

// ----------------------------------------------------------------
// Render: Levels column
// ----------------------------------------------------------------
function renderLevels() {
  const el = document.getElementById("levels-list");
  document.getElementById("levels-header").textContent = t("levels");
  el.innerHTML = "";

  if (state.levels.length === 0) {
    el.innerHTML = '<div class="empty-state">' + t("loading") + '</div>';
    return;
  }

  state.levels.forEach((lv) => {
    const tr = lv.translations[state.locale] || {};
    const div = document.createElement("button");
    div.className = "list-item" + (lv.id === state.currentLevelId ? " active" : "");
    div.innerHTML =
      '<div class="item-top">' +
        '<span class="item-code">' + lv.cefr_code + '</span>' +
        '<span class="item-title">' + escapeHtml(tr.name || lv.cefr_code) + '</span>' +
        (lv.is_locked ? '<span class="lock-icon">\uD83D\uDD12</span>' : '') +
      '</div>' +
      '<div class="item-meta">' + lv.unit_count + ' ' + t("units").toLowerCase() + '</div>';
    div.addEventListener("click", () => loadUnits(lv.id));
    el.appendChild(div);
  });
}

// ----------------------------------------------------------------
// Render: CEFR reference panel (shown above units column)
// ----------------------------------------------------------------
async function renderCefrPanel() {
  const el = document.getElementById("cefr-panel");
  if (!state.currentLevelId) {
    el.innerHTML = "";
    return;
  }
  try {
    const ref = await Api.cefrReference(state.currentLevelId);
    let html = '<h3>' + t("cefr_reference") + '</h3>';
    const grid = ref.self_assessment_grid && ref.self_assessment_grid[state.locale];
    const global = ref.global_scale && ref.global_scale[state.locale];

    if (global && global.overall) {
      html += '<p>' + escapeHtml(global.overall) + '</p>';
    } else if (ref.global_scale) {
      const anyLocale = Object.keys(ref.global_scale)[0];
      if (anyLocale) html += '<p>' + escapeHtml(ref.global_scale[anyLocale].overall) + '</p>';
    }

    if (grid) {
      const skillLabels = {
        listening: { ar: "الاستماع", de: "Hören", en: "Listening" },
        reading: { ar: "القراءة", de: "Lesen", en: "Reading" },
        spoken_interaction: { ar: "التحدث (تفاعل)", de: "Sprechen (Interaktion)", en: "Spoken Interaction" },
        spoken_production: { ar: "التحدث (إنتاج)", de: "Sprechen (Produktion)", en: "Spoken Production" },
        writing: { ar: "الكتابة", de: "Schreiben", en: "Writing" },
      };
      Object.keys(grid).forEach((skill) => {
        const text = grid[skill];
        const label = (skillLabels[skill] && skillLabels[skill][state.locale]) || skill;
        html += '<p><span class="cefr-skill-label">' + escapeHtml(label) + ':</span> ' + escapeHtml(text) + '</p>';
      });
    }
    el.innerHTML = html;
  } catch (e) {
    el.innerHTML = "";
  }
}

// ----------------------------------------------------------------
// Render: Units column
// ----------------------------------------------------------------
function renderUnits() {
  const el = document.getElementById("units-list");
  document.getElementById("units-header").textContent = t("units");
  const addBtn = document.getElementById("btn-add-unit");
  addBtn.textContent = t("add_unit");
  addBtn.style.display = state.currentLevelId ? "inline-block" : "none";
  el.innerHTML = "";

  if (!state.currentLevelId) {
    el.innerHTML = '<div class="empty-state">' + t("select_level") + '</div>';
    return;
  }
  if (state.units.length === 0) {
    el.innerHTML = '<div class="empty-state">' + t("no_units") + '</div>';
    return;
  }

  state.units.forEach((u) => {
    const tr = u.translations[state.locale] || {};
    const div = document.createElement("button");
    div.className = "list-item" + (u.id === state.currentUnitId ? " active" : "");
    div.innerHTML =
      '<div class="item-top">' +
        '<span class="item-code">U' + u.sort_order + '</span>' +
        '<span class="item-title">' + escapeHtml(tr.title || "") + '</span>' +
        (u.is_locked ? '<span class="lock-icon">\uD83D\uDD12</span>' : '') +
      '</div>' +
      '<div class="item-desc">' + escapeHtml(tr.communicative_objective || "") + '</div>' +
      '<div class="item-meta">' + u.lesson_count + ' ' + t("lessons").toLowerCase() + '</div>';
    div.addEventListener("click", () => loadLessons(u.id));
    el.appendChild(div);
  });
}

// ----------------------------------------------------------------
// Render: Lessons column
// ----------------------------------------------------------------
function renderLessons() {
  const el = document.getElementById("lessons-list");
  document.getElementById("lessons-header").textContent = t("lessons");
  const addBtn = document.getElementById("btn-add-lesson");
  addBtn.textContent = t("add_lesson");
  addBtn.style.display = state.currentUnitId ? "inline-block" : "none";
  el.innerHTML = "";

  if (!state.currentUnitId) {
    el.innerHTML = '<div class="empty-state">' + t("select_unit") + '</div>';
    return;
  }
  if (state.lessons.length === 0) {
    el.innerHTML = '<div class="empty-state">' + t("no_lessons") + '</div>';
    return;
  }

  state.lessons.forEach((l) => {
    const tr = l.translations[state.locale] || {};
    const div = document.createElement("button");
    div.className = "list-item" + (l.id === state.currentLessonId ? " active" : "");
    div.innerHTML =
      '<div class="item-top">' +
        '<span class="item-code">L' + l.sort_order + '</span>' +
        '<span class="item-title">' + escapeHtml(tr.title || "") + '</span>' +
      '</div>' +
      '<div class="item-desc">' + escapeHtml(tr.objective || "") + '</div>' +
      '<div class="item-meta">' + l.stages_with_content + '/' + l.stage_count + ' ' + t("stages_progress") + '</div>';
    div.addEventListener("click", () => loadStages(l.id));
    el.appendChild(div);
  });
}

// ----------------------------------------------------------------
// Render: Stages detail pane
// ----------------------------------------------------------------
function renderStages() {
  const el = document.getElementById("detail-pane");

  if (!state.currentLessonId) {
    el.innerHTML = '<div class="placeholder-msg">' + t("select_lesson") + '</div>';
    return;
  }

  const lesson = state.lessons.find((l) => l.id === state.currentLessonId);
  const lessonTr = (lesson && lesson.translations[state.locale]) || {};

  let html =
    '<div class="lesson-header">' +
      '<h2>' + escapeHtml(lessonTr.title || "") + '</h2>' +
      '<div class="objective">' + escapeHtml(lessonTr.objective || "") + '</div>' +
    '</div>' +
    '<div class="stage-track">';

  state.stages.forEach((s, idx) => {
    const tr = s.translations[state.locale] || {};
    const hasContent = s.content !== null && s.content !== undefined;
    const icon = STAGE_ICONS[s.stage_key] || "\u2022";
    html +=
      '<div class="stage-card">' +
        '<div class="stage-num">' + String(idx + 1).padStart(2, "0") + '</div>' +
        '<div class="stage-icon">' + icon + '</div>' +
        '<div class="stage-body">' +
          '<div class="stage-title-row">' +
            '<span class="stage-title">' + escapeHtml(tr.title || s.stage_key) + '</span>' +
            '<span class="stage-key-tag">' + s.stage_key + '</span>' +
          '</div>' +
          '<div class="stage-instructions">' + escapeHtml(tr.instructions || "") + '</div>' +
          '<div class="stage-status ' + (hasContent ? "filled" : "empty") + '">' +
            '<span class="dot"></span>' +
            (hasContent ? t("content_filled") : t("content_empty")) +
          '</div>' +
          '<div class="skill-tags">' +
            s.skills.map((sk) => '<span class="skill-tag">' + sk + '</span>').join("") +
          '</div>' +
          '<button class="stage-edit-btn" data-stage-id="' + s.id + '">' + t("edit_content") + '</button>' +
        '</div>' +
      '</div>';
  });

  html += '</div>';
  el.innerHTML = html;

  el.querySelectorAll(".stage-edit-btn").forEach((btn) => {
    btn.addEventListener("click", () => openEditStageModal(parseInt(btn.dataset.stageId, 10)));
  });
}

// ----------------------------------------------------------------
// Modals
// ----------------------------------------------------------------
function openModal(innerHtml) {
  const overlay = document.createElement("div");
  overlay.className = "modal-overlay";
  overlay.innerHTML = '<div class="modal">' + innerHtml + '</div>';
  overlay.addEventListener("click", (e) => {
    if (e.target === overlay) overlay.remove();
  });
  document.body.appendChild(overlay);
  return overlay;
}

function localeBlock(fieldsHtmlFn) {
  return LOCALES.map((loc) =>
    '<div class="modal-locale-block">' +
      '<span class="locale-label">' + loc.label + ' (' + loc.code + ')</span>' +
      fieldsHtmlFn(loc) +
    '</div>'
  ).join("");
}

function openAddUnitModal() {
  const overlay = openModal(
    '<h3>' + t("add_unit") + '</h3>' +
    localeBlock((loc) =>
      '<div class="field">' +
        '<label>' + t("title_label") + '</label>' +
        '<input dir="' + loc.dir + '" data-locale="' + loc.code + '" data-field="title" />' +
      '</div>' +
      '<div class="field">' +
        '<label>' + t("objective_label") + '</label>' +
        '<textarea dir="' + loc.dir + '" data-locale="' + loc.code + '" data-field="communicative_objective"></textarea>' +
      '</div>' +
      '<div class="field">' +
        '<label>' + t("description_label") + '</label>' +
        '<textarea dir="' + loc.dir + '" data-locale="' + loc.code + '" data-field="description"></textarea>' +
      '</div>'
    ) +
    '<div class="modal-actions">' +
      '<button class="btn-secondary" id="modal-cancel">' + t("cancel") + '</button>' +
      '<button class="btn-primary" id="modal-save">' + t("save") + '</button>' +
    '</div>'
  );

  overlay.querySelector("#modal-cancel").addEventListener("click", () => overlay.remove());
  overlay.querySelector("#modal-save").addEventListener("click", async () => {
    const translations = collectTranslations(overlay, ["title", "communicative_objective", "description"]);
    try {
      await Api.createUnit(state.currentLevelId, { translations });
      overlay.remove();
      await loadUnits(state.currentLevelId);
    } catch (e) {
      showError(t("error_generic"));
    }
  });
}

function openAddLessonModal() {
  const overlay = openModal(
    '<h3>' + t("add_lesson") + '</h3>' +
    localeBlock((loc) =>
      '<div class="field">' +
        '<label>' + t("title_label") + '</label>' +
        '<input dir="' + loc.dir + '" data-locale="' + loc.code + '" data-field="title" />' +
      '</div>' +
      '<div class="field">' +
        '<label>' + t("objective_label") + '</label>' +
        '<textarea dir="' + loc.dir + '" data-locale="' + loc.code + '" data-field="objective"></textarea>' +
      '</div>'
    ) +
    '<div class="modal-actions">' +
      '<button class="btn-secondary" id="modal-cancel">' + t("cancel") + '</button>' +
      '<button class="btn-primary" id="modal-save">' + t("save") + '</button>' +
    '</div>'
  );

  overlay.querySelector("#modal-cancel").addEventListener("click", () => overlay.remove());
  overlay.querySelector("#modal-save").addEventListener("click", async () => {
    const translations = collectTranslations(overlay, ["title", "objective"]);
    try {
      await Api.createLesson(state.currentUnitId, { translations });
      overlay.remove();
      await loadLessons(state.currentUnitId);
    } catch (e) {
      showError(t("error_generic"));
    }
  });
}

function openEditStageModal(stageId) {
  const stage = state.stages.find((s) => s.id === stageId);
  if (!stage) return;

  const contentStr = stage.content ? JSON.stringify(stage.content, null, 2) : "";

  const overlay = openModal(
    '<h3>' + t("edit_content") + ' \u2014 ' + stage.stage_key + '</h3>' +
    localeBlock((loc) =>
      '<div class="field">' +
        '<label>' + t("title_label") + '</label>' +
        '<input dir="' + loc.dir + '" data-locale="' + loc.code + '" data-field="title" value="' +
          escapeAttr((stage.translations[loc.code] || {}).title || "") + '" />' +
      '</div>' +
      '<div class="field">' +
        '<label>' + t("instructions_label") + '</label>' +
        '<textarea dir="' + loc.dir + '" data-locale="' + loc.code + '" data-field="instructions">' +
          escapeHtml((stage.translations[loc.code] || {}).instructions || "") + '</textarea>' +
      '</div>'
    ) +
    '<div class="field">' +
      '<label>' + t("content_label") + '</label>' +
      '<textarea class="json-editor" id="content-json" dir="ltr" placeholder=\'{ "example": "any JSON structure" }\'>' +
        escapeHtml(contentStr) + '</textarea>' +
    '</div>' +
    '<div class="modal-actions">' +
      '<button class="btn-secondary" id="modal-cancel">' + t("cancel") + '</button>' +
      '<button class="btn-primary" id="modal-save">' + t("save") + '</button>' +
    '</div>'
  );

  overlay.querySelector("#modal-cancel").addEventListener("click", () => overlay.remove());
  overlay.querySelector("#modal-save").addEventListener("click", async () => {
    const translations = collectTranslations(overlay, ["title", "instructions"]);
    const rawJson = overlay.querySelector("#content-json").value.trim();
    let content = null;
    if (rawJson) {
      try {
        content = JSON.parse(rawJson);
      } catch (e) {
        showError("JSON \u063A\u064A\u0631 \u0635\u0627\u0644\u062D / Invalid JSON / Ung\u00FCltiges JSON");
        return;
      }
    }
    try {
      await Api.updateStageContent(stageId, { content, translations });
      overlay.remove();
      await loadStages(state.currentLessonId);
    } catch (e) {
      showError(t("error_generic"));
    }
  });
}

function collectTranslations(overlay, fields) {
  const translations = {};
  LOCALES.forEach((loc) => {
    translations[loc.code] = {};
    fields.forEach((field) => {
      const input = overlay.querySelector('[data-locale="' + loc.code + '"][data-field="' + field + '"]');
      translations[loc.code][field] = input ? input.value : "";
    });
  });
  return translations;
}

// ----------------------------------------------------------------
// Utilities
// ----------------------------------------------------------------
function escapeHtml(str) {
  if (str == null) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}
function escapeAttr(str) {
  return escapeHtml(str).replace(/"/g, "&quot;");
}

document.addEventListener("DOMContentLoaded", init);
