"""
URL configuration for warehouse_project_v2 project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
# warehouse_project_v2/urls.py
from django.contrib import admin
from django.urls import path, include
from django.conf.urls.i18n import i18n_patterns
from django.contrib.auth import views as auth_views

# --- URL-адреси БЕЗ мовного префікса ---
# Ці URL-и будуть однакові для всіх мов
urlpatterns = [
    # 1. URL для механізму перемикання мови
    path('i18n/', include('django.conf.urls.i18n')),

    # 2. URL для адмін-панелі (вона має власну систему перекладу)
    path('admin/', admin.site.urls),
]

# --- URL-адреси З мовним префіксом ---
# Django автоматично додасть /uk/ або /pl/ до цих URL-ів
urlpatterns += i18n_patterns(

    # 1. Ваш додаток inventory (тепер це єдиний варіант)
    # Тепер він буде доступний за адресами /uk/ та /pl/
    path('', include('inventory.urls', namespace='inventory')),

    # 2. Сторінки входу та виходу
    # Ми перенесли їх сюди, щоб сторінка входу теж перекладалася
    path('login/', auth_views.LoginView.as_view(
        template_name='registration/login.html'
    ), name='login'),

    path('logout/', auth_views.LogoutView.as_view(), name='logout'),

)