from django.utils import timezone
from django.db.models import Count, Q
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import (
    Exam, ExamParticipation, LearningPlan, LearningTopic,
    Flashcard, QuizQuestion, MockExam, MockExamAttempt,
)


def _learning_stats_for_student(student):
    plans = LearningPlan.objects.filter(student=student).prefetch_related(
        'topics__flashcards', 'topics__quiz_questions', 'mock_exams'
    )
    topics_total = 0
    topics_completed = 0
    flashcards_total = 0
    flashcards_known = 0
    quiz_total = 0
    mock_exams = 0
    plan_summaries = []
    knowledge_gaps = []

    for plan in plans:
        plan_topics = list(plan.topics.all())
        plan_topic_count = len(plan_topics)
        plan_completed = sum(1 for t in plan_topics if t.status == 'completed')
        plan_fc_total = 0
        plan_fc_known = 0

        for topic in plan_topics:
            topics_total += 1
            if topic.status == 'completed':
                topics_completed += 1
            fc_count = topic.flashcards.count()
            fc_known = topic.flashcards.filter(known=True).count()
            plan_fc_total += fc_count
            plan_fc_known += fc_known
            flashcards_total += fc_count
            flashcards_known += fc_known
            quiz_total += topic.quiz_questions.count()

            if fc_count > 0:
                mastery = round((fc_known / fc_count) * 100)
                if mastery < 70:
                    knowledge_gaps.append({
                        'topic_id': topic.id,
                        'topic_title': topic.title,
                        'plan_title': plan.title,
                        'mastery_pct': mastery,
                        'flashcards_total': fc_count,
                        'flashcards_known': fc_known,
                    })

        mock_exams += plan.mock_exams.count()
        progress = round((plan_completed / plan_topic_count) * 100) if plan_topic_count else 0
        plan_summaries.append({
            'plan_id': plan.id,
            'plan_title': plan.title,
            'slide_title': plan.slide.title,
            'topic_count': plan_topic_count,
            'topics_completed': plan_completed,
            'progress_pct': progress,
            'flashcards_total': plan_fc_total,
            'flashcards_known': plan_fc_known,
        })

    mastery_pct = round((flashcards_known / flashcards_total) * 100) if flashcards_total else 0
    knowledge_gaps.sort(key=lambda g: g['mastery_pct'])

    attempts = MockExamAttempt.objects.filter(student=student).select_related('mock_exam').order_by('-completed_at')[:5]
    recent_attempts = [{
        'mock_exam_id': a.mock_exam_id,
        'title': a.mock_exam.title,
        'score_pct': a.score_pct,
        'correct': a.correct,
        'total': a.total,
        'completed_at': a.completed_at.isoformat(),
    } for a in attempts]

    return {
        'plans_count': len(plan_summaries),
        'topics_total': topics_total,
        'topics_completed': topics_completed,
        'flashcards_total': flashcards_total,
        'flashcards_known': flashcards_known,
        'mastery_pct': mastery_pct,
        'quiz_questions': quiz_total,
        'mock_exams': mock_exams,
        'plans': plan_summaries,
        'knowledge_gaps': knowledge_gaps[:8],
        'recent_mock_attempts': recent_attempts,
    }


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def student_dashboard(request):
    if request.user.is_staff:
        return Response({'error': 'Use professor dashboard.'}, status=403)

    learning = _learning_stats_for_student(request.user)

    participations = ExamParticipation.objects.filter(
        student=request.user
    ).select_related('exam').order_by('-joined_at')
    now = timezone.now()
    joined_exams = []
    upcoming = []
    for p in participations:
        item = {
            'exam_id': p.exam.id,
            'title': p.exam.title,
            'date': p.exam.date.isoformat(),
            'joined_at': p.joined_at.isoformat(),
            'is_past': p.exam.date < now,
        }
        joined_exams.append(item)
        if p.exam.date >= now:
            upcoming.append(item)

    all_exams = Exam.objects.filter(date__gte=now).order_by('date')[:5]
    available = [{
        'exam_id': e.id,
        'title': e.title,
        'date': e.date.isoformat(),
        'duration_minutes': e.duration_minutes,
        'joined': participations.filter(exam=e).exists(),
    } for e in all_exams]

    recommendations = []
    if learning['knowledge_gaps']:
        g = learning['knowledge_gaps'][0]
        recommendations.append(f"Review flashcards: {g['topic_title']} ({g['mastery_pct']}% mastered)")
    if learning['mock_exams'] and not learning['recent_mock_attempts']:
        recommendations.append('Take a mock exam to test your knowledge.')
    if learning['topics_completed'] < learning['topics_total']:
        recommendations.append(f"Complete {learning['topics_total'] - learning['topics_completed']} open topics.")
    if upcoming:
        recommendations.append(f"Upcoming exam: {upcoming[0]['title']}")

    return Response({
        'student': {
            'name': f"{request.user.first_name} {request.user.last_name}".strip(),
            'email': request.user.email,
        },
        'summary': {
            'plans_count': learning['plans_count'],
            'topics_total': learning['topics_total'],
            'topics_completed': learning['topics_completed'],
            'flashcards_total': learning['flashcards_total'],
            'flashcards_known': learning['flashcards_known'],
            'mastery_pct': learning['mastery_pct'],
            'quiz_questions': learning['quiz_questions'],
            'mock_exams': learning['mock_exams'],
            'exams_joined': len(joined_exams),
            'upcoming_exams': len(upcoming),
        },
        'plans': learning['plans'],
        'knowledge_gaps': learning['knowledge_gaps'],
        'recent_mock_attempts': learning['recent_mock_attempts'],
        'joined_exams': joined_exams,
        'upcoming_exams': upcoming,
        'available_exams': available,
        'recommendations': recommendations[:5],
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def save_mock_exam_attempt(request, mock_exam_id):
    try:
        mock = MockExam.objects.select_related('plan').get(id=mock_exam_id, plan__student=request.user)
    except MockExam.DoesNotExist:
        return Response({'error': 'Mock exam not found.'}, status=404)

    correct = int(request.data.get('correct', 0))
    total = int(request.data.get('total', 0))
    score_pct = int(request.data.get('score_pct', 0))
    if total <= 0:
        total = len(mock.questions)
    if score_pct <= 0 and total > 0:
        score_pct = round((correct / total) * 100)

    attempt = MockExamAttempt.objects.create(
        student=request.user,
        mock_exam=mock,
        correct=correct,
        total=total,
        score_pct=score_pct,
    )
    return Response({
        'attempt_id': attempt.id,
        'score_pct': attempt.score_pct,
        'correct': attempt.correct,
        'total': attempt.total,
    }, status=201)


def professor_class_insights(professor):
    """Aggregate learning data for students who joined professor's exams."""
    exam_ids = Exam.objects.filter(created_by=professor).values_list('id', flat=True)
    student_ids = ExamParticipation.objects.filter(
        exam_id__in=exam_ids
    ).values_list('student_id', flat=True).distinct()

    from .models import Student
    students = Student.objects.filter(id__in=student_ids, is_staff=False)

    student_progress = []
    gap_counter = {}

    for student in students:
        stats = _learning_stats_for_student(student)
        joined = ExamParticipation.objects.filter(
            student=student, exam_id__in=exam_ids
        ).select_related('exam')
        exams_joined = [{'exam_id': p.exam.id, 'title': p.exam.title} for p in joined]

        for gap in stats['knowledge_gaps']:
            key = gap['topic_title'][:80]
            if key not in gap_counter:
                gap_counter[key] = {'topic': key, 'students': 0, 'mastery_sum': 0}
            gap_counter[key]['students'] += 1
            gap_counter[key]['mastery_sum'] += gap['mastery_pct']

        student_progress.append({
            'student_id': student.id,
            'name': f"{student.first_name} {student.last_name}".strip(),
            'email': student.email,
            'matriculation_number': student.matriculation_number,
            'exams_joined': exams_joined,
            'learning': {
                'plans_count': stats['plans_count'],
                'mastery_pct': stats['mastery_pct'],
                'topics_completed': stats['topics_completed'],
                'topics_total': stats['topics_total'],
                'flashcards_known': stats['flashcards_known'],
                'flashcards_total': stats['flashcards_total'],
            },
            'knowledge_gaps': stats['knowledge_gaps'][:3],
        })

    knowledge_gaps_aggregate = sorted([
        {
            'topic': v['topic'],
            'students_affected': v['students'],
            'avg_mastery_pct': round(v['mastery_sum'] / v['students']) if v['students'] else 0,
        }
        for v in gap_counter.values()
    ], key=lambda x: -x['students_affected'])[:10]

    masteries = [s['learning']['mastery_pct'] for s in student_progress if s['learning']['flashcards_total'] > 0]
    avg_mastery = round(sum(masteries) / len(masteries)) if masteries else 0

    return {
        'students_tracked': len(student_progress),
        'students_with_learning': sum(1 for s in student_progress if s['learning']['plans_count'] > 0),
        'avg_mastery_pct': avg_mastery,
        'student_progress': student_progress,
        'knowledge_gaps_aggregate': knowledge_gaps_aggregate,
    }
