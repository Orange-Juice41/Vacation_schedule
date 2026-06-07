from datetime import timedelta, date
from .models import User, VacationRequest, VacationSchedule, ScheduleItem

RF_HOLIDAYS = [
    (1, 1), (1, 2), (1, 3), (1, 4), (1, 5), (1, 6), (1, 7), (1, 8),
    (2, 23), (3, 8), (5, 1), (5, 9), (6, 12), (11, 4)
]


def is_working_day(check_date):
    # Проверка, является ли день рабочим (не суббота/воскресенье и не праздник)
    if check_date.weekday() >= 5:
        return False
    if (check_date.month, check_date.day) in RF_HOLIDAYS:
        return False
    return True


def generate_optimal_schedule(year, department, min_employees):
    # Генерация графика для конкретного отдела с учетом лимита присутствующих.
    # 1. Находим или создаем объект графика для конкретного года и отдела
    schedule, created = VacationSchedule.objects.get_or_create(
        year=year,
        department=department,
        defaults={'status': 'draft', 'min_employees': min_employees}
    )

    # 2. Если график уже был, очищаем старые записи перед перерасчетом
    if not created:
        schedule.min_employees = min_employees  # Обновляем лимит, если он изменился
        ScheduleItem.objects.filter(schedule=schedule).delete()

    # 3. Фильтруем заявки: только этого отдела и только те, что еще не распределены окончательно
    requests = VacationRequest.objects.filter(
        user__department=department,
        status__in=['submitted', 'included_in_schedule']
    ).prefetch_related('periods')

    # 4. Считаем общее число сотрудников в отделе
    total_employees_in_dept = User.objects.filter(department=department, role='employee').count()

    # 5. Календарь занятости отдела: {дата: кол-во_людей_в_отпуске}
    daily_vacation_counts = {}

    for req in requests:
        periods = req.periods.all().order_by('priority')
        approved_any = False

        for period in periods:
            is_period_possible = True

            current_date = period.date_start
            while current_date <= period.date_end:
                # Сколько людей из этого отдела УЖЕ будут в отпуске в этот день
                already_away = daily_vacation_counts.get(current_date, 0)

                # Сколько останется на работе
                remaining = total_employees_in_dept - already_away - 1

                if remaining < min_employees:
                    is_period_possible = False
                    break

                current_date += timedelta(days=1)

            # 6. Если лимит не нарушен во все дни периода — утверждаем его
            if is_period_possible:
                ScheduleItem.objects.create(
                    schedule=schedule,
                    user=req.user,
                    date_start=period.date_start,
                    date_end=period.date_end
                )

                # Обновляем календарь занятости
                d = period.date_start
                while d <= period.date_end:
                    daily_vacation_counts[d] = daily_vacation_counts.get(d, 0) + 1
                    d += timedelta(days=1)

                req.status = 'included_in_schedule'
                req.save()
                approved_any = True
                break

        # Если ни один из вариантов сотрудника не прошел по лимитам
        if not approved_any:
            req.status = 'submitted'  # Оставляем в статусе "Ожидает", чтобы HR видел проблему
            req.save()

    # 7. Финализируем график
    schedule.status = 'published'
    schedule.save()

    return schedule