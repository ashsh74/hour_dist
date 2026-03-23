from django import template

register = template.Library()

@register.filter
def divide(value, arg):
    """Делит значение на аргумент"""
    try:
        return float(value) / float(arg)
    except (ValueError, ZeroDivisionError):
        return 0

@register.filter
def multiply(value, arg):
    """Умножает значение на аргумент"""
    try:
        return float(value) * float(arg)
    except ValueError:
        return 0

@register.filter
def calculate_workload_percentage(teacher_hours, teacher_workload):
    """Рассчитывает процент нагрузки"""
    try:
        if teacher_workload and teacher_workload > 0:
            # teacher_workload - недельная нагрузка, умножаем на 36 недель
            max_hours = teacher_workload * 36
            if max_hours > 0:
                percentage = (teacher_hours / max_hours) * 100
                return round(percentage, 1)
        return 0
    except:
        return 0

@register.filter
def get_overloaded_count(workload_data):
    """Считает количество преподавателей с перегрузкой"""
    count = 0
    for data in workload_data:
        if data.get('workload_percentage', 0) > 100:
            count += 1
    return count

@register.filter
def get_subjects_count(workload_data):
    """Считает общее количество дисциплин"""
    count = 0
    for data in workload_data:
        count += len(data.get('workloads', []))
    return count

@register.filter
def get_percentage(current_value, max_value):
    """Рассчитывает процент от максимального значения"""
    try:
        if max_value and max_value > 0:
            percentage = (float(current_value) / float(max_value)) * 100
            return int(round(percentage))
        return 0
    except (ValueError, ZeroDivisionError, TypeError):
        return 0

@register.filter
def get_avg_hours(total_hours, teachers_count):
    """Рассчитывает среднюю нагрузку на преподавателя"""
    try:
        if teachers_count and teachers_count > 0:
            return round(total_hours / teachers_count, 1)
        return 0
    except:
        return 0

@register.simple_tag
def calculate_hour_distribution(workloads, hour_type):
    """Рассчитывает распределение часов по типу"""
    total = 0
    for wl in workloads:
        if hour_type == 'lecture':
            total += wl.hours_lecture
        elif hour_type == 'practice':
            total += wl.hours_practice
        elif hour_type == 'lab':
            total += wl.hours_lab
    return total