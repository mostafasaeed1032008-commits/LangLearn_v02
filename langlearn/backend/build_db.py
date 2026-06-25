#!/usr/bin/env python3
"""
build_db.py
============
Builds (or rebuilds) the SQLite database from the JSON source files
in data/. The JSON files are the single source of truth — this script
is idempotent: running it again wipes and rebuilds the DB cleanly.

Usage:
    python build_db.py [--db PATH] [--data PATH]

Folder convention expected under --data:
    locales.json
    courses/<course_code>/course.json
    courses/<course_code>/<CEFR_CODE>/level.json
    courses/<course_code>/<CEFR_CODE>/unit_XX/unit.json
    courses/<course_code>/<CEFR_CODE>/unit_XX/lesson_XX.json
"""

import argparse
import json
import os
import sqlite3
import sys

LEVEL_ORDER = {"A1": 1, "A2": 2, "B1": 3, "B2": 4, "C1": 5, "C2": 6}
LOCALES = ("ar", "de", "en")


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def init_schema(conn, schema_path):
    with open(schema_path, "r", encoding="utf-8") as f:
        conn.executescript(f.read())


def insert_translations(cur, table, id_col, entity_id, translations, columns):
    """
    Generic helper: inserts one row per locale into a *_translations table.
    `columns` = list of JSON keys that map 1:1 to DB columns (order matters).
    """
    for locale in LOCALES:
        if locale not in translations:
            print(f"  [WARN] missing locale '{locale}' for {table} id={entity_id}")
            continue
        values = translations[locale]
        col_values = [values.get(c) for c in columns]
        placeholders = ", ".join(["?"] * (2 + len(columns)))
        col_names = ", ".join([id_col, "locale"] + columns)
        cur.execute(
            f"INSERT INTO {table} ({col_names}) VALUES ({placeholders})",
            [entity_id, locale] + col_values,
        )


def build_locales(conn, data_dir):
    # locales table is already seeded by schema.sql; this just verifies
    # the JSON file matches, for sanity-checking authoring mistakes.
    path = os.path.join(data_dir, "locales.json")
    if not os.path.exists(path):
        return
    declared = {l["code"] for l in load_json(path)}
    if declared != set(LOCALES):
        print(f"  [WARN] locales.json declares {declared}, expected {set(LOCALES)}")


def build_course(conn, course_dir, course_code):
    cur = conn.cursor()
    course = load_json(os.path.join(course_dir, "course.json"))

    cur.execute(
        """INSERT INTO courses (code, target_language_code, cefr_framework_version, is_active)
           VALUES (?, ?, ?, ?)""",
        (
            course["code"],
            course["target_language_code"],
            course.get("cefr_framework_version", "2020"),
            1 if course.get("is_active", True) else 0,
        ),
    )
    course_id = cur.lastrowid
    insert_translations(
        cur, "course_translations", "course_id", course_id,
        course["translations"], ["name", "description"],
    )
    print(f"[OK] Course '{course_code}' -> id={course_id}")
    return course_id


def build_level(conn, level_dir, course_id, cefr_code):
    cur = conn.cursor()
    level = load_json(os.path.join(level_dir, "level.json"))

    cur.execute(
        """INSERT INTO levels (course_id, cefr_code, sort_order, is_locked)
           VALUES (?, ?, ?, ?)""",
        (
            course_id,
            level["cefr_code"],
            level.get("sort_order", LEVEL_ORDER.get(cefr_code, 0)),
            1 if level.get("is_locked", True) else 0,
        ),
    )
    level_id = cur.lastrowid
    insert_translations(
        cur, "level_translations", "level_id", level_id,
        level["translations"], ["name", "description"],
    )

    # CEFR reference rows (validation reference, not generated content)
    ref = level.get("cefr_reference", {})
    for source_doc, by_locale in ref.items():
        if source_doc == "_note":
            continue
        for locale, payload in by_locale.items():
            if isinstance(payload, str):
                # global_scale style: single "overall" string
                cur.execute(
                    """INSERT INTO level_cefr_reference
                       (level_id, locale, source_document, skill, can_do_text)
                       VALUES (?, ?, ?, ?, ?)""",
                    (level_id, locale, source_doc, "overall", payload),
                )
            elif isinstance(payload, dict):
                for skill, text in payload.items():
                    cur.execute(
                        """INSERT INTO level_cefr_reference
                           (level_id, locale, source_document, skill, can_do_text)
                           VALUES (?, ?, ?, ?, ?)""",
                        (level_id, locale, source_doc, skill, text),
                    )
    print(f"  [OK] Level '{cefr_code}' -> id={level_id}")
    return level_id


def build_unit(conn, unit_dir, level_id, sort_order):
    cur = conn.cursor()
    unit = load_json(os.path.join(unit_dir, "unit.json"))

    cur.execute(
        """INSERT INTO units (level_id, sort_order, is_locked) VALUES (?, ?, ?)""",
        (level_id, unit.get("sort_order", sort_order), 1 if unit.get("is_locked", True) else 0),
    )
    unit_id = cur.lastrowid
    insert_translations(
        cur, "unit_translations", "unit_id", unit_id,
        unit["translations"], ["title", "communicative_objective", "description"],
    )
    if "mastery_criteria" in unit:
        insert_translations(
            cur, "unit_mastery_criteria", "unit_id", unit_id,
            unit["mastery_criteria"], ["criteria_text", "min_score_pct"],
        )
    print(f"    [OK] Unit #{sort_order} -> id={unit_id}")
    return unit_id


def build_lesson(conn, lesson_path, unit_id, sort_order):
    cur = conn.cursor()
    lesson = load_json(lesson_path)

    cur.execute(
        """INSERT INTO lessons (unit_id, sort_order, is_locked) VALUES (?, ?, ?)""",
        (unit_id, lesson.get("sort_order", sort_order), 1),
    )
    lesson_id = cur.lastrowid
    insert_translations(
        cur, "lesson_translations", "lesson_id", lesson_id,
        lesson["translations"], ["title", "objective"],
    )
    if "mastery_criteria" in lesson:
        insert_translations(
            cur, "lesson_mastery_criteria", "lesson_id", lesson_id,
            lesson["mastery_criteria"], ["criteria_text", "min_score_pct"],
        )

    for stage in lesson.get("stages", []):
        cur.execute(
            """INSERT INTO lesson_stages (lesson_id, stage_key, sort_order, content_json)
               VALUES (?, ?, ?, ?)""",
            (
                lesson_id,
                stage["stage_key"],
                stage["sort_order"],
                json.dumps(stage["content"], ensure_ascii=False) if stage.get("content") is not None else None,
            ),
        )
        stage_id = cur.lastrowid
        insert_translations(
            cur, "lesson_stage_translations", "lesson_stage_id", stage_id,
            stage["translations"], ["title", "instructions"],
        )
        for skill_code in stage.get("skills", []):
            cur.execute(
                "INSERT OR IGNORE INTO lesson_stage_skills (lesson_stage_id, skill_code) VALUES (?, ?)",
                (stage_id, skill_code),
            )

    print(f"      [OK] Lesson #{sort_order} -> id={lesson_id} ({len(lesson.get('stages', []))} stages)")
    return lesson_id


def build_all(db_path, data_dir, schema_path):
    if os.path.exists(db_path):
        os.remove(db_path)

    conn = sqlite3.connect(db_path)
    init_schema(conn, schema_path)
    build_locales(conn, data_dir)

    courses_dir = os.path.join(data_dir, "courses")
    if not os.path.isdir(courses_dir):
        print(f"[ERROR] No courses/ folder found at {courses_dir}")
        sys.exit(1)

    for course_code in sorted(os.listdir(courses_dir)):
        course_dir = os.path.join(courses_dir, course_code)
        if not os.path.isdir(course_dir):
            continue
        course_id = build_course(conn, course_dir, course_code)

        for cefr_code in sorted(os.listdir(course_dir), key=lambda c: LEVEL_ORDER.get(c, 99)):
            level_dir = os.path.join(course_dir, cefr_code)
            if not os.path.isdir(level_dir) or cefr_code not in LEVEL_ORDER:
                continue
            level_id = build_level(conn, level_dir, course_id, cefr_code)

            unit_folders = sorted(
                d for d in os.listdir(level_dir)
                if os.path.isdir(os.path.join(level_dir, d)) and d.startswith("unit_")
            )
            for u_idx, unit_folder in enumerate(unit_folders, start=1):
                unit_dir = os.path.join(level_dir, unit_folder)
                unit_id = build_unit(conn, unit_dir, level_id, u_idx)

                lesson_files = sorted(
                    f for f in os.listdir(unit_dir)
                    if f.startswith("lesson_") and f.endswith(".json")
                )
                for l_idx, lesson_file in enumerate(lesson_files, start=1):
                    build_lesson(conn, os.path.join(unit_dir, lesson_file), unit_id, l_idx)

    conn.commit()
    conn.close()
    print(f"\n✅ Database built successfully at: {db_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build SQLite DB from JSON source data.")
    parser.add_argument("--db", default=os.path.join(os.path.dirname(__file__), "langlearn.db"))
    parser.add_argument("--data", default=os.path.join(os.path.dirname(__file__), "data"))
    parser.add_argument("--schema", default=os.path.join(os.path.dirname(__file__), "schema.sql"))
    args = parser.parse_args()

    build_all(args.db, args.data, args.schema)
