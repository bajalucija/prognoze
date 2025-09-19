from flask import Flask, render_template, request, redirect
import psycopg2
import os
from datetime import datetime

app = Flask(__name__)

DATABASE_URL = os.environ.get("DATABASE_URL")

def get_conn():
    return psycopg2.connect(DATABASE_URL, sslmode='require')

@app.route('/')
def index():
    now = datetime.now()
    with get_conn() as conn:
        with conn.cursor() as c:
            c.execute('SELECT id, home, away, deadline, round FROM events ORDER BY id ASC LIMIT 10')
            events = c.fetchall()

    dostupni_parovi = []
    for eid, home, away, deadline_str, rnd in events:
        if deadline_str:
            try:
                deadline_dt = datetime.strptime(deadline_str, '%Y-%m-%d %H:%M')
                if deadline_dt > now:
                    dostupni_parovi.append((eid, home, away))
            except ValueError:
                pass

    return render_template('index.html', events=dostupni_parovi)

@app.route('/submit', methods=['POST'])
def submit():
    username = request.form.get('username', '').strip()
    if not username:
        return "Morate unijeti nadimak", 400

    with get_conn() as conn:
        with conn.cursor() as c:
            c.execute("SELECT id FROM events ORDER BY id ASC LIMIT 10")
            event_ids = [row[0] for row in c.fetchall()]

            for event_id in event_ids:
                pred = request.form.get(f'prediction_{event_id}')
                if pred:
                    try:
                        c.execute("INSERT INTO predictions (username, event_id, prediction) VALUES (%s, %s, %s)",
                                  (username, event_id, pred))
                    except:
                        c.execute("UPDATE predictions SET prediction = %s WHERE username = %s AND event_id = %s",
                                  (pred, username, event_id))
        conn.commit()

    return redirect('/')

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

            with get_conn() as conn:
                with conn.cursor() as c:
                    c.execute("SELECT id FROM events WHERE round = %s ORDER BY id ASC", (round_num,))
                    existing_ids = [row[0] for row in c.fetchall()]

                    for i in range(1, 11):
                        home = request.form.get(f'home_{i}')
                        away = request.form.get(f'away_{i}')
                        if home and away:
                            if i <= len(existing_ids):
                                c.execute("""UPDATE events SET home = %s, away = %s, deadline = %s WHERE id = %s""",
                                          (home, away, deadline, existing_ids[i - 1]))
                            else:
                                c.execute("""INSERT INTO events (home, away, deadline, round) VALUES (%s, %s, %s, %s)""",
                                          (home, away, deadline, round_num))
                conn.commit()
            return redirect(f'/admin?round={round_num}')

        elif form_type == 'results':
            round_num = int(request.form.get('round'))
            with get_conn() as conn:
                with conn.cursor() as c:
                    c.execute("SELECT id FROM events WHERE round = %s ORDER BY id ASC", (round_num,))
                    event_ids = c.fetchall()
                    for idx, (event_id,) in enumerate(event_ids):
                        result = request.form.get(f'result_{idx + 1}')
                        if result:
                            c.execute("UPDATE events SET result = %s WHERE id = %s", (result, event_id))
                conn.commit()
            return redirect(f'/admin?round={round_num}')

    # GET
    round_param = request.args.get('round')
    if round_param:
        try:
            round_num = int(round_param)
            with get_conn() as conn:
                with conn.cursor() as c:
                    c.execute("SELECT home, away, deadline, result FROM events WHERE round = %s ORDER BY id ASC", (round_num,))
                    rows = c.fetchall()
                    if rows:
                        parovi = []
                        for row in rows:
                            parovi.append({'home': row[0], 'away': row[1]})
                            deadline = row[2]
                            rezultati[len(parovi) - 1] = row[3] if row[3] else ''
        except ValueError:
            pass

    return render_template('admin.html', parovi=parovi, round_num=round_num, deadline=deadline, rezultati=rezultati)

@app.route('/pregled')
def pregled():
    with get_conn() as conn:
        with conn.cursor() as c:
            c.execute('''
                SELECT p.username, e.home, e.away, p.prediction, e.round
                FROM predictions p
                JOIN events e ON p.event_id = e.id
                ORDER BY e.round, p.username, e.id
            ''')
            podaci = c.fetchall()

    return render_template('pregled.html', podaci=podaci)

@app.route('/leaderboard')
def leaderboard():
    def normalize(s):
        return s.strip().upper() if s else ''

    with get_conn() as conn:
        with conn.cursor() as c:
            c.execute("SELECT DISTINCT round FROM events ORDER BY round")
            rounds = [row[0] for row in c.fetchall()]

            c.execute("SELECT id, round, result FROM events WHERE result IS NOT NULL")
            events = c.fetchall()
            event_id_to_result = {row[0]: row[2] for row in events}
            event_id_to_round = {row[0]: row[1] for row in events}

            c.execute("SELECT username, event_id, prediction FROM predictions")
            predictions = c.fetchall()

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

    table = []
    for username in sorted(scores.keys()):
        red = [username]
        ukupno = 0
        for r in rounds:
            bodova = scores[username].get(r, 0)
            red.append(bodova)
            ukupno += bodova
        red.append(ukupno)
        table.append(red)

    return render_template('leaderboard.html', rounds=rounds, table=table)

@app.route('/rezultati_po_kolima')
def rezultati_po_kolima():
    with get_conn() as conn:
        with conn.cursor() as c:
            c.execute("SELECT round, home, away, result FROM events ORDER BY round DESC, id ASC")
            podaci = c.fetchall()

    rezultati = {}
    for round_num, home, away, result in podaci:
        if round_num not in rezultati:
            rezultati[round_num] = []
        prikaz = f"{home} - {away} {result if result else ''}"
        rezultati[round_num].append(prikaz)

    return render_template("rezultati_po_kolima.html", rezultati=rezultati)

if __name__ == '__main__':
    app.run(debug=True)
