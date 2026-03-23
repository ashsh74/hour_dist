from django.core.management.base import BaseCommand
from django.utils import timezone
from hours_distribution.models import *
from hours_distribution.utils.planning_utils import PlanningAssistant

class Command(BaseCommand):
    help = 'Генерация планов на следующий учебный год для всех кафедр'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--department',
            type=int,
            help='ID кафедры для генерации плана (если не указано - для всех кафедр)'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Перезаписать существующие планы'
        )
    
    def handle(self, *args, **options):
        # Получаем текущий учебный год
        current_year = AcademicYear.objects.filter(is_current=True).first()
        if not current_year:
            self.stdout.write(self.style.ERROR('Текущий учебный год не установлен'))
            return
        
        # Создаем или получаем следующий учебный год
        next_year, created = AcademicYear.objects.get_or_create(
            start_year=current_year.start_year + 1,
            end_year=current_year.end_year + 1,
            defaults={
                'name': f'{current_year.start_year + 1}-{current_year.end_year + 1}',
                'is_planned': True
            }
        )
        
        if created:
            self.stdout.write(self.style.SUCCESS(f'Создан учебный год: {next_year}'))
        
        # Определяем кафедры для обработки
        if options['department']:
            departments = Department.objects.filter(id=options['department'])
        else:
            departments = Department.objects.all()
        
        total_departments = departments.count()
        processed = 0
        created_plans = 0
        updated_plans = 0
        
        for department in departments:
            processed += 1
            
            # Проверяем существующий план
            existing_plan = NextYearPlan.objects.filter(
                department=department,
                academic_year=next_year
            ).first()
            
            if existing_plan and not options['force']:
                self.stdout.write(
                    f'{processed}/{total_departments}: План для кафедры {department.name} уже существует'
                )
                continue
            
            try:
                # Генерируем план
                plan = PlanningAssistant.generate_next_year_plan(
                    current_year, next_year, department
                )
                
                if existing_plan:
                    updated_plans += 1
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'{processed}/{total_departments}: План для кафедры {department.name} обновлен'
                        )
                    )
                else:
                    created_plans += 1
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'{processed}/{total_departments}: План для кафедры {department.name} создан'
                        )
                    )
                
                # Валидируем план
                validation = PlanningAssistant.validate_department_plan(plan)
                if validation.get('issues'):
                    self.stdout.write(
                        self.style.WARNING(
                            f'  Предупреждения: {len(validation["issues"])} проблем обнаружено'
                        )
                    )
                    
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(
                        f'{processed}/{total_departments}: Ошибка для кафедры {department.name}: {str(e)}'
                    )
                )
        
        # Сводная статистика
        self.stdout.write('\n' + '='*50)
        self.stdout.write(self.style.SUCCESS('Сводка:'))
        self.stdout.write(f'Обработано кафедр: {processed}')
        self.stdout.write(f'Создано планов: {created_plans}')
        self.stdout.write(f'Обновлено планов: {updated_plans}')
        
        if created_plans + updated_plans > 0:
            self.stdout.write(self.style.SUCCESS(
                f'\nПланы доступны для просмотра в интерфейсе планирования'
            ))