-- ============================================================
-- Language Learning System — Database Schema
-- Language-independent core + Multilingual (i18n) content layer
-- ============================================================
-- Design principles:
-- 1. The structural tables (course, level, unit, lesson, activity)
--    hold NO language-specific text directly.
-- 2. ALL human-readable text lives in *_translations tables,
--    keyed by (entity_id, locale).
-- 3. "locale" = interface language the text is written in (ar/de/en).
-- 4. "target_language" = the language being learned by the student,
--    set once per course (e.g. a course can teach German, English,
--    Arabic, or any future language) — never hardcoded in logic.
-- ============================================================

PRAGMA foreign_keys = ON;

-- ------------------------------------------------------------
-- 0. Supported interface locales (closed, small set: ar/de/en)
-- ------------------------------------------------------------
CREATE TABLE locales (
    code        TEXT PRIMARY KEY,   -- 'ar' | 'de' | 'en'
    name_native TEXT NOT NULL,      -- 'العربية' / 'Deutsch' / 'English'
    direction   TEXT NOT NULL CHECK (direction IN ('rtl','ltr'))
);

-- ------------------------------------------------------------
-- 1. Courses — one course = one target language track (A1→C2)
--    This is what makes the system language-independent:
--    you can have a "German track", an "English track", etc.
--    all living side-by-side using the same schema.
-- ------------------------------------------------------------
CREATE TABLE courses (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    code                TEXT NOT NULL UNIQUE,   -- e.g. 'de-track', 'en-track'
    target_language_code TEXT NOT NULL,         -- ISO 639-1, e.g. 'de', 'en', 'ar'
    cefr_framework_version TEXT DEFAULT '2020', -- which CEFR edition is referenced
    is_active           INTEGER NOT NULL DEFAULT 1,
    created_at          TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE course_translations (
    course_id   INTEGER NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    locale      TEXT NOT NULL REFERENCES locales(code),
    name        TEXT NOT NULL,            -- "German Track" / "مسار اللغة الألمانية" / "Deutsch-Track"
    description TEXT,
    PRIMARY KEY (course_id, locale)
);

-- ------------------------------------------------------------
-- 2. Levels — A1, A2, B1, B2, C1, C2 (per course)
--    CEFR alignment fields are validation references,
--    pulled from the two CEFR documents provided.
-- ------------------------------------------------------------
CREATE TABLE levels (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    course_id       INTEGER NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    cefr_code       TEXT NOT NULL CHECK (cefr_code IN ('A1','A2','B1','B2','C1','C2')),
    sort_order      INTEGER NOT NULL,     -- 1..6, enforces level sequence
    is_locked       INTEGER NOT NULL DEFAULT 1,  -- mastery-gated: locked until previous level mastered
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (course_id, cefr_code)
);

CREATE TABLE level_translations (
    level_id    INTEGER NOT NULL REFERENCES levels(id) ON DELETE CASCADE,
    locale      TEXT NOT NULL REFERENCES locales(code),
    name        TEXT NOT NULL,           -- "Beginner" / "أساسي" / "Anfänger"
    description TEXT,
    PRIMARY KEY (level_id, locale)
);

-- CEFR validation reference per level (from the two uploaded documents)
-- This is NOT content we invented — it is copied/aligned from the
-- official CEFR Global Scale + Self-Assessment Grid, used to validate
-- that our designed outcomes match the official descriptors.
CREATE TABLE level_cefr_reference (
    level_id        INTEGER NOT NULL REFERENCES levels(id) ON DELETE CASCADE,
    locale          TEXT NOT NULL REFERENCES locales(code),
    source_document TEXT NOT NULL CHECK (source_document IN ('global_scale','self_assessment_grid')),
    skill           TEXT CHECK (skill IN (
                        'overall','listening','reading',
                        'spoken_interaction','spoken_production','writing'
                    )),
    can_do_text     TEXT NOT NULL,        -- verbatim/aligned descriptor text
    PRIMARY KEY (level_id, locale, source_document, skill)
);

-- ------------------------------------------------------------
-- 3. Units — each unit = ONE communicative objective
--    e.g. "Introducing yourself", "Ordering food"
-- ------------------------------------------------------------
CREATE TABLE units (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    level_id        INTEGER NOT NULL REFERENCES levels(id) ON DELETE CASCADE,
    sort_order      INTEGER NOT NULL,
    is_locked       INTEGER NOT NULL DEFAULT 1,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (level_id, sort_order)
);

CREATE TABLE unit_translations (
    unit_id     INTEGER NOT NULL REFERENCES units(id) ON DELETE CASCADE,
    locale      TEXT NOT NULL REFERENCES locales(code),
    title       TEXT NOT NULL,             -- "Ordering food"/"طلب الطعام"/"Essen bestellen"
    communicative_objective TEXT NOT NULL, -- the ONE objective this unit teaches
    description TEXT,
    PRIMARY KEY (unit_id, locale)
);

-- Unit-level mastery check (gate before unlocking next unit)
CREATE TABLE unit_mastery_criteria (
    unit_id         INTEGER NOT NULL REFERENCES units(id) ON DELETE CASCADE,
    locale          TEXT NOT NULL REFERENCES locales(code),
    criteria_text   TEXT NOT NULL,   -- e.g. "Score >= 80% on unit assessment AND complete all lessons"
    min_score_pct   INTEGER DEFAULT 80,
    PRIMARY KEY (unit_id, locale)
);

-- ------------------------------------------------------------
-- 4. Lessons — fixed internal order per the Lesson Architecture:
--    1 new_sounds 2 new_vocabulary 3 new_structures 4 reading
--    5 listening 6 speaking 7 writing 8 grammar_discovery
--    9 grammar_explanation 10 final_task 11 assessment
-- ------------------------------------------------------------
CREATE TABLE lessons (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    unit_id         INTEGER NOT NULL REFERENCES units(id) ON DELETE CASCADE,
    sort_order      INTEGER NOT NULL,
    is_locked       INTEGER NOT NULL DEFAULT 1,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (unit_id, sort_order)
);

CREATE TABLE lesson_translations (
    lesson_id   INTEGER NOT NULL REFERENCES lessons(id) ON DELETE CASCADE,
    locale      TEXT NOT NULL REFERENCES locales(code),
    title       TEXT NOT NULL,
    objective   TEXT,
    PRIMARY KEY (lesson_id, locale)
);

-- The 11 fixed stages of a lesson, enforced by CHECK + sort_order
CREATE TABLE lesson_stages (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    lesson_id       INTEGER NOT NULL REFERENCES lessons(id) ON DELETE CASCADE,
    stage_key       TEXT NOT NULL CHECK (stage_key IN (
                        'new_sounds','new_vocabulary','new_structures',
                        'reading','listening','speaking','writing',
                        'grammar_discovery','grammar_explanation',
                        'final_task','assessment'
                    )),
    sort_order      INTEGER NOT NULL,   -- 1..11, must follow the fixed architecture
    -- content_ref points to where the actual lesson content (text, audio
    -- script, exercises) will live once authored. Kept generic (JSON blob)
    -- so any content type can be slotted in without a schema migration.
    content_json    TEXT,              -- NULL until content is authored
    UNIQUE (lesson_id, stage_key),
    UNIQUE (lesson_id, sort_order)
);

CREATE TABLE lesson_stage_translations (
    lesson_stage_id INTEGER NOT NULL REFERENCES lesson_stages(id) ON DELETE CASCADE,
    locale          TEXT NOT NULL REFERENCES locales(code),
    title           TEXT NOT NULL,   -- e.g. "New Vocabulary" / "مفردات جديدة" / "Neuer Wortschatz"
    instructions    TEXT,
    PRIMARY KEY (lesson_stage_id, locale)
);

-- ------------------------------------------------------------
-- 5. Mastery checks (lesson-level) — gate before unlocking
--    the next lesson. Mirrors the "progression requires
--    mastery" core principle.
-- ------------------------------------------------------------
CREATE TABLE lesson_mastery_criteria (
    lesson_id       INTEGER NOT NULL REFERENCES lessons(id) ON DELETE CASCADE,
    locale          TEXT NOT NULL REFERENCES locales(code),
    criteria_text   TEXT NOT NULL,
    min_score_pct   INTEGER DEFAULT 80,
    PRIMARY KEY (lesson_id, locale)
);

-- ------------------------------------------------------------
-- 6. Skills taxonomy — every lesson stage maps to one or more
--    of the 4 core skills (listening/reading/speaking/writing)
--    per the Skills Model. This enables reporting/validation
--    ("does every lesson integrate all 4 skills?").
-- ------------------------------------------------------------
CREATE TABLE skills (
    code TEXT PRIMARY KEY CHECK (code IN ('listening','reading','speaking','writing'))
);

CREATE TABLE lesson_stage_skills (
    lesson_stage_id INTEGER NOT NULL REFERENCES lesson_stages(id) ON DELETE CASCADE,
    skill_code      TEXT NOT NULL REFERENCES skills(code),
    PRIMARY KEY (lesson_stage_id, skill_code)
);

-- ------------------------------------------------------------
-- 7. Language model tags — every vocabulary/structure item
--    introduced can be tagged by type, per the Language Model
--    (sounds / vocabulary / structures / grammar).
--    This is a lightweight content-tagging table; actual
--    content payload lives in lesson_stages.content_json.
-- ------------------------------------------------------------
CREATE TABLE language_elements (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    lesson_stage_id INTEGER NOT NULL REFERENCES lesson_stages(id) ON DELETE CASCADE,
    element_type    TEXT NOT NULL CHECK (element_type IN ('sound','vocabulary','structure','grammar')),
    target_text     TEXT,   -- the actual word/structure in the TARGET language
    notes           TEXT
);

CREATE TABLE language_element_translations (
    language_element_id INTEGER NOT NULL REFERENCES language_elements(id) ON DELETE CASCADE,
    locale               TEXT NOT NULL REFERENCES locales(code),
    gloss                TEXT NOT NULL,  -- translation/explanation in that interface locale
    PRIMARY KEY (language_element_id, locale)
);

-- ------------------------------------------------------------
-- 8. Helpful views for the frontend (read convenience)
-- ------------------------------------------------------------
CREATE VIEW v_lesson_full AS
SELECT
    l.id AS lesson_id,
    l.unit_id,
    l.sort_order AS lesson_sort_order,
    lt.locale,
    lt.title,
    lt.objective
FROM lessons l
JOIN lesson_translations lt ON lt.lesson_id = l.id;

CREATE VIEW v_unit_full AS
SELECT
    u.id AS unit_id,
    u.level_id,
    u.sort_order AS unit_sort_order,
    ut.locale,
    ut.title,
    ut.communicative_objective,
    ut.description
FROM units u
JOIN unit_translations ut ON ut.unit_id = u.id;

CREATE VIEW v_level_full AS
SELECT
    lv.id AS level_id,
    lv.course_id,
    lv.cefr_code,
    lv.sort_order AS level_sort_order,
    lvt.locale,
    lvt.name,
    lvt.description
FROM levels lv
JOIN level_translations lvt ON lvt.level_id = lv.id;

-- ------------------------------------------------------------
-- Seed fixed lookup data
-- ------------------------------------------------------------
INSERT INTO locales (code, name_native, direction) VALUES
    ('ar', 'العربية', 'rtl'),
    ('de', 'Deutsch', 'ltr'),
    ('en', 'English', 'ltr');

INSERT INTO skills (code) VALUES
    ('listening'), ('reading'), ('speaking'), ('writing');
