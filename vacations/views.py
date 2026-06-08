import csv
import io
import json
from datetime import datetime, timedelta

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.utils import timezone
from django.contrib import messages
from django.contrib.auth.views import LoginView

# Импортируем все модели
from .models import VacationRequest, RequestedPeriod, VacationSchedule, ScheduleItem, User, WorkDay
from .services import generate_optimal_schedule
from .forms import CustomUserForm


# 1. МАРШРУТИЗАЦИЯ (DASHBOARD)
@login_required
def dashboard(request):
    if request.user.is_admin():
        return redirect('admin_panel')
    elif request.user.is_hr():
        return redirect('hr_panel')
    else:
        return redirect('employee_panel')


# 2. ПАНЕЛЬ АДМИНИСТРАТОРА (УПРАВЛЕНИЕ ПОЛЬЗОВАТЕЛЯМИ)
@login_required
def admin_panel(request):
    if not request.user.is_admin():
        return HttpResponse("Доступ запрещен", status=403)
    users = User.objects.all().order_by('-date_joined')
    return render(request, 'vacations/admin_panel.html', {'users': users})


@login_required
def user_create(request):
    if not request.user.is_admin():
        return HttpResponse("Доступ запрещен", status=403)
    if request.method == 'POST':
        form = CustomUserForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Пользователь успешно создан!")
            return redirect('admin_panel')
    else:
        form = CustomUserForm()
    return render(request, 'vacations/user_form.html', {'form': form, 'title': 'Создание пользователя'})


@login_required
def user_edit(request, user_id):
    if not request.user.is_admin():
        return HttpResponse("Доступ запрещен", status=403)
    user_obj = get_object_or_404(User, id=user_id)
    if request.method == 'POST':
        form = CustomUserForm(request.POST, instance=user_obj)
        if form.is_valid():
            form.save()
            messages.success(request, "Данные пользователя обновлены!")
            return redirect('admin_panel')
    else:
        form = CustomUserForm(instance=user_obj)
    return render(request, 'vacations/user_form.html', {'form': form, 'title': f'Редактирование: {user_obj.username}'})


@login_required
def user_delete(request, user_id):
    if not request.user.is_admin():
        return HttpResponse("Доступ запрещен", status=403)
    user_obj = get_object_or_404(User, id=user_id)
    if user_obj.id == request.user.id:
        messages.error(request, "Вы не можете удалить свой собственный аккаунт!")
    else:
        user_obj.delete()
        messages.success(request, "Пользователь удален.")
    return redirect('admin_panel')


# 3. ПАНЕЛЬ СОТРУДНИКА
@login_required
def employee_panel(request):
    if request.user.role != 'employee':
        return redirect('dashboard')

    tomorrow = (timezone.now().date() + timedelta(days=1))
    existing_request = VacationRequest.objects.filter(user=request.user).first()

    #Обработка подачи заявки
    if request.method == 'POST' and not existing_request:
        s1 = request.POST.get('start_1')
        e1 = request.POST.get('end_1')
        s2 = request.POST.get('start_2')
        e2 = request.POST.get('end_2')

        def get_days(start_str, end_str):
            if not start_str or not end_str: return 0
            start = datetime.strptime(start_str, '%Y-%m-%d').date()
            end = datetime.strptime(end_str, '%Y-%m-%d').date()
            return (end - start).days + 1

        days_p1 = get_days(s1, e1)
        days_p2 = get_days(s2, e2)

        if days_p1 > 28 or days_p2 > 28:
            messages.error(request, "Ошибка: отпуск не может превышать 28 дней.")
            return redirect('employee_panel')

        if days_p1 <= 0:
            messages.error(request, "Ошибка: дата окончания не может быть раньше начала.")
            return redirect('employee_panel')

        new_req = VacationRequest.objects.create(user=request.user, status='submitted')
        RequestedPeriod.objects.create(request=new_req, priority=1, date_start=s1, date_end=e1)
        if s2 and e2:
            RequestedPeriod.objects.create(request=new_req, priority=2, date_start=s2, date_end=e2)

        messages.success(request, "Заявка успешно подана!")
        return redirect('employee_panel')

    #Поиск рекомендованных дат (3 окна по 14 дней)
    recommendations = []
    if not existing_request:
        # 1. Берем опубликованные графики (как было раньше)
        dept_vacs = ScheduleItem.objects.filter(
            user__department=request.user.department,
            schedule__status='published'
        )

        # Ищем периоды, связанные с заявками нашего отдела
        pending_periods = RequestedPeriod.objects.filter(
            request__user__department=request.user.department,
            request__status='submitted'
        )

        curr = tomorrow
        limit_date = curr + timedelta(days=365)

        while len(recommendations) < 3 and curr < limit_date:
            w_start = curr
            w_end = w_start + timedelta(days=13)

            # Проверяем конфликты в графике
            has_conflict_schedule = dept_vacs.filter(
                date_start__lte=w_end,
                date_end__gte=w_start
            ).exists()

            # Проверяем конфликты в поданных заявках
            has_conflict_requests = pending_periods.filter(
                date_start__lte=w_end,
                date_end__gte=w_start
            ).exists()

            if not has_conflict_schedule and not has_conflict_requests:
                recommendations.append({'start': w_start, 'end': w_end})
                curr = w_end + timedelta(days=1)
            else:
                curr += timedelta(days=1)

    #Данные для календаря и график
    my_schedule = ScheduleItem.objects.filter(user=request.user, schedule__status='published').first()
    work_days = list(WorkDay.objects.filter(user=request.user).values_list('date', flat=True))
    work_days_json = json.dumps([d.isoformat() for d in work_days])

    return render(request, 'vacations/employee.html', {
        'req': existing_request,
        'my_schedule': my_schedule,
        'tomorrow': tomorrow.isoformat(),
        'work_days_json': work_days_json,
        'recommendations': recommendations
    })


# 4. ПАНЕЛЬ HR
@login_required
def hr_panel(request):
    if not request.user.is_hr():
        return HttpResponse("Доступ запрещен", status=403)

    # 1. Получаем список всех уникальных отделов для выпадающего списка
    unique_departments = User.objects.filter(role='employee').values_list('department', flat=True).distinct()
    departments_list = [d for d in unique_departments if d]  # Убираем пустые значения, если есть

    if request.method == 'POST':
        action = request.POST.get('action')
        year = int(request.POST.get('year', 2026))

        if action == 'generate':
            min_emp = int(request.POST.get('min_employees', 2))
            selected_dept = request.POST.get('department')

            if selected_dept == 'all':
                for dept in departments_list:
                    generate_optimal_schedule(year, dept, min_employees=min_emp)
                messages.success(request, f"Графики для всех отделов на {year} год успешно сформированы!")

            else:
                generate_optimal_schedule(year, selected_dept, min_employees=min_emp)
                messages.success(request, f"График отпусков для отдела «{selected_dept}» успешно сформирован!")

            return redirect('hr_panel')

        elif action == 'upload_work_schedule':
            user_id = request.POST.get('employee_id')
            file = request.FILES.get('schedule_file')
            if user_id and file:
                emp = get_object_or_404(User, id=user_id)
                try:
                    decoded_file = file.read().decode('utf-8')
                    io_string = io.StringIO(decoded_file)
                    reader = csv.reader(io_string, delimiter=';')
                    next(reader, None)

                    WorkDay.objects.filter(user=emp).delete()
                    work_days_to_create = []
                    for row in reader:
                        if row and row[0].strip():
                            try:
                                date_obj = datetime.strptime(row[0].strip(), '%d.%m.%Y').date()
                                work_days_to_create.append(WorkDay(user=emp, date=date_obj))
                            except ValueError:
                                continue

                    if work_days_to_create:
                        WorkDay.objects.bulk_create(work_days_to_create)
                        messages.success(request, f"График для {emp.username} загружен.")
                    else:
                        messages.warning(request, "Валидных дат не найдено.")
                except Exception as e:
                    messages.error(request, f"Ошибка: {e}")
            return redirect('hr_panel')

        elif action == 'export_csv':
            response = HttpResponse(content_type='text/csv; charset=utf-8')
            response['Content-Disposition'] = f'attachment; filename="vacation_schedule_{year}.csv"'
            response.write('\ufeff'.encode('utf8'))
            writer = csv.writer(response, delimiter=';')
            writer.writerow(['Сотрудник', 'Отдел', 'Начало отпуска', 'Конец отпуска'])
            items = ScheduleItem.objects.filter(schedule__year=year)
            for item in items:
                name = item.user.full_name if item.user.full_name else item.user.username
                writer.writerow([name, item.user.department, item.date_start.strftime('%d.%m.%Y'),
                                 item.date_end.strftime('%d.%m.%Y')])
            return response

    schedules = VacationSchedule.objects.all()
    all_requests = VacationRequest.objects.select_related('user').prefetch_related('periods').order_by('-created_at')
    employees = User.objects.filter(role='employee')

    users_with_requests = VacationRequest.objects.values_list('user_id', flat=True)
    pending_users = User.objects.filter(role='employee').exclude(id__in=users_with_requests)

    return render(request, 'vacations/hr.html', {
        'schedules': schedules,
        'all_requests': all_requests,
        'total_employees': employees.count(),
        'submitted_count': VacationRequest.objects.count(),
        'pending_users': pending_users,
        'users': employees,
        'departments_list': departments_list,
    })


class MyLoginView(LoginView):
    template_name = 'registration/login.html'

    def form_invalid(self, form):
        form.add_error(None, "Неверный логин или пароль")
        return super().form_invalid(form)


@login_required
def cancel_vacation_request(request, request_id):
    vacation_req = get_object_or_404(VacationRequest, id=request_id, user=request.user)

    if vacation_req.status == 'submitted':
        vacation_req.delete()  # Удаляем заявку
        messages.success(request, "Ваша заявка была успешно отменена.")
    else:
        messages.error(request, "Невозможно отменить заявку: она уже находится в обработке или принята.")

    return redirect('employee_panel')