# hours_distribution/api_views.py
# API endpoints для AJAX запросов

from rest_framework import viewsets, status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.http import JsonResponse
from .models import (
    Semester, AcademicYear, StudentGroup, StreamGroup,
    CurriculumSubject, Subject, Course, Faculty, Department
)
from .serializers import (
    SemesterSerializer, StudentGroupSerializer, CurriculumSubjectSerializer
)


# ────────────────────────────────────────────────────────────────────────────────
# API для семестров
# ────────────────────────────────────────────────────────────────────────────────

""" @api_view(['GET'])
def api_semesters(request):
    # Получить список семестров по учебному году.
    academic_year_id = request.GET.get('academic_year')
    
    if not academic_year_id:
        return Response(
            {'error': 'academic_year parameter is required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        semesters = Semester.objects.filter(
            academic_year_id=academic_year_id
        ).order_by('number')
        
        serializer = SemesterSerializer(semesters, many=True)
        return Response(serializer.data)
    
    except Exception as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        ) """

@login_required
def api_semesters(request):
    academic_year_id = request.GET.get('academic_year')
    
    if not academic_year_id:
        return JsonResponse({'error': 'academic_year required'}, status=400)
    
    try:
        from .models import Semester
        
        semesters = Semester.objects.filter(
            academic_year_id=academic_year_id
        ).values('id', 'number', 'start_date', 'end_date')
        
        return JsonResponse(list(semesters), safe=False)
    
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

# ────────────────────────────────────────────────────────────────────────────────
# API для групп студентов
# ────────────────────────────────────────────────────────────────────────────────

@api_view(['GET'])
def api_student_groups(request):
    """Получить список групп студентов с фильтрацией."""
    course_id = request.GET.get('course')
    faculty_id = request.GET.get('faculty')
    program_id = request.GET.get('program')
    
    groups = StudentGroup.objects.filter(is_active=True)
    
    if course_id:
        groups = groups.filter(course_id=course_id)
    if faculty_id:
        groups = groups.filter(bachelor_program__faculty_id=faculty_id)
    if program_id:
        groups = groups.filter(bachelor_program_id=program_id)
    
    groups = groups.select_related(
        'course', 'bachelor_program', 'bachelor_program__faculty'
    ).order_by('course__number', 'name')
    
    serializer = StudentGroupSerializer(groups, many=True)
    return Response(serializer.data)


# ────────────────────────────────────────────────────────────────────────────────
# API для дисциплин учебного плана
# ────────────────────────────────────────────────────────────────────────────────

@api_view(['GET'])
def api_curriculum_subjects(request):
    """Получить дисциплины по курсу и семестру."""
    course_id = request.GET.get('course')
    semester_id = request.GET.get('semester')
    
    subjects = CurriculumSubject.objects.all()
    
    if course_id:
        subjects = subjects.filter(course_id=course_id)
    if semester_id:
        subjects = subjects.filter(semester_id=semester_id)
    
    subjects = subjects.select_related(
        'subject', 'course', 'semester', 'curriculum'
    ).order_by('subject__name')
    
    serializer = CurriculumSubjectSerializer(subjects, many=True)
    return Response(serializer.data)


# ────────────────────────────────────────────────────────────────────────────────
# Вспомогательные API endpoints
# ────────────────────────────────────────────────────────────────────────────────

@login_required
@require_http_methods(["GET"])
def api_departments_by_faculty(request):
    """Получить кафедры по факультету."""
    faculty_id = request.GET.get('faculty')
    
    if not faculty_id:
        return JsonResponse({'departments': []})
    
    departments = Department.objects.filter(
        faculty_id=faculty_id
    ).values('id', 'name', 'short_name')
    
    return JsonResponse({'departments': list(departments)})


@login_required
@require_http_methods(["GET"])
def api_courses(request):
    """Получить список всех курсов."""
    courses = Course.objects.all().values('id', 'number', 'name')
    return JsonResponse({'courses': list(courses)})


@login_required
@require_http_methods(["GET"])
def api_faculties(request):
    """Получить список всех факультетов."""
    faculties = Faculty.objects.all().values('id', 'name', 'short_name')
    return JsonResponse({'faculties': list(faculties)})