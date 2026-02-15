# Використовуємо slim-образ для економії місця на SSD
FROM python:3.11-slim

# Встановлюємо змінні оточення
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Встановлюємо системні залежності для Postgres та перекладів
RUN apt-get update && apt-get install -y \
    libpq-dev \
    gcc \
    gettext \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Встановлюємо Python-залежності
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копіюємо весь проєкт
COPY . .

# Скомпілюємо переклади (у тебе є папка locale)
RUN python manage.py compilemessages

# Запуск через Gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "warehouse_project_v2.wsgi:application"]