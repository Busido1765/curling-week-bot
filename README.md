# Curling Week Bot

Каркас Telegram-бота проекта «Неделя кёрлинга».

## Требования

- Python 3.11+
- PostgreSQL

## Запуск локально (venv + python)

1. Создайте виртуальное окружение и установите зависимости:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2. Создайте файл `.env` на основе `.env.example` и заполните значения.

3. Примените миграции:

```bash
alembic upgrade head
```

4. Запустите бота:

```bash
python -m bot.main
```

## Запуск через Docker Compose

1. Создайте файл `.env` на основе `.env.example` и заполните значения.
2. Запустите сервисы:

```bash
docker compose up --build
```

Миграции выполняются автоматически при старте сервиса бота.

## Переменные окружения

Список обязательных переменных см. в `.env.example`.
