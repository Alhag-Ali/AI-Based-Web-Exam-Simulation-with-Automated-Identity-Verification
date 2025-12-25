from django.urls import path
from .views import LoginView, ExamListView, JoinExamView, ExamQuestionsView, verify_identity, request_manual_check, upload_exam_questions, upload_pdf_and_generate_questions, get_exam_questions_for_professor, save_exam_questions



urlpatterns = [
    path('login/', LoginView.as_view(), name='login'),
    path('exams/', ExamListView.as_view(), name='exam-list'),  # GET: list, POST: create
    path('exams/<int:exam_id>/join/', JoinExamView.as_view(), name='join-exam'),
    path('exams/<int:exam_id>/questions/', ExamQuestionsView.as_view(), name='exam-questions'),  # GET: get questions (for students)
    path('exams/<int:exam_id>/questions/professor/', get_exam_questions_for_professor, name='exam-questions-professor'),  # GET: get questions (for professors)
    path('exams/<int:exam_id>/questions/save/', save_exam_questions, name='save-exam-questions'),  # POST: save questions
    path('exams/<int:exam_id>/upload-questions/', upload_exam_questions, name='upload-exam-questions'),
    path('exams/<int:exam_id>/upload-pdf/', upload_pdf_and_generate_questions, name='upload-pdf'),  # POST: upload PDF
    path('verify-identity/', verify_identity, name='verify_identity'),
    path('help-request/', request_manual_check, name='help_request'),


]
