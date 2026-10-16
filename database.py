import sqlite3
from contextlib import contextmanager
from pathlib import Path

DB_PATH = Path(__file__).parent / "books.db"

FIELDS = ("title", "author", "year", "genre", "rating", "description")

SEED_BOOKS = [
    {
        "title": "Мастер и Маргарита",
        "author": "Михаил Булгаков",
        "year": 1967,
        "genre": "Роман",
        "rating": 5,
        "description": (
            "Весенним вечером на Патриарших прудах появляется таинственный иностранец — "
            "и Москва 1930-х годов уже никогда не будет прежней.\n"
            "Сатира, мистика и история любви, переплетённые с евангельским сюжетом о Понтии Пилате."
        ),
    },
    {
        "title": "1984",
        "author": "Джордж Оруэлл",
        "year": 1949,
        "genre": "Антиутопия",
        "rating": 5,
        "description": (
            "Мир, в котором Старший Брат следит за каждым, а прошлое переписывается ежедневно.\n"
            "Уинстон Смит решается на маленький бунт — вести дневник и думать самостоятельно."
        ),
    },
    {
        "title": "Преступление и наказание",
        "author": "Фёдор Достоевский",
        "year": 1866,
        "genre": "Роман",
        "rating": 4,
        "description": (
            "Бедный студент Родион Раскольников решается проверить свою теорию о «право имеющих».\n"
            "Психологический роман о вине, совести и пути к искуплению."
        ),
    },
    {
        "title": "Маленький принц",
        "author": "Антуан де Сент-Экзюпери",
        "year": 1943,
        "genre": "Сказка",
        "rating": 5,
        "description": (
            "Лётчик, потерпевший крушение в пустыне, встречает мальчика с далёкой планеты.\n"
            "Самое главное глазами не увидишь — зорко одно лишь сердце."
        ),
    },
    {
        "title": "Сто лет одиночества",
        "author": "Габриэль Гарсиа Маркес",
        "year": 1967,
        "genre": "Магический реализм",
        "rating": 4,
        "description": (
            "История семьи Буэндиа и городка Макондо на протяжении ста лет.\n"
            "Чудеса здесь так же обыденны, как дождь, а время ходит по кругу."
        ),
    },
    {
        "title": "Пикник на обочине",
        "author": "Аркадий и Борис Стругацкие",
        "year": 1972,
        "genre": "Фантастика",
        "rating": 5,
        "description": (
            "После визита пришельцев на Земле остались Зоны, полные странных и опасных артефактов.\n"
            "Сталкер Рэдрик Шухарт снова и снова идёт туда, где исполняются желания."
        ),
    },
]


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with get_conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS books (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                title       TEXT    NOT NULL,
                author      TEXT    NOT NULL,
                year        INTEGER,
                genre       TEXT    NOT NULL DEFAULT '',
                rating      INTEGER NOT NULL DEFAULT 0,
                description TEXT    NOT NULL DEFAULT '',
                created_at  TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
                updated_at  TEXT    NOT NULL DEFAULT (datetime('now', 'localtime'))
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                google_sub    TEXT    NOT NULL UNIQUE,
                email         TEXT    NOT NULL DEFAULT '',
                name          TEXT    NOT NULL DEFAULT '',
                picture       TEXT    NOT NULL DEFAULT '',
                created_at    TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
                last_login_at TEXT    NOT NULL DEFAULT (datetime('now', 'localtime'))
            )
            """
        )
        count = conn.execute("SELECT COUNT(*) FROM books").fetchone()[0]
        if count == 0:
            for book in SEED_BOOKS:
                _insert(conn, book)


def _insert(conn: sqlite3.Connection, data: dict) -> int:
    cur = conn.execute(
        f"INSERT INTO books ({', '.join(FIELDS)}) VALUES ({', '.join('?' for _ in FIELDS)})",
        [data[f] for f in FIELDS],
    )
    return cur.lastrowid


def list_books(query: str = "", genre: str = "") -> list[sqlite3.Row]:
    sql = "SELECT * FROM books WHERE 1=1"
    params: list = []
    if query:
        # SQLite's LIKE is case-insensitive only for ASCII, so fold case in Python
        sql += " AND (pyfold(title) LIKE ? OR pyfold(author) LIKE ?)"
        folded = query.casefold()
        params += [f"%{folded}%", f"%{folded}%"]
    if genre:
        sql += " AND genre = ?"
        params.append(genre)
    sql += " ORDER BY updated_at DESC, id DESC"
    with get_conn() as conn:
        conn.create_function("pyfold", 1, str.casefold, deterministic=True)
        return conn.execute(sql, params).fetchall()


def list_genres() -> list[str]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT DISTINCT genre FROM books WHERE genre != '' ORDER BY genre"
        ).fetchall()
    return [r["genre"] for r in rows]


def get_stats() -> dict:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS books, COUNT(DISTINCT author) AS authors, "
            "COUNT(DISTINCT NULLIF(genre, '')) AS genres FROM books"
        ).fetchone()
    return dict(row)


def get_book(book_id: int) -> sqlite3.Row | None:
    with get_conn() as conn:
        return conn.execute("SELECT * FROM books WHERE id = ?", (book_id,)).fetchone()


def create_book(data: dict) -> int:
    with get_conn() as conn:
        return _insert(conn, data)


def update_book(book_id: int, data: dict) -> None:
    with get_conn() as conn:
        conn.execute(
            f"UPDATE books SET {', '.join(f'{f} = ?' for f in FIELDS)}, "
            "updated_at = datetime('now', 'localtime') WHERE id = ?",
            [data[f] for f in FIELDS] + [book_id],
        )


def delete_book(book_id: int) -> None:
    with get_conn() as conn:
        conn.execute("DELETE FROM books WHERE id = ?", (book_id,))


def upsert_user(google_sub: str, email: str, name: str, picture: str) -> int:
    """Create the user on first Google sign-in, refresh profile on later ones."""
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO users (google_sub, email, name, picture) VALUES (?, ?, ?, ?)
            ON CONFLICT(google_sub) DO UPDATE SET
                email = excluded.email,
                name = excluded.name,
                picture = excluded.picture,
                last_login_at = datetime('now', 'localtime')
            """,
            (google_sub, email, name, picture),
        )
        return conn.execute(
            "SELECT id FROM users WHERE google_sub = ?", (google_sub,)
        ).fetchone()[0]


def get_user(user_id: int) -> sqlite3.Row | None:
    with get_conn() as conn:
        return conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
