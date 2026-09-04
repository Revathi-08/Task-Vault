from flask import Flask, render_template, request, redirect, session, send_from_directory
import sqlite3
import os
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import date

app = Flask(__name__)
app.secret_key = 'taskvault_secret_123'
app.config['UPLOAD_FOLDER'] = 'uploads'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

def get_db():
    conn = sqlite3.connect('notes.db')
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.execute('''CREATE TABLE IF NOT EXISTS users
                    (id INTEGER PRIMARY KEY, username TEXT UNIQUE, password TEXT)''')
    conn.execute('''CREATE TABLE IF NOT EXISTS notes
                    (id INTEGER PRIMARY KEY, title TEXT, description TEXT,
                     due_date TEXT, priority TEXT, status TEXT DEFAULT 'Pending',
                     file_name TEXT, user_id INTEGER)''')
    # old db lo file_name lekapothe add chey
    try:
        conn.execute("ALTER TABLE notes ADD COLUMN file_name TEXT")
    except: pass
    conn.commit()
    conn.close()

init_db()

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/')
def index():
    if 'user_id' not in session: return redirect('/login')
    user_id = session['user_id']
    username = session.get('username', 'Captain')
    q = request.args.get('q', '')
    f = request.args.get('filter', 'all') # super filter

    conn = get_db()
    query = "SELECT * FROM notes WHERE user_id=?"
    params = [user_id]

    if q:
        query += " AND (title LIKE? OR description LIKE?)"
        params.extend([f'%{q}%', f'%{q}%'])

    if f == 'high':
        query += " AND priority='High'"
    elif f == 'today':
        today = date.today().isoformat()
        query += " AND due_date=?"
        params.append(today)
    elif f == 'done':
        query += " AND status='Done'"
    elif f == 'pending':
        query += " AND status='Pending'"

    query += " ORDER BY id DESC"
    tasks = conn.execute(query, tuple(params)).fetchall()

    total = conn.execute("SELECT COUNT(*) FROM notes WHERE user_id=?", (user_id,)).fetchone()[0]
    pending = conn.execute("SELECT COUNT(*) FROM notes WHERE user_id=? AND status='Pending'", (user_id,)).fetchone()[0]
    done = conn.execute("SELECT COUNT(*) FROM notes WHERE user_id=? AND status='Done'", (user_id,)).fetchone()[0]
    conn.close()
    return render_template('index.html', tasks=tasks, username=username, total=total, pending=pending, done=done, current_filter=f)

@app.route('/add', methods=['POST'])
def add():
    if 'user_id' not in session: return redirect('/login')
    file_name = None
    if 'attachment' in request.files:
        file = request.files['attachment']
        if file and file.filename!= '':
            file_name = secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], file_name))

    conn = get_db()
    conn.execute("INSERT INTO notes (title, description, due_date, priority, file_name, user_id) VALUES (?,?,?,?,?,?)",
                 (request.form['title'], request.form['description'], request.form['due_date'], request.form['priority'], file_name, session['user_id']))
    conn.commit()
    conn.close()
    return redirect('/')

@app.route('/toggle/<int:id>')
def toggle(id):
    conn = get_db()
    task = conn.execute("SELECT * FROM notes WHERE id=? AND user_id=?", (id, session['user_id'])).fetchone()
    if task:
        new_status = 'Done' if task['status'] == 'Pending' else 'Pending'
        conn.execute("UPDATE notes SET status=? WHERE id=?", (new_status, id))
        conn.commit()
    conn.close()
    return redirect('/')

@app.route('/edit/<int:id>', methods=['GET','POST'])
def edit(id):
    conn = get_db()
    task = conn.execute("SELECT * FROM notes WHERE id=? AND user_id=?", (id, session['user_id'])).fetchone()
    if not task: return redirect('/')
    if request.method == 'POST':
        file_name = task['file_name']
        if 'attachment' in request.files:
            file = request.files['attachment']
            if file and file.filename!= '':
                file_name = secure_filename(file.filename)
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], file_name))
        conn.execute("UPDATE notes SET title=?, description=?, due_date=?, priority=?, file_name=? WHERE id=?",
                     (request.form['title'], request.form['description'], request.form['due_date'], request.form['priority'], file_name, id))
        conn.commit()
        conn.close()
        return redirect('/')
    conn.close()
    return render_template('edit.html', task=task)

@app.route('/delete/<int:id>')
def delete(id):
    conn = get_db()
    conn.execute("DELETE FROM notes WHERE id=? AND user_id=?", (id, session['user_id']))
    conn.commit()
    conn.close()
    return redirect('/')

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        u = request.form['username']; p = request.form['password']
        conn = get_db()
        user = conn.execute("SELECT * FROM users WHERE username=?", (u,)).fetchone()
        conn.close()
        if user and check_password_hash(user['password'], p):
            session['user_id'] = user['id']
            session['username'] = user['username']
            return redirect('/')
        return "Invalid login"
    return render_template('login.html')

@app.route('/register', methods=['GET','POST'])
def register():
    if request.method == 'POST':
        u = request.form['username']; p = generate_password_hash(request.form['password'])
        conn = get_db()
        try:
            conn.execute("INSERT INTO users (username, password) VALUES (?,?)", (u,p))
            conn.commit()
        except: return "Username exists"
        finally: conn.close()
        return redirect('/login')
    return render_template('register.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')

if __name__ == '__main__':
    app.run(debug=True)