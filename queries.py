"""Demonstration of what a CRIS can answer: every question is an exact SQL query over stored relations.

Run (inside cris/):  python queries.py
"""

import sqlite3
import sys
from pathlib import Path

DB_PATH = Path("data/cris.db")
RATCLIFF = "A5024018318"

# (what is asked, SQL, parameters)
QUERIES: list[tuple[str, str, tuple]] = [
    (
        "1. Papers written by Roger Ratcliff, newest first (relation paper-author)",
        """SELECT p.year, p.title
           FROM paper p JOIN authorship x ON x.paper_id = p.id
           WHERE x.author_id = ?
           ORDER BY p.year DESC LIMIT 8""",
        (RATCLIFF,),
    ),
    (
        "2. Co-authors of Roger Ratcliff and the number of shared papers (the same relation, joined to itself)",
        """SELECT a.name, COUNT(*) AS shared_papers
           FROM authorship x1
           JOIN authorship x2 ON x1.paper_id = x2.paper_id AND x1.author_id <> x2.author_id
           JOIN author a ON a.id = x2.author_id
           WHERE x1.author_id = ?
           GROUP BY a.id ORDER BY shared_papers DESC, a.name LIMIT 8""",
        (RATCLIFF,),
    ),
    (
        "3. Which seed authors have published together, and how often",
        """SELECT a1.name, a2.name, COUNT(*) AS shared_papers
           FROM authorship x1
           JOIN authorship x2 ON x1.paper_id = x2.paper_id AND x1.author_id < x2.author_id
           JOIN author a1 ON a1.id = x1.author_id
           JOIN author a2 ON a2.id = x2.author_id
           WHERE a1.is_seed = 1 AND a2.is_seed = 1
           GROUP BY x1.author_id, x2.author_id
           ORDER BY shared_papers DESC LIMIT 8""",
        (),
    ),
    (
        "4. Journals with the most papers in the database (relation paper-journal)",
        """SELECT j.name, COUNT(*) AS papers
           FROM paper p JOIN journal j ON j.id = p.journal_id
           GROUP BY j.id ORDER BY papers DESC LIMIT 8""",
        (),
    ),
    (
        "5. Number of papers per decade",
        """SELECT (year / 10) * 10 AS decade, COUNT(*) AS papers
           FROM paper WHERE year IS NOT NULL
           GROUP BY decade ORDER BY decade""",
        (),
    ),
    (
        "6. Most frequent keywords (relation paper-keyword)",
        """SELECT k.name, COUNT(*) AS papers
           FROM paper_keyword pk JOIN keyword k ON k.id = pk.keyword_id
           GROUP BY k.id ORDER BY papers DESC LIMIT 8""",
        (),
    ),
    (
        "7. Papers cited most often by other papers in this database (relation citation)",
        """SELECT p.year, p.title, COUNT(*) AS cited_by
           FROM citation c JOIN paper p ON p.id = c.cited_id
           GROUP BY p.id ORDER BY cited_by DESC LIMIT 8""",
        (),
    ),
    (
        "8. LIMIT of a CRIS: papers whose title contains the exact text 'diffusion'",
        "SELECT year, title FROM paper WHERE title LIKE '%diffusion%' ORDER BY year DESC LIMIT 5",
        (),
    ),
    (
        "9. LIMIT of a CRIS: the same idea in other words ('how people accumulate evidence'): nothing is found",
        "SELECT year, title FROM paper WHERE title LIKE '%accumulate evidence%' LIMIT 5",
        (),
    ),
]


def run(conn: sqlite3.Connection, title: str, sql: str, params: tuple) -> None:
    print(f"\n{title}")
    print("   " + " ".join(sql.split()))
    rows = conn.execute(sql, params).fetchall()
    if not rows:
        print("   -> no rows")
    for row in rows:
        print("   -> " + " | ".join(str(v) for v in row))


def main() -> int:
    if not DB_PATH.exists():
        print("No database yet. Run: python load.py")
        return 1
    conn = sqlite3.connect(DB_PATH)
    for title, sql, params in QUERIES:
        run(conn, title, sql, params)
    conn.close()
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
