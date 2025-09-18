import sqlite3

DB = 'db.sqlite3'

conn = sqlite3.connect(DB)
c = conn.cursor()

# Dodaj novu kolonu 'round' ako već ne postoji
try:
    c.execute("ALTER TABLE events ADD COLUMN round INTEGER")
    print("Kolona 'round' je dodana.")
except sqlite3.OperationalError as e:
    # Ako je već dodana, dobit ćeš grešku, možeš je ignorirati
    if "duplicate column name" in str(e):
        print("Kolona 'round' već postoji.")
    else:
        print("Greška:", e)

conn.commit()
conn.close()
