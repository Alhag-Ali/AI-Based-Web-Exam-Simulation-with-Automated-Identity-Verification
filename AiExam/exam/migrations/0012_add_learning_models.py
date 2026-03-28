from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def create_tables(apps, schema_editor):
    with schema_editor.connection.cursor() as cursor:
        cursor.execute("PRAGMA table_info(exam_lectureslide)")
        if not cursor.fetchall():
            cursor.execute("""
                CREATE TABLE exam_lectureslide (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id INTEGER NOT NULL REFERENCES exam_student(id) DEFERRABLE INITIALLY DEFERRED,
                    title VARCHAR(200) NOT NULL,
                    file_name VARCHAR(255) NOT NULL,
                    text_content TEXT NOT NULL DEFAULT '',
                    page_count INTEGER NOT NULL DEFAULT 0,
                    status VARCHAR(20) NOT NULL DEFAULT 'processing',
                    created_at DATETIME NOT NULL
                )
            """)

        cursor.execute("PRAGMA table_info(exam_learningplan)")
        if not cursor.fetchall():
            cursor.execute("""
                CREATE TABLE exam_learningplan (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id INTEGER NOT NULL REFERENCES exam_student(id) DEFERRABLE INITIALLY DEFERRED,
                    slide_id INTEGER NOT NULL REFERENCES exam_lectureslide(id) DEFERRABLE INITIALLY DEFERRED,
                    title VARCHAR(200) NOT NULL,
                    created_at DATETIME NOT NULL
                )
            """)

        cursor.execute("PRAGMA table_info(exam_learningtopic)")
        existing = cursor.fetchall()
        existing_cols = [r[1] for r in existing]

        if not existing:
            cursor.execute("""
                CREATE TABLE exam_learningtopic (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    plan_id INTEGER NOT NULL REFERENCES exam_learningplan(id) DEFERRABLE INITIALLY DEFERRED,
                    title VARCHAR(300) NOT NULL,
                    summary TEXT NOT NULL DEFAULT '',
                    key_concepts TEXT NOT NULL DEFAULT '[]',
                    raw_text TEXT NOT NULL DEFAULT '',
                    "order" INTEGER NOT NULL DEFAULT 0,
                    status VARCHAR(20) NOT NULL DEFAULT 'open'
                )
            """)
        else:
            needed = {
                'plan_id': 'INTEGER NOT NULL DEFAULT 0',
                'summary': "TEXT NOT NULL DEFAULT ''",
                'key_concepts': "TEXT NOT NULL DEFAULT '[]'",
                'raw_text': "TEXT NOT NULL DEFAULT ''",
                'status': "VARCHAR(20) NOT NULL DEFAULT 'open'",
            }
            for col, definition in needed.items():
                if col not in existing_cols:
                    cursor.execute(f'ALTER TABLE exam_learningtopic ADD COLUMN {col} {definition}')


class Migration(migrations.Migration):

    dependencies = [
        ('exam', '0011_add_duration_minutes_column'),
    ]

    operations = [
        migrations.RunPython(create_tables, migrations.RunPython.noop),
    ]
