"""
Context processors для добавления контрольной информации в шаблоны
"""
from .permissions import get_user_profile

def role_context(request):
    """
    Добавляет информацию о роли пользователя и соответствующий base-шаблон в контекст.
    """
    profile = get_user_profile(request.user)
    
    if not profile:
        return {
            'user_role': None,
            'base_template': 'hours_distribution/base.html',
        }
    
    role = profile.role
    base_templates = {
        'admin': 'hours_distribution/base_admin.html',
        'dean': 'hours_distribution/base_dean.html',
        'head': 'hours_distribution/base_head.html',
        'teacher': 'hours_distribution/base_teacher.html',
        'planner': 'hours_distribution/base_planner.html',
    }
    
    return {
        'user_role': role,
        'base_template': base_templates.get(role, 'hours_distribution/base.html'),
        'is_admin': role == 'admin',
        'is_dean': role == 'dean',
        'is_head': role == 'head',
        'is_teacher': role == 'teacher',
        'is_planner': role == 'planner',
    }
