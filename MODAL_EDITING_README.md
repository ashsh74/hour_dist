# Modal редактирование групп студентов

## Описание

Реализована функция модального редактирования групп студентов без использования админ-панели Django. Это позволяет пользователям редактировать информацию о группах прямо на странице списка групп.

## Новые компоненты

### 1. Views (`views.py`)

Добавлены три новых view функции:

#### `student_group_modal(request, group_id)` - GET запрос
- Загружает форму редактирования группы
- Возвращает JSON с HTML формы для вставки в модальное окно
- Требует авторизации

#### `student_group_update_modal(request, group_id)` - POST запрос
- Обрабатывает сохранение изменений группы
- Возвращает JSON ответ со статусом успешности
- При ошибках возвращает детальные ошибки по полям

#### `student_groups_list(request)`
- Обновлен вид списка групп с поддержкой фильтрации
- Поддерживает поиск по коду и названию
- Фильтрация по курсу и программе
- Пагинация по 15 групп на странице

#### `student_group_detail(request, group_id)`
- Детальная информация о конкретной группе
- Показывает все дисциплины группы

### 2. Forms (`forms.py`)

Добавлена новая форма:

#### `StudentGroupModalForm`
- Форма для модального редактирования
- Редактируемые поля: name, group_type, students_count, max_students, is_active
- Поле code (только для чтения)
- Bootstrap CSS классы для стилизации
- Валидация данных

### 3. URL маршруты (`urls.py`)

Добавлены новые маршруты:
```python
path('groups/students/<int:group_id>/modal/', views.student_group_modal, name='student_group_modal'),
path('groups/students/<int:group_id>/update-modal/', views.student_group_update_modal, name='student_group_update_modal'),
```

### 4. Templates

#### `modals/student_group_modal.html`
- HTML форма в модаль окне
- Показывает информацию о группе (только для чтения)
- Редактируемые поля с валидацией на клиенте
- Обработка AJAX запросов
- Показ ошибок при сохранении
- Свежее отображение после сохранения

#### `groups/student_groups_list.html` (обновлен)
- Добавлена кнопка "Редактировать в модале" (зеленая с иконкой карандаша)
- Модальное окно с id="studentGroupEditModal"
- Подключен JavaScript файл для обработки открытия модали

### 5. Static JavaScript (`static/js/student_group_modal.js`)

#### `openStudentGroupModal(groupId)`
- Открывает модальное окно редактирования
- Загружает форму через AJAX запрос
- Показывает индикатор загрузки

#### `initEditButtons()`
- Инициализирует обработчики для кнопок редактирования
- Вешает обработчики на кнопки с атрибутом `data-edit-group`

### 6. Custom Filters (`templatetags/custom_filters.py`)

Добавлен новый фильтр:

#### `get_percentage`
- Рассчитывает процент от максимального значения
- Используется для показа заполненности группы

## Использование

### Для разработчика

1. Откройте страницу со списком групп: `/groups/students/`
2. Найдите группу которую хотите отредактировать
3. Кликните на зеленую кнопку с карандашом (Редактировать в модале)
4. В модальном окне отредактируйте нужные поля
5. Кликните "Сохранить изменения"
6. При успехе страница автоматически обновится через 1.5 сек

### Для встраивания в свои шаблоны

Если вы хотите добавить кнопку редактирования в свой шаблон:

```html
<button type="button" class="btn btn-outline-success" 
        data-edit-group="{{ group.id }}" 
        title="Редактировать в модале">
    <i class="fas fa-pencil-alt"></i>
</button>

<!-- В конце шаблона добавьте модальное окно: -->
<div class="modal fade" id="studentGroupEditModal" tabindex="-1">
    <div class="modal-dialog modal-lg">
        <div class="modal-content">
            <div class="modal-body">
                <div class="text-center">
                    <div class="spinner-border" role="status"></div>
                    <p class="mt-2">Загрузка...</p>
                </div>
            </div>
        </div>
    </div>
</div>

<!-- Подключите JavaScript: -->
<script src="{% static 'js/student_group_modal.js' %}"></script>
```

## Безопасность

- Все view функции защищены декоратором `@login_required`
- POST запросы обрабатывают CSRF токены
- Форма использует стандартную валидацию Django
- Пользователь может редактировать только разрешенные поля

## API

### GET /groups/students/{id}/modal/
Возвращает JSON:
```json
{
    "success": true,
    "html": "<form>...</form>"
}
```

### POST /groups/students/{id}/update-modal/
Принимает:
- Поля формы StudentGroupModalForm
- CSRF токен

Возвращает при успехе:
```json
{
    "success": true,
    "message": "Группа ABC успешно обновлена",
    "group": {
        "id": 3,
        "code": "ABC",
        "name": "...",
        ...
    }
}
```

Возвращает при ошибке:
```json
{
    "success": false,
    "message": "Ошибка при сохранении данных",
    "errors": {
        "name": "Это поле обязательно",
        ...
    }
}
```

## Примечания

- Форма автоматически скрывает поля, которые нельзя редактировать (code, course, program и т.д.)
- Показывается индикатор заполненности группы
- При ошибках сохранения показываются подробные сообщения об ошибках
- После успешного сохранения модаль закрывается и страница обновляется
