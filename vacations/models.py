from django.db import models
from django.contrib.auth.models import AbstractUser


class User(AbstractUser):
    ROLE_CHOICES = (
        ('employee', 'Сотрудник'),
        ('hr', 'HR-специалист'),
        ('admin', 'Администратор'),
    )
    full_name = models.CharField(max_length=255, verbose_name="ФИО", blank=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='employee')
    department = models.CharField(max_length=100, default='Общий')

    def __str__(self):
        return self.full_name if self.full_name else self.username

    def is_hr(self):
        return self.role == 'hr'

    def is_admin(self):
        return self.role == 'admin'


class VacationSchedule(models.Model):
    # УБЕРИ параметр unique=True, если он тут есть!
    year = models.IntegerField(verbose_name="Год")

    # Твое поле отдела (название может немного отличаться, используй свое)
    department = models.CharField(max_length=100, verbose_name="Отдел")

    status = models.CharField(max_length=20, default='draft')
    min_employees = models.IntegerField(default=2)


    class Meta:
        # ДОБАВЬ это: теперь база разрешит несколько графиков на 2026 год,
        # но только если у них разные отделы.
        unique_together = ('year', 'department')

    def __str__(self):
        return f"График {self.department} на {self.year} год"

class VacationRequest(models.Model):
    STATUS_CHOICES = (
        ('submitted', 'Submitted'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('included_in_schedule', 'Included in Schedule'),
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='submitted')
    created_at = models.DateTimeField(auto_now_add=True)


class RequestedPeriod(models.Model):
    request = models.ForeignKey(VacationRequest, related_name='periods', on_delete=models.CASCADE)
    priority = models.IntegerField()
    date_start = models.DateField()
    date_end = models.DateField()


class ScheduleItem(models.Model):
    schedule = models.ForeignKey(VacationSchedule, related_name='items', on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    date_start = models.DateField()
    date_end = models.DateField()

class WorkScheduleFile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='work_schedule')
    file = models.FileField(upload_to='work_schedules/')
    uploaded_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"График: {self.user.username}"

class WorkDay(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='work_days')
    date = models.DateField()

    class Meta:
        unique_together = ('user', 'date')