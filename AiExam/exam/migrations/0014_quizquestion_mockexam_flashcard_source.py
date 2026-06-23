from django.db import migrations


def apply_changes(apps, schema_editor):
    with schema_editor.connection.cursor() as cursor:
        cursor.execute("PRAGMA table_info(exam_flashcard)")
        cols = [r[1] for r in cursor.fetchall()]
        if cols and 'source' not in cols:
            cursor.execute(
                "ALTER TABLE exam_flashcard ADD COLUMN source VARCHAR(20) NOT NULL DEFAULT 'rule'"
            )

        cursor.execute("PRAGMA table_info(exam_quizquestion)")
        if not cursor.fetchall():
            cursor.execute("""
                CREATE TABLE exam_quizquestion (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    topic_id INTEGER NOT NULL REFERENCES exam_learningtopic(id)
                                DEFERRABLE INITIALLY DEFERRED,
                    text TEXT NOT NULL,
                    options TEXT NOT NULL DEFAULT '[]',
                    answer TEXT NOT NULL DEFAULT '',
                    "order" INTEGER NOT NULL DEFAULT 0
                )
            """)

        cursor.execute("PRAGMA table_info(exam_mockexam)")
        if not cursor.fetchall():
            cursor.execute("""
                CREATE TABLE exam_mockexam (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    plan_id INTEGER NOT NULL REFERENCES exam_learningplan(id)
                                DEFERRABLE INITIALLY DEFERRED,
                    title VARCHAR(200) NOT NULL,
                    duration_minutes INTEGER NOT NULL DEFAULT 30,
                    questions TEXT NOT NULL DEFAULT '[]',
                    created_at DATETIME NOT NULL
                )
            """)


class Migration(migrations.Migration):

    dependencies = [
        ('exam', '0013_add_flashcard'),
    ]

    operations = [
        migrations.RunPython(apply_changes, migrations.RunPython.noop),
    ]
