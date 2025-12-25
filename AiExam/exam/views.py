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
from .models import Exam, ExamParticipation
from deepface import DeepFace

import numpy as np
import cv2
import os
import json
import uuid

# =======================================
# 🔐 LOGIN VIEW
# =======================================
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


# =======================================
# 📋 EXAM LIST VIEW
# =======================================
class ExamListView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        """
        Get exams:
        - Students see all exams
        - Staff/Professors see only exams they created
        """
        if request.user.is_staff:
            # Professoren sehen nur ihre eigenen Prüfungen
            exam_queryset = Exam.objects.filter(created_by=request.user)
        else:
            # Studenten sehen alle Prüfungen
            exam_queryset = Exam.objects.all()
        
        exams = []
        for exam in exam_queryset:
            exams.append({
                "id": exam.id,
                "title": exam.title,
                "date": exam.date.isoformat() if exam.date else None,
                "description": exam.description or ""
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

        if not title or not date_str:
            return Response(
                {"error": "Title and date are required."},
                status=status.HTTP_400_BAD_REQUEST
            )

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
            created_by=request.user  # Speichere den Ersteller
        )

        return Response(
            {"id": exam.id, "title": exam.title, "date": exam.date, "description": exam.description},
            status=status.HTTP_201_CREATED
        )


# =======================================
# 🧑‍🎓 JOIN EXAM VIEW
# =======================================
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


# =======================================
# 🧠 VERIFY IDENTITY (Face Recognition)
# =======================================
# >>> Stelle hier deine Schwelle ein (du wolltest "wenn Distanz <= 0.80 dann ok")
MATCH_THRESHOLD = 0.80         # ggf. 0.85 probieren
MODEL = "VGG-Face"             # Alternative: "ArcFace" (oft robuster bei Ausweisfotos)
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

    # --- 1) Gesichter erkennen (zwingend) ---
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

    # Größtes Live-Gesicht, kleinstes Ausweis-Gesicht (ID-Foto ist normalerweise kleiner)
    live_faces_sorted = sorted(live_faces, key=lambda f: f["facial_area"]["w"]*f["facial_area"]["h"], reverse=True)
    id_faces_sorted   = sorted(id_faces,   key=lambda f: f["facial_area"]["w"]*f["facial_area"]["h"])

    live_face_rgb = (live_faces_sorted[0]["face"] * 255).astype("uint8")
    id_face_rgb   = (id_faces_sorted[0]["face"]   * 255).astype("uint8")

    # --- 2) Vergleich ---
    try:
        result = DeepFace.verify(
            img1_path=live_face_rgb,
            img2_path=id_face_rgb,
            model_name=MODEL,
            detector_backend=DETECTOR,
            enforce_detection=False   # Detection haben wir vorher erledigt
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


# =======================================
# 📝 GET EXAM QUESTIONS
# =======================================
class ExamQuestionsView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, exam_id):
        """
        Get questions for an exam. Only accessible if student has joined the exam.
        Tries to load from JSON files in Exams_folder or uploads/exams.
        """
        student = request.user
        try:
            exam = Exam.objects.get(id=exam_id)
        except Exam.DoesNotExist:
            return Response(
                {"error": "Exam not found."},
                status=status.HTTP_404_NOT_FOUND
            )

        # Check if student has joined the exam
        try:
            ExamParticipation.objects.get(student=student, exam=exam)
        except ExamParticipation.DoesNotExist:
            return Response(
                {"error": "You must join the exam first."},
                status=status.HTTP_403_FORBIDDEN
            )

        # Try to load questions from JSON files
        questions = []
        
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        exam_title_normalized = exam.title.replace(' ', '_')
        exam_title_lower = exam_title_normalized.lower()
        exam_title_parts = exam.title.split()
        exam_first_part = exam_title_parts[0] if exam_title_parts else exam.title
        
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


# =======================================
# 📤 UPLOAD EXAM QUESTIONS (JSON)
# =======================================
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

    # Validate file extension
    if not json_file.name.endswith('.json'):
        return Response(
            {"error": "File must be a JSON file."},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Save file to uploads/exams directory
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    upload_dir = os.path.join(base_dir, "uploads", "exams")
    os.makedirs(upload_dir, exist_ok=True)
    
    # Generate unique filename
    filename = f"exam_from_Prof_{exam.id}_{uuid.uuid4().hex[:8]}.json"
    file_path = os.path.join(upload_dir, filename)

    try:
        # Save uploaded file
        with open(file_path, 'wb+') as destination:
            for chunk in json_file.chunks():
                destination.write(chunk)

        # Validate JSON structure
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            # Basic validation - should be dict or list
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


# =======================================
# 🆘 Manual check request (Support)
# =======================================
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def request_manual_check(request):
    """
    Student requests a manual identity review by the provider.
    We append a JSON line into uploads/json/manual_checks.jsonl for later review.
    """
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
    # Fallback to project-level uploads if app-level uploads is not desired
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
