from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth.models import User
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.cache import never_cache
from django.http import JsonResponse
from .permissions import RoleManager
from .forms import UserRegistrationForm
import logging

logger = logging.getLogger(__name__)


@csrf_protect
@never_cache
def login_view(request):
    """Вход в систему."""
    if request.user.is_authenticated:
        return redirect('hours_distribution:index')
    
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        remember = request.POST.get('remember', False)
        
        # Аутентификация
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            if user.is_active:
                auth_login(request, user)
                
                # Настройка сессии
                if not remember:
                    request.session.set_expiry(0)  # Сессия до закрытия браузера
                else:
                    request.session.set_expiry(1209600)  # 2 недели
                
                logger.info(f'Успешный вход: {username}')
                
                # Редирект на страницу, с которой пришли, или на главную
                next_url = request.GET.get('next', 'hours_distribution:index')
                return redirect(next_url)
            else:
                messages.error(request, 'Учётная запись отключена.')
        else:
            logger.warning(f'Неудачная попытка входа: {username}')
            messages.error(request, 'Неверное имя пользователя или пароль.')
    
    return render(request, 'hours_distribution/auth/login.html')


@login_required
def logout_view(request):
    """Выход из системы."""
    username = request.user.username
    auth_logout(request)
    logger.info(f'Выход пользователя: {username}')
    messages.success(request, 'Вы успешно вышли из системы.')
    return redirect('hours_distribution:login')


@csrf_protect
def register_view(request):
    """Регистрация нового пользователя (только для админов)."""
    # Проверяем, что регистрацию запускает админ
    if not request.user.is_authenticated or not request.user.is_staff:
        messages.error(request, 'Доступ запрещён.')
        return redirect('hours_distribution:login')
    
    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.set_password(form.cleaned_data['password'])
            user.save()
            
            # Назначаем роль через RoleManager
            role = form.cleaned_data.get('role')
            faculty = form.cleaned_data.get('faculty')
            department = form.cleaned_data.get('department')
            
            RoleManager.assign_role(user, role, faculty, department)
            
            logger.info(f'Новый пользователь зарегистрирован: {user.username} (роль: {role})')
            messages.success(request, f'Пользователь {user.username} создан.')
            return redirect('hours_distribution:index')
    else:
        form = UserRegistrationForm()
    
    return render(request, 'hours_distribution/auth/register.html', {'form': form})


@login_required
def profile_view(request):
    """Профиль пользователя."""
    profile = getattr(request.user, 'profile', None)
    context = {
        'user': request.user,
        'profile': profile,
    }
    return render(request, 'hours_distribution/auth/profile.html', context)


# API endpoint для проверки статуса авторизации
@login_required
def auth_status(request):
    """Возвращает информацию о текущем пользователе."""
    profile = getattr(request.user, 'profile', None)
    return JsonResponse({
        'authenticated': True,
        'username': request.user.username,
        'role': profile.role if profile else None,
        'faculty': profile.faculty.name if profile and profile.faculty else None,
        'department': profile.department.name if profile and profile.department else None,
    })