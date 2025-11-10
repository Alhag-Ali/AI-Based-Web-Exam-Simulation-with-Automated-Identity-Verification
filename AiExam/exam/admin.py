from django.contrib import admin
from .models import Student, Exam, ExamParticipation

admin.site.register(Student)
admin.site.register(Exam)
admin.site.register(ExamParticipation)

