#!/usr/bin/env python
"""Erstellt Demo-Accounts für Studenten und einen Staff-Account (Professor)."""
import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "AiExam.settings")
django.setup()

from exam.models import Student

def main():
    demo_users = [
        {"email": "student@demo.de", "password": "demo123", "first_name": "Demo", "last_name": "Student", "matriculation_number": "12345678"},
        {"email": "professor@demo.de", "password": "demo123", "first_name": "Demo", "last_name": "Professor", "matriculation_number": "prof001", "is_staff": True},
    ]
    for u in demo_users:
        is_staff = u.pop("is_staff", False)
        if not Student.objects.filter(email=u["email"]).exists():
            user = Student.objects.create_user(**u)
            user.is_staff = is_staff
            user.save()
            print(f"Created: {u['email']} (staff={is_staff})")
        else:
            print(f"Exists: {u['email']}")
    print("Demo accounts ready.")

if __name__ == "__main__":
    main()
