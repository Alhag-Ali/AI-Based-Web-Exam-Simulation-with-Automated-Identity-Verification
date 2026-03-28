from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from rest_framework.authtoken.models import Token
from rest_framework.authentication import TokenAuthentication
from rest_framework.decorators import api_view, permission_classes, parser_classes
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone

from django.contrib.auth import authenticate
from .models import Exam, ExamParticipation, ExamEnrollment
from deepface import DeepFace

import numpy as np
import cv2
import os
import json
import uuid
import glob

class LoginView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        email = request.data.get("email")
        password = request.data.get("password")

        if not email or not password:
            return Response(
                {"error": "E-Mail und Passwort sind erforderlich."},
                status=status.HTTP_400_BAD_REQUEST
            )

        user = authenticate(request, email=email, password=password)
        if user is None:
            return Response(
                {"error": "Ungültige Anmeldedaten."},
                status=status.HTTP_401_UNAUTHORIZED
            )

        token, _ = Token.objects.get_or_create(user=user)
        return Response({
            "token": token.key,
            "is_staff": user.is_staff
        }, status=status.HTTP_200_OK)


class ExamListView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        if request.user.is_staff:
            exam_queryset = Exam.objects.filter(created_by=request.user)
        else:
            exam_queryset = Exam.objects.all()
        
        exams = []
        for exam in exam_queryset:
            exams.append({
                "id": exam.id,
                "title": exam.title,
                "date": exam.date.isoformat() if exam.date else None,
                "description": exam.description or "",
                "duration_minutes": exam.duration_minutes
            })
        
        return Response(exams, status=status.HTTP_200_OK)

    def post(self, request):
        """
        Create a new exam. Only staff/superusers can create exams.
        """
        if not request.user.is_staff:
            return Response(
                {"error": "Only staff members can create exams."},
                status=status.HTTP_403_FORBIDDEN
            )

        title = request.data.get("title")
        date_str = request.data.get("date")
        description = request.data.get("description", "")
        duration_minutes = request.data.get("duration_minutes", 60)

        if not title or not date_str:
            return Response(
                {"error": "Title and date are required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            duration_minutes = int(duration_minutes)
            if duration_minutes <= 0:
                duration_minutes = 60
        except (ValueError, TypeError):
            duration_minutes = 60

        try:
            from django.utils.dateparse import parse_datetime
            exam_date = parse_datetime(date_str)
            if not exam_date:
                exam_date = timezone.now()
        except:
            exam_date = timezone.now()

        exam = Exam.objects.create(
            title=title,
            date=exam_date,
            description=description,
            duration_minutes=duration_minutes,
            created_by=request.user
        )

        return Response(
            {"id": exam.id, "title": exam.title, "date": exam.date, "description": exam.description, "duration_minutes": exam.duration_minutes},
            status=status.HTTP_201_CREATED
        )


class JoinExamView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, exam_id):
        student = request.user
        try:
            exam = Exam.objects.get(id=exam_id)
        except Exam.DoesNotExist:
            return Response(
                {"error": "Exam not found."},
                status=status.HTTP_404_NOT_FOUND
            )

        enrollments = ExamEnrollment.objects.filter(exam=exam)
        if enrollments.exists():
            student_matrikel = getattr(student, 'matriculation_number', None)
            if not student_matrikel or not enrollments.filter(matriculation_number=student_matrikel).exists():
                return Response(
                    {
                        "error": "not_enrolled",
                        "message": (
                            f"Sie sind nicht für diese Prüfung zugelassen. "
                            f"Ihre Matrikelnummer ({student_matrikel or 'unbekannt'}) "
                            f"befindet sich nicht in der Zulassungsliste. "
                            f"Bitte wenden Sie sich an den Professor."
                        ),
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )

        participation, created = ExamParticipation.objects.get_or_create(
            student=student,
            exam=exam
        )

        message = (
            f"{student.email} successfully joined {exam.title}."
            if created
            else f"{student.email} already joined {exam.title}."
        )
        return Response({"message": message}, status=status.HTTP_200_OK)


MATCH_THRESHOLD = 0.80
MODEL = "VGG-Face"
DETECTOR = "retinaface"

@api_view(['POST'])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser, FormParser])
def verify_identity(request):
    live_image = request.FILES.get("live_image")
    id_image   = request.FILES.get("id_image")

    if not live_image or not id_image:
        return Response({"verified": False, "message": "Beide Bilder sind erforderlich."}, status=400)

    def to_cv(fileobj):
        buf = np.asarray(bytearray(fileobj.read()), dtype=np.uint8)
        return cv2.imdecode(buf, cv2.IMREAD_COLOR)

    live_bgr = to_cv(live_image)
    id_bgr   = to_cv(id_image)

    try:
        live_faces = DeepFace.extract_faces(live_bgr, detector_backend=DETECTOR)
    except Exception as e:
        live_faces = []
    try:
        id_faces = DeepFace.extract_faces(id_bgr, detector_backend=DETECTOR)
    except Exception as e:
        id_faces = []

    if len(live_faces) == 0:
        return Response({
            "verified": False,
            "face_detected_live": False,
            "face_detected_id": len(id_faces) > 0,
            "message": "Kein Gesicht im Live-Bild erkannt.",
            "hints": ["Direkt in die Kamera schauen", "Licht von vorne", "Kamera näher ans Gesicht"]
        }, status=200)

    if len(id_faces) == 0:
        return Response({
            "verified": False,
            "face_detected_live": True,
            "face_detected_id": False,
            "message": "Kein Gesicht im Ausweisfoto erkannt.",
            "hints": ["Karte gerader halten", "Foto auf Karte vollständig zeigen", "Reflexion vermeiden"]
        }, status=200)

    live_faces_sorted = sorted(live_faces, key=lambda f: f["facial_area"]["w"]*f["facial_area"]["h"], reverse=True)
    id_faces_sorted   = sorted(id_faces,   key=lambda f: f["facial_area"]["w"]*f["facial_area"]["h"])

    live_face_rgb = (live_faces_sorted[0]["face"] * 255).astype("uint8")
    id_face_rgb   = (id_faces_sorted[0]["face"]   * 255).astype("uint8")

    try:
        result = DeepFace.verify(
            img1_path=live_face_rgb,
            img2_path=id_face_rgb,
            model_name=MODEL,
            detector_backend=DETECTOR,
            enforce_detection=False
        )
    except Exception as e:
        return Response({"verified": False, "message": f"Fehler beim Vergleich: {e}"}, status=500)

    distance = float(result.get("distance", 1.0))
    verified = distance <= MATCH_THRESHOLD

    hints = []
    if not verified:
        hints = [
            "Karte näher und ruhiger halten (ID-Foto größer/schärfer im Bild).",
            "Gesicht frontal ausrichten, ähnlich wie am Ausweisfoto.",
            "Gegenlicht vermeiden; gleichmäßige Beleuchtung."
        ]

    return Response({
        "verified": verified,
        "distance": distance,
        "threshold": MATCH_THRESHOLD,
        "model": MODEL,
        "face_detected_live": True,
        "face_detected_id": True,
        "message": ("✅ Identität bestätigt." if verified else f"Gesichter stimmen nicht ausreichend überein (Distanz {distance:.2f})."),
        "hints": hints
    }, status=200)


class ExamQuestionsView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, exam_id):
        student = request.user
        try:
            exam = Exam.objects.get(id=exam_id)
        except Exam.DoesNotExist:
            return Response(
                {"error": "Exam not found."},
            status=status.HTTP_404_NOT_FOUND
        )

        try:
            ExamParticipation.objects.get(student=student, exam=exam)
        except ExamParticipation.DoesNotExist:
            return Response(
                {"error": "You must join the exam first."},
                status=status.HTTP_403_FORBIDDEN
            )

        questions = []
        
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        exam_title_normalized = exam.title.replace(' ', '_')
        exam_title_lower = exam_title_normalized.lower()
        exam_title_parts = exam.title.split()
        exam_first_part = exam_title_parts[0] if exam_title_parts else exam.title
        
        upload_dir = os.path.join(base_dir, "uploads", "exams")
        
        possible_paths = [
            os.path.join(base_dir, "Exams_folder", f"{exam_first_part}_exam.json"),
            os.path.join(base_dir, "Exams_folder", f"{exam_title_normalized}exam.json"),
            os.path.join(base_dir, "Exams_folder", f"{exam_title_lower}exam.json"),
            os.path.join(base_dir, "Exams_folder", f"{exam_title_normalized}_exam.json"),
            os.path.join(base_dir, "Exams_folder", f"{exam_title_lower}_exam.json"),
            os.path.join(base_dir, "Exams_folder", f"{exam_title_normalized}.json"),
            os.path.join(base_dir, "Exams_folder", f"{exam_title_lower}.json"),
            os.path.join(base_dir, "uploads", "exams", f"exam_from_Prof_{exam.id}.json"),
            os.path.join(base_dir, "uploads", "exams", f"exam_from_Prof.json"),
            os.path.join(base_dir, "uploads", "json", "exam.json"),
        ]
        
        if os.path.exists(upload_dir):
            uuid_pattern = os.path.join(upload_dir, f"exam_from_Prof_{exam.id}_*.json")
            uuid_files = glob.glob(uuid_pattern)
            if uuid_files:
                uuid_files.sort(key=os.path.getmtime, reverse=True)
                possible_paths.insert(0, uuid_files[0])

        for json_path in possible_paths:
            if os.path.exists(json_path):
                try:
                    with open(json_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        
                        if isinstance(data, list):
                            questions = data
                        elif isinstance(data, dict):
                            if "questions" in data:
                                questions = data["questions"]
                            elif "question" in data or "Question" in data:
                                q_text = data.get("question") or data.get("Question", "")
                                q_answer = data.get("answer") or data.get("Answer", "")
                                questions = [{
                                    "text": q_text,
                                    "answer": q_answer,
                                    "options": []
                                }]
                            elif any(key.lower() in ["text", "question"] for key in data.keys()):
                                questions = [data]
                        
                        if questions:
                            break
                except Exception as e:
                    continue

        if not questions:
            return Response(
                {"questions": [], "message": "No questions found for this exam."},
                status=status.HTTP_200_OK
            )

        normalized_questions = []
        for q in questions:
            if isinstance(q, str):
                normalized_questions.append({"text": q, "options": []})
            elif isinstance(q, dict):
                normalized_q = {
                    "text": q.get("text") or q.get("question") or q.get("Question") or "Question",
                    "options": q.get("options") or q.get("Options") or [],
                    "answer": q.get("answer") or q.get("Answer") or q.get("correct_answer"),
                }
                normalized_questions.append(normalized_q)

        return Response({"questions": normalized_questions}, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_exam_questions_for_professor(request, exam_id):
    try:
        exam = Exam.objects.get(id=exam_id)
    except Exam.DoesNotExist:
        return Response(
            {"error": "Exam not found."},
            status=status.HTTP_404_NOT_FOUND
        )

    if not request.user.is_staff:
        return Response(
            {"error": "Only staff members can access this endpoint."},
            status=status.HTTP_403_FORBIDDEN
        )

    questions = []
    
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    exam_title_normalized = exam.title.replace(' ', '_')
    exam_title_lower = exam_title_normalized.lower()
    exam_title_parts = exam.title.split()
    exam_first_part = exam_title_parts[0] if exam_title_parts else exam.title
    
    upload_dir = os.path.join(base_dir, "uploads", "exams")
    
    possible_paths = [
        os.path.join(base_dir, "Exams_folder", f"{exam_first_part}_exam.json"),
        os.path.join(base_dir, "Exams_folder", f"{exam_title_normalized}exam.json"),
        os.path.join(base_dir, "Exams_folder", f"{exam_title_lower}exam.json"),
        os.path.join(base_dir, "Exams_folder", f"{exam_title_normalized}_exam.json"),
        os.path.join(base_dir, "Exams_folder", f"{exam_title_lower}_exam.json"),
        os.path.join(base_dir, "Exams_folder", f"{exam_title_normalized}.json"),
        os.path.join(base_dir, "Exams_folder", f"{exam_title_lower}.json"),
        os.path.join(base_dir, "uploads", "exams", f"exam_from_Prof_{exam.id}.json"),
        os.path.join(base_dir, "uploads", "exams", f"exam_from_Prof.json"),
        os.path.join(base_dir, "uploads", "json", "exam.json"),
    ]
    
    if os.path.exists(upload_dir):
        uuid_pattern = os.path.join(upload_dir, f"exam_from_Prof_{exam.id}_*.json")
        uuid_files = glob.glob(uuid_pattern)
        if uuid_files:
            uuid_files.sort(key=os.path.getmtime, reverse=True)
            possible_paths.insert(0, uuid_files[0])

    for json_path in possible_paths:
        if os.path.exists(json_path):
            try:
                with open(json_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    
                    if isinstance(data, list):
                        questions = data
                    elif isinstance(data, dict):
                        if "questions" in data:
                            questions = data["questions"]
                        elif "question" in data or "Question" in data:
                            q_text = data.get("question") or data.get("Question", "")
                            q_answer = data.get("answer") or data.get("Answer", "")
                            questions = [{
                                "text": q_text,
                                "answer": q_answer,
                                "options": []
                            }]
                        elif any(key.lower() in ["text", "question"] for key in data.keys()):
                            questions = [data]
                    
                    if questions:
                        break
            except Exception as e:
                continue

    normalized_questions = []
    for q in questions:
        if isinstance(q, str):
            normalized_questions.append({"text": q, "options": []})
        elif isinstance(q, dict):
            normalized_q = {
                "text": q.get("text") or q.get("question") or q.get("Question") or "Question",
                "options": q.get("options") or q.get("Options") or [],
                "answer": q.get("answer") or q.get("Answer") or q.get("correct_answer"),
            }
            normalized_questions.append(normalized_q)

    return Response({"questions": normalized_questions}, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def save_exam_questions(request, exam_id):
    if not request.user.is_staff:
        return Response(
            {"error": "Only staff members can save questions."},
            status=status.HTTP_403_FORBIDDEN
        )

    try:
        exam = Exam.objects.get(id=exam_id)
    except Exam.DoesNotExist:
        return Response(
            {"error": "Exam not found."},
            status=status.HTTP_404_NOT_FOUND
        )

    questions = request.data.get("questions", [])
    
    if not isinstance(questions, list):
        return Response(
            {"error": "Questions must be a list."},
            status=status.HTTP_400_BAD_REQUEST
        )

    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    upload_dir = os.path.join(base_dir, "uploads", "exams")
    os.makedirs(upload_dir, exist_ok=True)
    
    filename = f"exam_from_Prof_{exam.id}.json"
    file_path = os.path.join(upload_dir, filename)

    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump({"questions": questions}, f, ensure_ascii=False, indent=2)
        
        return Response(
            {
                "message": f"Successfully saved {len(questions)} questions.",
                "filename": filename,
                "questions_count": len(questions)
            },
            status=status.HTTP_200_OK
        )
    except Exception as e:
        return Response(
            {"error": f"Error saving questions: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser, FormParser])
def upload_pdf_and_generate_questions(request, exam_id):
    if not request.user.is_staff:
        return Response(
            {"error": "Only staff members can upload PDFs."},
            status=status.HTTP_403_FORBIDDEN
        )

    try:
        exam = Exam.objects.get(id=exam_id)
    except Exam.DoesNotExist:
        return Response(
            {"error": "Exam not found."},
            status=status.HTTP_404_NOT_FOUND
        )

    pdf_file = request.FILES.get("pdf_file")
    if not pdf_file:
        return Response(
            {"error": "No file provided. Please upload a PDF file."},
            status=status.HTTP_400_BAD_REQUEST
        )

    if not pdf_file.name.lower().endswith('.pdf'):
        return Response(
            {"error": "File must be a PDF file."},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        from pypdf import PdfReader
        import tempfile
        
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        upload_dir = os.path.join(base_dir, "uploads", "exams")
        os.makedirs(upload_dir, exist_ok=True)
        
        temp_pdf_path = os.path.join(upload_dir, f"temp_{exam.id}_{uuid.uuid4().hex[:8]}.pdf")
        
        with open(temp_pdf_path, 'wb+') as destination:
            for chunk in pdf_file.chunks():
                destination.write(chunk)
        
        reader = PdfReader(temp_pdf_path)
        
        all_text_parts = []
        total_text_length = 0
        
        for page_num, page in enumerate(reader.pages):
            try:
                page_text = page.extract_text()
                if page_text and page_text.strip():
                    cleaned_text = page_text.strip()
                    all_text_parts.append(cleaned_text)
                    total_text_length += len(cleaned_text)
            except Exception:
                continue
        
        all_text = "\n\n".join(all_text_parts)
        
        if not all_text.strip() or total_text_length < 100:
            os.remove(temp_pdf_path)
            return Response(
                {"error": "Konnte keinen Text aus der PDF-Datei extrahieren. Die PDF-Datei könnte gescannt (nur Bilder) oder verschlüsselt sein. Bitte stellen Sie sicher, dass die PDF-Datei Text enthält."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        num_pages = len(reader.pages)
        num_questions = min(15, max(5, num_pages, total_text_length // 500))
        
        questions = generate_questions_from_text(all_text, num_questions=num_questions)
        
        if len(questions) == 0:
            os.remove(temp_pdf_path)
            return Response(
                {"error": "Es konnten keine Fragen aus der PDF-Datei generiert werden. Bitte stellen Sie sicher, dass die PDF-Datei ausreichend Text enthält."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        filename = f"exam_from_Prof_{exam.id}_{uuid.uuid4().hex[:8]}.json"
        file_path = os.path.join(upload_dir, filename)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump({"questions": questions}, f, ensure_ascii=False, indent=2)
        
        os.remove(temp_pdf_path)
        
        return Response(
            {
                "message": f"Successfully generated {len(questions)} questions from PDF.",
                "filename": filename,
                "exam_id": exam.id,
                "questions_count": len(questions)
            },
            status=status.HTTP_200_OK
        )
    except ImportError:
        return Response(
            {"error": "pypdf library is not installed. Please install it with: pip install pypdf"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
    except Exception as e:
        if os.path.exists(temp_pdf_path):
            os.remove(temp_pdf_path)
        return Response(
            {"error": f"Error processing PDF: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


def generate_questions_from_text(text, num_questions=10):
    """
    Generate multiple-choice questions from PDF lecture slides text.
    Extracts key concepts and creates relevant questions based on actual content.
    """
    import re
    
    text = text.strip()
    if not text or len(text) < 50:
        return [{
            "text": "Die PDF-Datei enthält nicht genug Text. Bitte stellen Sie sicher, dass die PDF-Datei Text enthält (nicht nur Bilder).",
            "options": ["OK", "Wiederholen", "Abbrechen", "Weiter"],
            "answer": "OK"
        }]
    
    questions = []
    
    text_clean = re.sub(r'--- Folie \d+ ---', '', text)
    text_clean = re.sub(r'Goethe-Universität[^\n]*', '', text_clean)
    text_clean = re.sub(r'Institut für Informatik[^\n]*', '', text_clean)
    text_clean = re.sub(r'Dr\.?\s+[A-Z][a-z]+\s+[A-Z][a-z]+', '', text_clean)
    text_clean = re.sub(r'\d+\s*\n\s*\d+\.\d+', '', text_clean)
    text_clean = re.sub(r'\n{3,}', '\n\n', text_clean)
    text_clean = re.sub(r'^\d+\s*$', '', text_clean, flags=re.MULTILINE)
    
    paragraphs = re.split(r'\n\s*\n', text_clean)
    paragraphs = [p.strip() for p in paragraphs if len(p.strip()) > 50]
    paragraphs = [p for p in paragraphs if not re.match(r'^[\d\s\.]+$', p)]
    
    sentences = re.split(r'[.!?]\s+', text_clean)
    sentences = [s.strip() for s in sentences if len(s.strip()) > 25 and len(s.strip()) < 300]
    
    important_concepts = []
    concept_patterns = [
        r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+(?:ist|sind|bedeutet|bezeichnet|beschreibt)',
        r'(?:ist|sind|bedeutet|bezeichnet)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)',
        r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s*:',
    ]
    
    excluded_terms = {'Folie', 'Goethe', 'Universität', 'Frankfurt', 'Institut', 'Informatik', 
                     'Aleksey', 'Koschowoj', 'Main', 'Dr', 'Prof', 'Professor'}
    
    for sentence in sentences:
        for pattern in concept_patterns:
            matches = re.findall(pattern, sentence)
            for match in matches:
                if isinstance(match, tuple):
                    match = ' '.join(match)
                if match and len(match) > 3 and match not in excluded_terms:
                    if not any(ex in match for ex in excluded_terms):
                        important_concepts.append((match, sentence))
    
    definitions = []
    for sentence in sentences:
        lower_s = sentence.lower()
        if any(word in lower_s for word in ['ist', 'sind', 'bedeutet', 'bezeichnet', 'beschreibt', 'definiert']):
            if 40 < len(sentence) < 250:
                if not any(ex in sentence for ex in excluded_terms):
                    definitions.append(sentence)
    
    num_questions = min(num_questions, max(5, len(paragraphs) // 2, len(definitions) // 2, len(sentences) // 10))
    
    used_content = set()
    used_concepts = set()
    
    for i in range(num_questions):
        if i < len(definitions) and len(definitions) > 0:
            definition = definitions[i % len(definitions)]
            if definition in used_content:
                continue
            used_content.add(definition)
            
            words = definition.split()
            concept = None
            for word in words:
                if word[0].isupper() and len(word) > 4:
                    if not any(ex in word for ex in excluded_terms):
                        concept = word
                        break
            
            if not concept or len(definition) < 40:
                continue
            
            clean_def = re.sub(r'\s+', ' ', definition).strip()[:200]
            
            question = {
                "text": f"Was bedeutet '{concept}'?" if concept else "Was ist die Definition?",
                "options": [
                    clean_def,
                    f"{concept} ist eine Methode zur Datenverarbeitung." if concept else "Es ist eine Methode.",
                    f"{concept} ist ein Algorithmus." if concept else "Es ist ein Algorithmus.",
                    f"{concept} ist eine Datenstruktur." if concept else "Es ist eine Datenstruktur."
                ],
                "answer": clean_def
            }
            
        elif i < len(paragraphs) and len(paragraphs) > 0:
            para = paragraphs[i % len(paragraphs)]
            if para in used_content or len(para) < 50:
                continue
            used_content.add(para)
            
            para_clean = re.sub(r'\s+', ' ', para).strip()
            if len(para_clean) > 400:
                para_clean = para_clean[:400] + "..."
            
            words = para_clean.split()
            if len(words) < 10:
                continue
            
            main_concept = None
            for word in words:
                if word[0].isupper() and len(word) > 4:
                    if not any(ex in word for ex in excluded_terms):
                        main_concept = word
                        break
            
            if not main_concept:
                continue
            
            summary = para_clean[:250] + "..." if len(para_clean) > 250 else para_clean
            
            question = {
                "text": f"Was ist {main_concept}?",
                "options": [
                    summary,
                    f"{main_concept} ist eine Programmiersprache.",
                    f"{main_concept} ist ein Betriebssystem.",
                    f"{main_concept} ist nicht im Material definiert."
                ],
                "answer": summary
            }
            
        elif important_concepts and i < len(important_concepts) * 2:
            concept, context = important_concepts[i % len(important_concepts)]
            if concept in used_concepts:
                continue
            used_concepts.add(concept)
            
            clean_context = re.sub(r'\s+', ' ', context).strip()[:200]
            
            question = {
                "text": f"Was ist {concept}?",
                "options": [
                    clean_context,
                    f"{concept} ist eine Methode.",
                    f"{concept} ist ein Algorithmus.",
                    f"{concept} ist nicht definiert."
                ],
                "answer": clean_context
            }
        else:
            if i < len(sentences):
                sentence = sentences[i % len(sentences)]
                if sentence in used_content or len(sentence) < 30:
                    continue
                used_content.add(sentence)
                
                clean_sentence = sentence[:200] + "..." if len(sentence) > 200 else sentence
                
                question = {
                    "text": f"Welche Aussage ist korrekt?",
                    "options": [
                        clean_sentence,
                        "Die Aussage ist teilweise korrekt.",
                        "Die Aussage ist falsch.",
                        "Die Aussage benötigt mehr Kontext."
                    ],
                    "answer": clean_sentence
                }
            else:
                break
        
        if question and question not in questions:
            questions.append(question)
    
    if len(questions) == 0:
        questions.append({
            "text": "Es konnten keine Fragen aus der PDF-Datei generiert werden. Bitte stellen Sie sicher, dass die PDF-Datei Text enthält.",
            "options": ["OK", "Wiederholen", "Abbrechen", "Weiter"],
            "answer": "OK"
        })
    
    return questions[:num_questions]


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser, FormParser])
def upload_exam_questions(request, exam_id):
    """
    Upload exam questions as JSON file. Only staff can upload.
    """
    if not request.user.is_staff:
        return Response(
            {"error": "Only staff members can upload exam questions."},
            status=status.HTTP_403_FORBIDDEN
        )

    try:
        exam = Exam.objects.get(id=exam_id)
    except Exam.DoesNotExist:
        return Response(
            {"error": "Exam not found."},
            status=status.HTTP_404_NOT_FOUND
        )

    json_file = request.FILES.get("exam_file")
    if not json_file:
        return Response(
            {"error": "No file provided. Please upload a JSON file."},
            status=status.HTTP_400_BAD_REQUEST
        )

    if not json_file.name.endswith('.json'):
        return Response(
            {"error": "File must be a JSON file."},
            status=status.HTTP_400_BAD_REQUEST
        )

    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    upload_dir = os.path.join(base_dir, "uploads", "exams")
    os.makedirs(upload_dir, exist_ok=True)
    
    filename = f"exam_from_Prof_{exam.id}_{uuid.uuid4().hex[:8]}.json"
    file_path = os.path.join(upload_dir, filename)

    try:
        with open(file_path, 'wb+') as destination:
            for chunk in json_file.chunks():
                destination.write(chunk)

        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            if not isinstance(data, (dict, list)):
                os.remove(file_path)
                return Response(
                    {"error": "Invalid JSON structure. Expected object or array."},
                    status=status.HTTP_400_BAD_REQUEST
                )

        return Response(
            {
                "message": "Exam questions uploaded successfully.",
                "filename": filename,
                "exam_id": exam.id,
                "exam_title": exam.title
            },
            status=status.HTTP_200_OK
        )
    except json.JSONDecodeError:
        if os.path.exists(file_path):
            os.remove(file_path)
        return Response(
            {"error": "Invalid JSON file."},
            status=status.HTTP_400_BAD_REQUEST
        )
    except Exception as e:
        if os.path.exists(file_path):
            os.remove(file_path)
        return Response(
            {"error": f"Error uploading file: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def request_manual_check(request):
    exam_id = request.data.get("exam_id")
    message = request.data.get("message", "")

    if not exam_id:
        return Response({"ok": False, "error": "exam_id required"}, status=400)

    try:
        exam = Exam.objects.get(id=exam_id)
    except Exam.DoesNotExist:
        return Response({"ok": False, "error": "Exam not found"}, status=404)

    record = {
        "timestamp": timezone.now().isoformat(),
        "student_email": getattr(request.user, "email", None),
        "student_id": getattr(request.user, "id", None),
        "exam_id": exam.id,
        "exam_title": exam.title,
        "message": message,
    }

    folder = os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads", "json")
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    project_uploads = os.path.join(os.path.dirname(project_root), "uploads", "json")
    try_paths = [folder, project_uploads]
    saved = False
    for base in try_paths:
        try:
            os.makedirs(base, exist_ok=True)
            path = os.path.join(base, "manual_checks.jsonl")
            with open(path, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
            saved = True
            break
        except Exception as e:
            pass

    if not saved:
        pass

    return Response({"ok": True, "message": "Provider has been notified for manual review."}, status=200)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def professor_dashboard(request):
    if not request.user.is_staff:
        return Response({"error": "Nur Staff-Mitglieder dürfen auf das Dashboard zugreifen."}, status=403)

    exams = Exam.objects.filter(created_by=request.user).order_by('-created_at')

    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    upload_dir = os.path.join(base_dir, "uploads", "exams")

    def _question_count(exam):
        if not os.path.exists(upload_dir):
            return 0
        pattern = os.path.join(upload_dir, f"exam_from_Prof_{exam.id}_*.json")
        files = glob.glob(pattern)
        if not files:
            return 0
        files.sort(key=os.path.getmtime, reverse=True)
        try:
            with open(files[0], 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, list):
                    return len(data)
                if isinstance(data, dict) and "questions" in data:
                    return len(data["questions"])
        except Exception:
            pass
        return 0

    now = timezone.now()
    exam_list = []
    total_participants = 0

    for exam in exams:
        participants = ExamParticipation.objects.filter(exam=exam)
        participant_count = participants.count()
        total_participants += participant_count

        student_list = []
        for p in participants.select_related('student'):
            student_list.append({
                "email": p.student.email,
                "name": f"{p.student.first_name} {p.student.last_name}".strip(),
                "joined_at": p.joined_at.isoformat(),
            })

        q_count = _question_count(exam)
        is_past = exam.date < now

        exam_list.append({
            "id": exam.id,
            "title": exam.title,
            "date": exam.date.isoformat(),
            "duration_minutes": exam.duration_minutes,
            "description": exam.description or "",
            "created_at": exam.created_at.isoformat() if exam.created_at else None,
            "participant_count": participant_count,
            "question_count": q_count,
            "is_past": is_past,
            "students": student_list,
        })

    return Response({
        "total_exams": len(exam_list),
        "total_participants": total_participants,
        "exams": exam_list,
    })


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def exam_enrollments(request, exam_id):
    if not request.user.is_staff:
        return Response({"error": "Nur Professoren dürfen Zulassungslisten verwalten."}, status=403)

    try:
        exam = Exam.objects.get(id=exam_id, created_by=request.user)
    except Exam.DoesNotExist:
        return Response({"error": "Prüfung nicht gefunden."}, status=404)

    if request.method == 'GET':
        entries = ExamEnrollment.objects.filter(exam=exam)
        data = [
            {
                "matriculation_number": e.matriculation_number,
                "note": e.note,
                "added_at": e.added_at.isoformat(),
            }
            for e in entries
        ]
        return Response({"exam_id": exam_id, "enrollments": data})

    # POST – add one or many
    numbers = request.data.get('matriculation_numbers', [])
    single = request.data.get('matriculation_number', '')
    note = request.data.get('note', '')

    if single and not numbers:
        numbers = [single]

    if not numbers:
        return Response({"error": "Keine Matrikelnummern angegeben."}, status=400)

    added, skipped = [], []
    for mn in numbers:
        mn = str(mn).strip()
        if not mn:
            continue
        _, created = ExamEnrollment.objects.get_or_create(
            exam=exam,
            matriculation_number=mn,
            defaults={"note": note},
        )
        (added if created else skipped).append(mn)

    return Response({"added": added, "skipped": skipped}, status=201 if added else 200)


@api_view(['PUT', 'DELETE'])
@permission_classes([IsAuthenticated])
def exam_enrollment_detail(request, exam_id, matrikel):
    if not request.user.is_staff:
        return Response({"error": "Nur Professoren dürfen Zulassungslisten verwalten."}, status=403)

    try:
        exam = Exam.objects.get(id=exam_id, created_by=request.user)
    except Exam.DoesNotExist:
        return Response({"error": "Prüfung nicht gefunden."}, status=404)

    try:
        enrollment = ExamEnrollment.objects.get(exam=exam, matriculation_number=matrikel)
    except ExamEnrollment.DoesNotExist:
        return Response({"error": "Zulassung nicht gefunden."}, status=404)

    if request.method == 'DELETE':
        enrollment.delete()
        return Response({"message": "Zulassung entfernt."})

    # PUT – edit matrikel or note
    new_mn = str(request.data.get('matriculation_number', matrikel)).strip()
    new_note = request.data.get('note', enrollment.note)

    if new_mn != matrikel:
        if ExamEnrollment.objects.filter(exam=exam, matriculation_number=new_mn).exists():
            return Response({"error": f"Matrikelnummer {new_mn} ist bereits in der Zulassungsliste."}, status=400)
        enrollment.matriculation_number = new_mn

    enrollment.note = new_note
    enrollment.save()
    return Response({"matriculation_number": enrollment.matriculation_number, "note": enrollment.note})
