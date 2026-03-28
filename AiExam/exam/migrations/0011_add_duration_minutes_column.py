from django.db import migrations


def add_duration_minutes_column(apps, schema_editor):
    with schema_editor.connection.cursor() as cursor:
        cursor.execute("PRAGMA table_info(exam_exam)")
        columns = [row[1] for row in cursor.fetchall()]
        if "duration_minutes" not in columns:
            cursor.execute(
                "ALTER TABLE exam_exam ADD COLUMN duration_minutes INTEGER NOT NULL DEFAULT 60"
            )


class Migration(migrations.Migration):
    dependencies = [
        ("exam", "0010_add_created_by_to_exam"),
    ]

    operations = [
        migrations.RunPython(add_duration_minutes_column, migrations.RunPython.noop),
    ]
