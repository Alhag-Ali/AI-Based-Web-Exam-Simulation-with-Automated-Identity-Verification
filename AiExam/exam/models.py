from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.conf import settings


class StudentManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("Email muss angegeben werden")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        return self.create_user(email, password, **extra_fields)

class Student(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(unique=True)
    first_name = models.CharField(max_length=50)
    last_name = models.CharField(max_length=50)
    matriculation_number = models.CharField(max_length=20, unique=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    objects = StudentManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name', 'last_name', 'matriculation_number']

    def __str__(self):
        return self.email

 
class Exam(models.Model):
    title = models.CharField(max_length=100)
    date = models.DateTimeField()
    description = models.TextField(blank=True)
    duration_minutes = models.IntegerField(default=60, help_text="Prüfungsdauer in Minuten")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_exams'
    )
    created_at = models.DateTimeField(auto_now_add=True, null=True)

    def __str__(self):
        return self.title


class ExamParticipation(models.Model):
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('student', 'exam')

    def __str__(self):
        return f"{self.student.email} → {self.exam.title}"


class LectureSlide(models.Model):
    STATUS_CHOICES = [
        ('processing', 'Processing'),
        ('ready', 'Ready'),
        ('failed', 'Failed'),
    ]

    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='lecture_slides'
    )
    title = models.CharField(max_length=200)
    file_name = models.CharField(max_length=255)
    text_content = models.TextField(blank=True)
    page_count = models.IntegerField(default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='processing')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.student.email} — {self.title}"


class LearningPlan(models.Model):
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='learning_plans'
    )
    slide = models.ForeignKey(LectureSlide, on_delete=models.CASCADE, related_name='plans')
    title = models.CharField(max_length=200)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.student.email} — {self.title}"


class LearningTopic(models.Model):
    STATUS_CHOICES = [
        ('open', 'Open'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
    ]

    plan = models.ForeignKey(LearningPlan, on_delete=models.CASCADE, related_name='topics')
    title = models.CharField(max_length=300)
    summary = models.TextField(blank=True)
    key_concepts = models.JSONField(default=list)
    raw_text = models.TextField(blank=True)
    order = models.IntegerField(default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='open')

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"{self.plan.title} — Topic {self.order}: {self.title}"


class Flashcard(models.Model):
    topic = models.ForeignKey(LearningTopic, on_delete=models.CASCADE, related_name='flashcards')
    question = models.TextField()
    answer = models.TextField()
    order = models.IntegerField(default=0)
    known = models.BooleanField(default=False)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"[{self.topic.title}] {self.question[:60]}"
