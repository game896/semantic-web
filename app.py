"""A small web interface for the CRIS demo. Uses only the Python standard library.

Run (inside cris/):  python app.py      (or double-click start.bat)
It opens http://127.0.0.1:8001 in the browser. The database is opened read-only.
"""

import html
import re
import sqlite3
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, urlparse

from queries import QUERIES

DB_PATH = Path("data/cris.db")
HOST = "127.0.0.1"
PORT = 8001
LIMIT = 50

STYLE = """
:root { --bg:#fafaf9; --fg:#1c1917; --muted:#78716c; --card:#fff; --line:#e7e5e4; --accent:#3b5bdb; }
@media (prefers-color-scheme: dark) {
  :root { --bg:#171717; --fg:#f5f5f4; --muted:#a8a29e; --card:#232323; --line:#3a3a3a; --accent:#8ea2ff; }
}
* { box-sizing: border-box; }
body { margin:0; background:var(--bg); color:var(--fg); font:16px/1.5 system-ui,sans-serif; }
main { max-width:900px; margin:0 auto; padding:24px 16px 64px; }
a { color:var(--accent); text-decoration:none; } a:hover { text-decoration:underline; }
h1 { font-size:1.5rem; margin:0 0 4px; } h2 { font-size:1.1rem; margin:26px 0 8px; }
.muted { color:var(--muted); font-size:.9rem; }
form { display:flex; gap:8px; margin:16px 0; }
input[type=search] { flex:1; padding:10px 12px; font-size:1rem; border:1px solid var(--line); border-radius:8px;
  background:var(--card); color:var(--fg); }
button { padding:10px 16px; font-size:1rem; border:0; border-radius:8px; background:var(--accent); color:#fff; cursor:pointer; }
table { border-collapse:collapse; width:100%; margin:8px 0; font-size:.93rem; }
th,td { text-align:left; padding:6px 12px 6px 0; border-bottom:1px solid var(--line); vertical-align:top; }
th { color:var(--muted); font-weight:500; }
pre { background:var(--card); border:1px solid var(--line); border-radius:8px; padding:10px 12px; overflow-x:auto;
  font-size:.85rem; white-space:pre-wrap; }
ul { padding-left:20px; }
.badge { border:1px solid var(--line); border-radius:999px; padding:1px 8px; font-size:.8rem; color:var(--muted); }
"""


class Link:
    def __init__(self, text: str, href: str) -> None:
        self.text, self.href = text, href


def cell(value) -> str:
    if isinstance(value, Link):
        return f'<a href="{html.escape(value.href)}">{html.escape(value.text)}</a>'
    return html.escape("" if value is None else str(value))


def table(headers: list[str], rows: list[tuple]) -> str:
    if not rows:
        return '<p class="muted">No rows.</p>'
    head = "".join(f"<th>{html.escape(h)}</th>" for h in headers)
    body = "".join("<tr>" + "".join(f"<td>{cell(v)}</td>" for v in row) + "</tr>" for row in rows)
    return f"<table><tr>{head}</tr>{body}</table>"


def page(title: str, body: str) -> str:
    search = '<form action="/search"><input type="search" name="q" placeholder="Search papers and authors by text"><button>Search</button></form>'
    return (
        f"<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
        f"<title>{html.escape(title)}</title><style>{STYLE}</style></head><body><main>"
        f"<h1><a href='/'>CRIS: mathematical psychology</a></h1>"
        f"<div class='muted'>Every relation is stored in the database and read back exactly.</div>{search}{body}</main></body></html>"
    )


def paper_link(paper_id: str, title: str) -> Link:
    return Link(title, f"/paper/{quote(paper_id)}")


def author_link(author_id: str, name: str) -> Link:
    return Link(name, f"/author/{quote(author_id)}")


def home(db: sqlite3.Connection) -> str:
    counts = [(label, db.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]) for label, t in
              [("Papers", "paper"), ("Authors", "author"), ("Journals", "journal"), ("Keywords", "keyword"),
               ("Authorships", "authorship"), ("Citations", "citation")]]
    queries = "".join(f'<li><a href="/q/{i}">{html.escape(title)}</a></li>' for i, (title, _, _) in enumerate(QUERIES))
    return page("CRIS", f"<h2>What is stored</h2>{table(['Table', 'Rows'], counts)}<h2>Ready-made questions</h2><ul>{queries}</ul>")


def query_page(db: sqlite3.Connection, index: int) -> str | None:
    if not 0 <= index < len(QUERIES):
        return None
    title, sql, params = QUERIES[index]
    cursor = db.execute(sql, params)
    headers = [d[0] for d in cursor.description]
    rows = cursor.fetchall()
    return page(title, f"<h2>{html.escape(title)}</h2><p class='muted'>The question is answered by this SQL query:</p>"
                       f"<pre>{html.escape(' '.join(sql.split()))}</pre>{table(headers, rows)}")


def search_page(db: sqlite3.Connection, q: str) -> str:
    like = f"%{q}%"
    papers = [(paper_link(i, t), y) for i, t, y in db.execute(
        "SELECT id, title, year FROM paper WHERE title LIKE ? ORDER BY year DESC LIMIT ?", (like, LIMIT))]
    authors = [(author_link(i, n), c) for i, n, c in db.execute(
        "SELECT a.id, a.name, COUNT(x.paper_id) FROM author a LEFT JOIN authorship x ON x.author_id = a.id "
        "WHERE a.name LIKE ? GROUP BY a.id ORDER BY 3 DESC LIMIT ?", (like, LIMIT))]
    note = "<p class='muted'>This search only finds the exact text you typed. It does not know that other words can mean the same.</p>"
    return page("Search", f"<h2>Search: {html.escape(q)}</h2>{note}<h2>Papers</h2>{table(['Title', 'Year'], papers)}"
                          f"<h2>Authors</h2>{table(['Name', 'Papers in database'], authors)}")


def author_page(db: sqlite3.Connection, author_id: str) -> str | None:
    row = db.execute("SELECT name, is_seed FROM author WHERE id = ?", (author_id,)).fetchone()
    if row is None:
        return None
    papers = [(y, paper_link(i, t)) for i, t, y in db.execute(
        "SELECT p.id, p.title, p.year FROM paper p JOIN authorship x ON x.paper_id = p.id "
        "WHERE x.author_id = ? ORDER BY p.year DESC", (author_id,))]
    coauthors = [(author_link(i, n), c) for i, n, c in db.execute(
        "SELECT a.id, a.name, COUNT(*) FROM authorship x1 "
        "JOIN authorship x2 ON x1.paper_id = x2.paper_id AND x1.author_id <> x2.author_id "
        "JOIN author a ON a.id = x2.author_id WHERE x1.author_id = ? GROUP BY a.id ORDER BY 3 DESC, a.name LIMIT 15",
        (author_id,))]
    seed = ' <span class="badge">seed author</span>' if row[1] else ""
    return page(row[0], f"<h2>{html.escape(row[0])}{seed}</h2><p class='muted'>{len(papers)} papers in the database</p>"
                        f"<h2>Co-authors (most shared papers)</h2>{table(['Name', 'Shared papers'], coauthors)}"
                        f"<h2>Papers</h2>{table(['Year', 'Title'], papers)}")


def paper_page(db: sqlite3.Connection, paper_id: str) -> str | None:
    row = db.execute("SELECT p.title, p.year, p.doi, j.id, j.name FROM paper p "
                     "LEFT JOIN journal j ON j.id = p.journal_id WHERE p.id = ?", (paper_id,)).fetchone()
    if row is None:
        return None
    title, year, doi, journal_id, journal_name = row
    authors = [(pos + 1, author_link(i, n)) for pos, i, n in db.execute(
        "SELECT x.position, a.id, a.name FROM authorship x JOIN author a ON a.id = x.author_id "
        "WHERE x.paper_id = ? ORDER BY x.position", (paper_id,))]
    keywords = [k for (k,) in db.execute(
        "SELECT k.name FROM paper_keyword pk JOIN keyword k ON k.id = pk.keyword_id WHERE pk.paper_id = ?", (paper_id,))]
    cites = db.execute("SELECT COUNT(*) FROM citation c JOIN paper p ON p.id = c.cited_id WHERE c.paper_id = ?",
                       (paper_id,)).fetchone()[0]
    cited_by = [(y, paper_link(i, t)) for i, t, y in db.execute(
        "SELECT p.id, p.title, p.year FROM citation c JOIN paper p ON p.id = c.paper_id WHERE c.cited_id = ? "
        "ORDER BY p.year DESC LIMIT 20", (paper_id,))]
    doi_html = f'<a href="https://doi.org/{html.escape(quote(doi))}" rel="noopener noreferrer">{html.escape(doi)}</a>' if doi else "none"
    journal_html = f'<a href="/journal/{quote(journal_id)}">{html.escape(journal_name)}</a>' if journal_id else "none"
    facts = (f"<table><tr><th>Year</th><td>{year or ''}</td></tr><tr><th>Journal</th><td>{journal_html}</td></tr>"
             f"<tr><th>DOI</th><td>{doi_html}</td></tr><tr><th>Keywords</th><td>{html.escape('; '.join(keywords))}</td></tr>"
             f"<tr><th>Cites</th><td>{cites} papers in this database</td></tr></table>")
    return page(title, f"<h2>{html.escape(title)}</h2>{facts}<h2>Authors</h2>{table(['#', 'Name'], authors)}"
                       f"<h2>Cited by papers in this database</h2>{table(['Year', 'Title'], cited_by)}")


def journal_page(db: sqlite3.Connection, journal_id: str) -> str | None:
    row = db.execute("SELECT name FROM journal WHERE id = ?", (journal_id,)).fetchone()
    if row is None:
        return None
    papers = [(y, paper_link(i, t)) for i, t, y in db.execute(
        "SELECT id, title, year FROM paper WHERE journal_id = ? ORDER BY year DESC LIMIT ?", (journal_id, LIMIT))]
    return page(row[0], f"<h2>{html.escape(row[0])}</h2><p class='muted'>Papers in this journal (up to {LIMIT})</p>"
                        f"{table(['Year', 'Title'], papers)}")


def route(db: sqlite3.Connection, path: str, query: dict) -> str | None:
    if path == "/":
        return home(db)
    if path == "/search":
        q = (query.get("q") or [""])[0].strip()[:200]
        return search_page(db, q) if q else home(db)
    for pattern, handler in [(r"/q/(\d+)", lambda m: query_page(db, int(m))),
                             (r"/author/([\w-]+)", lambda m: author_page(db, m)),
                             (r"/paper/([\w-]+)", lambda m: paper_page(db, m)),
                             (r"/journal/([\w-]+)", lambda m: journal_page(db, m))]:
        match = re.fullmatch(pattern, path)
        if match:
            return handler(match.group(1))
    return None


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        url = urlparse(self.path)
        db = sqlite3.connect(f"file:{DB_PATH.as_posix()}?mode=ro", uri=True)
        try:
            body = route(db, url.path, parse_qs(url.query))
        finally:
            db.close()
        status = 200 if body is not None else 404
        data = (body or page("Not found", "<h2>Not found</h2><p><a href='/'>Back to the start</a></p>")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args) -> None:  # keep the console quiet
        pass


def create_server(port: int = PORT) -> ThreadingHTTPServer:
    return ThreadingHTTPServer((HOST, port), Handler)


def main() -> int:
    if not DB_PATH.exists():
        print("There is no database yet. Run load.py first.")
        return 1
    server = create_server()
    url = f"http://{HOST}:{PORT}"
    print(f"CRIS is running at {url}  (close this window or press Ctrl+C to stop)")
    threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
