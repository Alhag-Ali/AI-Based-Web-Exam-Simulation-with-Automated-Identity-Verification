from django.contrib import admin
from .models import User, Teature, Student, Exam, SubjectExam

admin.site.register(User)
admin.site.register(Teature)
admin.site.register(Student)
admin.site.register(Exam)
admin.site.register(SubjectExam)

# Register your models here.
