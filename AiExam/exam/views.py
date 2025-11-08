from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from .models import Exam
import json

@csrf_exempt
def upload_student_exam(request):
    if request.method != "POST":
        return JsonResponse({"error": "Nur POST request erlaubt"}, status=405)
    try:
        upload_file = request.FILES.get("exam_json")
        if not upload_file:
            return JsonResponse({'error': 'Keine Datei im Feld "json_file_upload" gefunden.'}, status=400)
        
        student_name = request.POST.get("student_name")
        student_id = request.POST.get("student_id")
        grad = request.POST.get("grad")
        
        # Validation if is a JOSN file
        try:
            json.load(upload_file)
            upload_file.seek(0)
        except json.JSONDecoderError:
            return JsonResponse({'error': 'Datei ist kein valides JSON.'}, status=400)
        
        # Create a Model object a save the JSON file
        new_file = Exam(student_name=student_name,
                        student_id=student_id,
                        grad=grad,
                        exam=upload_file)
        new_file.save()
        
        return JsonResponse({
            'message': 'Datei erfolgreich gespeichert.',
            'file_id': new_file.id
        }, status=201)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@csrf_exempt
def send_exam_to_student(requist):  
pfad_to_exam = "Project\AiExam\Exams_folder\ML_exam.json"