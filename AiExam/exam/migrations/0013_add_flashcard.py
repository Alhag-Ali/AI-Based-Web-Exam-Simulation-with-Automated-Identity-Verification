from django.db import migrations


def create_flashcard_table(apps, schema_editor):
    with schema_editor.connection.cursor() as cursor:
        cursor.execute("PRAGMA table_info(exam_flashcard)")
        if not cursor.fetchall():
            cursor.execute("""
                CREATE TABLE exam_flashcard (
                    id      INTEGER PRIMARY KEY AUTOINCREMENT,
                    topic_id INTEGER NOT NULL REFERENCES exam_learningtopic(id)
                                DEFERRABLE INITIALLY DEFERRED,
                    question TEXT    NOT NULL,
                    answer   TEXT    NOT NULL,
                    "order"  INTEGER NOT NULL DEFAULT 0,
                    known    BOOLEAN NOT NULL DEFAULT 0
                )
            """)


class Migration(migrations.Migration):

    dependencies = [
        ('exam', '0012_add_learning_models'),
    ]

    operations = [
        migrations.RunPython(create_flashcard_table, migrations.RunPython.noop),
    ]
