-- Every relation is an explicit, stored fact: this is what makes it a CRIS.

CREATE TABLE IF NOT EXISTS author (
    id      TEXT PRIMARY KEY,
    name    TEXT NOT NULL,
    is_seed INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS journal (
    id   TEXT PRIMARY KEY,
    name TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS paper (
    id         TEXT PRIMARY KEY,
    title      TEXT NOT NULL,
    year       INTEGER,
    doi        TEXT,
    journal_id TEXT REFERENCES journal(id)
);

-- paper <-> author (many to many), with the order of authors
CREATE TABLE IF NOT EXISTS authorship (
    paper_id  TEXT NOT NULL REFERENCES paper(id),
    author_id TEXT NOT NULL REFERENCES author(id),
    position  INTEGER NOT NULL,
    PRIMARY KEY (paper_id, author_id)
);

CREATE TABLE IF NOT EXISTS keyword (
    id   INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE
);

-- paper <-> keyword (many to many)
CREATE TABLE IF NOT EXISTS paper_keyword (
    paper_id   TEXT NOT NULL REFERENCES paper(id),
    keyword_id INTEGER NOT NULL REFERENCES keyword(id),
    PRIMARY KEY (paper_id, keyword_id)
);

-- paper cites paper. cited_id has no foreign key: most cited works are not in this database.
CREATE TABLE IF NOT EXISTS citation (
    paper_id TEXT NOT NULL REFERENCES paper(id),
    cited_id TEXT NOT NULL,
    PRIMARY KEY (paper_id, cited_id)
);
