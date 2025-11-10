
import cv2
import numpy as np
from deepface import DeepFace
import pytesseract
from PIL import Image
import re

def _to_opencv(bfile):
    file_bytes = np.asarray(bytearray(bfile.read()), dtype=np.uint8)
    img = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
    return img

def detect_live_face(img):
    """
    Liefert (face_img, bbox) des größten Gesichts im Frame.
    """
    # DeepFace.extract_faces akzeptiert ndarray
    faces = DeepFace.extract_faces(img_path=img, detector_backend="retinaface", enforce_detection=False)
    if not faces:
        return None, None
    # faces: list of dicts with "facial_area" and "face" (np.ndarray float32 rgb)
    # wähle größtes Gesicht
    faces_sorted = sorted(
        faces, key=lambda f: f.get("facial_area", {}).get("w", 0) * f.get("facial_area", {}).get("h", 0), reverse=True
    )
    best = faces_sorted[0]
    face_rgb_float = (best["face"] * 255).astype("uint8")  # DeepFace liefert float [0..1]
    bbox = best.get("facial_area", {})
    return face_rgb_float, (bbox.get("x"), bbox.get("y"), bbox.get("w"), bbox.get("h"))

def find_id_region(img):
    """
    Heuristik: wir nehmen die untere 40% als ID-Zone und versuchen dort Text-/Foto-Bereich zu finden.
    Gibt (id_roi_bgr) zurück.
    """
    h, w, _ = img.shape
    y0 = int(h * 0.58)  # etwas über dem unteren Drittel
    id_roi = img[y0:h, 0:w].copy()
    return id_roi, (0, y0, w, h - y0)

def detect_id_face(id_roi):
    """
    Versuche, ein Gesicht IM Ausweisbereich zu detektieren (Foto auf Karte).
    """
    faces = DeepFace.extract_faces(img_path=id_roi, detector_backend="retinaface", enforce_detection=False)
    if not faces:
        return None, None
    # wähle kleinstes Gesicht (Ausweisfoto ist oft kleiner)
    faces_sorted = sorted(
        faces, key=lambda f: f.get("facial_area", {}).get("w", 0) * f.get("facial_area", {}).get("h", 0)
    )
    best = faces_sorted[0]
    face_rgb_float = (best["face"] * 255).astype("uint8")
    bbox = best.get("facial_area", {})
    return face_rgb_float, (bbox.get("x"), bbox.get("y"), bbox.get("w"), bbox.get("h"))

def preprocess_for_ocr(bgr):
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    gray = cv2.bilateralFilter(gray, 7, 50, 50)
    _, th = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY+cv2.THRESH_OTSU)
    # etwas Schärfen hilft OCR
    kernel = np.array([[0,-1,0],[-1,5,-1],[0,-1,0]])
    sharp = cv2.filter2D(th, -1, kernel)
    return sharp

def ocr_id_text(id_roi_bgr):
    pre = preprocess_for_ocr(id_roi_bgr)
    pil_img = Image.fromarray(pre)
    # Deutsch & Englisch probieren, PSM 6 (Block), OEM LSTM
    config = "--oem 3 --psm 6 -l deu+eng"
    text = pytesseract.image_to_string(pil_img, config=config)
    return text

def extract_fields_from_text(text):
    """
    Sehr simple Extraktion:
    - Matrikelnummer: Folge aus 6-12 Ziffern
    - Name: suche 'Name' Label oder zwei Großwörter
    """
    # Matrikelnummer
    mnr = None
    m = re.search(r"(Mat(r)?ikel(nummer)?[:\s\-]*)(\d{6,12})", text, re.IGNORECASE)
    if m:
        mnr = m.group(4)
    else:
        m2 = re.search(r"\b(\d{6,12})\b", text)
        if m2: mnr = m2.group(1)

    # grobe Namensheuristik
    name = None
    mname = re.search(r"(Name[:\s\-]+)([A-ZÄÖÜ][A-Za-zÄÖÜäöüß\-]+(?:\s+[A-ZÄÖÜ][A-Za-zÄÖÜäöüß\-]+)?)", text)
    if mname:
        name = mname.group(2)
    else:
        # fallback: zwei große Wörter hintereinander
        m3 = re.search(r"\b([A-ZÄÖÜ][A-Za-zÄÖÜäöüß\-]+)\s+([A-ZÄÖÜ][A-Za-zÄÖÜäöüß\-]+)\b", text)
        if m3:
            name = f"{m3.group(1)} {m3.group(2)}"

    return {"matriculation_number": mnr, "name": name}

def faces_match(face_a_rgb, face_b_rgb):
    """
    Nutzt DeepFace.verify auf zwei RGB-Ausschnitten.
    """
    try:
        result = DeepFace.verify(img1_path=face_a_rgb, img2_path=face_b_rgb, model_name="VGG-Face", enforce_detection=False)
        return bool(result.get("verified", False)), float(result.get("distance", 1.0))
    except Exception:
        return False, 1.0
