import os
import re
import json
import uuid
import unicodedata
from datetime import datetime

from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes, parser_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response
from rest_framework import status

from .models import (
    LectureSlide, LearningPlan, LearningTopic, Flashcard,
    QuizQuestion, MockExam,
)


def _fix_umlauts(text):
    text = unicodedata.normalize('NFC', text)
    umlaut_map = {
        '\u00a8a': 'ä', '\u00a8o': 'ö', '\u00a8u': 'ü',
        '\u00a8A': 'Ä', '\u00a8O': 'Ö', '\u00a8U': 'Ü',
        'a\u0308': 'ä', 'o\u0308': 'ö', 'u\u0308': 'ü',
        'A\u0308': 'Ä', 'O\u0308': 'Ö', 'U\u0308': 'Ü',
        '\u0308a': 'ä', '\u0308o': 'ö', '\u0308u': 'ü',
        '\u0308A': 'Ä', '\u0308O': 'Ö', '\u0308U': 'Ü',
        's\u0307s': 'ß', 'S\u0307S': 'ß',
    }
    for bad, good in umlaut_map.items():
        text = text.replace(bad, good)
    return text


def _clean_pdf_text(text):
    text = _fix_umlauts(text)
    lines = text.split('\n')
    result = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            if result and result[-1] != '':
                result.append('')
        else:
            if result and result[-1] != '' and not stripped[0].isupper() and not result[-1].endswith(('.', '!', '?', ':')):
                result[-1] = result[-1] + ' ' + stripped
            else:
                result.append(stripped)
    return '\n'.join(result)


def _extract_text_from_pdf(path):
    from pypdf import PdfReader
    reader = PdfReader(path)
    parts = []
    for page in reader.pages:
        try:
            t = page.extract_text()
            if t and t.strip():
                parts.append(_clean_pdf_text(t.strip()))
        except Exception:
            continue
    return "\n\n".join(parts), len(reader.pages)


def _is_noise_title(title):
    t = title.strip().lower()
    if len(t) < 3:
        return True
    noise = [
        r'^(prof|dr|pd)\.',
        r'sose|wise\s*\d',
        r'^\d{1,2}$',
        r'^(seite|page)\s*\d',
        r'@|\.de$|\.com$',
    ]
    return any(re.search(p, t) for p in noise)


def _dedupe_and_filter_sections(sections):
    merged = {}
    for title, raw_text in sections:
        title = title.strip()[:300]
        raw_text = raw_text.strip()
        if len(raw_text) < 120 or _is_noise_title(title):
            continue
        key = title.lower()
        if key in merged:
            merged[key] = merged[key] + "\n\n" + raw_text
        else:
            merged[key] = raw_text
    return list(merged.items())[:10]


def _split_into_topics(text):
    heading_pattern = re.compile(
        r'^(?:'
        r'(?:\d+[\.\)]\s+[A-ZÜÄÖ].{4,80})'
        r'|(?:[A-ZÜÄÖ][A-ZÜÄÖ\s]{3,60}$)'
        r'|(?:#{1,3}\s+.{3,80})'
        r'|(?:[A-ZÜÄÖ].{3,60}:$)'
        r')$',
        re.MULTILINE
    )

    lines = text.split('\n')
    sections = []
    current_title = None
    current_lines = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        is_heading = (
            heading_pattern.match(stripped)
            or (len(stripped) < 80 and stripped.isupper() and len(stripped) > 4)
            or re.match(r'^(Kapitel|Chapter|Abschnitt|Section|Teil|Part)\s+\d+', stripped, re.IGNORECASE)
            or re.match(r'^\d+\.\s+[A-ZÜÄÖ]', stripped)
        )
        if is_heading and len(current_lines) > 5:
            sections.append((current_title or "Einleitung", "\n".join(current_lines)))
            current_title = stripped
            current_lines = []
        else:
            if current_title is None and not is_heading:
                current_title = "Einleitung"
            current_lines.append(stripped)

    if current_lines:
        sections.append((current_title or "Sonstiges", "\n".join(current_lines)))

    if len(sections) <= 1:
        paragraphs = [p.strip() for p in re.split(r'\n{2,}', text) if len(p.strip()) > 100]
        chunk_size = max(1, len(paragraphs) // 5)
        sections = []
        for i in range(0, len(paragraphs), chunk_size):
            chunk = paragraphs[i:i + chunk_size]
            first_sentence = re.split(r'[.!?]', chunk[0])[0][:60].strip() if chunk else f"Abschnitt {i+1}"
            sections.append((first_sentence or f"Abschnitt {i+1}", "\n\n".join(chunk)))

    return _dedupe_and_filter_sections(sections)


def _make_summary(raw_text):
    sentences = re.split(r'(?<=[.!?])\s+', raw_text.strip())
    meaningful = [s.strip() for s in sentences if len(s.strip()) > 40][:4]
    return " ".join(meaningful)[:600] if meaningful else raw_text[:300]


def _extract_key_concepts(raw_text):
    candidates = re.findall(
        r'\b([A-ZÜÄÖ][a-züäöa-zA-Z\-]{3,30}(?:\s+[A-Za-züäö][a-züäöa-zA-Z\-]{2,20})?)\b',
        raw_text
    )
    freq = {}
    for c in candidates:
        c = c.strip()
        freq[c] = freq.get(c, 0) + 1

    excluded = {'Das', 'Die', 'Der', 'Ein', 'Eine', 'Dieser', 'Diese', 'Dem',
                'Den', 'Des', 'Beim', 'Vom', 'Zum', 'Zur', 'Durch', 'Nach',
                'Auch', 'Aber', 'Oder', 'Und', 'Mit', 'Bei', 'Für', 'Auf',
                'The', 'This', 'That', 'Are', 'For', 'With', 'From', 'Have'}

    top = sorted(
        [(k, v) for k, v in freq.items() if k not in excluded and v >= 2],
        key=lambda x: -x[1]
    )[:8]

    return [k for k, _ in top]


def _get_groq_key(request):
    return request.data.get('groq_api_key') or os.environ.get('GROQ_API_KEY')


def _ai_available(request):
    return bool(_get_groq_key(request))


def _topic_rag_payload(topic):
    return {
        'title': topic.title,
        'raw_text': topic.raw_text or '',
        'summary': topic.summary or '',
        'key_concepts': topic.key_concepts if isinstance(topic.key_concepts, list) else [],
    }


def _generate_flashcards_for_topic(topic, pdf_text, groq_api_key=None, session=None):
    if groq_api_key and pdf_text:
        try:
            from .rag_service import generate_flashcards_for_topic_rag
            payload = _topic_rag_payload(topic)
            cards = generate_flashcards_for_topic_rag(
                pdf_text=pdf_text,
                topic_title=payload['title'],
                summary=payload['summary'],
                key_concepts=payload['key_concepts'],
                count=8,
                groq_api_key=groq_api_key,
                session=session,
            )
            if cards:
                return cards, 'ai'
        except Exception as e:
            print(f"[Learn] RAG flashcards failed for '{topic.title}': {e}")

    cards = _generate_flashcards(topic)
    return (cards, 'rule') if cards else ([], 'rule')


def _generate_quiz_for_topic(topic, pdf_text, groq_api_key=None, n=2, existing=None, session=None):
    if groq_api_key and pdf_text:
        try:
            from .rag_service import generate_questions_for_topic_rag
            payload = _topic_rag_payload(topic)
            qs = generate_questions_for_topic_rag(
                pdf_text=pdf_text,
                topic_title=payload['title'],
                summary=payload['summary'],
                key_concepts=payload['key_concepts'],
                n=n,
                groq_api_key=groq_api_key,
                existing_questions=existing,
                session=session,
            )
            if qs:
                return qs
        except Exception as e:
            print(f"[Learn] RAG quiz failed for '{topic.title}': {e}")
    return []


def _save_flashcards(topic, cards_data, source='rule'):
    Flashcard.objects.filter(topic=topic).delete()
    for j, card in enumerate(cards_data):
        Flashcard.objects.create(
            topic=topic,
            question=card['question'],
            answer=card['answer'],
            order=j,
            known=False,
            source=source,
        )


def _save_quiz_questions(topic, questions_data):
    QuizQuestion.objects.filter(topic=topic).delete()
    for j, q in enumerate(questions_data):
        QuizQuestion.objects.create(
            topic=topic,
            text=q['text'],
            options=q.get('options', []),
            answer=q.get('answer', ''),
            order=j,
        )


def _topic_to_dict(topic):
    return {
        'id': topic.id,
        'title': topic.title,
        'summary': topic.summary,
        'key_concepts': topic.key_concepts,
        'order': topic.order,
        'status': topic.status,
        'flashcard_count': topic.flashcards.count(),
        'quiz_count': topic.quiz_questions.count(),
    }


def _plan_to_dict(plan):
    topics = [_topic_to_dict(t) for t in plan.topics.all()]
    latest_mock = plan.mock_exams.first()
    return {
        'plan_id': plan.id,
        'plan_title': plan.title,
        'slide_title': plan.slide.title,
        'slide_pages': plan.slide.page_count,
        'created_at': plan.created_at.isoformat(),
        'topic_count': len(topics),
        'topics_completed': sum(1 for t in topics if t['status'] == 'completed'),
        'topics': topics,
        'has_mock_exam': latest_mock is not None,
        'mock_exam_id': latest_mock.id if latest_mock else None,
    }


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser, FormParser])
def upload_lecture_slide(request):
    pdf_file = request.FILES.get('pdf_file')
    if not pdf_file:
        return Response({'error': 'No file submitted.'}, status=400)
    if not pdf_file.name.lower().endswith('.pdf'):
        return Response({'error': 'Nur PDF-Dateien werden akzeptiert.'}, status=400)

    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    upload_dir = os.path.join(base_dir, 'uploads', 'slides')
    os.makedirs(upload_dir, exist_ok=True)

    safe_name = f"slide_{request.user.id}_{uuid.uuid4().hex[:8]}.pdf"
    pdf_path = os.path.join(upload_dir, safe_name)
    with open(pdf_path, 'wb+') as f:
        for chunk in pdf_file.chunks():
            f.write(chunk)

    try:
        text, page_count = _extract_text_from_pdf(pdf_path)
    except Exception as e:
        os.remove(pdf_path)
        return Response({'error': f'PDF could not be read: {str(e)}'}, status=400)

    if len(text.strip()) < 80:
        os.remove(pdf_path)
        return Response({'error': 'The PDF contains too little text. Please upload a different file.'}, status=400)

    slide = LectureSlide.objects.create(
        student=request.user,
        title=pdf_file.name.replace('.pdf', '').replace('_', ' ').strip(),
        file_name=safe_name,
        text_content=text,
        page_count=page_count,
        status='ready',
        created_at=timezone.now(),
    )

    return Response({
        'id': slide.id,
        'title': slide.title,
        'page_count': slide.page_count,
        'status': slide.status,
        'text_length': len(text),
    }, status=201)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_learning_plan(request, slide_id):
    try:
        slide = LectureSlide.objects.get(id=slide_id, student=request.user)
    except LectureSlide.DoesNotExist:
        return Response({'error': 'Slide set not found.'}, status=404)

    if slide.status != 'ready':
        return Response({'error': 'Slide set is still being processed.'}, status=400)

    plan = LearningPlan.objects.create(
        student=request.user,
        slide=slide,
        title=f"Lernplan: {slide.title}",
        created_at=timezone.now(),
    )

    sections = _split_into_topics(slide.text_content)
    groq_key = _get_groq_key(request)
    ai_used = bool(groq_key)
    total_quiz = 0

    rag_session = None
    if ai_used:
        try:
            from .rag_service import SlideRAGSession
            rag_session = SlideRAGSession(slide.text_content, groq_key)
        except Exception as e:
            print(f"[Learn] RAG session init failed: {e}")
            rag_session = None

    for i, (title, raw_text) in enumerate(sections):
        summary = _make_summary(raw_text)
        concepts = _extract_key_concepts(raw_text)
        topic = LearningTopic.objects.create(
            plan=plan,
            title=title[:300],
            summary=summary,
            key_concepts=concepts,
            raw_text=raw_text[:8000],
            order=i,
            status='open',
        )
        cards_data, source = _generate_flashcards_for_topic(
            topic, slide.text_content, groq_key, session=rag_session
        )
        _save_flashcards(topic, cards_data, source)

        if ai_used and rag_session and cards_data:
            quiz_data = _generate_quiz_for_topic(
                topic, slide.text_content, groq_key, n=2, session=rag_session
            )
            if quiz_data:
                _save_quiz_questions(topic, quiz_data)
                total_quiz += len(quiz_data)

    topics = [_topic_to_dict(t) for t in plan.topics.all()]

    return Response({
        **_plan_to_dict(plan),
        'ai_generated': ai_used,
        'quiz_count': total_quiz,
        'message': (
            'Study plan created with AI-generated flashcards and quizzes.'
            if ai_used else
            'Study plan created. Set GROQ_API_KEY for AI-generated content.'
        ),
    }, status=201)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_learning_plans(request):
    plans = LearningPlan.objects.filter(student=request.user).select_related('slide').prefetch_related(
        'topics__flashcards', 'topics__quiz_questions', 'mock_exams'
    )
    result = [_plan_to_dict(plan) for plan in plans.order_by('-created_at')]
    return Response(result)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_learning_plan(request, plan_id):
    try:
        plan = LearningPlan.objects.select_related('slide').prefetch_related(
            'topics__flashcards', 'topics__quiz_questions', 'mock_exams'
        ).get(id=plan_id, student=request.user)
    except LearningPlan.DoesNotExist:
        return Response({'error': 'Study plan not found.'}, status=404)

    return Response(_plan_to_dict(plan))


def _generate_flashcards(topic):
    text = topic.raw_text or topic.summary
    concepts = topic.key_concepts if isinstance(topic.key_concepts, list) else []
    cards = []

    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    sentences = [s.strip() for s in sentences if 40 < len(s.strip()) < 350]

    def_patterns = [
        (r'(.{4,60})\s+(?:is|are|means|refers to|describes|ist|sind|bezeichnet|bedeutet|beschreibt)\s+(.{15,250})', "What is {term}?", "{definition}"),
        (r'(.{4,60})\s*:\s*(.{15,250})', 'What is meant by "{term}"?', "{definition}"),
        (r'(?:The|Der|Die|Das)\s+(.{4,50})\s+(?:is|are|enables|describes|ist|sind|ermöglicht|beschreibt)\s+(.{15,200})', "What is {term}?", "{definition}"),
    ]

    used_questions = set()
    for sent in sentences:
        for pat, q_tmpl, a_tmpl in def_patterns:
            m = re.match(pat, sent, re.IGNORECASE)
            if m:
                term = m.group(1).strip()
                definition = m.group(2).strip()
                if len(term) < 4 or len(definition) < 15:
                    continue
                q = q_tmpl.format(term=term)
                a = a_tmpl.format(definition=definition)
                if q not in used_questions:
                    used_questions.add(q)
                    cards.append({'question': q, 'answer': a})
                break

    for concept in concepts[:6]:
        q = f"What is {concept}?"
        if q not in used_questions:
            relevant = next(
                (s for s in sentences if concept.lower() in s.lower()),
                concept
            )
            used_questions.add(q)
            cards.append({'question': q, 'answer': relevant[:300]})

    for sent in sentences:
        if len(cards) >= 15:
            break
        words = sent.split()
        if len(words) < 8:
            continue
        pivot = len(words) // 2
        blank_word = next(
            (w for w in words[pivot:pivot+4] if len(w) > 4 and w[0].isupper()),
            None
        )
        if not blank_word:
            continue
        masked = sent.replace(blank_word, "___", 1)
        q = f"Fill in the blank:\n{masked}"
        if q not in used_questions:
            used_questions.add(q)
            cards.append({'question': q, 'answer': blank_word})

    if not cards:
        for i, sent in enumerate(sentences[:8]):
            q = 'What does the following sentence describe?\n"' + sent[:120] + '..."'
            cards.append({'question': q, 'answer': sent})

    return cards[:15]


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def generate_flashcards(request, topic_id):
    try:
        topic = LearningTopic.objects.select_related('plan__slide', 'plan__student').get(
            id=topic_id, plan__student=request.user
        )
    except LearningTopic.DoesNotExist:
        return Response({'error': 'Topic not found.'}, status=404)

    groq_key = _get_groq_key(request)
    cards_data, source = _generate_flashcards_for_topic(
        topic, topic.plan.slide.text_content, groq_key
    )
    _save_flashcards(topic, cards_data, source)

    if not cards_data:
        return Response({
            'error': 'Keine Karteikarten generiert. Bitte GROQ_API_KEY prüfen und erneut versuchen.'
        }, status=500)

    created = list(topic.flashcards.values(
        'id', 'question', 'answer', 'order', 'known', 'source'
    ))

    return Response({
        'topic_id': topic.id,
        'topic_title': topic.title,
        'flashcard_count': len(created),
        'flashcards': created,
        'source': source,
    }, status=201)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_flashcards(request, topic_id):
    try:
        topic = LearningTopic.objects.select_related('plan__student').get(
            id=topic_id, plan__student=request.user
        )
    except LearningTopic.DoesNotExist:
        return Response({'error': 'Topic not found.'}, status=404)

    cards = list(topic.flashcards.values('id', 'question', 'answer', 'order', 'known'))
    return Response({
        'topic_id': topic.id,
        'topic_title': topic.title,
        'flashcard_count': len(cards),
        'flashcards': cards,
    })


@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def mark_flashcard(request, card_id):
    try:
        card = Flashcard.objects.select_related('topic__plan__student').get(
            id=card_id, topic__plan__student=request.user
        )
    except Flashcard.DoesNotExist:
        return Response({'error': 'Card not found.'}, status=404)

    card.known = request.data.get('known', card.known)
    card.save()
    return Response({'id': card.id, 'known': card.known})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_quiz(request, topic_id):
    try:
        topic = LearningTopic.objects.select_related('plan__student').get(
            id=topic_id, plan__student=request.user
        )
    except LearningTopic.DoesNotExist:
        return Response({'error': 'Topic not found.'}, status=404)

    questions = list(topic.quiz_questions.values('id', 'text', 'options', 'answer', 'order'))
    return Response({
        'topic_id': topic.id,
        'topic_title': topic.title,
        'question_count': len(questions),
        'questions': questions,
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def generate_quiz(request, topic_id):
    try:
        topic = LearningTopic.objects.select_related('plan__slide', 'plan__student').get(
            id=topic_id, plan__student=request.user
        )
    except LearningTopic.DoesNotExist:
        return Response({'error': 'Topic not found.'}, status=404)

    groq_key = _get_groq_key(request)
    if not groq_key:
        return Response({
            'error': 'AI generation requires GROQ_API_KEY. Set it as an environment variable.'
        }, status=400)

    n = int(request.data.get('count', 3))
    quiz_data = _generate_quiz_for_topic(
        topic, topic.plan.slide.text_content, groq_key, n=n
    )
    if not quiz_data:
        return Response({'error': 'Could not generate quiz questions.'}, status=500)

    _save_quiz_questions(topic, quiz_data)
    questions = list(topic.quiz_questions.values('id', 'text', 'options', 'answer', 'order'))

    return Response({
        'topic_id': topic.id,
        'topic_title': topic.title,
        'question_count': len(questions),
        'questions': questions,
    }, status=201)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def generate_mock_exam(request, plan_id):
    try:
        plan = LearningPlan.objects.select_related('slide').prefetch_related('topics').get(
            id=plan_id, student=request.user
        )
    except LearningPlan.DoesNotExist:
        return Response({'error': 'Study plan not found.'}, status=404)

    groq_key = _get_groq_key(request)
    if not groq_key:
        return Response({
            'error': 'Mock exam requires GROQ_API_KEY for RAG-based generation.'
        }, status=400)

    topics = list(plan.topics.all())
    if not topics:
        return Response({'error': 'No topics in this plan.'}, status=400)

    from .rag_service import generate_mock_exam_rag
    topics_data = [_topic_rag_payload(t) for t in topics]
    all_questions = generate_mock_exam_rag(
        pdf_text=plan.slide.text_content,
        topics=topics_data,
        groq_api_key=groq_key,
        questions_per_topic=2,
        max_questions=20,
    )

    if not all_questions:
        return Response({'error': 'Could not generate mock exam from slide content.'}, status=500)

    plan.mock_exams.all().delete()
    duration = min(90, max(15, len(all_questions) * 2))
    mock = MockExam.objects.create(
        plan=plan,
        title=f"Mock Exam: {plan.slide.title}",
        duration_minutes=duration,
        questions=all_questions[:20],
    )

    return Response({
        'mock_exam_id': mock.id,
        'title': mock.title,
        'duration_minutes': mock.duration_minutes,
        'question_count': len(mock.questions),
        'questions': mock.questions,
    }, status=201)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_mock_exam(request, plan_id):
    try:
        plan = LearningPlan.objects.get(id=plan_id, student=request.user)
    except LearningPlan.DoesNotExist:
        return Response({'error': 'Study plan not found.'}, status=404)

    mock = plan.mock_exams.first()
    if not mock:
        return Response({'error': 'No mock exam generated yet.'}, status=404)

    return Response({
        'mock_exam_id': mock.id,
        'title': mock.title,
        'duration_minutes': mock.duration_minutes,
        'question_count': len(mock.questions),
        'questions': mock.questions,
        'created_at': mock.created_at.isoformat(),
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def generate_all_content(request, plan_id):
    """Regenerate AI flashcards and quizzes for all topics in a plan."""
    try:
        plan = LearningPlan.objects.select_related('slide').prefetch_related('topics').get(
            id=plan_id, student=request.user
        )
    except LearningPlan.DoesNotExist:
        return Response({'error': 'Study plan not found.'}, status=404)

    groq_key = _get_groq_key(request)
    if not groq_key:
        return Response({
            'error': 'AI generation requires GROQ_API_KEY.'
        }, status=400)

    total_cards = 0
    total_quiz = 0

    rag_session = None
    try:
        from .rag_service import SlideRAGSession
        rag_session = SlideRAGSession(plan.slide.text_content, groq_key)
    except Exception as e:
        return Response({'error': f'RAG init failed: {e}'}, status=500)

    for topic in plan.topics.all():
        cards_data, source = _generate_flashcards_for_topic(
            topic, plan.slide.text_content, groq_key, session=rag_session
        )
        _save_flashcards(topic, cards_data, source)
        total_cards += len(cards_data)

        quiz_data = _generate_quiz_for_topic(
            topic, plan.slide.text_content, groq_key, n=2, session=rag_session
        )
        if quiz_data:
            _save_quiz_questions(topic, quiz_data)
            total_quiz += len(quiz_data)

    return Response({
        'plan_id': plan.id,
        'flashcard_count': total_cards,
        'quiz_count': total_quiz,
        'message': f'RAG: {total_cards} flashcards and {total_quiz} quiz questions generated from slide content.',
    }, status=201)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_lecture_slides(request):
    slides = LectureSlide.objects.filter(student=request.user).order_by('-created_at')
    result = []
    for slide in slides:
        plan_count = LearningPlan.objects.filter(slide=slide).count()
        result.append({
            'id': slide.id,
            'title': slide.title,
            'file_name': slide.file_name,
            'page_count': slide.page_count,
            'status': slide.status,
            'created_at': slide.created_at.isoformat(),
            'has_plan': plan_count > 0,
        })
    return Response(result)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_learning_plan(request, plan_id):
    try:
        plan = LearningPlan.objects.select_related('slide').get(
            id=plan_id, student=request.user
        )
    except LearningPlan.DoesNotExist:
        return Response({'error': 'Study plan not found.'}, status=404)

    slide = plan.slide
    title = plan.title
    plan.delete()

    if not LearningPlan.objects.filter(slide=slide).exists():
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        pdf_path = os.path.join(base_dir, 'uploads', 'slides', slide.file_name)
        if os.path.isfile(pdf_path):
            os.remove(pdf_path)
        slide.delete()

    return Response({'message': f'"{title}" deleted.'}, status=200)
