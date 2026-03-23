from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

# 1. Базовые модели
class AcademicYear(models.Model):
    """Учебный год"""
    name = models.CharField(max_length=50, verbose_name="Название учебного года")
    start_year = models.IntegerField(verbose_name="Год начала")
    end_year = models.IntegerField(verbose_name="Год окончания")
    is_current = models.BooleanField(default=False, verbose_name="Текущий учебный год")
    is_planned = models.BooleanField(default=False, verbose_name="Запланирован")
    
    class Meta:
        verbose_name = "Учебный год"
        verbose_name_plural = "Учебные годы"
        ordering = ['-start_year']
    
    def __str__(self):
        return self.name
    
    def save(self, *args, **kwargs):
        if self.is_current:
            AcademicYear.objects.filter(is_current=True).update(is_current=False)
        super().save(*args, **kwargs)

class Semester(models.Model):
    """Семестр"""
    academic_year = models.ForeignKey(AcademicYear, on_delete=models.CASCADE, verbose_name="Учебный год")
    number = models.IntegerField(
        verbose_name="Номер семестра",
        choices=[
            (1, '1'), 
            (2, '2'), 
            (3, '3'), 
            (4, '4'), 
            (5, '5'), 
            (6, '6'), 
            (7, '7'), 
            (8, '8')
        ]
    )
    start_date = models.DateField(verbose_name="Дата начала")
    end_date = models.DateField(verbose_name="Дата окончания")
    
    class Meta:
        verbose_name = "Семестр"
        verbose_name_plural = "Семестры"
        unique_together = ['academic_year', 'number']
    
    def __str__(self):
        return f"{self.academic_year} - Семестр {self.number}"

class Faculty(models.Model):
    """Факультет"""
    name = models.CharField(max_length=200, verbose_name="Название факультета")
    short_name = models.CharField(max_length=50, verbose_name="Короткое название")
    dean = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        verbose_name="Декан", 
        related_name='faculty_dean'
    )
    
    class Meta:
        verbose_name = "Факультет"
        verbose_name_plural = "Факультеты"
    
    def __str__(self):
        return self.name

class Department(models.Model):
    """Кафедра"""
    faculty = models.ForeignKey(Faculty, on_delete=models.CASCADE, verbose_name="Факультет")
    name = models.CharField(max_length=200, verbose_name="Название кафедры")
    short_name = models.CharField(max_length=50, verbose_name="Короткое название")
    head = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        verbose_name="Заведующий кафедрой", 
        related_name='department_head'
    )
    
    class Meta:
        verbose_name = "Кафедра"
        verbose_name_plural = "Кафедры"
    
    def __str__(self):
        return f"{self.name} ({self.faculty.short_name})"

class UserProfile(models.Model):
    """Расширенный профиль пользователя"""
    ROLE_CHOICES = [
        ('admin', 'Администратор'),
        ('dean', 'Декан'),
        ('head', 'Заведующий кафедрой'),
        ('teacher', 'Преподаватель'),
        ('planner', 'Планировщик'),
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='teacher', verbose_name="Роль")
    faculty = models.ForeignKey(Faculty, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Факультет")
    department = models.ForeignKey(
        Department, 
        on_delete=models.SET_NULL, 
        null=True, blank=True,
        verbose_name="Кафедра"
    )
    phone = models.CharField(max_length=20, blank=True, verbose_name="Телефон")
    
    class Meta:
        verbose_name = "Профиль пользователя"
        verbose_name_plural = "Профили пользователей"
    
    def __str__(self):
        return f"{self.user.get_full_name()} ({self.get_role_display()})"

# 2. Академические модели
class Course(models.Model):
    """Курс"""
    number = models.IntegerField(verbose_name="Номер курса", choices=[(1, '1'), (2, '2'), (3, '3'), (4, '4')])
    
    class Meta:
        verbose_name = "Курс"
        verbose_name_plural = "Курсы"
    
    def __str__(self):
        return f"{self.number} курс"

class BachelorProgram(models.Model):
    """Направление бакалавриата"""
    code = models.CharField(max_length=20, verbose_name="Код направления")
    name = models.CharField(max_length=200, verbose_name="Название направления")
    faculty = models.ForeignKey(Faculty, on_delete=models.CASCADE, verbose_name="Факультет")
    
    class Meta:
        verbose_name = "Направление бакалавриата"
        verbose_name_plural = "Направления бакалавриата"
    
    def __str__(self):
        return f"{self.code} - {self.name}"

class Curriculum(models.Model):
    """Учебный план"""
    bachelor_program = models.ForeignKey(BachelorProgram, on_delete=models.CASCADE, verbose_name="Направление")
    academic_year = models.ForeignKey(AcademicYear, on_delete=models.CASCADE, verbose_name="Учебный год")
    year_of_admission = models.IntegerField(verbose_name="Год набора")
    status = models.CharField(max_length=20, default='active', choices=[
        ('draft', 'Черновик'),
        ('active', 'Активный'),
        ('archived', 'Архивный')
    ])
    
    class Meta:
        verbose_name = "Учебный план"
        verbose_name_plural = "Учебные планы"
    
    def __str__(self):
        return f"План {self.bachelor_program.code} ({self.year_of_admission})"

# 3. Модели дисциплин
class Subject(models.Model):
    """Учебная дисциплина/Предмет"""
    name = models.CharField(max_length=200, verbose_name="Название дисциплины")
    code = models.CharField(max_length=50, verbose_name="Код дисциплины")
    department = models.ForeignKey(Department, on_delete=models.CASCADE, verbose_name="Кафедра")
    
    class Meta:
        verbose_name = "Дисциплина"
        verbose_name_plural = "Дисциплины"
    
    def __str__(self):
        return f"{self.code} - {self.name}"

class CurriculumSubject(models.Model):
    """Дисциплина в учебном плане"""
    curriculum = models.ForeignKey(Curriculum, on_delete=models.CASCADE, verbose_name="Учебный план")
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, verbose_name="Дисциплина")
    course = models.ForeignKey(Course, on_delete=models.CASCADE, verbose_name="Курс")
    semester = models.ForeignKey(Semester, on_delete=models.CASCADE, verbose_name="Семестр")
    
    # Изменим имена полей для совместимости
    lecture_hours = models.IntegerField(verbose_name="Лекционные часы", default=0)
    practice_hours = models.IntegerField(verbose_name="Практические часы", default=0)
    lab_hours = models.IntegerField(verbose_name="Лабораторные часы", default=0)
    
    department = models.ForeignKey(Department, on_delete=models.CASCADE, verbose_name="Кафедра")
    is_stream = models.BooleanField(default=False, verbose_name="Потоковая дисциплина")
    
    class Meta:
        verbose_name = "Дисциплина в плане"
        verbose_name_plural = "Дисциплины в плане"
    
    def __str__(self):
        return f"{self.subject.code} - {self.curriculum}"
    
    def total_hours(self):
        return self.lecture_hours + self.practice_hours + self.lab_hours
    
    # Добавим свойства для обратной совместимости
    @property
    def total_hours_lecture(self):
        return self.lecture_hours
    
    @property
    def total_hours_practice(self):
        return self.practice_hours
    
    @property
    def total_hours_lab(self):
        return self.lab_hours

# 4. Модели групп студентов
class StudentGroup(models.Model):
    """Группа студентов"""
    TYPE_CHOICES = [
        ('regular', 'Обычная группа'),
        ('stream', 'Потоковая группа'),
        ('subgroup', 'Подгруппа'),
    ]
    
    name = models.CharField(max_length=50, verbose_name="Название группы")
    code = models.CharField(max_length=20, verbose_name="Код группы", unique=True)
    group_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='regular', verbose_name="Тип группы")
    course = models.ForeignKey(Course, on_delete=models.CASCADE, verbose_name="Курс")
    bachelor_program = models.ForeignKey(BachelorProgram, on_delete=models.CASCADE, verbose_name="Направление")
    year_of_admission = models.IntegerField(verbose_name="Год набора")
    students_count = models.IntegerField(default=0, verbose_name="Количество студентов")
    max_students = models.IntegerField(default=25, verbose_name="Максимальное количество студентов")
    is_active = models.BooleanField(default=True, verbose_name="Активная группа")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Группа студентов"
        verbose_name_plural = "Группы студентов"
        ordering = ['-year_of_admission', 'course__number', 'name']
    
    def __str__(self):
        return f"{self.name} ({self.course.number} курс)"
    
    def get_full_name(self):
        return f"{self.name} - {self.bachelor_program.code} ({self.year_of_admission}г.)"

class StreamGroup(models.Model):
    """Поточная группа (объединение нескольких групп для лекций)"""
    name = models.CharField(max_length=100, verbose_name="Название потока")
    code = models.CharField(max_length=30, verbose_name="Код потока", unique=True)
    #subject = models.ForeignKey(Subject, on_delete=models.CASCADE, verbose_name="Дисциплина")
    bachelor_program = models.ForeignKey(BachelorProgram, on_delete=models.CASCADE, verbose_name="Направление")
    course = models.ForeignKey(Course, on_delete=models.CASCADE, verbose_name="Курс")
    semester = models.ForeignKey(Semester, on_delete=models.CASCADE, verbose_name="Семестр")
    student_groups = models.ManyToManyField(StudentGroup, verbose_name="Группы в потоке")
    total_students = models.IntegerField(default=0, verbose_name="Общее количество студентов")
    academic_year = models.ForeignKey(AcademicYear, on_delete=models.CASCADE, verbose_name="Учебный год")
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, verbose_name="Создал")
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Поточная группа"
        verbose_name_plural = "Поточные группы"
    
    def __str__(self):
        return f"Поток {self.code} - {self.bachelor_program.name} ({self.course.number} курс)"
    
    def save(self, *args, **kwargs):
        # Автоматически рассчитываем количество студентов при сохранении
        if self.pk:
            self.total_students = sum(group.students_count for group in self.student_groups.all())
        super().save(*args, **kwargs)

class CurriculumSubjectStream(models.Model):
    """Связь дисциплины с поточными группами"""
    curriculum_subject = models.ForeignKey(CurriculumSubject, on_delete=models.CASCADE)
    stream_group = models.ForeignKey(StreamGroup, on_delete=models.CASCADE)
    
    class Meta:
        unique_together = ['curriculum_subject', 'stream_group']
        verbose_name = "Связь дисциплины с потоком"
        verbose_name_plural = "Связи дисциплин с потоками"

class CurriculumSubjectGroup(models.Model):
    """Связь дисциплины в учебном плане с группами студентов"""
    curriculum_subject = models.ForeignKey(CurriculumSubject, on_delete=models.CASCADE, verbose_name="Дисциплина в плане")
    student_group = models.ForeignKey(StudentGroup, on_delete=models.CASCADE, verbose_name="Группа", null=True, blank=True)
    stream_group = models.ForeignKey(StreamGroup, on_delete=models.CASCADE, verbose_name="Поточная группа", null=True, blank=True)
    hours_lecture = models.IntegerField(verbose_name="Лекционные часы", default=0)
    hours_practice = models.IntegerField(verbose_name="Практические часы", default=0)
    hours_lab = models.IntegerField(verbose_name="Лабораторные часы", default=0)
    
    class Meta:
        verbose_name = "Группа для дисциплины"
        verbose_name_plural = "Группы для дисциплин"
        constraints = [
            models.CheckConstraint(
                check=models.Q(student_group__isnull=False) | models.Q(stream_group__isnull=False),
                name='at_least_one_group'
            )
        ]
    
    def __str__(self):
        if self.student_group:
            return f"{self.curriculum_subject.subject.code} - {self.student_group.code}"
        else:
            return f"{self.curriculum_subject.subject.code} - {self.stream_group.code}"
    
    def total_hours(self):
        return self.hours_lecture + self.hours_practice + self.hours_lab
    
    def get_group_display(self):
        if self.student_group:
            return self.student_group.get_full_name()
        else:
            return f"Поток: {self.stream_group.name}"

# 5. Модели нагрузки
class Teacher(models.Model):
    """Преподаватель"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='teacher_profile', null=True, blank=True)
    department = models.ForeignKey(Department, on_delete=models.CASCADE, verbose_name="Кафедра")
    last_name = models.CharField(max_length=100, verbose_name="Фамилия")
    first_name = models.CharField(max_length=100, verbose_name="Имя")
    middle_name = models.CharField(max_length=100, verbose_name="Отчество", blank=True)
    position = models.CharField(max_length=100, verbose_name="Должность")
    workload_hours = models.IntegerField(verbose_name="Нагрузка (часов в неделю)", default=18)
    is_active = models.BooleanField(default=True, verbose_name="Активный")
    
    class Meta:
        verbose_name = "Преподаватель"
        verbose_name_plural = "Преподаватели"
    
    def __str__(self):
        return f"{self.last_name} {self.first_name[0]}.{self.middle_name[0] + '.' if self.middle_name else ''}"
    
    def get_full_name(self):
        return f"{self.last_name} {self.first_name} {self.middle_name or ''}".strip()

class TeacherWorkload(models.Model):
    """Нагрузка преподавателя"""
    STATUS_CHOICES = [
        ('planned', 'Запланировано'),
        ('approved', 'Утверждено'),
        ('completed', 'Выполнено'),
        ('cancelled', 'Отменено'),
    ]
    
    teacher = models.ForeignKey(Teacher, on_delete=models.CASCADE, verbose_name="Преподаватель")
    curriculum_subject_group = models.ForeignKey(
        CurriculumSubjectGroup, on_delete=models.CASCADE,
        verbose_name="Дисциплина и группа"
    )
    hours_lecture = models.IntegerField(verbose_name="Лекционные часы", default=0)
    hours_practice = models.IntegerField(verbose_name="Практические часы", default=0)
    hours_lab = models.IntegerField(verbose_name="Лабораторные часы", default=0)
    academic_year = models.ForeignKey(
        AcademicYear, 
        on_delete=models.CASCADE, 
        verbose_name="Учебный год"
    )
    status = models.CharField(
        max_length=20, 
        choices=STATUS_CHOICES, 
        default='planned', 
        verbose_name="Статус"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    approved_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        verbose_name="Утвердил", 
        related_name='approved_workloads'
    )
    approved_date = models.DateTimeField(null=True, blank=True, verbose_name="Дата утверждения")
    
    class Meta:
        verbose_name = "Нагрузка преподавателя"
        verbose_name_plural = "Нагрузки преподавателей"
    
    def total_hours(self):
        return self.hours_lecture + self.hours_practice + self.hours_lab
    
    def get_groups_info(self):
        """Получить информацию о группах"""
        csg = self.curriculum_subject_group
        if csg.student_group:
            return {
                'type': 'group',
                'name': csg.student_group.get_full_name(),
                'students_count': csg.student_group.students_count
            }
        else:
            return {
                'type': 'stream',
                'name': csg.stream_group.name,
                'students_count': csg.stream_group.total_students,
                'groups_count': csg.stream_group.student_groups.count()
            }
    
    def approve(self, user):
        self.status = 'approved'
        self.approved_by = user
        self.approved_date = timezone.now()
        self.save()
    
    @property
    def curriculum_subject(self):
        return self.curriculum_subject_group.curriculum_subject

class TimeTracking(models.Model):
    """Учет рабочего времени"""
    teacher = models.ForeignKey(Teacher, on_delete=models.CASCADE, verbose_name="Преподаватель")
    workload = models.ForeignKey(TeacherWorkload, on_delete=models.CASCADE, verbose_name="Нагрузка")
    date = models.DateField(verbose_name="Дата")
    hours_spent = models.DecimalField(max_digits=4, decimal_places=1, verbose_name="Затрачено часов")
    activity_type = models.CharField(max_length=20, choices=[
        ('lecture', 'Лекция'),
        ('practice', 'Практика'),
        ('lab', 'Лабораторная'),
        ('preparation', 'Подготовка'),
        ('consultation', 'Консультация'),
        ('checking', 'Проверка работ'),
    ])
    description = models.TextField(blank=True, verbose_name="Описание")
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Учет времени"
        verbose_name_plural = "Учет времени"
    
    def __str__(self):
        return f"{self.teacher} - {self.date} - {self.hours_spent}ч"

class NextYearPlan(models.Model):
    """План на следующий учебный год"""
    STATUS_CHOICES = [
        ('draft', 'Черновик'),
        ('submitted', 'На рассмотрении'),
        ('approved_dean', 'Утверждено деканом'),
        ('approved_rector', 'Утверждено ректором'),
        ('rejected', 'Отклонено'),
    ]
    
    department = models.ForeignKey(Department, on_delete=models.CASCADE, verbose_name="Кафедра")
    academic_year = models.ForeignKey(AcademicYear, on_delete=models.CASCADE, verbose_name="Учебный год")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_plans')
    created_at = models.DateTimeField(auto_now_add=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    approved_by_dean = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                       related_name='dean_approved_plans')
    approved_by_rector = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                         related_name='rector_approved_plans')
    notes = models.TextField(blank=True, verbose_name="Примечания")
    
    class Meta:
        verbose_name = "План на следующий год"
        verbose_name_plural = "Планы на следующий год"
        unique_together = ['department', 'academic_year']
    
    def __str__(self):
        return f"План {self.department} на {self.academic_year}"

class PlannedWorkload(models.Model):
    """Запланированная нагрузка на следующий год"""
    plan = models.ForeignKey(NextYearPlan, on_delete=models.CASCADE, related_name='planned_workloads')
    teacher = models.ForeignKey(Teacher, on_delete=models.CASCADE, verbose_name="Преподаватель")
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, verbose_name="Дисциплина")
    hours_lecture = models.IntegerField(default=0, verbose_name="Лекционные часы")
    hours_practice = models.IntegerField(default=0, verbose_name="Практические часы")
    hours_lab = models.IntegerField(default=0, verbose_name="Лабораторные часы")
    course = models.ForeignKey(Course, on_delete=models.CASCADE, verbose_name="Курс")
    semester = models.ForeignKey(Semester, on_delete=models.CASCADE, verbose_name="Семестр")
    notes = models.TextField(blank=True, verbose_name="Примечания")
    
    class Meta:
        verbose_name = "Запланированная нагрузка"
        verbose_name_plural = "Запланированные нагрузки"
    
    def total_hours(self):
        return self.hours_lecture + self.hours_practice + self.hours_lab