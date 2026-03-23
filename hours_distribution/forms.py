from django import forms
from .models import *
from django.contrib.auth.models import User
from .permissions import ROLE_PERMISSIONS


class StudentGroupForm(forms.ModelForm):
    class Meta:
        model = StudentGroup
        fields = ['name', 'code', 'group_type', 'course', 'bachelor_program', 
                  'year_of_admission', 'students_count', 'max_students', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'code': forms.TextInput(attrs={'class': 'form-control'}),
            'group_type': forms.Select(attrs={'class': 'form-control'}),
            'course': forms.Select(attrs={'class': 'form-control'}),
            'bachelor_program': forms.Select(attrs={'class': 'form-control'}),
            'year_of_admission': forms.NumberInput(attrs={'class': 'form-control'}),
            'students_count': forms.NumberInput(attrs={'class': 'form-control'}),
            'max_students': forms.NumberInput(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

class StudentGroupModalForm(forms.ModelForm):
    """Форма для модального редактирования группы студентов"""
    code = forms.CharField(
        disabled=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'readonly': True
        })
    )
    
    class Meta:
        model = StudentGroup
        fields = ['code', 'name', 'group_type', 'students_count', 'max_students', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Название группы'
            }),
            'group_type': forms.Select(attrs={'class': 'form-control'}),
            'students_count': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '0'
            }),
            'max_students': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '0'
            }),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields['code'].initial = self.instance.code


class StudentGroupCreateForm(forms.ModelForm):
    """Форма для модального создания новой группы студентов"""
    
    class Meta:
        model = StudentGroup
        fields = ['code', 'name', 'group_type', 'course', 'bachelor_program','year_of_admission', 'students_count', 'max_students', 'is_active']
        widgets = {
            'code': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Уникальный код группы (например, БТ-411)',
                'required': True
            }),
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Название группы'
            }),
            'group_type': forms.Select(attrs={'class': 'form-control'}),
            'course': forms.Select(attrs={'class': 'form-control'}),
            'bachelor_program': forms.Select(attrs={'class': 'form-control'}),
            'year_of_admission': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Год набора (например, 2024)',
                'min': '2000',
                'max': '2100'
            }),
            'students_count': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '0',
                'placeholder': '0'
            }),
            'max_students': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '1',
                'placeholder': '25'
            }),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
    
    def clean_code(self):
        code = self.cleaned_data.get('code')
        if code and StudentGroup.objects.filter(code=code).exists():
            raise forms.ValidationError(f"Группа с кодом '{code}' уже существует")
        return code
    
    def clean(self):
        cleaned_data = super().clean()
        students_count = cleaned_data.get('students_count')
        max_students = cleaned_data.get('max_students')
        
        if students_count is not None and max_students is not None and students_count > max_students:
            raise forms.ValidationError("Количество студентов не может быть больше максимального")
        
        return cleaned_data


class StreamGroupForm(forms.ModelForm):

    class Meta:
        model = StreamGroup
        fields = ['name', 'code', 'bachelor_program', 'course', 'semester', 
                  'student_groups', 'academic_year']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'code': forms.TextInput(attrs={'class': 'form-control'}),
            'bachelor_program': forms.Select(attrs={'class': 'form-control'}),
            'course': forms.Select(attrs={'class': 'form-control'}),
            'semester': forms.Select(attrs={'class': 'form-control'}),
            'student_groups': forms.SelectMultiple(attrs={'class': 'form-control'}),            
            'academic_year': forms.Select(attrs={'class': 'form-control'}),
        }

class CurriculumSubjectGroupForm(forms.ModelForm):
    class Meta:
        model = CurriculumSubjectGroup
        fields = ['curriculum_subject', 'student_group', 'stream_group',
                  'hours_lecture', 'hours_practice', 'hours_lab']
        widgets = {
            'curriculum_subject': forms.Select(attrs={'class': 'form-control'}),
            'student_group': forms.Select(attrs={'class': 'form-control'}),
            'stream_group': forms.Select(attrs={'class': 'form-control'}),
            'hours_lecture': forms.NumberInput(attrs={'class': 'form-control'}),
            'hours_practice': forms.NumberInput(attrs={'class': 'form-control'}),
            'hours_lab': forms.NumberInput(attrs={'class': 'form-control'}),
        }
    
    def clean(self):
        cleaned_data = super().clean()
        student_group = cleaned_data.get('student_group')
        stream_group = cleaned_data.get('stream_group')
        
        if not student_group and not stream_group:
            raise forms.ValidationError("Необходимо указать либо группу, либо поточную группу")
        
        if student_group and stream_group:
            raise forms.ValidationError("Можно указать только группу ИЛИ поточную группу")
        
        return cleaned_data

class WorkloadDistributionForm(forms.Form):
    """Форма для распределения нагрузки по группам"""
    curriculum_subject = forms.ModelChoiceField(
        queryset=CurriculumSubject.objects.all(),
        label="Дисциплина",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    teacher = forms.ModelChoiceField(
        queryset=Teacher.objects.filter(is_active=True),
        label="Преподаватель",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    group_type = forms.ChoiceField(
        choices=[('single', 'Отдельная группа'), ('stream', 'Потоковая группа')],
        label="Тип распределения",
        widget=forms.RadioSelect(attrs={'class': 'form-check-input'})
    )
    student_group = forms.ModelChoiceField(
        queryset=StudentGroup.objects.filter(is_active=True),
        label="Группа студентов",
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    stream_group = forms.ModelChoiceField(
        queryset=StreamGroup.objects.all(),
        label="Поточная группа",
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    hours_lecture = forms.IntegerField(
        min_value=0,
        label="Лекционные часы",
        widget=forms.NumberInput(attrs={'class': 'form-control'})
    )
    hours_practice = forms.IntegerField(
        min_value=0,
        label="Практические часы",
        widget=forms.NumberInput(attrs={'class': 'form-control'})
    )
    hours_lab = forms.IntegerField(
        min_value=0,
        label="Лабораторные часы",
        widget=forms.NumberInput(attrs={'class': 'form-control'})
    )

    def clean(self):
        cleaned_data = super().clean()
        group_type = cleaned_data.get('group_type')
        student_group = cleaned_data.get('student_group')
        stream_group = cleaned_data.get('stream_group')

        if group_type == 'single' and not student_group:
            raise forms.ValidationError("Для отдельной группы необходимо указать группу студентов")
        elif group_type == 'stream' and not stream_group:
            raise forms.ValidationError("Для потоковой группы необходимо указать поток")

        return cleaned_data


# ----- User and Teacher forms for CRUD operations -----
from django.contrib.auth.forms import UserCreationForm, UserChangeForm

class CustomUserCreationForm(UserCreationForm):
    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email']
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
        }

class CustomUserChangeForm(UserChangeForm):
    password = None  # hide password field
    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email', 'is_active', 'is_staff']
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_staff': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

class TeacherForm(forms.ModelForm):
    class Meta:
        model = Teacher
        fields = ['user', 'department', 'last_name', 'first_name', 'middle_name', 'position', 'workload_hours', 'is_active']
        widgets = {
            'user': forms.Select(attrs={'class': 'form-control'}),
            'department': forms.Select(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'middle_name': forms.TextInput(attrs={'class': 'form-control'}),
            'position': forms.TextInput(attrs={'class': 'form-control'}),
            'workload_hours': forms.NumberInput(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
    
    teacher = forms.ModelChoiceField(
        queryset=Teacher.objects.filter(is_active=True),
        label="Преподаватель",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    group_type = forms.ChoiceField(
        choices=[('single', 'Отдельная группа'), ('stream', 'Потоковая группа')],
        label="Тип распределения",
        widget=forms.RadioSelect(attrs={'class': 'form-check-input'})
    )
    
    student_group = forms.ModelChoiceField(
        queryset=StudentGroup.objects.filter(is_active=True),
        label="Группа студентов",
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    stream_group = forms.ModelChoiceField(
        queryset=StreamGroup.objects.all(),
        label="Поточная группа",
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    hours_lecture = forms.IntegerField(
        min_value=0,
        label="Лекционные часы",
        widget=forms.NumberInput(attrs={'class': 'form-control'})
    )
    
    hours_practice = forms.IntegerField(
        min_value=0,
        label="Практические часы",
        widget=forms.NumberInput(attrs={'class': 'form-control'})
    )
    
    hours_lab = forms.IntegerField(
        min_value=0,
        label="Лабораторные часы",
        widget=forms.NumberInput(attrs={'class': 'form-control'})
    )
    
    def clean(self):
        cleaned_data = super().clean()
        group_type = cleaned_data.get('group_type')
        student_group = cleaned_data.get('student_group')
        stream_group = cleaned_data.get('stream_group')
        
        if group_type == 'single' and not student_group:
            raise forms.ValidationError("Для отдельной группы необходимо указать группу студентов")
        elif group_type == 'stream' and not stream_group:
            raise forms.ValidationError("Для потоковой группы необходимо указать поток")
        
        return cleaned_data



class UserRegistrationForm(forms.ModelForm):
    """Форма создания нового пользователя с назначением роли."""
    
    password = forms.CharField(
        widget=forms.PasswordInput(),
        min_length=8,
        label='Пароль'
    )
    password_confirm = forms.CharField(
        widget=forms.PasswordInput(),
        label='Подтверждение пароля'
    )
    role = forms.ChoiceField(
        choices=[(r, r) for r in ['admin'] + list(ROLE_PERMISSIONS.keys())],
        label='Роль'
    )
    faculty = forms.ModelChoiceField(
        queryset=Faculty.objects.all(),
        required=False,
        label='Факультет'
    )
    department = forms.ModelChoiceField(
        queryset=Department.objects.all(),
        required=False,
        label='Кафедра'
    )
    
    class Meta:
        model = User
        fields = ['username', 'email', 'first_name', 'last_name']
        labels = {
            'username': 'Логин',
            'email': 'Email',
            'first_name': 'Имя',
            'last_name': 'Фамилия',
        }
    
    def clean_password_confirm(self):
        password = self.cleaned_data.get('password')
        password_confirm = self.cleaned_data.get('password_confirm')
        if password and password_confirm and password != password_confirm:
            raise forms.ValidationError('Пароли не совпадают')
        return password_confirm
    
    def clean(self):
        cleaned_data = super().clean()
        role = cleaned_data.get('role')
        
        # Валидация: dean должен иметь faculty
        if role == 'dean' and not cleaned_data.get('faculty'):
            self.add_error('faculty', 'Деканам обязательно нужен факультет')
        
        # Валидация: head должен иметь department
        if role == 'head' and not cleaned_data.get('department'):
            self.add_error('department', 'Заведующим обязательна кафедра')
        
        return cleaned_data