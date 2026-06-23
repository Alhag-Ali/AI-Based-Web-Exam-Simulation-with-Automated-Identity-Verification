from django.urls import path
from .views import LoginView, ExamListView, JoinExamView, ExamQuestionsView, verify_identity, extract_matrikel, request_manual_check, upload_exam_questions, upload_pdf_and_generate_questions, get_exam_questions_for_professor, save_exam_questions, professor_dashboard, exam_enrollments, exam_enrollment_detail
from .learning_views import (
    upload_lecture_slide, create_learning_plan, list_learning_plans,
    get_learning_plan, list_lecture_slides,
    generate_flashcards, get_flashcards, mark_flashcard,
    get_quiz, generate_quiz, generate_mock_exam, get_mock_exam,
    generate_all_content, delete_learning_plan,
)
from .rag_views import rag_generate_questions

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
    path('extract-matrikel/', extract_matrikel, name='extract_matrikel'),
    path('help-request/', request_manual_check, name='help_request'),

    path('learn/slides/', list_lecture_slides, name='learn-slides'),
    path('learn/upload/', upload_lecture_slide, name='learn-upload'),
    path('learn/plans/', list_learning_plans, name='learn-plans'),
    path('learn/plans/<int:plan_id>/', get_learning_plan, name='learn-plan-detail'),
    path('learn/plans/<int:plan_id>/delete/', delete_learning_plan, name='learn-plan-delete'),
    path('learn/slides/<int:slide_id>/create-plan/', create_learning_plan, name='learn-create-plan'),
    path('learn/topics/<int:topic_id>/flashcards/', get_flashcards, name='learn-flashcards-get'),
    path('learn/topics/<int:topic_id>/flashcards/generate/', generate_flashcards, name='learn-flashcards-generate'),
    path('learn/flashcards/<int:card_id>/mark/', mark_flashcard, name='learn-flashcard-mark'),
    path('learn/topics/<int:topic_id>/quiz/', get_quiz, name='learn-quiz-get'),
    path('learn/topics/<int:topic_id>/quiz/generate/', generate_quiz, name='learn-quiz-generate'),
    path('learn/plans/<int:plan_id>/mock-exam/', get_mock_exam, name='learn-mock-exam-get'),
    path('learn/plans/<int:plan_id>/mock-exam/generate/', generate_mock_exam, name='learn-mock-exam-generate'),
    path('learn/plans/<int:plan_id>/generate-all/', generate_all_content, name='learn-generate-all'),

    path('exams/<int:exam_id>/rag-generate/', rag_generate_questions, name='rag-generate-questions'),
    path('professor/dashboard/', professor_dashboard, name='professor-dashboard'),
    path('exams/<int:exam_id>/enrollments/', exam_enrollments, name='exam-enrollments'),
    path('exams/<int:exam_id>/enrollments/<str:matrikel>/', exam_enrollment_detail, name='exam-enrollment-detail'),
]
