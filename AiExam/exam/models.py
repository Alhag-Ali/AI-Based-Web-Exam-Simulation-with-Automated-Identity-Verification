from django.db import models
from django.core.validators import MaxValueValidator, MinValueValidator
from django.contrib.auth.models import User

class User(models.Model):
    id = models.AutoField(primary_key=True)
    email = models.EmailField()
    roll = models.CharField(max_length=10)

class Teature(models.Model):
    id = models.AutoField(primary_key=True)
    user_id = models.ForeignKey(User, on_delete=models.CASCADE, blank=True, null=True)
    name = models.CharField()
    family_name = models.CharField()
    subject = models.CharField()
    
class Student(models.Model):
    id = models.AutoField(primary_key=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, blank=True, null=True) 
    name = models.CharField(max_length=100) 
    family_name = models.CharField(max_length=100) 

    def __str__(self):
        return f"{self.name} {self.family_name} {self.id}"
    
class Exam(models.Model):
    id = models.AutoField(primary_key=True)
    student_name = models.CharField()
    student = models.ForeignKey(Student, on_delete=models.CASCADE, null=True, blank=True)
    upload_at = models.DateTimeField(auto_now=True)
    grad = models.IntegerField(
        validators=[MaxValueValidator(100), MinValueValidator(0)])
    exam = models.FileField(upload_to="./uploads/json", null=True, blank=True)
    
class SubjectExam(models.Model):
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=50)
    upload_at = models.DateTimeField(auto_now=True)
    exam_datetime = models.DateTimeField()
    exam = models.FileField(upload_to="./uploads/exams", null=True, blank=True)
    
    def __str__(self):
        return f"{self.id} {self.name} {self.exam_datetime}"
    
    
    
    
    

