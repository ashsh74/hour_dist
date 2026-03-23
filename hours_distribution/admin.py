from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from .models import *

# Inline модели
class CurriculumSubjectStreamInline(admin.TabularInline):
    model = CurriculumSubjectStream
    extra = 1
    verbose_name = "Потоковая группа"
    verbose_name_plural = "Потоковые группы"

class CurriculumSubjectStreamInlineForStream(admin.TabularInline):
    model = CurriculumSubjectStream
    extra = 1
    verbose_name = "Дисциплина"
    verbose_name_plural = "Дисциплины"

class TeacherWorkloadInline(admin.TabularInline):
    model = TeacherWorkload
    extra = 1
    readonly_fields = ['created_at', 'updated_at']

class TimeTrackingInline(admin.TabularInline):
    model = TimeTracking
    extra = 1
    readonly_fields = ['created_at']

class PlannedWorkloadInline(admin.TabularInline):
    model = PlannedWorkload
    extra = 1

# Регистрация моделей
@admin.register(AcademicYear)
class AcademicYearAdmin(admin.ModelAdmin):
    list_display = ['name', 'start_year', 'end_year', 'is_current', 'is_planned']
    list_editable = ['is_current', 'is_planned']
    search_fields = ['name']
    list_filter = ['is_current', 'is_planned']

@admin.register(Semester)
class SemesterAdmin(admin.ModelAdmin):
    list_display = ['academic_year', 'number', 'start_date', 'end_date']
    list_filter = ['academic_year', 'number']
    search_fields = ['academic_year__name']

@admin.register(Faculty)
class FacultyAdmin(admin.ModelAdmin):
    list_display = ['name', 'short_name', 'dean']
    search_fields = ['name', 'short_name']

@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ['name', 'short_name', 'faculty', 'head']
    list_filter = ['faculty']
    search_fields = ['name', 'short_name']

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'role', 'faculty', 'department', 'phone']
    list_filter = ['role', 'faculty', 'department']
    search_fields = ['user__username', 'user__first_name', 'user__last_name']

@admin.register(BachelorProgram)
class BachelorProgramAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'faculty']
    list_filter = ['faculty']
    search_fields = ['code', 'name']

@admin.register(Curriculum)
class CurriculumAdmin(admin.ModelAdmin):
    list_display = ['bachelor_program', 'academic_year', 'year_of_admission', 'status']
    list_filter = ['academic_year', 'bachelor_program__faculty', 'status']
    search_fields = ['bachelor_program__code']

@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ['number']
    search_fields = ['number']

@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'department']
    list_filter = ['department', 'department__faculty']
    search_fields = ['code', 'name']

@admin.register(CurriculumSubject)
class CurriculumSubjectAdmin(admin.ModelAdmin):
    list_display = ['curriculum', 'subject', 'course', 'semester', 
                    'total_hours_lecture', 'total_hours_practice', 
                    'total_hours_lab', 'total_hours', 'department', 'is_stream']
    list_filter = ['curriculum', 'course', 'semester', 'department', 'is_stream']
    search_fields = ['subject__name', 'subject__code']
    inlines = [CurriculumSubjectStreamInline]

@admin.register(CurriculumSubjectStream)
class CurriculumSubjectStreamAdmin(admin.ModelAdmin):
    list_display = ['curriculum_subject', 'stream_group', 'get_course', 'get_semester']
    list_filter = ['curriculum_subject__curriculum', 'curriculum_subject__course', 'stream_group__academic_year']
    search_fields = ['curriculum_subject__subject__name', 'stream_group__name']
    
    def get_course(self, obj):
        return obj.curriculum_subject.course
    get_course.short_description = 'Курс'
    
    def get_semester(self, obj):
        return obj.curriculum_subject.semester
    get_semester.short_description = 'Семестр'

@admin.register(StudentGroup)
class StudentGroupAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'group_type', 'course', 'bachelor_program', 
                    'year_of_admission', 'students_count', 'is_active']
    list_filter = ['group_type', 'course', 'bachelor_program', 'year_of_admission', 'is_active']
    search_fields = ['code', 'name', 'bachelor_program__code']
    list_editable = ['students_count', 'is_active']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('name', 'code', 'group_type', 'course', 'bachelor_program')
        }),
        ('Параметры', {
            'fields': ('year_of_admission', 'students_count', 'max_students', 'is_active')
        }),
        ('Системная информация', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

@admin.register(StreamGroup)
class StreamGroupAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'bachelor_program', 'course', 'semester', 
                    'total_students', 'academic_year', 'created_by']
    list_filter = ['course', 'semester', 'academic_year', 'bachelor_program']
    search_fields = ['code', 'name', 'bachelor_program__name']
    filter_horizontal = ['student_groups']
    readonly_fields = ['total_students', 'created_at']
    inlines = [CurriculumSubjectStreamInlineForStream]
    
    def save_model(self, request, obj, form, change):
        if not obj.created_by:
            obj.created_by = request.user
        obj.save()
        # Пересчитываем количество студентов после сохранения
        obj.total_students = sum(group.students_count for group in obj.student_groups.all())
        super().save_model(request, obj, form, change)

@admin.register(CurriculumSubjectGroup)
class CurriculumSubjectGroupAdmin(admin.ModelAdmin):
    list_display = ['curriculum_subject', 'get_group_display', 'hours_lecture', 
                    'hours_practice', 'hours_lab', 'total_hours']
    list_filter = ['curriculum_subject__curriculum', 'curriculum_subject__subject__department']
    search_fields = ['curriculum_subject__subject__name', 
                    'student_group__code', 'stream_group__code']
    
    def get_group_display(self, obj):
        return obj.get_group_display()
    get_group_display.short_description = 'Группа'

@admin.register(Teacher)
class TeacherAdmin(admin.ModelAdmin):
    list_display = ['last_name', 'first_name', 'middle_name', 'department', 
                    'position', 'workload_hours', 'is_active']
    list_filter = ['department', 'position', 'is_active']
    search_fields = ['last_name', 'first_name', 'middle_name']
    inlines = [TeacherWorkloadInline]

@admin.register(TeacherWorkload)
class TeacherWorkloadAdmin(admin.ModelAdmin):
    list_display = ['teacher', 'get_subject', 'get_groups', 'academic_year', 
                    'status', 'total_hours', 'approved_by', 'approved_date']
    list_filter = ['academic_year', 'status', 'teacher__department']
    search_fields = ['teacher__last_name', 'curriculum_subject_group__curriculum_subject__subject__name']
    readonly_fields = ['created_at', 'updated_at', 'approved_date']
    inlines = [TimeTrackingInline]
    
    def get_subject(self, obj):
        return obj.curriculum_subject_group.curriculum_subject.subject.name
    get_subject.short_description = 'Дисциплина'
    
    def get_groups(self, obj):
        info = obj.get_groups_info()
        if info['type'] == 'group':
            return f"Группа: {info['name']}"
        else:
            return f"Поток: {info['name']} ({info['groups_count']} групп)"
    get_groups.short_description = 'Группы'

@admin.register(TimeTracking)
class TimeTrackingAdmin(admin.ModelAdmin):
    list_display = ['teacher', 'workload', 'date', 'hours_spent', 'activity_type', 'created_at']
    list_filter = ['activity_type', 'date', 'teacher__department']
    search_fields = ['teacher__last_name', 'description']
    readonly_fields = ['created_at']

@admin.register(NextYearPlan)
class NextYearPlanAdmin(admin.ModelAdmin):
    list_display = ['department', 'academic_year', 'status', 'created_by', 
                    'created_at', 'approved_by_dean', 'approved_by_rector']
    list_filter = ['status', 'academic_year', 'department__faculty']
    search_fields = ['department__name', 'notes']
    readonly_fields = ['created_at', 'submitted_at']
    inlines = [PlannedWorkloadInline]

@admin.register(PlannedWorkload)
class PlannedWorkloadAdmin(admin.ModelAdmin):
    list_display = ['plan', 'teacher', 'subject', 'course', 'semester', 'total_hours']
    list_filter = ['plan__academic_year', 'plan__department', 'course', 'semester']
    search_fields = ['teacher__last_name', 'subject__name', 'notes']