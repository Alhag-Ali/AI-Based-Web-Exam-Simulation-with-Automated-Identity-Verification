from django.shortcuts import render
from django.http import JsonResponse, FileResponse
from django.views.decorators.csrf import csrf_exempt
from .models import Exam, SubjectExam
from django.shortcuts import get_object_or_404
import os
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
def upload_exam_from_prof(request):
    if request.method != "POST":
        return JsonResponse({"error" : "Just POST requist is allowed"}, status=405)
    
    try:
        upload_file = request.FILES.get("exam_from_Prof")
        if not upload_file:
            return JsonResponse({'error': 'No file in exam_from_Prof'})
        
        name = request.POST.get("name")
        exam_datetime = request.POST.get("exam_datetime")
        
        # Validation Json File
        try:
            json.load(upload_file)
            upload_file.seek(0)
        except json.JSONDecodeError:
            return JsonResponse({'error':'No valid JSON File'}, status=500)
        
        # Create a Model object a save the JSON file
        new_file = SubjectExam(name=name,
                               exam_datetime=exam_datetime,
                               exam=upload_file
        )
        new_file.save()
        
        return JsonResponse({'Message':'Successfully upload.',
                             'file_id': new_file.id},
                            status=201)
    except Exception as e:
        return JsonResponse({'Error': str(e)}, status=500)

@csrf_exempt
def get_exam(request):
    if request.method != "GET":
        return JsonResponse({"error" : "Just get requist is allowed"}, status=405)
    student_id = request.GET.get("student_id")
    subject = request.GET.get("subject")
                
    if not student_id or not subject:
        return JsonResponse({'error': 'Parameter student_id and subject are necessary'})
    
    try:
        exam_record = get_object_or_404(
            SubjectExam,
            name__iexact=subject
        )
        
    except ValueError:
        return JsonResponse({'error': 'invalid subject'}, status=400)
    
    json_file = exam_record.exam
    if not json_file:
        return JsonResponse({'error': 'Datensatz gefunden, aber es ist keine JSON-Datei angehängt.'}, status=404)    
    filename = f"Exam_{subject}_{student_id}.json"

    return FileResponse(json_file.open('rb'), as_attachment=True, filename=filename)
    