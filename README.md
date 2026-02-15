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

## Аутентификация по токену сайта (JWT RS256)

Бот ожидает, что сайт передаёт токен в deep-link Telegram:

- Формат ссылки: `https://t.me/<bot_username>?start=<payload>`
- Важно: Telegram принимает в `start` только URL-safe payload (`A-Z`, `a-z`, `0-9`, `_`, `-`) длиной до 64 символов.
  Поэтому «сырой» JWT обычно не подходит. Рекомендуемый вариант — передавать JWT в виде base64url payload.
- Бот поддерживает оба варианта: raw JWT (для обратной совместимости) и base64url-encoded payload.
- Алгоритм подписи: `RS256`
- Публичный ключ: `JWT_PUBLIC_KEY` из `.env` (PEM, допускается формат с `\n`)

### Минимальная модель данных payload (JSON)

```json
{
  "sub": "site_user_id",
  "iat": 1730000000,
  "exp": 1730000300,
  "aud": "curling-week-bot"
}
```

Где:

- `sub` — идентификатор пользователя на стороне сайта.
- `iat` — время выпуска токена (Unix timestamp, секунды).
- `exp` — время истечения токена (Unix timestamp, секунды).
- `aud` — аудитория токена, должна быть `curling-week-bot`.

Токен считается невалидным, если:

- отсутствует хотя бы один из обязательных клеймов (`sub`, `iat`, `exp`, `aud`),
- `exp` уже истёк,
- `aud` не совпадает,
- подпись не проходит проверку `RS256` по `JWT_PUBLIC_KEY`.

### Поведение администратора (вход без токена)

Если пользователь входит в список `ADMIN_IDS`, он может запустить `/start` без токена.

- Для администратора это считается разрешённым входом.
- Для обычного пользователя без токена сохраняется стандартный сценарий с регистрацией на сайте.

### Пример `.env`

```env
BOT_TOKEN=replace_with_bot_token
DATABASE_URL=postgresql+asyncpg://curling_user:curling_password@postgres:5432/curling_db
JWT_PUBLIC_KEY="-----BEGIN PUBLIC KEY-----\nMIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAtestkeyreplace\n-----END PUBLIC KEY-----"
ADMIN_IDS=123456789,987654321
REQUIRED_CHANNELS=[{"id":-1001234567890,"title":"Новости","url":"https://t.me/channel1"}]
```
