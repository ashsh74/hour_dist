from django.urls import path
from . import views, auth_views, api_views

app_name = 'hours_distribution'

urlpatterns = [
    path('login/', auth_views.login_view, name='login'),
    path('logout/', auth_views.logout_view, name='logout'),
    path('register/', auth_views.register_view, name='register'),
    path('profile/', auth_views.profile_view, name='profile'),
    path('api/auth/status/', auth_views.auth_status, name='auth_status'),
    
    # ═══ API Endpoints ═══
    path('api/semesters/', api_views.api_semesters, name='api_semesters'),
    path('api/student-groups/', api_views.api_student_groups, name='api_student_groups'),
    path('api/curriculum-subjects/', api_views.api_curriculum_subjects, name='api_curriculum_subjects'),
    path('api/departments/', api_views.api_departments_by_faculty, name='api_departments'),
    path('api/courses/', api_views.api_courses, name='api_courses'),
    path('api/faculties/', api_views.api_faculties, name='api_faculties'),
        
    path('', views.index, name='index'),
    # Отчеты
    path('reports/department/', views.department_report, name='department_report'),
    path('reports/department/<int:department_id>/', views.department_report, name='department_report_detail'),
    path('reports/departments-summary/', views.departments_summary_report, name='departments_summary_report'),
    path('reports/faculty/', views.faculty_report, name='faculty_report'),
    path('reports/faculty/<int:faculty_id>/', views.faculty_report, name='faculty_report_detail'),
    path('reports/university/', views.university_report, name='university_report'),
    path('reports/teacher/', views.teacher_report, name='teacher_report'),
    path('reports/teacher/<int:teacher_id>/', views.teacher_report, name='teacher_report_detail'),
    path('reports/group-workload/', views.group_workload_report, name='group_workload_report'),
    # Экспорт
    path('export/group-report/', views.export_group_report, name='export_group_report'),
    path('export/<str:report_type>/', views.export_report, name='export_report'),
    # Группы студентов
    path('groups/students/', views.student_groups_list, name='student_groups_list'),
    path('groups/students/<int:group_id>/', views.student_group_detail, name='student_group_detail'),
    path('groups/students/<int:group_id>/modal/', views.student_group_modal, name='student_group_modal'),
    path('groups/students/<int:group_id>/update-modal/', views.student_group_update_modal, name='student_group_update_modal'),
    path('groups/students/create/modal/', views.student_group_create_modal, name='student_group_create_modal'),
    path('groups/students/store/modal/', views.student_group_store_modal, name='student_group_store_modal'),
    path('groups/streams/', views.stream_groups_list, name='stream_groups_list'),
    path('groups/streams/<int:stream_id>/', views.stream_group_detail, name='stream_group_detail'),
    path('groups/streams/create/', views.create_stream_group, name='create_stream_group'),
    
    # Распределение нагрузки
    path('workload/distribute/', views.distribute_workload, name='distribute_workload'),
    path('workload/distributions/', views.workload_distribution_list, name='workload_distribution_list'),
    
    # Users CRUD
    path('users/', views.UserListView.as_view(), name='user_list'),
    path('users/create/', views.UserCreateView.as_view(), name='user_create'),
    path('users/<int:pk>/edit/', views.UserUpdateView.as_view(), name='user_update'),
    path('users/<int:pk>/delete/', views.UserDeleteView.as_view(), name='user_delete'),
    
    # Teachers CRUD
    path('teachers/', views.TeacherListView.as_view(), name='teacher_list'),
    path('teachers/create/', views.TeacherCreateView.as_view(), name='teacher_create'),
    path('teachers/<int:pk>/edit/', views.TeacherUpdateView.as_view(), name='teacher_update'),
    path('teachers/<int:pk>/delete/', views.TeacherDeleteView.as_view(), name='teacher_delete'),
    
    # API endpoints
    path('api/curriculum-subject-groups/', views.api_curriculum_subject_groups, name='api_curriculum_subject_groups'),
]