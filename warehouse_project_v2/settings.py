import os
from pathlib import Path
from dotenv import load_dotenv
import dj_database_url
# Додаємо імпорт для перекладу
from django.utils.translation import gettext_lazy as _

load_dotenv()
# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/4.2/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.getenv('SECRET_KEY')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.getenv('DEBUG', 'False') == 'True'

ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS', '127.0.0.1,localhost').split(',')


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # Додаємо наш додаток
    'inventory.apps.InventoryConfig',
    'simple_history',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    # Middleware для визначення мови. Має бути після SessionMiddleware і перед CommonMiddleware.
    'django.middleware.locale.LocaleMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'simple_history.middleware.HistoryRequestMiddleware'
]

ROOT_URLCONF = 'warehouse_project_v2.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'inventory.context_processor.shift_status',
            ],
        },
    },
]

WSGI_APPLICATION = 'warehouse_project_v2.wsgi.application'


# --- Налаштування бази даних ---
# https://docs.djangoproject.com/en/4.2/ref/settings/#databases

# DATABASES = {
#     'default': {
#         'ENGINE': 'django.db.backends.sqlite3',
#         'NAME': BASE_DIR / 'db.sqlite3',
#     }
# }
DATABASES = {
    'default': dj_database_url.config(
        conn_max_age=600, # Опціонально: тримає з'єднання відкритим (прискорює роботу)
        conn_health_checks=True,
    )
}
#--- Кінець налаштувань бази даних ---

#------- Налаштування I18N ---

LANGUAGES = [
    ('uk', _('Українська')),
    ('pl', _('Польська')),
]
LANGUAGE_CODE = 'uk'
TIME_ZONE = 'Europe/Warsaw'
USE_I18N = True
USE_L10N = True
USE_TZ = True
LOCALE_PATHS = [BASE_DIR / 'locale']

# --- Кінець налаштувань I18N ---

#--- Налаштування статичних файлів та медіа ---
STATIC_URL = '/static/'
# STATIC_ROOT = os.path.join(BASE_DIR, 'static')
STATIC_ROOT = BASE_DIR / 'staticfiles'  # Окрема папка для зібраної статики
STATICFILES_DIRS = [BASE_DIR / 'static'] if (BASE_DIR / 'static').exists() else []# Тут лежать твої стилі під час розробки

MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
#--- Кінець налаштувань статичних файлів та медіа ---

# --- Налаштування аутентифікації ---
LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'inventory:product_list'
LOGOUT_REDIRECT_URL = 'login'


