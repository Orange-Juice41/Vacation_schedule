from django.contrib import admin
from django.urls import path, include
from django.views.generic.base import RedirectView
from vacations.views import MyLoginView
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth import views as auth_views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('vacations.urls')),
    path('accounts/', include('django.contrib.auth.urls')),
    path('accounts/login/', MyLoginView.as_view(), name='login'),
    path('password_reset/', auth_views.PasswordResetView.as_view(
        template_name='registration/reset_form.html',
        email_template_name='registration/password_reset_email.html',
        subject_template_name='registration/password_reset_subject.txt',
        html_email_template_name=None,
        extra_context={
            'title': 'Восстановление доступа',
            'desc': 'Введите ваш email, и мы отправим ссылку для сброса пароля.',
            'btn': 'Выслать письмо'
        }
    ), name='password_reset'),

    path('password_reset/done/', auth_views.PasswordResetDoneView.as_view(
        template_name='registration/reset_message.html',
        extra_context={
            'title': 'Письмо отправлено!',
            'desc': 'Если указанный адрес есть в базе, инструкции придут в течение пары минут. Проверьте консоль сервера!',
            'icon': 'bi-envelope-check text-primary'
        }
    ), name='password_reset_done'),

    path('reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(
        template_name='registration/reset_form.html',
        extra_context={
            'title': 'Придумайте новый пароль',
            'desc': 'Пароль должен быть надежным и не повторять старый.',
            'btn': 'Сохранить новый пароль'
        }
    ), name='password_reset_confirm'),

    path('reset/done/', auth_views.PasswordResetCompleteView.as_view(
        template_name='registration/reset_message.html',
        extra_context={
            'title': 'Пароль успешно изменен',
            'desc': 'Отлично! Теперь вы можете войти в систему, используя новые данные.',
            'icon': 'bi-check-circle-fill text-success'
        }
    ), name='password_reset_complete'),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)