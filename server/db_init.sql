CREATE TABLE IF NOT EXISTS accounts (
    account   TEXT PRIMARY KEY,
    password  TEXT NOT NULL,
    created_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS characters (
    char_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    account   TEXT NOT NULL,
    char_name TEXT NOT NULL UNIQUE,
    level     INTEGER NOT NULL DEFAULT 1,
    created_at REAL NOT NULL,
    FOREIGN KEY (account) REFERENCES accounts(account)
);
