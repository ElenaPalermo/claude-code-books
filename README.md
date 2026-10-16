# Книжная полка

Небольшой книжный блог: список книг, страницы с отзывами и оценками, добавление и редактирование записей. Сайт рендерится на сервере, интерфейс на русском языке.

## Технологии

- [FastAPI](https://fastapi.tiangolo.com/) + Uvicorn
- Шаблоны Jinja2
- SQLite через стандартный модуль `sqlite3` (без ORM)
- Вход через Google (Authlib), сессия в подписанной cookie
- Чистый CSS с тёмной темой через `prefers-color-scheme`

## Возможности

- Читать список книг и страницы книг может любой посетитель.
- Добавлять, редактировать и удалять книги можно только после входа через Google.
- Обложки рисуются CSS-градиентами, цвет зависит от id книги.
- При первом запуске база заполняется примерами книг.

## Запуск

Нужен Python 3.10+. Команды для Windows / PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env   # затем заполните значения
.\.venv\Scripts\python.exe main.py
```

Сайт откроется на http://127.0.0.1:8000.

## Настройка `.env`

| Переменная | Назначение |
|---|---|
| `GOOGLE_CLIENT_ID` | OAuth Client ID из Google Cloud Console |
| `GOOGLE_CLIENT_SECRET` | OAuth Client Secret |
| `SESSION_SECRET` | Длинная случайная строка для подписи cookie сессии |

В Google Cloud Console укажите redirect URI `http://127.0.0.1:8000/auth/google/callback`.
Без ключей Google сайт тоже работает, но только на чтение.

## Структура

```
main.py          маршруты, валидация форм, настройка Jinja
database.py      все SQL-запросы, создание и наполнение базы
templates/       шаблоны страниц (base.html — общий макет)
static/css/      стили
```

Файл `books.db` создаётся автоматически. Миграций нет: после изменения схемы удалите `books.db`, и база создастся заново.
