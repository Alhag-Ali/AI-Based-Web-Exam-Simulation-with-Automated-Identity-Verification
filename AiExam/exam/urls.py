from django.urls import path
from .views import LoginView, ExamListView, JoinExamView, verify_identity



urlpatterns = [
    path('login/', LoginView.as_view(), name='login'),
    path('exams/', ExamListView.as_view(), name='exam-list'),
    path('exams/<int:exam_id>/join/', JoinExamView.as_view(), name='join-exam'),
    path('verify-identity/', verify_identity, name='verify_identity'),


]
