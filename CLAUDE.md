# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

Book blog ("Книжная полка") — a server-rendered FastAPI app with Jinja2 templates and a SQLite database accessed via the stdlib `sqlite3` module (no ORM). UI text is in Russian.

## Commands

Environment is Windows / PowerShell; dependencies live in `.venv`.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt

# Run dev server (http://127.0.0.1:8000, auto-reload)
.\.venv\Scripts\python.exe main.py
```

There is no test suite or linter configured. For quick checks, use `fastapi.testclient.TestClient(app)` inside a `with` block — the block is required so the lifespan hook runs `init_db()`.

Configuration comes from `.env` (template: `.env.example`), loaded by `python-dotenv` at import time: `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `SESSION_SECRET`. Without Google keys the app still runs, but `/login` shows a "not configured" notice and nobody can edit.

## Architecture

- `database.py` — every SQL statement lives here. `get_conn()` is a context manager that commits on exit. `init_db()` creates the `books` table and seeds `SEED_BOOKS` only when the table is empty. `FIELDS` is the single list of editable columns: insert and update SQL are built from it, so a new column has to be added to `FIELDS`, the `CREATE TABLE`, `validate()` in `main.py` and the form in `edit.html`.
- `books.db` is created next to `database.py` on first startup. There are no migrations; after a schema change, delete `books.db` and it will be recreated and reseeded.
- `main.py` — routes, form validation, Jinja setup.
  - Forms use classic POST plus redirect (303) to `/books/{id}?saved=1`, which shows a toast on the book page.
  - When validation fails, `edit.html` is rendered again with an `errors` dict and HTTP 400.
  - The same `edit.html` serves create and edit: `book.id is None` means "new".
  - A custom `ru_date` Jinja filter formats the `created_at` and `updated_at` timestamps.
  - 404s render `templates/404.html` through an exception handler.
- Auth: Google sign-in only, through Authlib (`/login`, `/auth/google`, `/auth/google/callback`, `POST /logout`).
  - The first sign-in creates a row in the `users` table (`db.upsert_user`, keyed by Google `sub`).
  - The session is a signed cookie (Starlette `SessionMiddleware`) holding `user_id`.
  - `current_user` is injected into every template through a Jinja context processor.
  - Routes that change data take `dependencies=[Depends(require_user)]`. For guests this raises `LoginRequired`, which redirects to `/login?next=...`.
  - `safe_next()` limits redirects to local paths.
  - Reading pages stay public.
- `templates/` — `base.html` holds the layout, including the header nav and the footer nav (`.footer-nav`). **Every new page must get a link in the footer nav.** It also goes in the header nav if it is a primary section (the header hides `.nav-link:first-child` on mobile). The shared macros `cover()` and `stars()` live in `_macros.html`.
- Book covers are not images: they are CSS gradients whose hue comes from `book.id` (`--hue` custom property, `.cover` in `static/css/style.css`).
- Styles live in `static/css/style.css`, with color tokens defined on `:root` and a dark theme via `prefers-color-scheme`.
