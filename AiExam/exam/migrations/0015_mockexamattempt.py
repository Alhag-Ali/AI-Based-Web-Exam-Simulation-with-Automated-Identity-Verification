from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings


def create_mockexamattempt_table(apps, schema_editor):
    with schema_editor.connection.cursor() as cursor:
        cursor.execute("PRAGMA table_info(exam_mockexamattempt)")
        if not cursor.fetchall():
            cursor.execute("""
                CREATE TABLE exam_mockexamattempt (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id INTEGER NOT NULL REFERENCES exam_student(id)
                                DEFERRABLE INITIALLY DEFERRED,
                    mock_exam_id INTEGER NOT NULL REFERENCES exam_mockexam(id)
                                DEFERRABLE INITIALLY DEFERRED,
                    correct INTEGER NOT NULL DEFAULT 0,
                    total INTEGER NOT NULL DEFAULT 0,
                    score_pct INTEGER NOT NULL DEFAULT 0,
                    completed_at DATETIME NOT NULL
                )
            """)


class Migration(migrations.Migration):

    dependencies = [
        ('exam', '0014_quizquestion_mockexam_flashcard_source'),
    ]

    operations = [
        migrations.RunPython(create_mockexamattempt_table, migrations.RunPython.noop),
    ]
