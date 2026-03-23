from django.utils import timezone
from datetime import timedelta
from django.db.models import Q, Sum, Avg
import numpy as np
from ..models import *

class PlanningAssistant:
    """Помощник планирования нагрузки на следующий год"""
    
    @staticmethod
    def generate_next_year_plan(current_year, next_year, department):
        """Сгенерировать план на следующий год на основе текущих данных"""
        
        # Получаем текущие нагрузки кафедры
        current_workloads = TeacherWorkload.objects.filter(
            teacher__department=department,
            academic_year=current_year,
            status__in=['approved', 'completed']
        ).select_related('teacher', 'curriculum_subject__subject')
        
        # Создаем план
        plan, created = NextYearPlan.objects.get_or_create(
            department=department,
            academic_year=next_year,
            defaults={
                'status': 'draft',
                'created_by': department.head if department.head else None
            }
        )
        
        # Группируем нагрузки по преподавателям
        teacher_workloads = {}
        for workload in current_workloads:
            teacher_id = workload.teacher_id
            if teacher_id not in teacher_workloads:
                teacher_workloads[teacher_id] = []
            teacher_workloads[teacher_id].append(workload)
        
        # Создаем запланированные нагрузки
        planned_workloads = []
        
        for teacher_id, workloads in teacher_workloads.items():
            teacher = Teacher.objects.get(id=teacher_id)
            
            # Анализируем текущую нагрузку преподавателя
            total_current_hours = sum(w.total_hours() for w in workloads)
            
            # Определяем целевую нагрузку на следующий год
            target_hours = PlanningAssistant._calculate_target_hours(
                teacher, total_current_hours
            )
            
            # Распределяем часы между дисциплинами
            planned_subjects = PlanningAssistant._distribute_hours(
                workloads, target_hours
            )
            
            # Создаем запланированные нагрузки
            for subject_data in planned_subjects:
                # Получаем или создаем семестр для следующего года
                semester = PlanningAssistant._get_next_semester(
                    subject_data['semester'], next_year
                )
                
                planned_workload = PlannedWorkload(
                    plan=plan,
                    teacher=teacher,
                    subject=subject_data['subject'],
                    hours_lecture=subject_data['hours_lecture'],
                    hours_practice=subject_data['hours_practice'],
                    hours_lab=subject_data['hours_lab'],
                    course=subject_data['course'],
                    semester=semester,
                    notes=subject_data.get('notes', '')
                )
                planned_workloads.append(planned_workload)
        
        # Сохраняем все запланированные нагрузки
        PlannedWorkload.objects.bulk_create(planned_workloads)
        
        return plan
    
    @staticmethod
    def _calculate_target_hours(teacher, current_hours):
        """Рассчитать целевую нагрузку на следующий год"""
        base_target = teacher.workload_hours * 36  # 36 недель в учебном году
        
        # Учитываем опыт и должность
        position_factor = {
            'профессор': 0.9,
            'доцент': 1.0,
            'старший преподаватель': 1.1,
            'преподаватель': 1.2,
            'ассистент': 1.3,
        }.get(teacher.position.lower(), 1.0)
        
        # Корректируем на основе текущей нагрузки
        if current_hours > 0:
            trend_factor = current_hours / (teacher.workload_hours * 36)
            # Сглаживаем изменения
            target_hours = base_target * position_factor * (0.7 + 0.3 * trend_factor)
        else:
            target_hours = base_target * position_factor
        
        return round(target_hours / 10) * 10  # Округляем до десятков
    
    @staticmethod
    def _distribute_hours(workloads, target_hours):
        """Распределить часы между дисциплинами"""
        # Группируем по дисциплинам
        subject_data = {}
        
        for workload in workloads:
            subject_id = workload.curriculum_subject.subject_id
            if subject_id not in subject_data:
                subject_data[subject_id] = {
                    'subject': workload.curriculum_subject.subject,
                    'course': workload.curriculum_subject.course,
                    'semester': workload.curriculum_subject.semester,
                    'total_hours': 0,
                    'hours_lecture': 0,
                    'hours_practice': 0,
                    'hours_lab': 0,
                    'count': 0
                }
            
            data = subject_data[subject_id]
            data['total_hours'] += workload.total_hours()
            data['hours_lecture'] += workload.hours_lecture
            data['hours_practice'] += workload.hours_practice
            data['hours_lab'] += workload.hours_lab
            data['count'] += 1
        
        # Нормализуем и распределяем целевую нагрузку
        total_current_hours = sum(data['total_hours'] for data in subject_data.values())
        
        planned_subjects = []
        
        for data in subject_data.values():
            proportion = data['total_hours'] / total_current_hours
            planned_hours = target_hours * proportion
            
            # Сохраняем пропорции типов часов
            if data['total_hours'] > 0:
                lecture_ratio = data['hours_lecture'] / data['total_hours']
                practice_ratio = data['hours_practice'] / data['total_hours']
                lab_ratio = data['hours_lab'] / data['total_hours']
            else:
                lecture_ratio = practice_ratio = lab_ratio = 0.33
            
            planned_subjects.append({
                'subject': data['subject'],
                'course': data['course'],
                'semester': data['semester'],
                'hours_lecture': round(planned_hours * lecture_ratio),
                'hours_practice': round(planned_hours * practice_ratio),
                'hours_lab': round(planned_hours * lab_ratio),
                'notes': f"На основе {data['count']} записей текущего года"
            })
        
        return planned_subjects
    
    @staticmethod
    def _get_next_semester(current_semester, next_year):
        """Получить соответствующий семестр следующего года"""
        try:
            return Semester.objects.get(
                academic_year=next_year,
                number=current_semester.number
            )
        except Semester.DoesNotExist:
            # Создаем семестр, если его нет
            return Semester.objects.create(
                academic_year=next_year,
                number=current_semester.number,
                start_date=current_semester.start_date.replace(year=next_year.start_year),
                end_date=current_semester.end_date.replace(year=next_year.start_year)
            )
    
    @staticmethod
    def optimize_workload_distribution(plan):
        """Оптимизировать распределение нагрузки в плане"""
        planned_workloads = plan.planned_workloads.select_related('teacher', 'subject')
        
        # Собираем статистику по преподавателям
        teacher_stats = {}
        for pw in planned_workloads:
            teacher_id = pw.teacher_id
            if teacher_id not in teacher_stats:
                teacher_stats[teacher_id] = {
                    'teacher': pw.teacher,
                    'total_hours': 0,
                    'workloads': []
                }
            stats = teacher_stats[teacher_id]
            stats['total_hours'] += pw.total_hours()
            stats['workloads'].append(pw)
        
        # Оптимизируем для каждого преподавателя
        optimizations = []
        
        for stats in teacher_stats.values():
            teacher = stats['teacher']
            current_total = stats['total_hours']
            target_total = teacher.workload_hours * 36
            
            if abs(current_total - target_total) > 50:  # Значительное отклонение
                # Находим дисциплины для корректировки
                for pw in stats['workloads']:
                    adjustment = (target_total - current_total) / len(stats['workloads'])
                    
                    # Сохраняем пропорции
                    if pw.total_hours() > 0:
                        ratio = pw.total_hours() / current_total
                        new_hours = pw.total_hours() + adjustment * ratio
                        
                        # Пересчитываем по типам
                        if pw.total_hours() > 0:
                            lecture_ratio = pw.hours_lecture / pw.total_hours()
                            practice_ratio = pw.hours_practice / pw.total_hours()
                            lab_ratio = pw.hours_lab / pw.total_hours()
                        else:
                            lecture_ratio = practice_ratio = lab_ratio = 0.33
                        
                        optimizations.append({
                            'workload': pw,
                            'new_hours_lecture': max(0, round(new_hours * lecture_ratio)),
                            'new_hours_practice': max(0, round(new_hours * practice_ratio)),
                            'new_hours_lab': max(0, round(new_hours * lab_ratio))
                        })
        
        return optimizations

class WorkloadValidator:
    """Валидатор учебной нагрузки"""
    
    @staticmethod
    def validate_teacher_workload(teacher, planned_hours):
        """Проверить нагрузку преподавателя на соответствие нормам"""
        max_hours = teacher.workload_hours * 36  # Максимум на год
        min_hours = teacher.workload_hours * 30  # Минимум на год
        
        validation_result = {
            'is_valid': min_hours <= planned_hours <= max_hours,
            'planned_hours': planned_hours,
            'min_hours': min_hours,
            'max_hours': max_hours,
            'deviation': planned_hours - (teacher.workload_hours * 33),  # От среднего
            'recommendations': []
        }
        
        if planned_hours < min_hours:
            validation_result['recommendations'].append(
                f"Нагрузка ниже минимальной. Рекомендуется добавить {min_hours - planned_hours} часов."
            )
        elif planned_hours > max_hours:
            validation_result['recommendations'].append(
                f"Нагрузка превышает максимальную. Рекомендуется уменьшить на {planned_hours - max_hours} часов."
            )
        
        return validation_result
    
    @staticmethod
    def validate_department_plan(plan):
        """Проверить план кафедры"""
        planned_workloads = plan.planned_workloads.select_related('teacher')
        
        validation_results = {
            'total_hours': 0,
            'teachers_valid': 0,
            'teachers_total': 0,
            'issues': [],
            'warnings': []
        }
        
        # Проверяем каждого преподавателя
        teacher_hours = {}
        for pw in planned_workloads:
            teacher_id = pw.teacher_id
            if teacher_id not in teacher_hours:
                teacher_hours[teacher_id] = {
                    'teacher': pw.teacher,
                    'hours': 0,
                    'workloads': []
                }
            teacher_hours[teacher_id]['hours'] += pw.total_hours()
            teacher_hours[teacher_id]['workloads'].append(pw)
            validation_results['total_hours'] += pw.total_hours()
        
        validation_results['teachers_total'] = len(teacher_hours)
        
        for teacher_data in teacher_hours.values():
            validation = WorkloadValidator.validate_teacher_workload(
                teacher_data['teacher'], teacher_data['hours']
            )
            
            if validation['is_valid']:
                validation_results['teachers_valid'] += 1
            else:
                validation_results['issues'].append({
                    'teacher': teacher_data['teacher'],
                    'planned_hours': teacher_data['hours'],
                    'recommendations': validation['recommendations']
                })
        
        # Проверяем общую нагрузку кафедры
        total_teachers = len(teacher_hours)
        if total_teachers > 0:
            avg_hours = validation_results['total_hours'] / total_teachers
            if avg_hours < 500:  # Меньше 500 часов в среднем
                validation_results['warnings'].append(
                    "Средняя нагрузка по кафедре ниже обычного уровня"
                )
        
        return validation_results