# hours_distribution/serializers.py
# Сериализаторы для API

from rest_framework import serializers
from .models import Semester, StudentGroup, CurriculumSubject, Course, Subject


class SemesterSerializer(serializers.ModelSerializer):
    """Сериализатор для семестров."""
    
    class Meta:
        model = Semester
        fields = ['id', 'number', 'name', 'academic_year']


class StudentGroupSerializer(serializers.ModelSerializer):
    """Сериализатор для студенческих групп."""
    
    course_name = serializers.CharField(source='course.name', read_only=True)
    program_name = serializers.CharField(source='bachelor_program.name', read_only=True)
    faculty_name = serializers.CharField(source='bachelor_program.faculty.short_name', read_only=True)
    
    class Meta:
        model = StudentGroup
        fields = [
            'id', 'code', 'name', 'students_count',
            'course', 'course_name',
            'bachelor_program', 'program_name', 'faculty_name',
        ]


class CurriculumSubjectSerializer(serializers.ModelSerializer):
    """Сериализатор для дисциплин учебного плана."""
    
    subject_name = serializers.CharField(source='subject.name', read_only=True)
    course_number = serializers.IntegerField(source='course.number', read_only=True)
    semester_number = serializers.IntegerField(source='semester.number', read_only=True)
    
    class Meta:
        model = CurriculumSubject
        fields = [
            'id', 'subject', 'subject_name',
            'course', 'course_number',
            'semester', 'semester_number',
            'hours_lecture', 'hours_practice', 'hours_lab',
        ]