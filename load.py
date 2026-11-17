"""Fill the CRIS database from OpenAlex, once, for the seed authors.

Run (inside cris/):  python load.py

There is no relevance filter and no automatic expansion: a CRIS stores what it is given.
Running it again refreshes the same records.
"""

import sqlite3
import sys
import time
from pathlib import Path

import httpx
import yaml

BASE_URL = "https://api.openalex.org"
DB_PATH = Path("data/cris.db")
SCHEMA_PATH = Path("schema.sql")
SEED_PATH = Path("seed.yaml")

PAGE_SIZE = 200
WORKS_PER_AUTHOR = 200  # most cited first
KEYWORDS_PER_PAPER = 3  # OpenAlex topics are used as keywords
RETRIES = 3
FIELDS = "id,doi,title,publication_year,authorships,primary_location,topics,referenced_works"


def short_id(url: str | None) -> str:
    """OpenAlex ids come as URLs; keep the last part (e.g. W123)."""
    return (url or "").rsplit("/", 1)[-1]


def get(client: httpx.Client, path: str, params: dict) -> dict:
    for attempt in range(1, RETRIES + 1):
        try:
            response = client.get(path, params=params)
            response.raise_for_status()
            return response.json()
        except (httpx.TransportError, httpx.HTTPStatusError) as exc:
            if attempt == RETRIES:
                raise SystemExit(f"OpenAlex request failed after {RETRIES} attempts: {exc}")
            time.sleep(2**attempt)
    raise SystemExit("unreachable")


def works_of(client: httpx.Client, author_id: str) -> list[dict]:
    works: list[dict] = []
    page = 1
    while len(works) < WORKS_PER_AUTHOR:
        data = get(
            client,
            "/works",
            {
                "filter": f"author.id:{author_id}",
                "sort": "cited_by_count:desc",
                "per-page": PAGE_SIZE,
                "page": page,
                "select": FIELDS,
            },
        )
        batch = data.get("results", [])
        if not batch:
            break
        works.extend(batch)
        page += 1
    return works[:WORKS_PER_AUTHOR]


def save_work(conn: sqlite3.Connection, work: dict) -> bool:
    if not work.get("title"):
        return False
    paper_id = short_id(work["id"])

    venue = (work.get("primary_location") or {}).get("source") or {}
    journal_id = short_id(venue.get("id")) or None
    if journal_id:
        conn.execute("INSERT OR IGNORE INTO journal (id, name) VALUES (?, ?)", (journal_id, venue.get("display_name") or ""))

    doi = (work.get("doi") or "").removeprefix("https://doi.org/") or None
    conn.execute(
        "INSERT OR REPLACE INTO paper (id, title, year, doi, journal_id) VALUES (?, ?, ?, ?, ?)",
        (paper_id, work["title"], work.get("publication_year"), doi, journal_id),
    )

    for position, authorship in enumerate(work.get("authorships") or []):
        author = authorship.get("author") or {}
        author_id = short_id(author.get("id"))
        if not author_id:
            continue
        conn.execute("INSERT OR IGNORE INTO author (id, name) VALUES (?, ?)", (author_id, author.get("display_name") or ""))
        conn.execute(
            "INSERT OR IGNORE INTO authorship (paper_id, author_id, position) VALUES (?, ?, ?)",
            (paper_id, author_id, position),
        )

    for topic in (work.get("topics") or [])[:KEYWORDS_PER_PAPER]:
        name = topic.get("display_name")
        if not name:
            continue
        conn.execute("INSERT OR IGNORE INTO keyword (name) VALUES (?)", (name,))
        keyword_id = conn.execute("SELECT id FROM keyword WHERE name = ?", (name,)).fetchone()[0]
        conn.execute("INSERT OR IGNORE INTO paper_keyword (paper_id, keyword_id) VALUES (?, ?)", (paper_id, keyword_id))

    for cited in work.get("referenced_works") or []:
        conn.execute("INSERT OR IGNORE INTO citation (paper_id, cited_id) VALUES (?, ?)", (paper_id, short_id(cited)))
    return True


def main() -> int:
    seed = yaml.safe_load(SEED_PATH.read_text(encoding="utf-8"))
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))

    with httpx.Client(base_url=BASE_URL, timeout=60.0) as client:
        for author in seed["authors"]:
            conn.execute(
                "INSERT INTO author (id, name, is_seed) VALUES (?, ?, 1) "
                "ON CONFLICT(id) DO UPDATE SET is_seed = 1",
                (author["openalex_id"], author["name"]),
            )
            works = works_of(client, author["openalex_id"])
            saved = sum(save_work(conn, w) for w in works)
            conn.commit()
            print(f"{author['name']}: {saved} papers loaded")

    for table in ("paper", "author", "journal", "keyword", "authorship", "paper_keyword", "citation"):
        print(f"{table:14} {conn.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]}")
    conn.close()
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
