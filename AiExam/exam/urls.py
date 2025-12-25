from django.urls import path
from .views import LoginView, ExamListView, JoinExamView, ExamQuestionsView, verify_identity, request_manual_check



urlpatterns = [
    path('login/', LoginView.as_view(), name='login'),
    path('exams/', ExamListView.as_view(), name='exam-list'),
    path('exams/<int:exam_id>/join/', JoinExamView.as_view(), name='join-exam'),
    path('exams/<int:exam_id>/questions/', ExamQuestionsView.as_view(), name='exam-questions'),
    path('verify-identity/', verify_identity, name='verify_identity'),
    path('help-request/', request_manual_check, name='help_request'),


]
