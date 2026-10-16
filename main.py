import os
import secrets
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

from authlib.integrations.starlette_client import OAuth, OAuthError
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

import database as db

BASE_DIR = Path(__file__).parent
load_dotenv(BASE_DIR / ".env")

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "").strip()
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "").strip()
GOOGLE_ENABLED = bool(GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET)
# Without a fixed secret every restart logs everyone out — fine for a first run.
SESSION_SECRET = os.getenv("SESSION_SECRET", "").strip() or secrets.token_hex(32)

MONTHS = [
    "января", "февраля", "марта", "апреля", "мая", "июня",
    "июля", "августа", "сентября", "октября", "ноября", "декабря",
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    yield


app = FastAPI(title="Книжная полка", lifespan=lifespan)
app.add_middleware(SessionMiddleware, secret_key=SESSION_SECRET, same_site="lax", https_only=False)
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")

oauth = OAuth()
if GOOGLE_ENABLED:
    oauth.register(
        "google",
        client_id=GOOGLE_CLIENT_ID,
        client_secret=GOOGLE_CLIENT_SECRET,
        server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
        client_kwargs={"scope": "openid email profile"},
    )


def current_user(request: Request):
    user_id = request.session.get("user_id")
    if user_id is None:
        return None
    user = db.get_user(user_id)
    if user is None:
        request.session.clear()
    return user


class LoginRequired(Exception):
    def __init__(self, next_url: str):
        self.next_url = next_url


def require_user(request: Request):
    user = current_user(request)
    if user is None:
        path = request.url.path
        if request.method != "GET":
            # После входа возвращаемся на страницу, а не на адрес POST-обработчика.
            path = path.removesuffix("/delete")
        raise LoginRequired(path)
    return user


def safe_next(url: str | None) -> str:
    """Only local paths — never redirect to another site after login."""
    if url and url.startswith("/") and not url.startswith(("//", "/\\")):
        return url
    return "/"


templates = Jinja2Templates(
    directory=BASE_DIR / "templates",
    context_processors=[lambda request: {"current_user": current_user(request)}],
)


def ru_date(value: str) -> str:
    dt = datetime.fromisoformat(value)
    return f"{dt.day} {MONTHS[dt.month - 1]} {dt.year}"


templates.env.filters["ru_date"] = ru_date


def get_book_or_404(book_id: int):
    book = db.get_book(book_id)
    if book is None:
        raise HTTPException(status_code=404, detail="Книга не найдена")
    return book


def validate(title: str, author: str, year: str, genre: str, rating: str, description: str):
    data = {
        "title": title.strip(),
        "author": author.strip(),
        "genre": genre.strip(),
        "description": description.strip(),
        "year": None,
        "rating": 0,
    }
    errors: dict[str, str] = {}

    if not data["title"]:
        errors["title"] = "Укажите название книги"
    if not data["author"]:
        errors["author"] = "Укажите автора"

    if year.strip():
        try:
            data["year"] = int(year)
            if not -3000 <= data["year"] <= datetime.now().year + 1:
                raise ValueError
        except ValueError:
            errors["year"] = "Некорректный год"

    try:
        data["rating"] = max(0, min(5, int(rating or 0)))
    except ValueError:
        errors["rating"] = "Оценка должна быть от 0 до 5"

    return data, errors


def render_form(request: Request, book: dict, errors: dict | None = None, status_code: int = 200):
    return templates.TemplateResponse(
        request,
        "edit.html",
        {"book": book, "errors": errors or {}, "genres": db.list_genres()},
        status_code=status_code,
    )


@app.get("/", response_class=HTMLResponse)
def index(request: Request, q: str = "", genre: str = ""):
    books = db.list_books(q.strip(), genre)
    return templates.TemplateResponse(
        request,
        "index.html",
        {"books": books, "genres": db.list_genres(), "q": q, "genre": genre},
    )


@app.get("/about", response_class=HTMLResponse)
def about(request: Request):
    return templates.TemplateResponse(request, "about.html", {"stats": db.get_stats()})


@app.get("/login", response_class=HTMLResponse)
def login(request: Request, next: str = "/", error: bool = False):
    if current_user(request):
        return RedirectResponse(safe_next(next), status_code=303)
    return templates.TemplateResponse(
        request,
        "login.html",
        {"next": safe_next(next), "error": error, "google_enabled": GOOGLE_ENABLED},
    )


@app.get("/auth/google")
async def auth_google(request: Request, next: str = "/"):
    if not GOOGLE_ENABLED:
        return RedirectResponse("/login", status_code=303)
    request.session["next"] = safe_next(next)
    redirect_uri = request.url_for("auth_google_callback")
    return await oauth.google.authorize_redirect(request, redirect_uri)


@app.get("/auth/google/callback")
async def auth_google_callback(request: Request):
    if not GOOGLE_ENABLED:
        return RedirectResponse("/login", status_code=303)
    try:
        token = await oauth.google.authorize_access_token(request)
    except OAuthError:
        return RedirectResponse("/login?error=1", status_code=303)
    info = token.get("userinfo") or {}
    if not info.get("sub"):
        return RedirectResponse("/login?error=1", status_code=303)
    user_id = db.upsert_user(
        info["sub"],
        info.get("email", ""),
        info.get("name") or info.get("email", ""),
        info.get("picture", ""),
    )
    next_url = safe_next(request.session.pop("next", "/"))
    request.session["user_id"] = user_id
    return RedirectResponse(next_url, status_code=303)


@app.post("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/", status_code=303)


@app.get("/books/new", response_class=HTMLResponse, dependencies=[Depends(require_user)])
def new_book_form(request: Request):
    return render_form(request, {"id": None})


@app.post("/books/new", dependencies=[Depends(require_user)])
def create_book(
    request: Request,
    title: str = Form(""),
    author: str = Form(""),
    year: str = Form(""),
    genre: str = Form(""),
    rating: str = Form("0"),
    description: str = Form(""),
):
    data, errors = validate(title, author, year, genre, rating, description)
    if errors:
        return render_form(request, {"id": None, **data, "year": year}, errors, 400)
    book_id = db.create_book(data)
    return RedirectResponse(f"/books/{book_id}?saved=1", status_code=303)


@app.get("/books/{book_id:int}", response_class=HTMLResponse)
def view_book(request: Request, book_id: int, saved: bool = False):
    book = get_book_or_404(book_id)
    return templates.TemplateResponse(request, "book.html", {"book": book, "saved": saved})


@app.get("/books/{book_id:int}/edit", response_class=HTMLResponse, dependencies=[Depends(require_user)])
def edit_book_form(request: Request, book_id: int):
    return render_form(request, dict(get_book_or_404(book_id)))


@app.post("/books/{book_id:int}/edit", dependencies=[Depends(require_user)])
def update_book(
    request: Request,
    book_id: int,
    title: str = Form(""),
    author: str = Form(""),
    year: str = Form(""),
    genre: str = Form(""),
    rating: str = Form("0"),
    description: str = Form(""),
):
    get_book_or_404(book_id)
    data, errors = validate(title, author, year, genre, rating, description)
    if errors:
        return render_form(request, {"id": book_id, **data, "year": year}, errors, 400)
    db.update_book(book_id, data)
    return RedirectResponse(f"/books/{book_id}?saved=1", status_code=303)


@app.post("/books/{book_id:int}/delete", dependencies=[Depends(require_user)])
def delete_book(book_id: int):
    get_book_or_404(book_id)
    db.delete_book(book_id)
    return RedirectResponse("/", status_code=303)


@app.exception_handler(LoginRequired)
async def login_required(request: Request, exc: LoginRequired):
    return RedirectResponse(f"/login?next={quote(exc.next_url)}", status_code=303)


@app.exception_handler(404)
async def not_found(request: Request, exc):
    return templates.TemplateResponse(request, "404.html", status_code=404)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
