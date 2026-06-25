# بنية ملفات JSON — مصدر البيانات

هذا الفولدر هو **المصدر الحقيقي** لكل محتوى المشروع (Levels / Units / Lessons).
قاعدة بيانات SQLite بيتم بناؤها **منه**، مش العكس — يعني لو عدّلت هنا وشغّلت
`build_db.py`، قاعدة البيانات بتتحدث تلقائيًا.

## الفلسفة

- **كل لغة واجهة (ar/de/en) ليها مكانها الواضح** — مفيش نص لغتين مخبوطين في حقل واحد.
- **كل كورس (مسار لغة) في فولدر مستقل** تحت `courses/` — كده النظام يفضل
  language-independent: تقدر تضيف `en-track` أو `ar-track` بدون أي تغيير في الكود.
- **الترتيب الهرمي مطابق للـ schema**: `course → level → unit → lesson → stage`.

## شكل الفولدرات

```
data/
├── locales.json                  # تعريف اللغات الثابتة (ar/de/en) — لا تتغير
└── courses/
    └── de-track/                # مثال: مسار تعلّم الألمانية
        ├── course.json          # معلومات الكورس + ترجماته
        ├── A1/
        │   ├── level.json       # معلومات المستوى + ترجماته + مرجع CEFR
        │   ├── unit_01/
        │   │   ├── unit.json    # عنوان الوحدة + الهدف التواصلي + ترجماته
        │   │   ├── lesson_01.json
        │   │   ├── lesson_02.json
        │   │   └── ...
        │   ├── unit_02/
        │   │   └── ...
        │   └── ...
        ├── A2/
        ├── B1/
        ├── B2/
        ├── C1/
        └── C2/
```

## مثال لمحتوى `lesson_01.json`

كل Lesson لازم يحتوي على الـ 11 مرحلة بالترتيب الثابت
(`new_sounds → new_vocabulary → new_structures → reading → listening →
speaking → writing → grammar_discovery → grammar_explanation →
final_task → assessment`)، حتى لو المحتوى لسه مش جاهز (`content: null`).

```json
{
  "sort_order": 1,
  "translations": {
    "ar": { "title": "...", "objective": "..." },
    "de": { "title": "...", "objective": "..." },
    "en": { "title": "...", "objective": "..." }
  },
  "mastery_criteria": {
    "ar": { "criteria_text": "...", "min_score_pct": 80 },
    "de": { "criteria_text": "...", "min_score_pct": 80 },
    "en": { "criteria_text": "...", "min_score_pct": 80 }
  },
  "stages": [
    {
      "stage_key": "new_sounds",
      "sort_order": 1,
      "skills": ["listening"],
      "translations": {
        "ar": { "title": "أصوات جديدة", "instructions": "..." },
        "de": { "title": "Neue Laute", "instructions": "..." },
        "en": { "title": "New Sounds", "instructions": "..." }
      },
      "content": null
    },
    { "stage_key": "new_vocabulary", "sort_order": 2, "skills": ["reading","listening"], "translations": {...}, "content": null },
    { "stage_key": "new_structures",  "sort_order": 3, "skills": ["reading"], "translations": {...}, "content": null },
    { "stage_key": "reading",         "sort_order": 4, "skills": ["reading"], "translations": {...}, "content": null },
    { "stage_key": "listening",       "sort_order": 5, "skills": ["listening"], "translations": {...}, "content": null },
    { "stage_key": "speaking",        "sort_order": 6, "skills": ["speaking"], "translations": {...}, "content": null },
    { "stage_key": "writing",         "sort_order": 7, "skills": ["writing"], "translations": {...}, "content": null },
    { "stage_key": "grammar_discovery",    "sort_order": 8,  "skills": ["reading"], "translations": {...}, "content": null },
    { "stage_key": "grammar_explanation",  "sort_order": 9,  "skills": ["reading"], "translations": {...}, "content": null },
    { "stage_key": "final_task",      "sort_order": 10, "skills": ["speaking","writing"], "translations": {...}, "content": null },
    { "stage_key": "assessment",      "sort_order": 11, "skills": ["listening","reading","speaking","writing"], "translations": {...}, "content": null }
  ]
}
```

## مهم

- **content** ممكن يفضل `null` لحد ما تجهز المحتوى الفعلي — البنية مش متوقفة على وجوده.
- لما تجهز محتوى درس، تحط الـ payload جوه `content` بأي شكل JSON يناسب نوع المحتوى
  (نص، قائمة كلمات، تمارين...) — مش محتاج تغيير في الـ schema.
- بعد أي تعديل في ملفات JSON، شغّل: `python build_db.py` لتحديث قاعدة البيانات.
