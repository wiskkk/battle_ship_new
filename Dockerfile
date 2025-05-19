# Базовый образ Python
FROM python:3.12-slim

# Установка зависимостей для сборки
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Создание рабочей директории
WORKDIR /app

# Копирование зависимостей
COPY requirements.txt /app/

# Установка зависимостей
RUN pip install --upgrade pip && pip install -r requirements.txt

# Копирование остальных файлов приложения
COPY . .

# Команда запуска приложения
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]