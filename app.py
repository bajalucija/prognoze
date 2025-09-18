import os
import sqlite3
from flask import Flask, render_template, request, redirect
from datetime import datetime

app = Flask(__name__)
DB = os.environ.get("DATABASE_URL", "db.sqlite3")

def init_db():
    if not os.path.exists(DB):
        with sqlite3.connect(DB) as conn:
            c = conn.cursor()
            with open('init.sql', 'r') as f:
                c.executescript(f.read())
            print("✅ Baza inicijalizirana.")

init_db()


# Pomoćna funkcija za normalizaciju predikcija i rezultata (1, X, 2)
def normalize(s):
    return s.strip().upper() if s else ''

@app.route('/')
def index():
    now = datetime.now()

    with sqlite3.connect(DB) as conn:
        c = conn.cursor()
        # Dohvati sve evente s deadline u budućnosti
        c.execute('SELECT round, id, home, away, deadline FROM events')
        svi_eventi = c.fetchall()

    # Filter događaja koji su još aktivni (deadline u budućnosti)
    aktivni_eventi = []
    aktivna_kola = set()

    for round_, eid, home, away, deadline_str in svi_eventi:
        if deadline_str:
            try:
                deadline_dt = datetime.strptime(deadline_str, '%Y-%m-%d %H:%M')
                if deadline_dt > now:
                    aktivni_eventi.append((round_, eid, home, away, deadline_dt))
                    aktivna_kola.add(round_)
            except ValueError:
                pass

    if not aktivni_eventi:
        # Nema aktivnih događaja => nema kola za prikaz
        return render_template('index.html', events=[], round_num=None)

    # Odaberi najmanje kolo koje je aktivno (najranije)
    aktivno_kolo = min(aktivna_kola)

    # Uzmi samo događaje iz tog aktivnog kola
    dostupni_parovi = [
        (eid, home, away) 
        for round_, eid, home, away, dl in aktivni_eventi 
        if round_ == aktivno_kolo
    ]

    return render_template('index.html', events=dostupni_parovi, round_num=aktivno_kolo)

@app.route('/submit', methods=['POST'])
def submit():
    username = request.form.get('username', '').strip()
    if not username:
        return "Morate unijeti nadimak", 400

    try:
        round_num = int(request.form.get('round'))
    except (TypeError, ValueError):
        return "Neispravan broj kola", 400

    now = datetime.now()

    with sqlite3.connect(DB) as conn:
        c = conn.cursor()
        c.execute("SELECT id, deadline FROM events WHERE round = ? ORDER BY id ASC", (round_num,))
        rows = c.fetchall()

        for event_id, deadline in rows:
            if deadline:
                try:
                    deadline_dt = datetime.strptime(deadline, '%Y-%m-%d %H:%M')
                    if deadline_dt < now:
                        continue  # Preskoči ako je rok prošao
                except ValueError:
                    continue  # Ako je deadline neispravan format, preskoči

            pred = request.form.get(f'prediction_{event_id}')
            if pred:
                try:
                    c.execute("""
                        INSERT INTO predictions (username, event_id, prediction)
                        VALUES (?, ?, ?)
                    """, (username, event_id, pred))
                except sqlite3.IntegrityError:
                    c.execute("""
                        UPDATE predictions SET prediction = ?
                        WHERE username = ? AND event_id = ?
                    """, (pred, username, event_id))
        conn.commit()

    return redirect(f'/?round={round_num}')

@app.route('/admin', methods=['GET', 'POST'])
def admin():
    parovi = [{} for _ in range(10)]
    round_num = None
    deadline = ''
    rezultati = [''] * 10

    if request.method == 'POST':
        form_type = request.form.get('form_type')

        if form_type == 'events':
            round_num = int(request.form.get('round'))
            deadline = request.form.get('deadline')
            if deadline:
                deadline = deadline.replace('T', ' ')

            with sqlite3.connect(DB) as conn:
                c = conn.cursor()
                c.execute("SELECT id FROM events WHERE round = ? ORDER BY id ASC", (round_num,))
                existing_ids = [row[0] for row in c.fetchall()]

                for i in range(1, 11):
                    home = request.form.get(f'home_{i}')
                    away = request.form.get(f'away_{i}')
                    if home and away:
                        if i <= len(existing_ids):
                            c.execute("""
                                UPDATE events SET home = ?, away = ?, deadline = ?
                                WHERE id = ?
                            """, (home, away, deadline, existing_ids[i - 1]))
                        else:
                            c.execute("""
                                INSERT INTO events (home, away, deadline, round)
                                VALUES (?, ?, ?, ?)
                            """, (home, away, deadline, round_num))
                conn.commit()
            return redirect(f'/admin?round={round_num}')

        elif form_type == 'results':
            round_num = int(request.form.get('round'))
            with sqlite3.connect(DB) as conn:
                c = conn.cursor()
                c.execute("SELECT id FROM events WHERE round = ? ORDER BY id ASC", (round_num,))
                event_ids = c.fetchall()
                for idx, (event_id,) in enumerate(event_ids):
                    result = request.form.get(f'result_{idx + 1}')
                    if result:
                        c.execute("UPDATE events SET result = ? WHERE id = ?", (result.strip().upper(), event_id))
                conn.commit()
            return redirect(f'/admin?round={round_num}')

    # GET
    round_param = request.args.get('round')
    if round_param:
        try:
            round_num = int(round_param)
            with sqlite3.connect(DB) as conn:
                c = conn.cursor()
                c.execute("SELECT home, away, deadline, result FROM events WHERE round = ? ORDER BY id ASC", (round_num,))
                rows = c.fetchall()
                if rows:
                    parovi = []
                    for i, row in enumerate(rows):
                        parovi.append({'home': row[0], 'away': row[1]})
                        deadline = row[2]
                        rezultati[i] = row[3] if row[3] else ''
        except ValueError:
            pass

    return render_template('admin.html', parovi=parovi, round_num=round_num, deadline=deadline, rezultati=rezultati)

@app.route('/pregled')
def pregled():
    with sqlite3.connect(DB) as conn:
        c = conn.cursor()
        c.execute('''
            SELECT p.username, e.round, e.home, e.away, p.prediction
            FROM predictions p
            JOIN events e ON p.event_id = e.id
            ORDER BY p.username, e.round, e.id
        ''')
        podaci = c.fetchall()

    return render_template('pregled.html', podaci=podaci)

@app.route('/rezultati_po_kolima')
def rezultati_po_kolima():
    with sqlite3.connect(DB) as conn:
        c = conn.cursor()
        c.execute("""
            SELECT round, home, away, result
            FROM events
            WHERE result IS NOT NULL AND result != ''
            ORDER BY round DESC, id ASC
        """)
        podaci = c.fetchall()

    # Grupiraj po kolima (round)
    rezultati = {}
    for round_num, home, away, result in podaci:
        if round_num not in rezultati:
            rezultati[round_num] = []
        prikaz = f"{home} - {away} : {result}"
        rezultati[round_num].append(prikaz)

    return render_template("rezultati_po_kolima.html", rezultati=rezultati)


@app.route('/leaderboard')
def leaderboard():
    def normalize(s):
        return s.strip().upper() if s else ''

    with sqlite3.connect(DB) as conn:
        c = conn.cursor()
        # Dohvati sve različite brojeve kola
        c.execute("SELECT DISTINCT round FROM events WHERE result IS NOT NULL AND result != '' ORDER BY round ASC")
        rounds = [row[0] for row in c.fetchall()]

        if not rounds:
            return render_template('leaderboard.html', rounds=[], table=[])

        last_round = rounds[-1]  # Zadnje kolo

        # Dohvati event_id, round i rezultat
        c.execute("SELECT id, round, result FROM events WHERE result IS NOT NULL AND result != ''")
        events = c.fetchall()
        event_id_to_result = {row[0]: row[2] for row in events}
        event_id_to_round = {row[0]: row[1] for row in events}

        # Sve prognoze
        c.execute("SELECT username, event_id, prediction FROM predictions")
        predictions = c.fetchall()

    # Bodovi po korisniku i kolu
    scores = {}
    for username, event_id, prediction in predictions:
        if event_id in event_id_to_result:
            result = event_id_to_result[event_id]
            round_num = event_id_to_round[event_id]
            is_correct = normalize(prediction) == normalize(result)
            if username not in scores:
                scores[username] = {}
            if round_num not in scores[username]:
                scores[username][round_num] = 0
            if is_correct:
                scores[username][round_num] += 1

    # Priprema tablice: [username, kolo1, kolo2, ..., ukupno, last_round_score]
    table = []
    for username in scores.keys():
        red = [username]
        ukupno = 0
        for r in rounds:
            bod = scores[username].get(r, 0)
            red.append(bod)
            ukupno += bod
        red.append(ukupno)
        last_score = scores[username].get(last_round, 0)
        red.append(last_score)  # privremeno dodajemo radi sortiranja
        table.append(red)

    # Sortiraj po broju bodova u zadnjem kolu DESC, pa ukupno DESC
    table.sort(key=lambda x: (-x[-1], -x[-2]))

    # Ukloni privremeni last_round_score iz prikaza
    for red in table:
        red.pop()

    return render_template('leaderboard.html', rounds=rounds, table=table)



if __name__ == '__main__':
    app.run(debug=True)
