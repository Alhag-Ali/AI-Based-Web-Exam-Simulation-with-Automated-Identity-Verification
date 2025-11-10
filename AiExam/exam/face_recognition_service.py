import cv2
import numpy as np
from deepface import DeepFace
import pytesseract
from PIL import Image

class FaceRecognitionService:
    def __init__(self):
        pass

    def extract_text_from_id(self, id_image_path):
        """OCR liest Name und Matrikelnummer vom Ausweis"""
        img = Image.open(id_image_path)
        text = pytesseract.image_to_string(img)
        return text

    def compare_faces(self, live_image_path, id_image_path):
        """
        Vergleicht das Gesicht vom Livebild mit dem vom Ausweis.
        Gibt True zurück, wenn es dieselbe Person ist.
        """
        try:
            result = DeepFace.verify(
                img1_path=live_image_path,
                img2_path=id_image_path,
                model_name="VGG-Face",
                enforce_detection=False
            )
            return result["verified"]
        except Exception as e:
            print("Error during face comparison:", e)
            return False
    
    def compare_faces_arrays(self, img1_rgb, img2_rgb):
        """
        Vergleicht zwei bereits extrahierte RGB-Face-Ausschnitte (numpy arrays).
        """
        try:
            result = DeepFace.verify(
                img1_path=img1_rgb,
                img2_path=img2_rgb,
                model_name="VGG-Face",
                enforce_detection=False
            )
            return result.get("verified", False), result.get("distance", 1.0)
        except Exception as e:
            print("Error during face comparison:", e)
            return False, 1.0


