from django.urls import path
from .views import LoginView, ExamListView, JoinExamView, ExamQuestionsView, verify_identity, request_manual_check, upload_exam_questions, upload_pdf_and_generate_questions, get_exam_questions_for_professor, save_exam_questions
from .learning_views import upload_lecture_slide, create_learning_plan, list_learning_plans, get_learning_plan, list_lecture_slides

urlpatterns = [
    path('login/', LoginView.as_view(), name='login'),
    path('exams/', ExamListView.as_view(), name='exam-list'),
    path('exams/<int:exam_id>/join/', JoinExamView.as_view(), name='join-exam'),
    path('exams/<int:exam_id>/questions/', ExamQuestionsView.as_view(), name='exam-questions'),
    path('exams/<int:exam_id>/questions/professor/', get_exam_questions_for_professor, name='exam-questions-professor'),
    path('exams/<int:exam_id>/questions/save/', save_exam_questions, name='save-exam-questions'),
    path('exams/<int:exam_id>/upload-questions/', upload_exam_questions, name='upload-exam-questions'),
    path('exams/<int:exam_id>/upload-pdf/', upload_pdf_and_generate_questions, name='upload-pdf'),
    path('verify-identity/', verify_identity, name='verify_identity'),
    path('help-request/', request_manual_check, name='help_request'),

    path('learn/slides/', list_lecture_slides, name='learn-slides'),
    path('learn/upload/', upload_lecture_slide, name='learn-upload'),
    path('learn/plans/', list_learning_plans, name='learn-plans'),
    path('learn/plans/<int:plan_id>/', get_learning_plan, name='learn-plan-detail'),
    path('learn/slides/<int:slide_id>/create-plan/', create_learning_plan, name='learn-create-plan'),
]
