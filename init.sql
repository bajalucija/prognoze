CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    home TEXT NOT NULL,
    away TEXT NOT NULL,
    deadline TEXT,
    round INTEGER,
    result TEXT
);

CREATE TABLE IF NOT EXISTS predictions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL,
    event_id INTEGER NOT NULL,
    prediction TEXT NOT NULL,
    UNIQUE(username, event_id),
    FOREIGN KEY(event_id) REFERENCES events(id)
);
