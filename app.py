from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = 'hehesecret'

def get_db():
    db = sqlite3.connect('database/assignment.db', timeout = 10)
    db.row_factory = sqlite3.Row
    return db

@app.route('/')
def home():
    #db = get_db()

    return render_template('home.html')
    
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        db = get_db()
        user = db.execute(
            'SELECT * FROM users WHERE username = ?', (username,)
        ).fetchone()

        if user and check_password_hash(user['password'], password):
            session.clear()
            session['user.id'] = user['id']
            session['username'] = user['username']
            return redirect(url_for('home'))
    flash('Invalid username or password', 'error')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        db = get_db()
        try:
            db.execute(
                'INSERT INTO users (username, password, admin) VALUES (?, ?, ?)',
                (username, generate_password_hash(password), 0)
            )
            db.commit()
            flash('Registration successful! Please log in', 'success')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('Username already exists', 'error')

    return render_template('register.html')

#@app.route('/create-movie')

app.run(debug=True, port=5000)