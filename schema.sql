-- Signal Stack Relational Database Schema (SQLite 3)
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS companies (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    url TEXT NOT NULL,
    profile TEXT NOT NULL DEFAULT '{}',
    context_version INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS profile_answers (
    id INTEGER PRIMARY KEY,
    company_id INTEGER NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    position INTEGER NOT NULL,
    question TEXT NOT NULL,
    answer TEXT NOT NULL DEFAULT '',
    skipped INTEGER NOT NULL DEFAULT 0,
    follow_up TEXT,
    updated_at TEXT NOT NULL,
    UNIQUE(company_id, position)
);

CREATE TABLE IF NOT EXISTS sources (
    id INTEGER PRIMARY KEY,
    company_id INTEGER NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    url TEXT NOT NULL,
    name TEXT NOT NULL,
    category TEXT NOT NULL CHECK(category IN ('Customers','Competitors','Market','Internal')),
    reason TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'discovered' CHECK(status IN ('discovered','approved','rejected')),
    specificity REAL NOT NULL DEFAULT 0,
    recency REAL NOT NULL DEFAULT 0,
    credibility REAL NOT NULL DEFAULT 0,
    relevance REAL NOT NULL DEFAULT 0,
    reliability REAL NOT NULL DEFAULT 0.5,
    health TEXT NOT NULL DEFAULT 'unchecked',
    last_checked TEXT,
    last_success TEXT,
    error TEXT,
    content_hash TEXT,
    stale INTEGER NOT NULL DEFAULT 0,
    context_version INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    UNIQUE(company_id, url)
);

CREATE TABLE IF NOT EXISTS crawl_runs (
    id INTEGER PRIMARY KEY,
    company_id INTEGER NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    source_id INTEGER REFERENCES sources(id) ON DELETE SET NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    status TEXT NOT NULL,
    records INTEGER NOT NULL DEFAULT 0,
    detail TEXT
);

CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY,
    company_id INTEGER NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    source_id INTEGER REFERENCES sources(id) ON DELETE SET NULL,
    url TEXT NOT NULL,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    published_at TEXT,
    discovered_at TEXT NOT NULL,
    previous_id INTEGER REFERENCES documents(id),
    kind TEXT NOT NULL DEFAULT 'web',
    original_name TEXT,
    UNIQUE(company_id, url, content_hash)
);

CREATE TABLE IF NOT EXISTS signals (
    id INTEGER PRIMARY KEY,
    company_id INTEGER NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    category TEXT NOT NULL,
    evidence TEXT NOT NULL,
    interpretation TEXT NOT NULL,
    score REAL NOT NULL,
    factors TEXT NOT NULL,
    reliability REAL NOT NULL,
    evidence_strength REAL NOT NULL,
    strategic_relevance REAL NOT NULL,
    explanation TEXT NOT NULL,
    context_version INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(document_id)
);

CREATE TABLE IF NOT EXISTS briefs (
    id INTEGER PRIMARY KEY,
    company_id INTEGER NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    sections TEXT NOT NULL,
    markdown TEXT NOT NULL,
    context_version INTEGER NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS actions (
    id INTEGER PRIMARY KEY,
    company_id INTEGER NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    signal_id INTEGER REFERENCES signals(id) ON DELETE SET NULL,
    title TEXT NOT NULL,
    owner TEXT NOT NULL DEFAULT '',
    due_date TEXT,
    status TEXT NOT NULL DEFAULT 'open' CHECK(status IN ('open','in_progress','done','dismissed')),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS job_logs (
    id INTEGER PRIMARY KEY,
    company_id INTEGER REFERENCES companies(id) ON DELETE CASCADE,
    kind TEXT NOT NULL,
    status TEXT NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    result TEXT,
    error TEXT
);

CREATE TABLE IF NOT EXISTS settings (
    company_id INTEGER PRIMARY KEY REFERENCES companies(id) ON DELETE CASCADE,
    data TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS llm_cache (
    key TEXT PRIMARY KEY,
    data TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS context_changes (
    id INTEGER PRIMARY KEY,
    company_id INTEGER NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    before_profile TEXT NOT NULL,
    after_profile TEXT NOT NULL,
    diff TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS signals_rank ON signals(company_id, score DESC);
CREATE INDEX IF NOT EXISTS docs_company ON documents(company_id, discovered_at);
