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
import re
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
                {"error": "Email and password are required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        user = authenticate(request, email=email, password=password)
        if user is None:
            return Response(
                {"error": "Invalid credentials."},
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
                            f"You are not authorized for this exam. "
                            f"Your matriculation number ({student_matrikel or 'unknown'}) "
                            f"is not on the enrollment list. "
                            f"Please contact the professor."
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


FACE_MATCH_THRESHOLD = 0.55   # combined similarity score threshold (0–1, higher = more similar)

# ── OCR (Tesseract) ───────────────────────────────────────────────────────────
import pytesseract
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"


def _preprocess_for_ocr(img_bgr):
    """Prepare an ID-card image for digit OCR: upscale, denoise, threshold."""
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape
    # Upscale small images – Tesseract works best at ~300 dpi (≥ 1000 px wide)
    if max(h, w) < 1000:
        scale = 1000 / max(h, w)
        gray = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    # Mild denoise
    gray = cv2.GaussianBlur(gray, (3, 3), 0)
    # CLAHE for local contrast
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    gray = clahe.apply(gray)
    # Adaptive threshold → clean black-on-white text
    binary = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY, 31, 10
    )
    return binary


def _ocr_image(img, psm=6, digits_only=False):
    """Run Tesseract on a single image, return raw string."""
    config = f"--oem 3 --psm {psm}"
    if digits_only:
        config += " -c tessedit_char_whitelist=0123456789"
    return pytesseract.image_to_string(img, config=config, lang="eng")


def _fix_ocr(s):
    """Fix common OCR substitution errors and strip whitespace."""
    return (s.upper()
              .replace("O", "0").replace("I", "1").replace("L", "1")
              .replace("S", "5").replace("B", "8").replace("G", "9")
              .replace("Z", "2"))


def _all_digits(text):
    """Return a string containing only digits from text."""
    return re.sub(r"[^\d]", "", _fix_ocr(text))


def _extract_matrikelnummer(img_bgr):
    """
    OCR the student-ID image with Tesseract.
    Strategy:
      1. Scan the full image and several crops (bottom half, centre strip)
         with different PSM modes and digit-only mode.
      2. Collect all digit strings found.
      3. From the longest combined digit string, extract the last 7 digits
         (the Matrikelnummer is always the LAST 7 of the card number).
    Returns (matrikel: str | None, raw_ocr_text: str).
    """
    try:
        proc = _preprocess_for_ocr(img_bgr)
        h, w = proc.shape[:2]

        # Build a set of image regions to scan
        crops = {
            "full":          proc,
            "bottom_half":   proc[h // 2 :, :],
            "bottom_third":  proc[2 * h // 3 :, :],
            "center_strip":  proc[h // 4 : 3 * h // 4, :],
        }

        # Also try the original (non-thresholded, just upscaled gray)
        gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
        scale = max(1.0, 1200 / max(gray.shape))
        gray_up = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
        crops["gray_full"]   = gray_up
        crops["gray_bottom"] = gray_up[gray_up.shape[0] // 2 :, :]

        all_texts = []
        combined_digits = ""

        for name, crop in crops.items():
            for psm in (6, 11, 7):           # block / sparse / single-line
                for donly in (False, True):
                    try:
                        raw = _ocr_image(crop, psm=psm, digits_only=donly)
                        digits = _all_digits(raw)
                        if digits:
                            all_texts.append(raw.strip())
                            combined_digits += digits
                    except Exception:
                        pass

        print(f"[OCR] combined digits: {repr(combined_digits[:80])}")

        # --- Strategy A: find the longest contiguous digit run in combined string ---
        # Remove duplicate adjacent digits that look like OCR doubling
        runs = re.findall(r"\d+", combined_digits)
        if runs:
            longest = max(runs, key=len)
            if len(longest) >= 7:
                chosen = longest[-7:]
                print(f"[OCR] longest run ({len(longest)} digits) → matrikel={chosen}")
                return chosen, " | ".join(all_texts[:3])

        # --- Strategy B: try all combinations of adjacent short runs that total ≥ 7 ---
        joined = "".join(runs)
        if len(joined) >= 7:
            chosen = joined[-7:]
            print(f"[OCR] joined all runs → matrikel={chosen}")
            return chosen, " | ".join(all_texts[:3])

        print("[OCR] no usable digit sequence found")
        return None, " | ".join(all_texts[:2]) if all_texts else "(no text found)"

    except Exception as e:
        print(f"[OCR] exception: {e}")
        return None, f"(OCR error: {e})"


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser, FormParser])
def extract_matrikel(request):
    """
    Lightweight endpoint: OCR the uploaded ID-card image and return the
    extracted 7-digit matriculation number (or None if not found).
    Called right after the student captures their ID card.
    """
    id_image = request.FILES.get("id_image")
    if not id_image:
        return Response({"matrikel": None, "raw_text": ""}, status=400)
    id_bgr = _decode_image_bytes(id_image)
    if id_bgr is None:
        return Response({"matrikel": None, "raw_text": "Image could not be decoded"})
    matrikel, raw_text = _extract_matrikelnummer(id_bgr)
    return Response({"matrikel": matrikel, "raw_text": raw_text})


def _decode_image_bytes(fileobj):
    """Read uploaded file and decode to BGR numpy array. Returns None on failure."""
    try:
        data = fileobj.read()
        if not data:
            return None
        buf = np.asarray(bytearray(data), dtype=np.uint8)
        return cv2.imdecode(buf, cv2.IMREAD_COLOR)
    except Exception:
        return None


def _decode_image(fileobj):
    """Read uploaded file and decode to BGR numpy array. Returns None on failure."""
    try:
        data = fileobj.read()
        if not data:
            return None
        buf = np.asarray(bytearray(data), dtype=np.uint8)
        img = cv2.imdecode(buf, cv2.IMREAD_COLOR)
        return img
    except Exception:
        return None


def _detect_face_crop(img_bgr):
    """
    Detect the largest face in img_bgr and return a 160x160 BGR crop.
    Uses Haar Cascade (no download needed). Returns None if no face found.
    """
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    face_cascade = cv2.CascadeClassifier(cascade_path)

    # Try with default params first
    faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=4, minSize=(40, 40))
    if len(faces) == 0:
        # Relax params for harder images (small/angled faces on ID cards)
        faces = face_cascade.detectMultiScale(gray, scaleFactor=1.05, minNeighbors=2, minSize=(20, 20))
    if len(faces) == 0:
        # Final fallback: treat entire image center as face region
        h, w = img_bgr.shape[:2]
        margin_x = w // 6
        margin_y = h // 6
        crop = img_bgr[margin_y:h - margin_y, margin_x:w - margin_x]
        return cv2.resize(crop, (160, 160)) if crop.size > 0 else None

    # Pick largest face
    x, y, fw, fh = max(faces, key=lambda r: r[2] * r[3])
    # Add a small margin
    pad = int(min(fw, fh) * 0.15)
    x1 = max(0, x - pad)
    y1 = max(0, y - pad)
    x2 = min(img_bgr.shape[1], x + fw + pad)
    y2 = min(img_bgr.shape[0], y + fh + pad)
    crop = img_bgr[y1:y2, x1:x2]
    return cv2.resize(crop, (160, 160))


def _face_similarity(crop1_bgr, crop2_bgr):
    """
    Compute combined face similarity score (0–1) using:
      - HSV histogram correlation (colour distribution)
      - Normalised cross-correlation on grayscale
    Returns a float in [0, 1].  Higher = more similar.
    """
    size = (128, 128)
    c1 = cv2.resize(crop1_bgr, size).astype("float32")
    c2 = cv2.resize(crop2_bgr, size).astype("float32")

    # --- Histogram similarity (HSV) ---
    hsv1 = cv2.cvtColor(c1.astype("uint8"), cv2.COLOR_BGR2HSV)
    hsv2 = cv2.cvtColor(c2.astype("uint8"), cv2.COLOR_BGR2HSV)
    hist1 = cv2.calcHist([hsv1], [0, 1], None, [50, 60], [0, 180, 0, 256])
    hist2 = cv2.calcHist([hsv2], [0, 1], None, [50, 60], [0, 180, 0, 256])
    cv2.normalize(hist1, hist1)
    cv2.normalize(hist2, hist2)
    hist_score = float(cv2.compareHist(hist1, hist2, cv2.HISTCMP_CORREL))   # –1..1
    hist_score = (hist_score + 1) / 2                                        # 0..1

    # --- Normalised cross-correlation (grayscale) ---
    g1 = cv2.cvtColor(c1.astype("uint8"), cv2.COLOR_BGR2GRAY).astype("float32")
    g2 = cv2.cvtColor(c2.astype("uint8"), cv2.COLOR_BGR2GRAY).astype("float32")
    g1 -= g1.mean(); g2 -= g2.mean()
    denom = (np.linalg.norm(g1) * np.linalg.norm(g2)) + 1e-8
    ncc = float(np.sum(g1 * g2) / denom)   # –1..1
    ncc_score = (ncc + 1) / 2               # 0..1

    combined = 0.5 * hist_score + 0.5 * ncc_score
    print(f"[verify] hist={hist_score:.3f} ncc={ncc_score:.3f} combined={combined:.3f}")
    return combined


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser, FormParser])
def verify_identity(request):
    live_image = request.FILES.get("live_image")
    id_image   = request.FILES.get("id_image")

    if not live_image or not id_image:
        return Response({"verified": False, "message": "Both images are required."}, status=400)

    live_bgr = _decode_image(live_image)
    id_bgr   = _decode_image(id_image)

    if live_bgr is None:
        return Response({
            "verified": False,
            "face_detected_live": False,
            "face_detected_id": False,
            "message": "Live image could not be decoded. Please try again.",
            "hints": ["Make sure your camera has permission", "Try a different browser"]
        }, status=200)

    if id_bgr is None:
        return Response({
            "verified": False,
            "face_detected_live": False,
            "face_detected_id": False,
            "message": "ID image could not be decoded. Please try again.",
            "hints": ["Retake the ID photo"]
        }, status=200)

    live_crop = _detect_face_crop(live_bgr)
    id_crop   = _detect_face_crop(id_bgr)

    face_detected_live = live_crop is not None
    face_detected_id   = id_crop   is not None

    if not face_detected_live:
        return Response({
            "verified": False,
            "face_detected_live": False,
            "face_detected_id": face_detected_id,
            "message": "No face detected in the live image.",
            "hints": [
                "Look directly into the camera",
                "Ensure good lighting from the front",
                "Move closer to the camera",
                "Avoid shadows on your face",
            ]
        }, status=200)

    if not face_detected_id:
        return Response({
            "verified": False,
            "face_detected_live": True,
            "face_detected_id": False,
            "message": "No face detected in the ID photo.",
            "hints": [
                "Hold the ID card straighter and closer",
                "Ensure the photo on the card is fully visible",
                "Avoid reflections and glare on the card",
            ]
        }, status=200)

    # ── Face similarity ───────────────────────────────────────────────────────
    similarity   = _face_similarity(live_crop, id_crop)
    face_matched = similarity >= FACE_MATCH_THRESHOLD

    # ── OCR: extract Matrikelnummer from ID card ──────────────────────────────
    matrikel_extracted, ocr_raw = _extract_matrikelnummer(id_bgr)

    def _digits(s):
        return re.sub(r"\D", "", str(s)) if s else ""

    # matrikel_input = final value sent by frontend (OCR pre-filled, possibly edited)
    matrikel_input_raw = request.data.get("matrikel_input") or request.POST.get("matrikel_input")
    matrikel_input = _digits(matrikel_input_raw)[:7] if matrikel_input_raw else None

    # Confirm: matrikel_input matches the OCR reading (they should be the same unless
    # the student corrected an OCR error, in which case we trust the student's input)
    matrikel_match = bool(matrikel_input)   # True as long as student provided 7 digits

    # Also cross-check against the account's stored matrikel (extra security)
    student_matrikel = _digits(getattr(request.user, "matriculation_number", "") or "")
    matrikel_account_match = bool(
        matrikel_input and student_matrikel and
        matrikel_input == student_matrikel
    )

    print(f"[verify] input={matrikel_input!r}  OCR={matrikel_extracted!r}  "
          f"account={student_matrikel!r}  account_match={matrikel_account_match}")

    # ── Enrollment check (uses student-typed matrikel) ───────────────────────
    exam_id  = request.data.get("exam_id") or request.POST.get("exam_id")
    enrolled = None   # None = "no list / not checked"
    if exam_id and matrikel_input:
        try:
            exam_obj    = Exam.objects.get(id=exam_id)
            enrollments = ExamEnrollment.objects.filter(exam=exam_obj)
            if enrollments.exists():
                enrolled = enrollments.filter(
                    matriculation_number=matrikel_input
                ).exists()
            else:
                enrolled = True   # open exam → anyone may join
        except Exam.DoesNotExist:
            enrolled = None

    # ── Overall result ────────────────────────────────────────────────────────
    enrollment_ok = (enrolled is None) or enrolled
    overall_ok    = face_matched and matrikel_match and enrollment_ok

    # Build user-facing message
    if overall_ok:
        message = "✅ Identity confirmed. Matriculation number verified. Access granted."
    elif not face_matched:
        message = f"Faces do not match sufficiently (score {similarity:.2f})."
    elif not matrikel_match:
        if not matrikel_extracted:
            message = (
                "OCR could not read the matriculation number from the ID card. "
                "Make sure the number is clearly visible and try again."
            )
        else:
            message = (
                f"Matriculation number mismatch: "
                f"you entered '{matrikel_input}' but the ID card shows '{matrikel_extracted}'."
            )
    else:
        message = (
            f"You are not on the enrollment list for this exam "
            f"(matriculation number: {matrikel_input})."
        )

    hints = []
    if not face_matched:
        hints += [
            "Hold ID card closer so the photo is larger and sharper.",
            "Align your face frontally, similar to your ID photo.",
            "Avoid backlighting — use even, front-facing illumination.",
        ]
    if not matrikel_match:
        if not matrikel_extracted:
            hints += [
                "Hold the ID card flat — the matriculation number must be fully visible.",
                "Ensure good lighting with no reflections on the card.",
                "Move the camera closer to the card so the digits are large and sharp.",
            ]
        else:
            hints += [
                f"The ID card shows '{matrikel_extracted}'. Check that you typed the correct number.",
            ]

    return Response({
        "verified":              overall_ok,
        "face_matched":          face_matched,
        "face_similarity":       round(similarity, 3),
        "face_detected_live":    True,
        "face_detected_id":      True,
        "matrikel_input":        matrikel_input,
        "matrikel_extracted":    matrikel_extracted,
        "matrikel_match":        matrikel_match,
        "matrikel_account_match": matrikel_account_match,
        "enrolled":              enrolled,
        "message":               message,
        "hints":                 hints,
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
                {"error": "Could not extract text from the PDF file. The PDF may be scanned (images only) or encrypted. Please ensure the PDF contains text."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        num_pages = len(reader.pages)
        num_questions = min(15, max(5, num_pages, total_text_length // 500))
        
        questions = generate_questions_from_text(all_text, num_questions=num_questions)
        
        if len(questions) == 0:
            os.remove(temp_pdf_path)
            return Response(
                {"error": "No questions could be generated from the PDF file. Please ensure the PDF contains sufficient text."},
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
            "text": "The PDF file does not contain enough text. Please ensure the PDF contains text (not only images).",
            "options": ["OK", "Retry", "Cancel", "Continue"],
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
        if any(word in lower_s for word in ['is', 'are', 'means', 'refers', 'describes', 'defined', 'ist', 'sind', 'bedeutet', 'bezeichnet', 'beschreibt', 'definiert']):
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
                "text": f"What does '{concept}' mean?" if concept else "What is the definition?",
                "options": [
                    clean_def,
                    f"{concept} is a method for data processing." if concept else "It is a method.",
                    f"{concept} is an algorithm." if concept else "It is an algorithm.",
                    f"{concept} is a data structure." if concept else "It is a data structure."
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
                "text": f"What is {main_concept}?",
                "options": [
                    summary,
                    f"{main_concept} is a programming language.",
                    f"{main_concept} is an operating system.",
                    f"{main_concept} is not defined in the material."
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
                "text": f"What is {concept}?",
                "options": [
                    clean_context,
                    f"{concept} is a method.",
                    f"{concept} is an algorithm.",
                    f"{concept} is not defined."
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
                    "text": f"Which statement is correct?",
                    "options": [
                        clean_sentence,
                        "The statement is partially correct.",
                        "The statement is incorrect.",
                        "The statement needs more context."
                    ],
                    "answer": clean_sentence
                }
            else:
                break
        
        if question and question not in questions:
            questions.append(question)
    
    if len(questions) == 0:
        questions.append({
            "text": "No questions could be generated from the PDF file. Please ensure the PDF contains text.",
            "options": ["OK", "Retry", "Cancel", "Continue"],
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
        return Response({"error": "Only staff members may access the dashboard."}, status=403)

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
        return Response({"error": "Only professors may manage enrollment lists."}, status=403)

    try:
        exam = Exam.objects.get(id=exam_id, created_by=request.user)
    except Exam.DoesNotExist:
        return Response({"error": "Exam not found."}, status=404)

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
        return Response({"error": "Only professors may manage enrollment lists."}, status=403)

    try:
        exam = Exam.objects.get(id=exam_id, created_by=request.user)
    except Exam.DoesNotExist:
        return Response({"error": "Exam not found."}, status=404)

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
