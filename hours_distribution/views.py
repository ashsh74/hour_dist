from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponse, JsonResponse, HttpResponseForbidden
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Sum, Q, Avg
from django.views.decorators.http import require_http_methods
from django.middleware.csrf import get_token
import json
from hours_distribution.models import * 
from .utils.export_utils import ExcelExporter, PDFExporter, ChartGenerator
from .forms import StreamGroupForm, WorkloadDistributionForm, StudentGroupModalForm, StudentGroupCreateForm
from .permissions import role_required, user_has_any_role, CustomPermissions, RoleRequiredMixin, get_user_profile


# ============= HELPER FUNCTIONS FOR ROLE-BASED DATA FILTERING =============

def check_faculty_access(request, faculty_id):
    """Проверяет доступ декана/главы к факультету. Возвращает False если доступ запрещён."""
    profile = get_user_profile(request.user)
    
    if profile.role == 'admin':
        return True
    
    if profile.role == 'dean':
        # Декан может только смотреть свой факультет
        if profile.faculty_id != faculty_id:
            return False
    elif profile.role == 'head':
        # Главе доступны факультеты через их кафедру
        department = profile.department
        if department and department.faculty_id != faculty_id:
            return False
    
    return True


def check_department_access(request, department_id):
    """Проверяет доступ к кафедре. Возвращает False если доступ запрещён."""
    profile = get_user_profile(request.user)
    
    if profile.role == 'admin':
        return True
    
    if profile.role == 'dean':
        # Декан может смотреть кафедры только своего факультета
        try:
            dept = Department.objects.get(id=department_id)
            if profile.faculty_id != dept.faculty_id:
                return False
        except Department.DoesNotExist:
            return False
    elif profile.role == 'head':
        # Главе доступна только его кафедра
        if profile.department_id != department_id:
            return False
    
    return True


def filter_departments_by_role(request, departments_qs):
    """Фильтрует кафедры доступные для роли пользователя."""
    profile = get_user_profile(request.user)
    
    if profile.role == 'admin':
        return departments_qs
    elif profile.role == 'dean':
        return departments_qs.filter(faculty=profile.faculty)
    elif profile.role == 'head':
        return departments_qs.filter(id=profile.department_id)
    
    return departments_qs.none()


def filter_faculties_by_role(request, faculties_qs):
    """Фильтрует факультеты доступные для роли пользователя."""
    profile = get_user_profile(request.user)
    
    if profile.role == 'admin':
        return faculties_qs
    elif profile.role == 'dean':
        return faculties_qs.filter(id=profile.faculty_id)
    elif profile.role == 'head':
        # Главе доступен факультет через кафедру
        if profile.department:
            return faculties_qs.filter(id=profile.department.faculty_id)
    
    return faculties_qs.none()


@login_required
def index(request):
    """Главная страница с ролевыми шаблонами"""
    from .permissions import get_user_profile
    
    profile = get_user_profile(request.user)
    if not profile:
        return redirect('admin:login')
    
    role = profile.role
    
    # Выбираем шаблон и подготавливаем контекст в зависимости от роли
    if role == 'admin':
        template_name = 'hours_distribution/index_admin.html'
        context = get_admin_dashboard_context()
    elif role == 'dean':
        template_name = 'hours_distribution/index_dean.html'
        context = get_dean_dashboard_context(profile)
    elif role == 'head':
        template_name = 'hours_distribution/index_head.html'
        context = get_head_dashboard_context(profile)
    elif role == 'teacher':
        template_name = 'hours_distribution/index_teacher.html'
        context = get_teacher_dashboard_context(request.user)
    elif role == 'planner':
        template_name = 'hours_distribution/index_planner.html'
        context = get_planner_dashboard_context()
    else:
        template_name = 'hours_distribution/index.html'
        context = {}
    
    return render(request, template_name, context)


def get_admin_dashboard_context():
    """Контекст для администратора"""
    workload_agg = TeacherWorkload.objects.aggregate(
        lecture=Sum('hours_lecture'),
        practice=Sum('hours_practice'),
        lab=Sum('hours_lab')
    )
    workload_total = sum([   
            workload_agg['lecture'] or 0,
            workload_agg['practice'] or 0,
            workload_agg['lab'] or 0
    ])
    
    return {
        'departments_count': Department.objects.count(),
        'teachers_count': Teacher.objects.count(),
        'subjects_count': Subject.objects.count(),
        'faculties_count': Faculty.objects.count(),
        'current_year': AcademicYear.objects.filter(is_current=True).first(),
        'workload_total': workload_total,
    }


def get_dean_dashboard_context(profile):
    """Контекст для декана - только данные его факультета"""
    faculty = profile.faculty
    
    # Кафедры факультета
    departments = Department.objects.filter(faculty=faculty)
    
    # Преподаватели факультета
    teachers = Teacher.objects.filter(department__faculty=faculty)
    
    # Нагрузка факультета
    workload_agg = TeacherWorkload.objects.filter(
        teacher__department__faculty=faculty
    ).aggregate(
        lecture=Sum('hours_lecture'),
        practice=Sum('hours_practice'),
        lab=Sum('hours_lab')
    )
    workload_total = sum([   
            workload_agg['lecture'] or 0,
            workload_agg['practice'] or 0,
            workload_agg['lab'] or 0
    ])
    
    # Пользователи факультета
    users_in_faculty = User.objects.filter(profile__faculty=faculty)
    
    return {
        'departments_count': departments.count(),
        'teachers_count': teachers.count(),
        'users_count': users_in_faculty.count(),
        'current_year': AcademicYear.objects.filter(is_current=True).first(),
        'workload_total': workload_total,
    }


def get_head_dashboard_context(profile):
    """Контекст для зав. кафедрой - только данные его кафедры"""
    department = profile.department
    
    # Преподаватели кафедры
    teachers = Teacher.objects.filter(department=department)
    
    # Группы студентов (через TeacherWorkload -> CurriculumSubjectGroup)
    student_groups = StudentGroup.objects.filter(
        curriculumsubjectgroup__teacherworkload__teacher__department=department
    ).distinct()
    
    # Поточные группы (через TeacherWorkload -> CurriculumSubjectGroup)
    stream_groups = StreamGroup.objects.filter(
        curriculumsubjectgroup__teacherworkload__teacher__department=department
    ).distinct()
    
    # Нагрузка кафедры
    workload_agg = TeacherWorkload.objects.filter(
        teacher__department=department
    ).aggregate(
        lecture=Sum('hours_lecture'),
        practice=Sum('hours_practice'),
        lab=Sum('hours_lab')
    )
    workload_total = sum([   
            workload_agg['lecture'] or 0,
            workload_agg['practice'] or 0,
            workload_agg['lab'] or 0
    ])
    
    return {
        'departments_count': 1,
        'teachers_count': teachers.count(),
        'groups_count': student_groups.count(),
        'stream_groups_count': stream_groups.count(),
        'current_year': AcademicYear.objects.filter(is_current=True).first(),
        'workload_total': workload_total,
    }


def get_teacher_dashboard_context(user):
    """Контекст для преподавателя - только его нагрузка"""
    try:
        teacher = Teacher.objects.get(user=user)
    except Teacher.DoesNotExist:
        return {
            'subjects_count': 0,
            'workload_total': 0,
            'current_year': AcademicYear.objects.filter(is_current=True).first(),
        }
    
    # Дисциплины преподавателя (через TeacherWorkload -> CurriculumSubjectGroup -> CurriculumSubject)
    subjects = Subject.objects.filter(
        curriculumsubject__curriculumsubjectgroup__teacherworkload__teacher=teacher
    ).distinct()
    
    # Нагрузка преподавателя
    workload_agg = TeacherWorkload.objects.filter(
        teacher=teacher
    ).aggregate(
        lecture=Sum('hours_lecture'),
        practice=Sum('hours_practice'),
        lab=Sum('hours_lab')
    )
    workload_total = sum([   
            workload_agg['lecture'] or 0,
            workload_agg['practice'] or 0,
            workload_agg['lab'] or 0
    ])
    
    return {
        'subjects_count': subjects.count(),
        'workload_total': workload_total,
        'current_year': AcademicYear.objects.filter(is_current=True).first(),
    }


def get_planner_dashboard_context():
    """Контекст для планировщика - общие статистики"""
    workload_agg = TeacherWorkload.objects.aggregate(
        lecture=Sum('hours_lecture'),
        practice=Sum('hours_practice'),
        lab=Sum('hours_lab')
    )
    workload_total = sum([   
            workload_agg['lecture'] or 0,
            workload_agg['practice'] or 0,
            workload_agg['lab'] or 0
    ])
    
    return {
        'groups_count': StudentGroup.objects.count(),
        'stream_groups_count': StreamGroup.objects.count(),
        'current_year': AcademicYear.objects.filter(is_current=True).first(),
        'workload_total': workload_total,
    }

@role_required('admin', 'dean', 'head')
def department_report(request, department_id=None):
    """Отчет по кафедре"""
    # Фильтруем доступные кафедры по ролям
    departments = filter_departments_by_role(request, Department.objects.all().select_related('faculty'))
    
    if not department_id:
        return render(request, 'hours_distribution/reports/department.html', {
            'departments': departments,
            'department': None
        })
    
    department = get_object_or_404(Department, id=department_id)
    
    # Проверяем доступ к кафедре
    if not check_department_access(request, department_id):
        return HttpResponseForbidden("Доступ запрещён. Вы не можете просматривать эту кафедру.")
    
    current_year = AcademicYear.objects.filter(is_current=True).first()
    
    if not current_year:
        messages.error(request, "Не установлен текущий учебный год")
        return redirect('hours_distribution:index')
    
    # Получаем всю нагрузку кафедры за один запрос
    workloads_qs = TeacherWorkload.objects.filter(
        teacher__department=department,
        academic_year=current_year,
        status__in=['approved', 'completed']
    ).select_related(
        'teacher',
        'curriculum_subject_group',
        'curriculum_subject_group__curriculum_subject',
        'curriculum_subject_group__curriculum_subject__subject',
        'curriculum_subject_group__curriculum_subject__course',
        'curriculum_subject_group__student_group',
        'curriculum_subject_group__stream_group',
    )
    
    # Получаем учителей с активным статусом
    teachers = Teacher.objects.filter(department=department, is_active=True)
    
    # Группируем нагрузку по преподавателям в один проход
    workload_by_teacher = {}
    for wl in workloads_qs:
        teacher_id = wl.teacher_id
        if teacher_id not in workload_by_teacher:
            workload_by_teacher[teacher_id] = []
        workload_by_teacher[teacher_id].append(wl)
    
    workload_data = []
    total_hours_all = 0
    
    for teacher in teachers:
        teacher_workloads = workload_by_teacher.get(teacher.id, [])
        total_hours = sum(wl.total_hours() for wl in teacher_workloads)
        total_hours_all += total_hours
        
        # Рассчитываем процент нагрузки
        workload_percentage = 0
        if teacher.workload_hours and teacher.workload_hours > 0:
            max_hours = teacher.workload_hours * 36  # 36 недель в учебном году
            workload_percentage = round((total_hours / max_hours) * 100, 1)
        
        workload_data.append({
            'teacher': teacher,
            'total_hours': total_hours,
            'workloads': teacher_workloads,
            'workload_percentage': workload_percentage
        })
    
    # Подготовка данных для графика
    chart_data = None
    if workload_data:
        teacher_names = [f"{wd['teacher'].last_name} {wd['teacher'].first_name[0]}." for wd in workload_data]
        teacher_hours = [wd['total_hours'] for wd in workload_data]
        chart_data = {
            'teacher_names': json.dumps(teacher_names, ensure_ascii=False),
            'teacher_hours': json.dumps(teacher_hours)
        }
    
    # Получаем распределение часов по типам единым запросом
    hour_types_data = workloads_qs.aggregate(
        lecture=Sum('hours_lecture'),
        practice=Sum('hours_practice'),
        lab=Sum('hours_lab')
    )
    
    hour_types = {
        'lecture': hour_types_data['lecture'] or 0,
        'practice': hour_types_data['practice'] or 0,
        'lab': hour_types_data['lab'] or 0,
    }
    
    context = {
        'department': department,
        'departments': departments,
        'workload_data': workload_data,
        'teachers_count': teachers.count(),
        'total_hours': total_hours_all,
        'current_year': current_year,
        'hour_types': hour_types,
        'chart_data': chart_data,
        'student_groups': list({
            (wl.curriculum_subject_group.student_group.id if wl.curriculum_subject_group and wl.curriculum_subject_group.student_group else None): wl.curriculum_subject_group.student_group
            for wl in workloads_qs
            if wl.curriculum_subject_group and wl.curriculum_subject_group.student_group
        }.values()),
        'stream_groups': list({
            (wl.curriculum_subject_group.stream_group.id if wl.curriculum_subject_group and wl.curriculum_subject_group.stream_group else None): wl.curriculum_subject_group.stream_group
            for wl in workloads_qs
            if wl.curriculum_subject_group and wl.curriculum_subject_group.stream_group
        }.values())
    }
    
    return render(request, 'hours_distribution/reports/department_detail.html', context)

@role_required('admin', 'dean', 'head')
def faculty_report(request, faculty_id=None):
    """Отчет по факультету"""
    # Фильтруем доступные факультеты по ролям
    faculties = filter_faculties_by_role(request, Faculty.objects.all())
    
    if not faculty_id:
        return render(request, 'hours_distribution/reports/faculty.html', {
            'faculties': faculties,
            'faculty': None
        })
    
    faculty = get_object_or_404(Faculty, id=faculty_id)
    
    # Проверяем доступ к факультету
    if not check_faculty_access(request, faculty_id):
        return HttpResponseForbidden("Доступ запрещён. Вы не можете просматривать этот факультет.")
    
    current_year = AcademicYear.objects.filter(is_current=True).first()
    
    if not current_year:
        messages.error(request, "Не установлен текущий учебный год")
        return redirect('hours_distribution:index')
    
    # Получаем все нагрузки факультета за один запрос
    workloads = TeacherWorkload.objects.filter(
        teacher__department__faculty=faculty,
        academic_year=current_year,
        status__in=['approved', 'completed']
    ).select_related(
        'teacher__department',
        'curriculum_subject_group',
        'curriculum_subject_group__student_group',
        'curriculum_subject_group__stream_group'
    )
    
    # Получаем все кафедры факультета
    departments = Department.objects.filter(faculty=faculty)
    department_ids = set(departments.values_list('id', flat=True))
    
    # Группируем статистику по кафедрам (один проход)
    dept_stats_dict = {}
    
    for wl in workloads:
        dept_id = wl.teacher.department_id
        if dept_id not in dept_stats_dict:
            dept_stats_dict[dept_id] = {
                'total_hours': 0,
                'lecture_hours': 0,
                'practice_hours': 0,
                'lab_hours': 0,
                'teachers': set()
            }
        
        stats = dept_stats_dict[dept_id]
        stats['total_hours'] += wl.total_hours()
        stats['lecture_hours'] += wl.hours_lecture
        stats['practice_hours'] += wl.hours_practice
        stats['lab_hours'] += wl.hours_lab
        stats['teachers'].add(wl.teacher_id)
    
    # Получим количество учителей на каждую кафедру
    teachers_by_dept = {}
    for teacher_info in Teacher.objects.filter(department__in=department_ids, is_active=True).values('id', 'department_id'):
        dept_id = teacher_info['department_id']
        if dept_id not in teachers_by_dept:
            teachers_by_dept[dept_id] = 0
        teachers_by_dept[dept_id] += 1
    
    # Формируем итоговый список
    department_stats = []
    total_faculty_hours = 0
    total_faculty_teachers = 0
    
    for dept in departments:
        stats = dept_stats_dict.get(dept.id, {
            'total_hours': 0,
            'lecture_hours': 0,
            'practice_hours': 0,
            'lab_hours': 0,
            'teachers': set()
        })
        
        teachers_count = teachers_by_dept.get(dept.id, 0)
        total_faculty_hours += stats['total_hours']
        total_faculty_teachers += teachers_count
        
        department_stats.append({
            'department': dept,
            'teachers_count': teachers_count,
            'total_hours': stats['total_hours'],
            'lecture_hours': stats['lecture_hours'],
            'practice_hours': stats['practice_hours'],
            'lab_hours': stats['lab_hours'],
            'avg_hours_per_teacher': round(stats['total_hours'] / teachers_count, 1) if teachers_count > 0 else 0
        })
    
    # Программы бакалавриата факультета
    programs = BachelorProgram.objects.filter(faculty=faculty)
    
    # Подготовка данных для графика
    chart_data = None
    if department_stats:
        dept_names = [ds['department'].short_name for ds in department_stats]
        dept_hours = [ds['total_hours'] for ds in department_stats]
        chart_data = {
            'dept_names': json.dumps(dept_names, ensure_ascii=False),
            'dept_hours': json.dumps(dept_hours),
            'dept_teachers': json.dumps([ds['teachers_count'] for ds in department_stats])
        }
    
    context = {
        'faculty': faculty,
        'faculties': faculties,
        'department_stats': department_stats,
        'programs': programs,
        'total_faculty_hours': total_faculty_hours,
        'total_faculty_teachers': total_faculty_teachers,
        'departments_count': departments.count(),
        'current_year': current_year,
        'chart_data': chart_data,
        'student_groups': list({
            (wl.curriculum_subject_group.student_group.id if wl.curriculum_subject_group and wl.curriculum_subject_group.student_group else None): wl.curriculum_subject_group.student_group
            for wl in workloads
            if wl.curriculum_subject_group and wl.curriculum_subject_group.student_group
        }.values()),
        'stream_groups': list({
            (wl.curriculum_subject_group.stream_group.id if wl.curriculum_subject_group and wl.curriculum_subject_group.stream_group else None): wl.curriculum_subject_group.stream_group
            for wl in workloads
            if wl.curriculum_subject_group and wl.curriculum_subject_group.stream_group
        }.values())
    }
    
    return render(request, 'hours_distribution/reports/faculty_detail.html', context)

@role_required('admin', 'dean', 'head')
def university_report(request):
    """Отчет по университету"""
    current_year = AcademicYear.objects.filter(is_current=True).first()
    if not current_year:
        messages.error(request, "Не установлен текущий учебный год")
        return redirect('hours_distribution:index')

    # Получаем все нагрузки за один запрос
    workloads = TeacherWorkload.objects.filter(
        academic_year=current_year,
        status__in=['approved', 'completed']
    ).select_related('teacher__department__faculty')

    # Статистика по факультетам (группируем в памяти один раз)
    faculty_stats_dict = {}

    for wl in workloads:
        faculty = wl.teacher.department.faculty
        faculty_id = faculty.id

        if faculty_id not in faculty_stats_dict:
            faculty_stats_dict[faculty_id] = {
                'faculty': faculty,
                'departments': set(),
                'teachers': set(),
                'total_hours': 0,
                'lecture_hours': 0,
                'practice_hours': 0,
                'lab_hours': 0
            }

        stats = faculty_stats_dict[faculty_id]
        stats['departments'].add(wl.teacher.department_id)
        stats['teachers'].add(wl.teacher_id)
        stats['total_hours'] += wl.total_hours()
        stats['lecture_hours'] += wl.hours_lecture
        stats['practice_hours'] += wl.hours_practice
        stats['lab_hours'] += wl.hours_lab

    # Подсчитаем общее количество учителей для точности
    all_active_teachers = Teacher.objects.filter(is_active=True).values('id', 'department__faculty_id')
    teachers_by_faculty = {}
    for teacher_info in all_active_teachers:
        faculty_id = teacher_info['department__faculty_id']
        if faculty_id not in teachers_by_faculty:
            teachers_by_faculty[faculty_id] = set()
        teachers_by_faculty[faculty_id].add(teacher_info['id'])

    # Формируем финальный список со всеми stat'ми
    faculty_stats = []
    for faculty_id, stats in faculty_stats_dict.items():
        teachers_count = len(teachers_by_faculty.get(faculty_id, set()))
        faculty_stats.append({
            'faculty': stats['faculty'],
            'departments_count': len(stats['departments']),
            'teachers_count': teachers_count,
            'total_hours': stats['total_hours'],
            'lecture_hours': stats['lecture_hours'],
            'practice_hours': stats['practice_hours'],
            'lab_hours': stats['lab_hours'],
            'avg_hours_per_teacher': stats['total_hours'] / teachers_count if teachers_count > 0 else 0
        })

    # Общая статистика
    total_stats = {
        'faculties_count': Faculty.objects.count(),
        'departments_count': Department.objects.count(),
        'teachers_count': Teacher.objects.filter(is_active=True).count(),
        'programs_count': BachelorProgram.objects.count(),
        'subjects_count': Subject.objects.count(),
        'total_hours': sum(item['total_hours'] for item in faculty_stats)
    }

    # Распределение часов по типам
    hour_types = {
        'lecture': sum(item['lecture_hours'] for item in faculty_stats),
        'practice': sum(item['practice_hours'] for item in faculty_stats),
        'lab': sum(item['lab_hours'] for item in faculty_stats),
    }

    # Генерация графиков
    if faculty_stats:
        faculty_names = [fs['faculty'].short_name for fs in faculty_stats]
        faculty_hours = [fs['total_hours'] for fs in faculty_stats]

        import json
        chart_data = {
            'faculty_names': json.dumps(faculty_names, ensure_ascii=False),
            'faculty_hours': json.dumps(faculty_hours),
            'hour_types': json.dumps(list(hour_types.values())),
            'hour_labels': json.dumps(['Лекции', 'Практики', 'Лабораторные'])
        }
    else:
        chart_data = None

    context = {
        'faculty_stats': faculty_stats,
        'total_stats': total_stats,
        'hour_types': hour_types,
        'current_year': current_year,
        'chart_data': chart_data
    }

    return render(request, 'hours_distribution/reports/university.html', context)

@role_required('admin', 'dean', 'head')
def departments_summary_report(request):
    """Итоговый отчет по кафедрам с преподавателями"""
    current_year = AcademicYear.objects.filter(is_current=True).first()
    if not current_year:
        messages.error(request, "Не установлен текущий учебный год")
        return redirect('hours_distribution:index')

    # Фильтруем доступные кафедры по ролям
    departments = filter_departments_by_role(request, Department.objects.all())

    # Получаем все нагрузки за один запрос, фильтруя по доступным кафедрам
    workloads = TeacherWorkload.objects.filter(
        academic_year=current_year,
        status__in=['approved', 'completed'],
        teacher__department__in=departments
    ).select_related('teacher__department__faculty')

    # Статистика по преподавателям
    teacher_stats_dict = {}
    department_stats_dict = {}

    for wl in workloads:
        teacher = wl.teacher
        department = teacher.department
        department_id = department.id
        teacher_id = teacher.id

        # Инициализируем статистику преподавателя
        if teacher_id not in teacher_stats_dict:
            teacher_stats_dict[teacher_id] = {
                'teacher': teacher,
                'department_id': department_id,
                'total_hours': 0,
                'lecture_hours': 0,
                'practice_hours': 0,
                'lab_hours': 0
            }

        # Обновляем статистику преподавателя
        teacher_stats = teacher_stats_dict[teacher_id]
        teacher_stats['total_hours'] += wl.total_hours()
        teacher_stats['lecture_hours'] += wl.hours_lecture
        teacher_stats['practice_hours'] += wl.hours_practice
        teacher_stats['lab_hours'] += wl.hours_lab

        # Инициализируем статистику кафедры
        if department_id not in department_stats_dict:
            department_stats_dict[department_id] = {
                'department': department,
                'teachers': set(),
                'total_hours': 0,
                'lecture_hours': 0,
                'practice_hours': 0,
                'lab_hours': 0
            }

        # Обновляем статистику кафедры
        stats = department_stats_dict[department_id]
        stats['teachers'].add(teacher_id)
        stats['total_hours'] += wl.total_hours()
        stats['lecture_hours'] += wl.hours_lecture
        stats['practice_hours'] += wl.hours_practice
        stats['lab_hours'] += wl.hours_lab

    # Подсчитаем общее количество учителей для точности
    # Список всех активных преподавателей по кафедрам
    all_active_teachers = Teacher.objects.filter(
        is_active=True,
        department__in=departments
    ).values('id', 'department_id')

    # Чтобы не выполнять отдельный запрос за каждым учителем,
    # заранее получим объекты преподавателей в словарь по id.
    teacher_objects = Teacher.objects.filter(
        is_active=True,
        department__in=departments
    ).in_bulk()

    teachers_by_department = {}
    for teacher_info in all_active_teachers:
        department_id = teacher_info['department_id']
        if department_id not in teachers_by_department:
            teachers_by_department[department_id] = set()
        teachers_by_department[department_id].add(teacher_info['id'])

        # Убедимся, что даже преподаватели без нагрузок присутствуют
        # в словаре teacher_stats_dict с нулевой статистикой.
        tid = teacher_info['id']
        if tid not in teacher_stats_dict:
            teacher = teacher_objects.get(tid)
            teacher_stats_dict[tid] = {
                'teacher': teacher,
                'department_id': department_id,
                'total_hours': 0,
                'lecture_hours': 0,
                'practice_hours': 0,
                'lab_hours': 0,
            }

    # Формируем финальный список со всеми stat'ми и преподавателями
    department_stats = []
    for department_id, stats in department_stats_dict.items():
        teachers_count = len(teachers_by_department.get(department_id, set()))
        
        # Получаем преподавателей этой кафедры
        department_teachers = [
            teacher_stats_dict[t_id]
            for t_id in teachers_by_department.get(department_id, set())
        ]
        # Сортируем по фамилии
        department_teachers.sort(key=lambda x: x['teacher'].last_name)
        
        department_stats.append({
            'department': stats['department'],
            'faculty': stats['department'].faculty,
            'teachers_count': teachers_count,
            'total_hours': stats['total_hours'],
            'lecture_hours': stats['lecture_hours'],
            'practice_hours': stats['practice_hours'],
            'lab_hours': stats['lab_hours'],
            'avg_hours_per_teacher': stats['total_hours'] / teachers_count if teachers_count > 0 else 0,
            'teachers': department_teachers
        })

    # Общая статистика
    total_stats = {
        'departments_count': len(department_stats),
        'teachers_count': sum(item['teachers_count'] for item in department_stats),
        'total_hours': sum(item['total_hours'] for item in department_stats),
        'lecture_hours': sum(item['lecture_hours'] for item in department_stats),
        'practice_hours': sum(item['practice_hours'] for item in department_stats),
        'lab_hours': sum(item['lab_hours'] for item in department_stats)
    }

    # Генерация графиков
    if department_stats:
        department_names = [f"{ds['department'].name} ({ds['department'].faculty.short_name})" for ds in department_stats]
        department_hours = [ds['total_hours'] for ds in department_stats]

        import json
        chart_data = {
            'department_names': json.dumps(department_names, ensure_ascii=False),
            'department_hours': json.dumps(department_hours),
            'hour_types': json.dumps([total_stats['lecture_hours'], total_stats['practice_hours'], total_stats['lab_hours']]),
            'hour_labels': json.dumps(['Лекции', 'Практики', 'Лабораторные'])
        }
    else:
        chart_data = None

    context = {
        'department_stats': department_stats,
        'total_stats': total_stats,
        'current_year': current_year,
        'chart_data': chart_data
    }

    return render(request, 'hours_distribution/reports/departments_summary.html', context)

@role_required('admin', 'dean', 'head')
def teacher_report(request, teacher_id=None):
    """Отчет по нагрузке конкретного преподавателя"""
    teachers = Teacher.objects.filter(is_active=True).select_related('department')
    
    if not teacher_id:
        return render(request, 'hours_distribution/reports/teacher.html', {
            'teachers': teachers,
            'teacher': None
        })
    
    teacher = get_object_or_404(Teacher, id=teacher_id)
    current_year = AcademicYear.objects.filter(is_current=True).first()
    if not current_year:
        messages.error(request, "Не установлен текущий учебный год")
        return redirect('hours_distribution:index')
    
    workloads = TeacherWorkload.objects.filter(
        teacher=teacher,
        academic_year=current_year,
        status__in=['approved', 'completed']
    ).select_related(
        'curriculum_subject_group__curriculum_subject__subject',
        'curriculum_subject_group__curriculum_subject__course',
    )

    total_hours = sum(wl.total_hours() for wl in workloads)
    hour_types = {
        'lecture': sum(wl.hours_lecture for wl in workloads),
        'practice': sum(wl.hours_practice for wl in workloads),
        'lab': sum(wl.hours_lab for wl in workloads),
    }

    # процент нагрузки
    workload_percentage = 0
    if teacher.workload_hours and teacher.workload_hours > 0:
        max_hours = teacher.workload_hours * 36
        workload_percentage = round((total_hours / max_hours) * 100, 1)

    context = {
        'teacher': teacher,
        'teachers': teachers,
        'workloads': workloads,
        'total_hours': total_hours,
        'hour_types': hour_types,
        'current_year': current_year,
        'workload_percentage': workload_percentage
    }
    return render(request, 'hours_distribution/reports/teacher_detail.html', context)

@role_required('admin', 'dean', 'head', 'planner')
def export_report(request, report_type):
    """Экспорт отчета"""
    format_type = request.GET.get('format', 'excel')
    year_id = request.GET.get('year')
    
    current_year = AcademicYear.objects.filter(is_current=True).first()
    if not current_year:
        messages.error(request, "Не установлен текущий учебный год")
        return redirect('hours_distribution:index')
    
    if report_type == 'department':
        department_id = request.GET.get('department')
        if not department_id:
            return HttpResponse('Не указана кафедра', status=400)
        
        department = get_object_or_404(Department, id=department_id)
        
        workloads = TeacherWorkload.objects.filter(
            teacher__department=department,
            academic_year=current_year,
            status__in=['approved', 'completed']
        ).select_related(
            'teacher', 
            'curriculum_subject_group__curriculum_subject__subject',
            'curriculum_subject_group__curriculum_subject__course',
        )
        
        if format_type == 'excel':
            buffer = ExcelExporter.export_department_report(department, workloads, current_year)
            response = HttpResponse(
                buffer.getvalue(),
                content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
            filename = f"отчет_кафедра_{department.short_name}_{current_year.start_year}.xlsx"
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            return response
        
        elif format_type == 'pdf':
            buffer = PDFExporter.export_department_report(department, workloads, current_year)
            response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
            filename = f"отчет_кафедра_{department.short_name}_{current_year.start_year}.pdf"
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            return response
    elif report_type == 'teacher':
        teacher_id = request.GET.get('teacher')
        if not teacher_id:
            return HttpResponse('Не указан преподаватель', status=400)
        teacher = get_object_or_404(Teacher, id=teacher_id)
        workloads = TeacherWorkload.objects.filter(
            teacher=teacher,
            academic_year=current_year,
            status__in=['approved', 'completed']
        ).select_related(
            'curriculum_subject_group__curriculum_subject__subject',
            'curriculum_subject_group__curriculum_subject__course',
        )
        if format_type == 'excel':
            buffer = ExcelExporter.export_teacher_report(teacher, workloads, current_year)
            response = HttpResponse(
                buffer.getvalue(),
                content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
            filename = f"отчет_преподаватель_{teacher.last_name}_{current_year.start_year}.xlsx"
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            return response
        elif format_type == 'pdf':
            buffer = PDFExporter.export_teacher_report(teacher, workloads, current_year)
            response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
            filename = f"отчет_преподаватель_{teacher.last_name}_{current_year.start_year}.pdf"
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            return response
    elif report_type == 'departments_summary':
        # Получаем данные аналогично view
        departments = filter_departments_by_role(request, Department.objects.all())
        
        workloads = TeacherWorkload.objects.filter(
            academic_year=current_year,
            status__in=['approved', 'completed'],
            teacher__department__in=departments
        ).select_related('teacher__department__faculty')
        
        # Статистика по преподавателям и кафедрам
        teacher_stats_dict = {}
        department_stats_dict = {}

        for wl in workloads:
            teacher = wl.teacher
            department = teacher.department
            department_id = department.id
            teacher_id = teacher.id

            # Инициализируем статистику преподавателя
            if teacher_id not in teacher_stats_dict:
                teacher_stats_dict[teacher_id] = {
                    'teacher': teacher,
                    'department_id': department_id,
                    'total_hours': 0,
                    'lecture_hours': 0,
                    'practice_hours': 0,
                    'lab_hours': 0
                }

            # Обновляем статистику преподавателя
            teacher_stats = teacher_stats_dict[teacher_id]
            teacher_stats['total_hours'] += wl.total_hours()
            teacher_stats['lecture_hours'] += wl.hours_lecture
            teacher_stats['practice_hours'] += wl.hours_practice
            teacher_stats['lab_hours'] += wl.hours_lab

            # Инициализируем статистику кафедры
            if department_id not in department_stats_dict:
                department_stats_dict[department_id] = {
                    'department': department,
                    'teachers': set(),
                    'total_hours': 0,
                    'lecture_hours': 0,
                    'practice_hours': 0,
                    'lab_hours': 0
                }

            # Обновляем статистику кафедры
            stats = department_stats_dict[department_id]
            stats['teachers'].add(teacher_id)
            stats['total_hours'] += wl.total_hours()
            stats['lecture_hours'] += wl.hours_lecture
            stats['practice_hours'] += wl.hours_practice
            stats['lab_hours'] += wl.hours_lab
        
        # Собираем всех активных преподавателей по кафедрам, как в report
        all_active_teachers = Teacher.objects.filter(
            is_active=True,
            department__in=departments
        ).values('id', 'department_id')

        # кешируем объекты преподавателей чтобы не дергать бд при инициализации
        teacher_objects = Teacher.objects.filter(
            is_active=True,
            department__in=departments
        ).in_bulk()

        teachers_by_department = {}
        for teacher_info in all_active_teachers:
            department_id = teacher_info['department_id']
            if department_id not in teachers_by_department:
                teachers_by_department[department_id] = set()
            teachers_by_department[department_id].add(teacher_info['id'])

            tid = teacher_info['id']
            if tid not in teacher_stats_dict:
                teacher = teacher_objects.get(tid)
                teacher_stats_dict[tid] = {
                    'teacher': teacher,
                    'department_id': department_id,
                    'total_hours': 0,
                    'lecture_hours': 0,
                    'practice_hours': 0,
                    'lab_hours': 0
                }
        
        department_stats = []
        for department_id, stats in department_stats_dict.items():
            teachers_count = len(teachers_by_department.get(department_id, set()))
            
            # Получаем преподавателей этой кафедры
            department_teachers = [
                teacher_stats_dict[t_id] 
                for t_id in teachers_by_department.get(department_id, set())
            ]
            # Сортируем по фамилии
            department_teachers.sort(key=lambda x: x['teacher'].last_name)
            
            department_stats.append({
                'department': stats['department'],
                'faculty': stats['department'].faculty,
                'teachers_count': teachers_count,
                'total_hours': stats['total_hours'],
                'lecture_hours': stats['lecture_hours'],
                'practice_hours': stats['practice_hours'],
                'lab_hours': stats['lab_hours'],
                'avg_hours_per_teacher': stats['total_hours'] / teachers_count if teachers_count > 0 else 0,
                'teachers': department_teachers
            })
        
        total_stats = {
            'departments_count': len(department_stats),
            'teachers_count': sum(item['teachers_count'] for item in department_stats),
            'total_hours': sum(item['total_hours'] for item in department_stats),
            'lecture_hours': sum(item['lecture_hours'] for item in department_stats),
            'practice_hours': sum(item['practice_hours'] for item in department_stats),
            'lab_hours': sum(item['lab_hours'] for item in department_stats)
        }
        
        if format_type == 'excel':
            buffer = ExcelExporter.export_departments_summary_report(department_stats, total_stats, current_year)
            response = HttpResponse(
                buffer.getvalue(),
                content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
            filename = f"итоговый_отчет_по_кафедрам_{current_year.start_year}.xlsx"
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            return response
        
        elif format_type == 'pdf':
            buffer = PDFExporter.export_departments_summary_report(department_stats, total_stats, current_year)
            response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
            filename = f"итоговый_отчет_по_кафедрам_{current_year.start_year}.pdf"
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            return response
    return HttpResponse('Неверный формат запроса', status=400)

@login_required
def student_groups_list(request):
    """Список групп студентов"""
    groups = StudentGroup.objects.select_related(
        'course',
        'bachelor_program',
        'bachelor_program__faculty'
    )

    # Фильтрация
    course_id = request.GET.get('course')
    faculty_id = request.GET.get('faculty')
    group_type = request.GET.get('type')
    year = request.GET.get('year')

    if course_id:
        groups = groups.filter(course_id=course_id)
    if faculty_id:
        groups = groups.filter(bachelor_program__faculty_id=faculty_id)
    if group_type:
        groups = groups.filter(group_type=group_type)
    if year:
        groups = groups.filter(year_of_admission=year)

    # Сортировка (важно для пагинации)
    groups = groups.order_by(
        'bachelor_program__faculty__name',
        'course__number',
        'name'
    )

    # Агрегация
    total_groups = groups.count()
    total_students = groups.aggregate(
        total=Sum('students_count')
    )['total'] or 0

    # Пагинация
    paginator = Paginator(groups, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Фильтры
    courses = Course.objects.all()
    faculties = Faculty.objects.all()
    programs = BachelorProgram.objects.all()
    years = (
        StudentGroup.objects
        .values_list('year_of_admission', flat=True)
        .distinct()
        .order_by('-year_of_admission')
    )

    context = {
        'page_obj': page_obj,
        'groups': page_obj.object_list,
        'courses': courses,
        'faculties': faculties,
        'programs': programs,
        'years': years,
        'group_types': StudentGroup.TYPE_CHOICES,
        'total_groups': total_groups,
        'total_students': total_students,
    }

    return render(
        request,
        'hours_distribution/groups/student_groups_list.html',
        context
    )

@login_required
def student_group_detail(request, group_id):
    """Детальная информация о группе"""
    group = get_object_or_404(StudentGroup, id=group_id)
    
    # Нагрузки для группы
    workloads = TeacherWorkload.objects.filter(
        curriculum_subject_group__student_group=group,
        academic_year__is_current=True
    ).select_related(
        'teacher',
        'curriculum_subject_group__curriculum_subject__subject'
    )
    
    # Статистика по дисциплинам (один проход)
    subject_stats = {}
    for wl in workloads:
        subject_name = wl.curriculum_subject_group.curriculum_subject.subject.name
        if subject_name not in subject_stats:
            subject_stats[subject_name] = {
                'total_hours': 0,
                'lecture': 0,
                'practice': 0,
                'lab': 0,
                'teachers': []
            }
        
        stats = subject_stats[subject_name]
        stats['total_hours'] += wl.total_hours()
        stats['lecture'] += wl.hours_lecture
        stats['practice'] += wl.hours_practice
        stats['lab'] += wl.hours_lab
        teacher_info = str(wl.teacher)
        if teacher_info not in stats['teachers']:
            stats['teachers'].append(teacher_info)
    
    # Потоковые группы, в которые входит эта группа
    stream_groups = StreamGroup.objects.filter(student_groups=group)
    
    context = {
        'group': group,
        'workloads': workloads,
        'subject_stats': subject_stats,
        'stream_groups': stream_groups,
        'total_hours': sum(wl.total_hours() for wl in workloads),
        'modal_form': StudentGroupModalForm(instance=group)
    }
    
    return render(request, 'hours_distribution/groups/student_group_detail.html', context)

@login_required
def stream_groups_list(request):
    """Список поточных групп"""
    streams = StreamGroup.objects.all().select_related('bachelor_program', 'course', 'semester', 'academic_year')
    
    # Фильтрация
    course_id = request.GET.get('course')
    bachelor_program_id = request.GET.get('bachelor_program')
    year_id = request.GET.get('year')
    
    if course_id:
        streams = streams.filter(course_id=course_id)
    if bachelor_program_id:
        streams = streams.filter(bachelor_program_id=bachelor_program_id)
    if year_id:
        streams = streams.filter(academic_year_id=year_id)
    
    # Статистика
    total_streams = streams.count()
    total_students = sum(s.total_students for s in streams)
    avg_groups_per_stream = streams.aggregate(avg=Avg('student_groups'))['avg'] or 0
    
    context = {
        'streams': streams,
        'total_streams': total_streams,
        'total_students': total_students,
        'avg_groups_per_stream': round(avg_groups_per_stream, 1),
        'courses': Course.objects.all(),
        'bachelor_programs': BachelorProgram.objects.all(),
        'years': AcademicYear.objects.all(),
    }
    
    return render(request, 'hours_distribution/groups/stream_groups_list.html', context)

@login_required
def stream_group_detail(request, stream_id):
    """Детальная информация о потоковой группе"""
    stream = get_object_or_404(StreamGroup, id=stream_id)
    
    # Группы в потоке
    groups = stream.student_groups.all().select_related('course', 'bachelor_program')
    
    # Нагрузки для потока
    workloads = TeacherWorkload.objects.filter(
        curriculum_subject_group__stream_group=stream,
        academic_year=stream.academic_year
    ).select_related('teacher', 'curriculum_subject_group__curriculum_subject__subject')
    
    # Распределение нагрузки по преподавателям (один проход)
    teacher_stats = {}
    for wl in workloads:
        teacher_id = wl.teacher_id
        if teacher_id not in teacher_stats:
            teacher_stats[teacher_id] = {
                'teacher': wl.teacher,
                'total_hours': 0,
                'lecture': 0,
                'practice': 0,
                'lab': 0
            }
        
        stats = teacher_stats[teacher_id]
        stats['total_hours'] += wl.total_hours()
        stats['lecture'] += wl.hours_lecture
        stats['practice'] += wl.hours_practice
        stats['lab'] += wl.hours_lab
    
    context = {
        'stream': stream,
        'groups': groups,
        'workloads': workloads,
        'teacher_stats': teacher_stats.values(),
        'total_students': stream.total_students,
        'groups_count': groups.count(),
    }
    
    return render(request, 'hours_distribution/groups/stream_group_detail.html', context)

@login_required
def create_stream_group(request):
    """Создание поточной группы"""
    if request.method == 'POST':
        form = StreamGroupForm(request.POST)
        if form.is_valid():
            stream = form.save(commit=False)
            stream.created_by = request.user
            stream.save()
            form.save_m2m()  # Сохраняем ManyToMany связи
            
            # Пересчитываем количество студентов
            stream.total_students = sum(group.students_count for group in stream.student_groups.all())
            stream.save()
            
            messages.success(request, f'Поточная группа "{stream.name}" создана')
            return redirect('hours_distribution:stream_group_detail', stream_id=stream.id)
    else:
        form = StreamGroupForm()
    
    context = {
        'form': form,
        'title': 'Создание поточной группы'
    }
    
    return render(request, 'hours_distribution/groups/stream_group_form.html', context)

@login_required
def distribute_workload(request):
    """Распределение нагрузки по группам"""
    if request.method == 'POST':
        form = WorkloadDistributionForm(request.POST)
        if form.is_valid():
            cd = form.cleaned_data
            
            # Создаем CurriculumSubjectGroup
            curriculum_subject = cd['curriculum_subject']
            
            # Проверяем, существует ли уже такая связь с явным указанием обоих полей
            if cd['group_type'] == 'single':
                csg, created = CurriculumSubjectGroup.objects.get_or_create(
                    curriculum_subject=curriculum_subject,
                    student_group=cd['student_group'],
                    stream_group=None,
                    defaults={
                        'hours_lecture': cd['hours_lecture'],
                        'hours_practice': cd['hours_practice'],
                        'hours_lab': cd['hours_lab']
                    }
                )
                group_info = cd['student_group'].get_full_name()
            else:
                csg, created = CurriculumSubjectGroup.objects.get_or_create(
                    curriculum_subject=curriculum_subject,
                    student_group=None,
                    stream_group=cd['stream_group'],
                    defaults={
                        'hours_lecture': cd['hours_lecture'],
                        'hours_practice': cd['hours_practice'],
                        'hours_lab': cd['hours_lab']
                    }
                )
                group_info = f"Поток: {cd['stream_group'].name}"
            
            if not created:
                csg.hours_lecture = cd['hours_lecture']
                csg.hours_practice = cd['hours_practice']
                csg.hours_lab = cd['hours_lab']
                csg.save()
            
            # Создаем или обновляем нагрузку преподавателя
            current_year = AcademicYear.objects.filter(is_current=True).first()
            workload, w_created = TeacherWorkload.objects.get_or_create(
                teacher=cd['teacher'],
                curriculum_subject_group=csg,
                academic_year=current_year,
                defaults={
                    'hours_lecture': cd['hours_lecture'],
                    'hours_practice': cd['hours_practice'],
                    'hours_lab': cd['hours_lab'],
                    'status': 'planned'
                }
            )
            
            if not w_created:
                workload.hours_lecture = cd['hours_lecture']
                workload.hours_practice = cd['hours_practice']
                workload.hours_lab = cd['hours_lab']
                workload.save()
            
            messages.success(request, f'Нагрузка распределена для {group_info}')
            return redirect('hours_distribution:workload_distribution_list')
    
    else:
        form = WorkloadDistributionForm()
    
    context = {
        'form': form,
        'title': 'Распределение нагрузки'
    }
    
    return render(request, 'hours_distribution/groups/distribute_workload.html', context)

@login_required
def workload_distribution_list(request):
    """Список распределенных нагрузок"""
    distributions = CurriculumSubjectGroup.objects.all().select_related(
        'curriculum_subject__subject',
        'curriculum_subject__curriculum',
        'student_group',
        'stream_group'
    )
    
    # Фильтрация
    subject_id = request.GET.get('subject')
    group_type = request.GET.get('group_type')
    curriculum_id = request.GET.get('curriculum')
    
    if subject_id:
        distributions = distributions.filter(curriculum_subject__subject_id=subject_id)
    if group_type:
        if group_type == 'single':
            distributions = distributions.filter(student_group__isnull=False)
        else:
            distributions = distributions.filter(stream_group__isnull=False)
    if curriculum_id:
        distributions = distributions.filter(curriculum_subject__curriculum_id=curriculum_id)
    
    # Статистика (конвертируем в список один раз для эффективности)
    distributions_list = list(distributions)
    total_hours = sum(d.total_hours() for d in distributions_list)
    
    # Подсчет групп (один проход)
    single_groups = 0
    stream_groups = 0
    for d in distributions_list:
        if d.student_group:
            single_groups += 1
        else:
            stream_groups += 1
    
    context = {
        'distributions': distributions_list,
        'total_hours': total_hours,
        'single_groups': single_groups,
        'stream_groups': stream_groups,
        'subjects': Subject.objects.all(),
        'curricula': Curriculum.objects.all(),
    }
    
    return render(request, 'hours_distribution/groups/workload_distribution_list.html', context)

@role_required('admin', 'dean', 'head', 'planner')
def group_workload_report(request):
    """Отчет по нагрузке с учетом групп"""
    department_id = request.GET.get('department')
    course_id = request.GET.get('course')
    group_type = request.GET.get('group_type')
    
    # Преобразуем course_id в integer один раз
    course_id_int = int(course_id) if course_id else None
    
    current_year = AcademicYear.objects.filter(is_current=True).first()
    
    # Получаем нагрузки с оптимизацией запроса
    workloads_filter = {'academic_year': current_year, 'status__in': ['approved', 'completed']}
    if department_id:
        workloads_filter['teacher__department_id'] = department_id
    
    workloads = TeacherWorkload.objects.filter(**workloads_filter).select_related(
        'teacher',
        'curriculum_subject_group__curriculum_subject__subject',
        'curriculum_subject_group__student_group__course',
        'curriculum_subject_group__stream_group',
        'teacher__department',
    )
    
    # Группируем данные в один проход
    report_data = {}
    
    def get_group_info(csg):
        """Извлекает информацию о группе"""
        is_student = csg.student_group is not None
        group = csg.student_group if is_student else csg.stream_group
        return {
            'is_student': is_student,
            'group': group,
            'key': f"{'group' if is_student else 'stream'}_{group.id}",
            'name': group.get_full_name() if is_student else f"Поток: {group.name}",
            'type': 'group' if is_student else 'stream',
            'students_count': group.students_count if is_student else group.total_students,
            'course': group.course.id if is_student else None,
        }
    
    for wl in workloads:
        info = get_group_info(wl.curriculum_subject_group)
        key = info['key']
        
        if key not in report_data:
            report_data[key] = {
                **{k: v for k, v in info.items() if k != 'is_student'},
                'total_hours': 0,
                'lecture': 0,
                'practice': 0,
                'lab': 0,
                'teachers': [],
                'subjects': []
            }
        
        data = report_data[key]
        total = wl.total_hours()
        data['total_hours'] += total
        data['lecture'] += wl.hours_lecture
        data['practice'] += wl.hours_practice
        data['lab'] += wl.hours_lab
        teacher_info = f"{wl.teacher} ({wl.teacher.position})"
        if teacher_info not in data['teachers']:
            data['teachers'].append(teacher_info)
        subject_name = wl.curriculum_subject_group.curriculum_subject.subject.name
        if subject_name not in data['subjects']:
            data['subjects'].append(subject_name)
    
    # Фильтруем и сортируем в одном проходе
    def should_include(data):
        """Проверяет, должны ли мы включить группу в отчет"""
        group_type_match = not group_type or (group_type == 'single') == (data['type'] == 'group')
        course_match = not course_id_int or data['type'] != 'group' or data['course'] == course_id_int
        return group_type_match and course_match
    
    report_data_values = report_data.values()
    sorted_data = sorted(
        (
            data
            for data in report_data_values
            if should_include(data)
        ),
        key=lambda x: x['total_hours'],
        reverse=True
    )
    
    context = {
        'report_data': sorted_data,
        'total_groups': len(sorted_data),
        'total_hours': sum(d['total_hours'] for d in sorted_data),
        'total_students': sum(d['students_count'] for d in sorted_data),
        'departments': Department.objects.all(),
        'courses': Course.objects.all(),
        'current_year': current_year,
    }
    
    return render(request, 'hours_distribution/reports/group_workload_report.html', context)

@role_required('admin', 'dean', 'head', 'planner')
def export_group_report(request):

    """Экспорт отчета по группам"""
    format_type = request.GET.get('format', 'excel')
    report_type = request.GET.get('type', 'detailed')
    
    # Получаем параметры фильтрации из запроса     
    department_id = request.GET.get('department') or None
    course_id = request.GET.get('course') or None
    group_type = request.GET.get('group_type') or None  # 'single' или 'stream'
    
    current_year = AcademicYear.objects.filter(is_current=True).first()
    
    if not current_year:
        return HttpResponse('Не установлен текущий учебный год', status=400)
    
    if report_type == 'summary':
        # Сводный отчет по группам
        groups = StudentGroup.objects.filter(is_active=True).select_related(
            'course', 'bachelor_program', 'bachelor_program__faculty'
        )
        
        # Применяем фильтрацию
        if course_id:
            groups = groups.filter(course_id=course_id)
        
        data = []
        for group in groups:
            # Получаем нагрузку для группы
            workloads = TeacherWorkload.objects.filter(
                curriculum_subject_group__student_group=group,
                academic_year=current_year
            )
            
            total_hours = sum(wl.total_hours() for wl in workloads)
            
            # Исправляем вызов метода get_group_type_display
            # Стандартный Django метод для полей с choices
            group_type_display = group.get_group_type_display()
            
            data.append({
                'Код группы': group.code,
                'Название': group.name,
                'Тип': group_type_display,
                'Курс': group.course.number,
                'Направление': group.bachelor_program.code,
                'Факультет': group.bachelor_program.faculty.short_name,
                'Год набора': group.year_of_admission,
                'Кол-во студентов': group.students_count,
                'Всего часов': total_hours,
                'Часов на студента': round(total_hours / group.students_count, 1) if group.students_count > 0 else 0
            })
        
        buffer = ExcelExporter.export_group_summary(data, current_year)
        filename = f"отчет_группы_сводный_{current_year.start_year}.xlsx"
    
    else:
        # Детальный отчет
        workloads = TeacherWorkload.objects.filter(
            academic_year=current_year,
            status__in=['approved', 'completed']
        ).select_related(
            'teacher',
            'curriculum_subject_group__curriculum_subject__subject',
            'curriculum_subject_group__student_group',
            'curriculum_subject_group__stream_group',
            'teacher__department'
        )
        
        # Применяем фильтрацию по кафедре
        if department_id:
            workloads = workloads.filter(teacher__department_id=department_id)
        
        # Фильтрация по типу группы
        if group_type == 'single':
            workloads = workloads.filter(curriculum_subject_group__student_group__isnull=False)
        elif group_type == 'stream':
            workloads = workloads.filter(curriculum_subject_group__stream_group__isnull=False)
        
        # Фильтрация по курсу через CurriculumSubjectGroup
        if course_id:
            workloads = workloads.filter(
                curriculum_subject_group__curriculum_subject__course_id=course_id
            )
        
        buffer = ExcelExporter.export_group_detailed(workloads, current_year)
        filename = f"отчет_группы_детальный_{current_year.start_year}.xlsx"
    
    if format_type == 'excel':
        response = HttpResponse(
            buffer.getvalue(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response
    
    return HttpResponse('Неверный формат', status=400)


@login_required
def api_curriculum_subject_groups(request):
    """API endpoint для получения групп по дисциплине"""
    curriculum_subject_id = request.GET.get('curriculum_subject')
    
    if not curriculum_subject_id:
        return JsonResponse({'error': 'curriculum_subject parameter is required'}, status=400)
    
    try:
        curriculum_subject = CurriculumSubject.objects.get(id=curriculum_subject_id)
    except CurriculumSubject.DoesNotExist:
        return JsonResponse({'error': 'Curriculum subject not found'}, status=404)
    
    # Получаем все студенческие группы (кроме неактивных)
    student_groups = StudentGroup.objects.filter(is_active=True).values('id', 'code', 'name')
    
    # Получаем все потоковые группы
    stream_groups = StreamGroup.objects.all().values('id', 'code', 'name')
    
    # Форматируем данные для JSON ответа
    groups_list = [
        {
            'id': group['id'],
            'code': group['code'],
            'name': group['name']
        }
        for group in student_groups
    ]
    
    streams_list = [
        {
            'id': stream['id'],
            'code': stream['code'],
            'name': stream['name']
        }
        for stream in stream_groups
    ]
    
    return JsonResponse({
        'groups': groups_list,
        'streams': streams_list
    })


@login_required
@require_http_methods(["GET"])
def student_group_modal(request, group_id):
    """Получить форму для модального редактирования группы"""
    group = get_object_or_404(StudentGroup, id=group_id)
    form = StudentGroupModalForm(instance=group)
    
    context = {
        'form': form,
        'group': group,
        'csrf_token': get_token(request)
    }
    
    # Возвращаем HTML формы для вставки в модальное окно
    from django.template.loader import render_to_string
    html = render_to_string('hours_distribution/modals/student_group_modal.html', context, request=request)
    
    return JsonResponse({'html': html, 'success': True})


@login_required
@require_http_methods(["POST"])
def student_group_update_modal(request, group_id):
    """Сохранить изменения группы из модального окна"""
    group = get_object_or_404(StudentGroup, id=group_id)
    form = StudentGroupModalForm(request.POST, instance=group)
    
    if form.is_valid():
        form.save()
        return JsonResponse({
            'success': True,
            'message': f'Группа {group.code} успешно обновлена',
            'group': {
                'id': group.id,
                'code': group.code,
                'name': group.name,
                'students_count': group.students_count,
                'max_students': group.max_students,
                'is_active': group.is_active,
                'group_type': group.group_type,
            }
        })
    else:
        # Возвращаем ошибки формы
        errors = {field: error[0] for field, error in form.errors.items()}
        return JsonResponse({
            'success': False,
            'errors': errors,
            'message': 'Ошибка при сохранении данных'
        }, status=400)


@login_required
@require_http_methods(["GET"])
def student_group_create_modal(request):
    """Получить форму для модального создания новой группы"""
    form = StudentGroupCreateForm()
    
    context = {
        'form': form,
        'is_create': True,
        'csrf_token': get_token(request)
    }
    
    # Возвращаем HTML формы для вставки в модальное окно
    from django.template.loader import render_to_string
    html = render_to_string('hours_distribution/modals/student_group_create_modal.html', context, request=request)
    
    return JsonResponse({'html': html, 'success': True})


@login_required
@require_http_methods(["POST"])
def student_group_store_modal(request):
    """Сохранить новую группу из модального окна"""
    form = StudentGroupCreateForm(request.POST)
    
    if form.is_valid():
        group = form.save()
        return JsonResponse({
            'success': True,
            'message': f'Группа {group.code} успешно создана',
            'group': {
                'id': group.id,
                'code': group.code,
                'name': group.name,
                'students_count': group.students_count,
                'max_students': group.max_students,
                'is_active': group.is_active,
                'group_type': group.group_type,
            }
        })
    else:
        # Возвращаем ошибки формы
        errors = {field: error[0] for field, error in form.errors.items()}
        return JsonResponse({
            'success': False,
            'errors': errors,
            'message': 'Ошибка при создании группы'
        }, status=400)

# ---------- CRUD для пользователей и преподавателей ----------
from django.contrib.auth.models import User
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy
from django.contrib.auth.mixins import LoginRequiredMixin
from .forms import CustomUserCreationForm, CustomUserChangeForm, TeacherForm


class UserListView(RoleRequiredMixin, LoginRequiredMixin, ListView):
    model = User
    template_name = 'hours_distribution/users/user_list.html'
    context_object_name = 'users'
    paginate_by = 20
    ordering = ['username']
    required_roles = ('admin', 'dean')


class UserCreateView(RoleRequiredMixin, LoginRequiredMixin, CreateView):
    model = User
    form_class = CustomUserCreationForm
    template_name = 'hours_distribution/users/user_form.html'
    success_url = reverse_lazy('hours_distribution:user_list')
    required_roles = ('admin', 'dean')


class UserUpdateView(RoleRequiredMixin, LoginRequiredMixin, UpdateView):
    model = User
    form_class = CustomUserChangeForm
    template_name = 'hours_distribution/users/user_form.html'
    success_url = reverse_lazy('hours_distribution:user_list')
    required_roles = ('admin', 'dean')


class UserDeleteView(RoleRequiredMixin, LoginRequiredMixin, DeleteView):
    model = User
    template_name = 'hours_distribution/users/user_confirm_delete.html'
    success_url = reverse_lazy('hours_distribution:user_list')
    required_roles = ('admin', 'dean')


class TeacherListView(RoleRequiredMixin, LoginRequiredMixin, ListView):
    model = Teacher
    template_name = 'hours_distribution/teachers/teacher_list.html'
    context_object_name = 'teachers'
    paginate_by = 20
    ordering = ['last_name', 'first_name']
    required_roles = ('admin', 'dean', 'head')

    def get_queryset(self):
        qs = super().get_queryset()
        last = self.request.GET.get('last_name', '').strip()
        dept = self.request.GET.get('department')
        if last:
            qs = qs.filter(last_name__icontains=last)
        if dept:
            qs = qs.filter(department_id=dept)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['departments'] = Department.objects.all()
        ctx['filter_last_name'] = self.request.GET.get('last_name', '')
        ctx['filter_department'] = self.request.GET.get('department', '')
        return ctx


class TeacherCreateView(RoleRequiredMixin, LoginRequiredMixin, CreateView):
    model = Teacher
    form_class = TeacherForm
    template_name = 'hours_distribution/teachers/teacher_form.html'
    success_url = reverse_lazy('hours_distribution:teacher_list')
    required_roles = ('admin', 'dean', 'head')


class TeacherUpdateView(RoleRequiredMixin, LoginRequiredMixin, UpdateView):
    model = Teacher
    form_class = TeacherForm
    template_name = 'hours_distribution/teachers/teacher_form.html'
    success_url = reverse_lazy('hours_distribution:teacher_list')
    required_roles = ('admin', 'dean', 'head')


class TeacherDeleteView(RoleRequiredMixin, LoginRequiredMixin, DeleteView):
    model = Teacher
    template_name = 'hours_distribution/teachers/teacher_confirm_delete.html'
    success_url = reverse_lazy('hours_distribution:teacher_list')
    required_roles = ('admin', 'dean', 'head')