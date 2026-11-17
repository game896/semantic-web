# CRIS demo: mathematical psychology

A small Current Research Information System (CRIS) for the same field as the EMPG case study. Papers, authors, journals, keywords and citations are stored in a relational database (SQLite), and every relation between them is an explicit, stored fact. It is a point of comparison for the embedding-based platform, where relations are not stored but computed as closeness of vectors.

## Running

The environment is created once:

```
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
```

Then two steps, each started by double-clicking a file (or running it from the command line):

1. `load.bat` fetches, from OpenAlex, up to 200 most cited papers of each seed author listed in `seed.yaml` and stores them in `data/cris.db`. This is done once; running it again refreshes the same records.
2. `start.bat` starts the web interface at http://127.0.0.1:8001 and opens it in the browser.

No API key is needed.

## What is stored

The schema is in `schema.sql`. Each kind of thing has its own table, and relations have their own tables:

```
paper          id, title, year, doi, journal_id
author         id, name, is_seed
journal        id, name
keyword        id, name
authorship     paper_id, author_id, position      (who wrote which paper, and in which order)
paper_keyword  paper_id, keyword_id
citation       paper_id, cited_id                 (which paper cites which)
```

Example: the paper "The Diffusion Decision Model" has two rows in `authorship`, one for Roger Ratcliff and one for Gail McKoon. Questions such as "who are Ratcliff's co-authors" are answered exactly by joining these tables.

## What the interface shows

- Ready-made questions with their SQL and results (papers of an author, co-authors, seed authors who published together, largest journals, papers per decade, frequent keywords, most cited papers within the database).
- Text search over paper titles and author names. It matches only the exact text typed and does not know about meaning.
- Pages for each author, paper and journal, linked through the stored relations.

There is no relevance filter and no automatic expansion: the database holds exactly what was loaded, including papers that are outside the field.
