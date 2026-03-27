import os
import uuid

from rest_framework.decorators import api_view, permission_classes, parser_classes
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Exam


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser, FormParser])
def rag_generate_questions(request, exam_id):
    if not request.user.is_staff:
        return Response({"error": "Nur Staff-Mitglieder dürfen Fragen generieren."}, status=403)

    try:
        exam = Exam.objects.get(id=exam_id)
    except Exam.DoesNotExist:
        return Response({"error": "Prüfung nicht gefunden."}, status=404)

    pdf_file = request.FILES.get("pdf_file")
    topics_raw = request.data.get("topics", "")
    n_per_topic = int(request.data.get("n_per_topic", 1))
    groq_api_key = request.data.get("groq_api_key", "").strip() or os.environ.get("GROQ_API_KEY", "")

    if not pdf_file:
        return Response({"error": "Keine PDF-Datei hochgeladen."}, status=400)

    if not pdf_file.name.lower().endswith(".pdf"):
        return Response({"error": "Datei muss eine PDF-Datei sein."}, status=400)

    topics = [t.strip() for t in topics_raw.split("\n") if t.strip()]
    if not topics:
        return Response({"error": "Bitte mindestens ein Thema angeben."}, status=400)

    if n_per_topic < 1 or n_per_topic > 5:
        n_per_topic = 1

    try:
        from pypdf import PdfReader

        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        upload_dir = os.path.join(base_dir, "uploads", "rag_temp")
        os.makedirs(upload_dir, exist_ok=True)

        temp_path = os.path.join(upload_dir, f"rag_{exam.id}_{uuid.uuid4().hex[:8]}.pdf")

        with open(temp_path, "wb+") as f:
            for chunk in pdf_file.chunks():
                f.write(chunk)

        reader = PdfReader(temp_path)
        pages_text = []
        for page in reader.pages:
            t = page.extract_text()
            if t and t.strip():
                pages_text.append(t.strip())

        os.remove(temp_path)

        pdf_text = "\n\n".join(pages_text)

        if len(pdf_text.strip()) < 100:
            return Response(
                {"error": "PDF-Text zu kurz oder konnte nicht extrahiert werden."},
                status=400,
            )

        from .rag_service import generate_questions_rag

        questions = generate_questions_rag(
            pdf_text=pdf_text,
            topics=topics,
            groq_api_key=groq_api_key,
            n_per_topic=n_per_topic,
        )

        if not questions:
            return Response(
                {"error": "Keine Fragen konnten generiert werden. Bitte Themen und PDF prüfen."},
                status=422,
            )

        return Response(
            {
                "questions": questions,
                "count": len(questions),
                "message": f"{len(questions)} Frage(n) erfolgreich mit RAG generiert.",
            }
        )

    except ImportError as e:
        return Response({"error": f"RAG-Pakete fehlen: {str(e)}"}, status=500)
    except ValueError as e:
        return Response({"error": str(e)}, status=400)
    except Exception as e:
        return Response({"error": f"Fehler bei der RAG-Generierung: {str(e)}"}, status=500)
