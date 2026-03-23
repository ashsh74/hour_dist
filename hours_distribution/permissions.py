from __future__ import annotations
from functools import lru_cache, wraps
from typing import Literal
from django.contrib.auth.models import Permission, User
from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.http import HttpResponseForbidden
from django.contrib.auth.decorators import login_required

# ✅ Единый источник истины для всех ролей
Role = Literal['admin', 'dean', 'head', 'teacher', 'planner']

ROLE_PERMISSIONS: dict[str, list[str]] = {
    'dean': [
        'view_faculty', 'change_faculty',
        'view_department', 'change_department',
        'view_teacher', 'change_teacher',
        'view_teacherworkload', 'change_teacherworkload',
        'approve_teacherworkload',
        'view_nextyearplan', 'change_nextyearplan',
        'approve_nextyearplan',
        'view_report', 'export_report',
    ],
    'head': [
        'view_department', 'change_department',
        'view_teacher', 'change_teacher',
        'view_teacherworkload', 'change_teacherworkload',
        'approve_teacherworkload',
        'view_nextyearplan', 'change_nextyearplan',
        'add_nextyearplan',  # ← исправлено (было create_)
        'view_report', 'export_report',
    ],
    'teacher': [
        'view_teacherworkload', 'view_teacher',
        'view_subject',
        'view_timetracking', 'add_timetracking', 'change_timetracking',
    ],
    'planner': [
        'view_curriculum', 'change_curriculum',
        'view_curriculumsubject', 'change_curriculumsubject',
        'view_nextyearplan', 'change_nextyearplan', 'add_nextyearplan',
    ],
}

CUSTOM_PERMISSIONS = [
    ('approve_teacherworkload', 'Can approve teacher workload'),
    ('approve_nextyearplan', 'Can approve next year plan'),
    ('export_report', 'Can export reports'),
    ('view_report', 'Can view reports'),
]


class RoleManager:
    """Менеджер ролей и разрешений."""

    @staticmethod
    def setup_permissions() -> None:
        """Создать кастомные разрешения в БД (вызывать в миграции/manage.py)."""
        from .models import TeacherWorkload
        content_type = ContentType.objects.get_for_model(TeacherWorkload)
        for codename, name in CUSTOM_PERMISSIONS:
            Permission.objects.get_or_create(
                codename=codename,
                content_type=content_type,
                defaults={'name': name},
            )

    @staticmethod
    @lru_cache(maxsize=None)  # ✅ кешируем — БД не дергаем повторно
    def get_role_permissions(role: Role) -> list[Permission]:
        """Вернуть объекты Permission для роли."""
        codenames = ROLE_PERMISSIONS.get(role, [])
        return list(Permission.objects.filter(codename__in=codenames))

    @staticmethod
    @transaction.atomic()  # ✅ атомарность — нет окна без прав
    def assign_role(
        user: User,
        role: Role,
        faculty=None,
        department=None,
    ) -> None:
        """Назначить роль пользователю."""
        if role not in (list(ROLE_PERMISSIONS) + ['admin']):
            raise ValueError(f"Unknown role: {role}")

        from .models import UserProfile
        profile, _ = UserProfile.objects.update_or_create(
            user=user,
            defaults={'role': role, 'faculty': faculty, 'department': department},
        )

        is_admin = role == 'admin'
        User.objects.filter(pk=user.pk).update(
            is_superuser=is_admin,
            is_staff=True,
        )

        perms = RoleManager.get_role_permissions(role) if not is_admin else []
        user.user_permissions.set(perms)  # ✅ set() вместо clear()+add()


class CustomPermissions:
    """Контекстные проверки прав."""
    @staticmethod
    def _get_profile(user: User):  # ✅ метод теперь существует
        return getattr(user, 'profile', None)

    @classmethod
    def can_view_faculty_report(cls, user: User, faculty) -> bool:
        profile = cls._get_profile(user)
        if not profile:
            return False
        return (
            profile.role == 'admin'
            or (profile.role == 'dean' and profile.faculty == faculty)
            or (profile.role == 'head' and profile.department.faculty == faculty)
        )

    @classmethod
    def can_approve_workload(cls, user: User, workload) -> bool:
        profile = cls._get_profile(user)
        if not profile:
            return False
        dept = workload.teacher.department
        return (
            profile.role == 'admin'
            or (profile.role == 'dean' and profile.faculty == dept.faculty)
            or (profile.role == 'head' and profile.department == dept)
        )

    @classmethod
    def can_export_report(cls, user: User) -> bool:
        profile = cls._get_profile(user)  # ✅ баг исправлен
        return profile is not None and profile.role in {'admin', 'dean', 'head', 'planner'}


# ✅ Декоратор для проверки ролей
def role_required(*allowed_roles):
    """
    Декоратор для проверки роли пользователя.
    Использование: @role_required('admin', 'dean')
    """
    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def wrapper(request, *args, **kwargs):
            profile = getattr(request.user, 'profile', None)
            if not profile:
                return HttpResponseForbidden("Профиль пользователя не найден")
            
            if profile.role not in allowed_roles:
                return HttpResponseForbidden(f"Доступ запрещён. Требуемые роли: {', '.join(allowed_roles)}")
            
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


def get_user_profile(user: User):
    """Получить профиль пользователя или None."""
    return getattr(user, 'profile', None)


def user_has_role(user: User, role: str) -> bool:
    """Проверить, имеет ли пользователь определённую роль."""
    profile = get_user_profile(user)
    return profile is not None and profile.role == role


def user_has_any_role(user: User, *roles: str) -> bool:
    """Проверить, имеет ли пользователь одну из указанных ролей."""
    profile = get_user_profile(user)
    return profile is not None and profile.role in roles


# ✅ Миксин для CBV с проверкой ролей
class RoleRequiredMixin:
    """
    Миксин для Class-Based Views, требующих определённую роль пользователя.
    Использование:
        class MyView(RoleRequiredMixin, ListView):
            required_roles = ('admin', 'dean')
            model = MyModel
    """
    required_roles = ('admin',)
    
    def dispatch(self, request, *args, **kwargs):
        from django.http import HttpResponseForbidden
        
        profile = get_user_profile(request.user)
        if not profile or profile.role not in self.required_roles:
            return HttpResponseForbidden(f"Доступ запрещён. Требуемые роли: {', '.join(self.required_roles)}")
        
        return super().dispatch(request, *args, **kwargs)


# ✅ Миксин для выбора base-шаблона по роли
class RoleBasedTemplateMixin:
    """
    Миксин для автоматического выбора base.html в зависимости от роли пользователя.
    Переопределяет get_template_names() для выбора правильного base-шаблона.
    """
    role_based_base_templates = {
        'admin': 'hours_distribution/base_admin.html',
        'dean': 'hours_distribution/base_dean.html',
        'head': 'hours_distribution/base_head.html',
        'teacher': 'hours_distribution/base_teacher.html',
        'planner': 'hours_distribution/base_planner.html',
    }
    
    def get_template_names(self):
        """Получить имя шаблона с учетом роли пользователя"""
        profile = get_user_profile(self.request.user)
        if not profile:
            return super().get_template_names()
        
        # Если шаблон уже переопределён в подклассе, используем его
        templates = super().get_template_names() if hasattr(super(), 'get_template_names') else []
        
        # Добавляем версию с расширением по ролям если есть
        if isinstance(templates, list) and templates:
            base_template = templates[0]
            role = profile.role
            
            # Проверяем есть ли версия для конкретной роли
            if role in self.role_based_base_templates:
                role_template = base_template.replace('index.html', f'index_{role}.html')
                return [role_template] + templates
        
        return templates