import sqlite3

DB_NAME = 'db.sqlite3'

with sqlite3.connect(DB_NAME) as conn:
    c = conn.cursor()

    # Kreiraj tablicu `events`
    c.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            home TEXT NOT NULL,
            away TEXT NOT NULL,
            deadline TEXT,
            round INTEGER NOT NULL,
            result TEXT
        )
    """)

    # Kreiraj tablicu `predictions`
    c.execute("""
        CREATE TABLE IF NOT EXISTS predictions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            event_id INTEGER NOT NULL,
            prediction TEXT NOT NULL,
            UNIQUE(username, event_id),
            FOREIGN KEY (event_id) REFERENCES events(id)
        )
    """)

    conn.commit()

print("Baza i tablice su uspješno kreirane.")
