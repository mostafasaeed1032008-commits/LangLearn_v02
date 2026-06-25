#!/usr/bin/env python3
"""
app.py — Backend API for the Language Learning System.

Run locally with:
    python app.py

Then open frontend/index.html in your browser (it talks to
http://localhost:5050 by default — see frontend/js/config.js).

This API is read+write: it lets the browser UI both BROWSE the
existing Level/Unit/Lesson/Stage structure and ADD new content
(new units, lessons, stage content) directly into the SQLite DB.
"""

import json
import os
import sqlite3

from flask import Flask, g, jsonify, request
from flask_cors import CORS

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "langlearn.db")
LOCALES = ("ar", "de", "en")
STAGE_KEYS = [
    "new_sounds", "new_vocabulary", "new_structures", "reading",
    "listening", "speaking", "writing", "grammar_discovery",
    "grammar_explanation", "final_task", "assessment",
]

app = Flask(__name__)
CORS(app)


# ----------------------------------------------------------------
# DB connection helpers
# ----------------------------------------------------------------
def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(exception=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def rows_to_translations(rows, text_cols):
    """Pivot a list of *_translations rows into {locale: {col: val}}."""
    out = {}
    for r in rows:
        out[r["locale"]] = {c: r[c] for c in text_cols}
    return out


def require_fields(payload, fields):
    missing = [f for f in fields if f not in payload]
    if missing:
        raise ValueError(f"Missing required fields: {missing}")


# ----------------------------------------------------------------
# Health / meta
# ----------------------------------------------------------------
@app.get("/api/health")
def health():
    return jsonify({"status": "ok"})


@app.get("/api/locales")
def get_locales():
    db = get_db()
    rows = db.execute("SELECT code, name_native, direction FROM locales").fetchall()
    return jsonify([dict(r) for r in rows])


# ----------------------------------------------------------------
# Courses
# ----------------------------------------------------------------
@app.get("/api/courses")
def list_courses():
    db = get_db()
    courses = db.execute("SELECT * FROM courses ORDER BY id").fetchall()
    result = []
    for c in courses:
        tr = db.execute(
            "SELECT * FROM course_translations WHERE course_id = ?", (c["id"],)
        ).fetchall()
        result.append({
            **dict(c),
            "translations": rows_to_translations(tr, ["name", "description"]),
        })
    return jsonify(result)


@app.post("/api/courses")
def create_course():
    payload = request.get_json(force=True)
    try:
        require_fields(payload, ["code", "target_language_code", "translations"])
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    db = get_db()
    cur = db.execute(
        """INSERT INTO courses (code, target_language_code, cefr_framework_version, is_active)
           VALUES (?, ?, ?, ?)""",
        (
            payload["code"],
            payload["target_language_code"],
            payload.get("cefr_framework_version", "2020"),
            1 if payload.get("is_active", True) else 0,
        ),
    )
    course_id = cur.lastrowid
    for locale in LOCALES:
        t = payload["translations"].get(locale, {})
        db.execute(
            "INSERT INTO course_translations (course_id, locale, name, description) VALUES (?, ?, ?, ?)",
            (course_id, locale, t.get("name", ""), t.get("description", "")),
        )
    db.commit()
    return jsonify({"id": course_id}), 201


# ----------------------------------------------------------------
# Levels
# ----------------------------------------------------------------
@app.get("/api/courses/<int:course_id>/levels")
def list_levels(course_id):
    db = get_db()
    levels = db.execute(
        "SELECT * FROM levels WHERE course_id = ? ORDER BY sort_order", (course_id,)
    ).fetchall()
    result = []
    for lv in levels:
        tr = db.execute(
            "SELECT * FROM level_translations WHERE level_id = ?", (lv["id"],)
        ).fetchall()
        unit_count = db.execute(
            "SELECT COUNT(*) AS n FROM units WHERE level_id = ?", (lv["id"],)
        ).fetchone()["n"]
        result.append({
            **dict(lv),
            "unit_count": unit_count,
            "translations": rows_to_translations(tr, ["name", "description"]),
        })
    return jsonify(result)


@app.get("/api/levels/<int:level_id>/cefr-reference")
def get_level_cefr_reference(level_id):
    db = get_db()
    rows = db.execute(
        "SELECT * FROM level_cefr_reference WHERE level_id = ?", (level_id,)
    ).fetchall()
    out = {}
    for r in rows:
        out.setdefault(r["source_document"], {}).setdefault(r["locale"], {})[r["skill"]] = r["can_do_text"]
    return jsonify(out)


# ----------------------------------------------------------------
# Units
# ----------------------------------------------------------------
@app.get("/api/levels/<int:level_id>/units")
def list_units(level_id):
    db = get_db()
    units = db.execute(
        "SELECT * FROM units WHERE level_id = ? ORDER BY sort_order", (level_id,)
    ).fetchall()
    result = []
    for u in units:
        tr = db.execute(
            "SELECT * FROM unit_translations WHERE unit_id = ?", (u["id"],)
        ).fetchall()
        lesson_count = db.execute(
            "SELECT COUNT(*) AS n FROM lessons WHERE unit_id = ?", (u["id"],)
        ).fetchone()["n"]
        result.append({
            **dict(u),
            "lesson_count": lesson_count,
            "translations": rows_to_translations(
                tr, ["title", "communicative_objective", "description"]
            ),
        })
    return jsonify(result)


@app.post("/api/levels/<int:level_id>/units")
def create_unit(level_id):
    payload = request.get_json(force=True)
    try:
        require_fields(payload, ["translations"])
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    db = get_db()
    max_order = db.execute(
        "SELECT COALESCE(MAX(sort_order), 0) AS m FROM units WHERE level_id = ?", (level_id,)
    ).fetchone()["m"]
    sort_order = payload.get("sort_order", max_order + 1)

    cur = db.execute(
        "INSERT INTO units (level_id, sort_order, is_locked) VALUES (?, ?, ?)",
        (level_id, sort_order, 1 if payload.get("is_locked", True) else 0),
    )
    unit_id = cur.lastrowid
    for locale in LOCALES:
        t = payload["translations"].get(locale, {})
        db.execute(
            """INSERT INTO unit_translations
               (unit_id, locale, title, communicative_objective, description)
               VALUES (?, ?, ?, ?, ?)""",
            (unit_id, locale, t.get("title", ""), t.get("communicative_objective", ""), t.get("description", "")),
        )

    mastery = payload.get("mastery_criteria")
    if mastery:
        for locale in LOCALES:
            m = mastery.get(locale, {})
            if m:
                db.execute(
                    """INSERT INTO unit_mastery_criteria (unit_id, locale, criteria_text, min_score_pct)
                       VALUES (?, ?, ?, ?)""",
                    (unit_id, locale, m.get("criteria_text", ""), m.get("min_score_pct", 80)),
                )

    db.commit()
    return jsonify({"id": unit_id, "sort_order": sort_order}), 201


# ----------------------------------------------------------------
# Lessons
# ----------------------------------------------------------------
@app.get("/api/units/<int:unit_id>/lessons")
def list_lessons(unit_id):
    db = get_db()
    lessons = db.execute(
        "SELECT * FROM lessons WHERE unit_id = ? ORDER BY sort_order", (unit_id,)
    ).fetchall()
    result = []
    for l in lessons:
        tr = db.execute(
            "SELECT * FROM lesson_translations WHERE lesson_id = ?", (l["id"],)
        ).fetchall()
        stage_count = db.execute(
            "SELECT COUNT(*) AS n FROM lesson_stages WHERE lesson_id = ?", (l["id"],)
        ).fetchone()["n"]
        filled_count = db.execute(
            "SELECT COUNT(*) AS n FROM lesson_stages WHERE lesson_id = ? AND content_json IS NOT NULL",
            (l["id"],),
        ).fetchone()["n"]
        result.append({
            **dict(l),
            "stage_count": stage_count,
            "stages_with_content": filled_count,
            "translations": rows_to_translations(tr, ["title", "objective"]),
        })
    return jsonify(result)


@app.post("/api/units/<int:unit_id>/lessons")
def create_lesson(unit_id):
    payload = request.get_json(force=True)
    try:
        require_fields(payload, ["translations"])
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    db = get_db()
    max_order = db.execute(
        "SELECT COALESCE(MAX(sort_order), 0) AS m FROM lessons WHERE unit_id = ?", (unit_id,)
    ).fetchone()["m"]
    sort_order = payload.get("sort_order", max_order + 1)

    cur = db.execute(
        "INSERT INTO lessons (unit_id, sort_order, is_locked) VALUES (?, ?, 1)",
        (unit_id, sort_order),
    )
    lesson_id = cur.lastrowid
    for locale in LOCALES:
        t = payload["translations"].get(locale, {})
        db.execute(
            "INSERT INTO lesson_translations (lesson_id, locale, title, objective) VALUES (?, ?, ?, ?)",
            (lesson_id, locale, t.get("title", ""), t.get("objective", "")),
        )

    mastery = payload.get("mastery_criteria")
    if mastery:
        for locale in LOCALES:
            m = mastery.get(locale, {})
            if m:
                db.execute(
                    """INSERT INTO lesson_mastery_criteria (lesson_id, locale, criteria_text, min_score_pct)
                       VALUES (?, ?, ?, ?)""",
                    (lesson_id, locale, m.get("criteria_text", ""), m.get("min_score_pct", 80)),
                )

    # Auto-create the 11 fixed stages (empty translations placeholder),
    # so the lesson always conforms to the Lesson Architecture even
    # before content is authored.
    default_stage_titles = {
        "new_sounds": {"ar": "أصوات جديدة", "de": "Neue Laute", "en": "New Sounds"},
        "new_vocabulary": {"ar": "مفردات جديدة", "de": "Neuer Wortschatz", "en": "New Vocabulary"},
        "new_structures": {"ar": "تراكيب جديدة", "de": "Neue Strukturen", "en": "New Structures"},
        "reading": {"ar": "قراءة", "de": "Lesen", "en": "Reading"},
        "listening": {"ar": "استماع", "de": "Hören", "en": "Listening"},
        "speaking": {"ar": "محادثة", "de": "Sprechen", "en": "Speaking"},
        "writing": {"ar": "كتابة", "de": "Schreiben", "en": "Writing"},
        "grammar_discovery": {"ar": "استكشاف القاعدة", "de": "Grammatik entdecken", "en": "Grammar Discovery"},
        "grammar_explanation": {"ar": "شرح القاعدة", "de": "Grammatikerklärung", "en": "Grammar Explanation"},
        "final_task": {"ar": "المهمة النهائية", "de": "Abschlussaufgabe", "en": "Final Task"},
        "assessment": {"ar": "تقييم", "de": "Bewertung", "en": "Assessment"},
    }
    default_skills = {
        "new_sounds": ["listening"], "new_vocabulary": ["reading", "listening"],
        "new_structures": ["reading"], "reading": ["reading"], "listening": ["listening"],
        "speaking": ["speaking"], "writing": ["writing"], "grammar_discovery": ["reading"],
        "grammar_explanation": ["reading"], "final_task": ["speaking", "writing"],
        "assessment": ["listening", "reading", "speaking", "writing"],
    }
    for i, stage_key in enumerate(STAGE_KEYS, start=1):
        cur2 = db.execute(
            "INSERT INTO lesson_stages (lesson_id, stage_key, sort_order, content_json) VALUES (?, ?, ?, NULL)",
            (lesson_id, stage_key, i),
        )
        stage_id = cur2.lastrowid
        for locale in LOCALES:
            db.execute(
                "INSERT INTO lesson_stage_translations (lesson_stage_id, locale, title, instructions) VALUES (?, ?, ?, ?)",
                (stage_id, locale, default_stage_titles[stage_key][locale], ""),
            )
        for skill in default_skills[stage_key]:
            db.execute(
                "INSERT OR IGNORE INTO lesson_stage_skills (lesson_stage_id, skill_code) VALUES (?, ?)",
                (stage_id, skill),
            )

    db.commit()
    return jsonify({"id": lesson_id, "sort_order": sort_order}), 201


# ----------------------------------------------------------------
# Lesson stages (the actual content slots)
# ----------------------------------------------------------------
@app.get("/api/lessons/<int:lesson_id>/stages")
def list_stages(lesson_id):
    db = get_db()
    stages = db.execute(
        "SELECT * FROM lesson_stages WHERE lesson_id = ? ORDER BY sort_order", (lesson_id,)
    ).fetchall()
    result = []
    for s in stages:
        tr = db.execute(
            "SELECT * FROM lesson_stage_translations WHERE lesson_stage_id = ?", (s["id"],)
        ).fetchall()
        skills = [
            r["skill_code"] for r in db.execute(
                "SELECT skill_code FROM lesson_stage_skills WHERE lesson_stage_id = ?", (s["id"],)
            ).fetchall()
        ]
        result.append({
            "id": s["id"],
            "lesson_id": s["lesson_id"],
            "stage_key": s["stage_key"],
            "sort_order": s["sort_order"],
            "content": json.loads(s["content_json"]) if s["content_json"] else None,
            "skills": skills,
            "translations": rows_to_translations(tr, ["title", "instructions"]),
        })
    return jsonify(result)


@app.put("/api/stages/<int:stage_id>/content")
def update_stage_content(stage_id):
    """
    Update the authored content of a single stage. This is the main
    endpoint used once you start authoring real lesson content.
    Body: { "content": {...any JSON...}, "translations": {...optional...} }
    """
    payload = request.get_json(force=True)
    db = get_db()

    if "content" in payload:
        content_json = json.dumps(payload["content"], ensure_ascii=False) if payload["content"] is not None else None
        db.execute(
            "UPDATE lesson_stages SET content_json = ? WHERE id = ?",
            (content_json, stage_id),
        )

    if "translations" in payload:
        for locale, t in payload["translations"].items():
            db.execute(
                """INSERT INTO lesson_stage_translations (lesson_stage_id, locale, title, instructions)
                   VALUES (?, ?, ?, ?)
                   ON CONFLICT(lesson_stage_id, locale)
                   DO UPDATE SET title = excluded.title, instructions = excluded.instructions""",
                (stage_id, locale, t.get("title", ""), t.get("instructions", "")),
            )

    db.commit()
    return jsonify({"ok": True})


# ----------------------------------------------------------------
# Breadcrumb / full-path helper (for the frontend header trail)
# ----------------------------------------------------------------
@app.get("/api/breadcrumb/lesson/<int:lesson_id>")
def breadcrumb_lesson(lesson_id):
    db = get_db()
    row = db.execute(
        """SELECT l.id AS lesson_id, u.id AS unit_id, lv.id AS level_id, c.id AS course_id
           FROM lessons l
           JOIN units u ON u.id = l.unit_id
           JOIN levels lv ON lv.id = u.level_id
           JOIN courses c ON c.id = lv.course_id
           WHERE l.id = ?""",
        (lesson_id,),
    ).fetchone()
    return jsonify(dict(row)) if row else (jsonify({"error": "not found"}), 404)


if __name__ == "__main__":
    if not os.path.exists(DB_PATH):
        print(f"[!] No database found at {DB_PATH}.")
        print("    Run `python build_db.py` first to create it from data/.")
    debug_mode = os.environ.get("FLASK_DEBUG", "0") == "1"
    app.run(host="0.0.0.0", port=5050, debug=debug_mode)
