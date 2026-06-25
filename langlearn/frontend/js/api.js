// frontend/js/api.js
// Thin wrapper around fetch() for the backend API.

const Api = {
  async _get(path) {
    const res = await fetch(`${API_BASE}${path}`);
    if (!res.ok) throw new Error(`GET ${path} failed: ${res.status}`);
    return res.json();
  },
  async _post(path, body) {
    const res = await fetch(`${API_BASE}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!res.ok) throw new Error(`POST ${path} failed: ${res.status}`);
    return res.json();
  },
  async _put(path, body) {
    const res = await fetch(`${API_BASE}${path}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!res.ok) throw new Error(`PUT ${path} failed: ${res.status}`);
    return res.json();
  },

  health: () => Api._get("/health"),
  listCourses: () => Api._get("/courses"),
  listLevels: (courseId) => Api._get(`/courses/${courseId}/levels`),
  cefrReference: (levelId) => Api._get(`/levels/${levelId}/cefr-reference`),
  listUnits: (levelId) => Api._get(`/levels/${levelId}/units`),
  createUnit: (levelId, payload) => Api._post(`/levels/${levelId}/units`, payload),
  listLessons: (unitId) => Api._get(`/units/${unitId}/lessons`),
  createLesson: (unitId, payload) => Api._post(`/units/${unitId}/lessons`, payload),
  listStages: (lessonId) => Api._get(`/lessons/${lessonId}/stages`),
  updateStageContent: (stageId, payload) => Api._put(`/stages/${stageId}/content`, payload),
};
