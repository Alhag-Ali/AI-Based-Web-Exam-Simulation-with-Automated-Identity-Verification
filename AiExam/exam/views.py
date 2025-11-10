from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from rest_framework.authtoken.models import Token
from rest_framework.authentication import TokenAuthentication
from rest_framework.decorators import api_view, permission_classes, parser_classes
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.permissions import IsAuthenticated

from django.contrib.auth import authenticate
from .models import Exam, ExamParticipation
from deepface import DeepFace

import numpy as np
import cv2
import os

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
        return Response({"token": token.key}, status=status.HTTP_200_OK)


# =======================================
# 📋 EXAM LIST VIEW
# =======================================
class ExamListView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        exams = Exam.objects.all().values("id", "title", "date", "description")
        return Response(list(exams), status=status.HTTP_200_OK)


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
        print("extract_faces(live) error:", e)
        live_faces = []
    try:
        id_faces = DeepFace.extract_faces(id_bgr, detector_backend=DETECTOR)
    except Exception as e:
        print("extract_faces(id) error:", e)
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
        print("verify error:", e)
        return Response({"verified": False, "message": f"Fehler beim Vergleich: {e}"}, status=500)

    distance = float(result.get("distance", 1.0))
    verified = distance <= MATCH_THRESHOLD

    # Debug im Server-Log
    print(f"[verify_identity] model={MODEL} dist={distance:.4f} thr={MATCH_THRESHOLD} -> verified={verified}")
    print("live bbox:", live_faces_sorted[0]["facial_area"], " | id bbox:", id_faces_sorted[0]["facial_area"])

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
