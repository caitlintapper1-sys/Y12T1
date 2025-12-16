from flask import Flask, render_template, request, redirect, url_for, session, flash, make_response, send_from_directory
import sqlite3
import os
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'hehesecret'

UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_db():
    db = sqlite3.connect('database/assignment.db', timeout = 15)
    db.row_factory = sqlite3.Row
    return db

#main homepage
@app.route('/')
def home():
    db = get_db()

    recent = db.execute(f'''
        SELECT * FROM ratings_and_movies
        ORDER BY created_at DESC LIMIT 1 
    ''').fetchone()

    rate = db.execute(f'''
        SELECT * FROM ratings_and_movies
        ORDER BY rating DESC LIMIT 1 
    ''').fetchone()
    
    return render_template('home.html', recent=recent, rate=rate)


#login page
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
            session['user_id'] = user['id']
            session['username'] = user['username']
            #allows to check if user is admin
            session['admin'] = user['admin']
            return redirect(url_for('home'))
        flash('Invalid username or password', 'error')
    return render_template('login.html')

#register page
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

#logout route
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))

#page to show the create movie form, should only be accessable to users who are logged in and an admin
@app.route('/add_movie')
def add_movie():
    if 'user_id' not in session:
        flash('Please log in', 'error')
        return redirect(url_for('login'))

    #statement to make it admin exclusive, + flash message that tells user it's admin only
    if session['admin'] == 0:
        flash('User not an admin', 'error')
        return redirect(url_for('home'))
    
    return render_template('create_movie.html')

#route that connects the create movie form and movies database
@app.route('/create_movie', methods=['POST'])
def create_movie():
    if 'user_id' not in session:
        return redirect(url_for('home'))
    
    if 'image' not in request.files:
        flash('No image uploaded','error')

    file = request.files['image']
    if file.filename == '':
        flash('No image selected', 'error')
        return redirect(url_for('home'))
    
    if file and allowed_file(file.filename):
        filename = secure_filename(f"{datetime.now().timestamp()}_{file.filename}")
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)

        db = get_db()
        #remove rating later
        db.execute('''
            INSERT INTO movies (title, description, image_path, release_year, director)
            VALUES(?, ?, ?, ?, ?)
        ''',(
            request.form['title'],
            request.form['description'],
            f"uploads/{filename}",
            request.form['year'],
            request.form['director'],
        ))
        db.commit()

        flash('Movie added successfully!', 'success')
    else:
        flash('Invalid file type', 'error')
    
    return redirect(url_for('home'))

@app.route('/create_review', methods=['POST'])
def create_review():
    if 'user_id' not in session:
        flash('Please log in to write a review', 'error')
    db = get_db()
    db.execute('''
        INSERT INTO reviews (user_id, movie_id, rating, description)
        VALUES(?, ?, ?, ?)
    ''',(
        session['user_id'],
        request.form['movie_id'],
        request.form['rating'],
        request.form['description']
    ))
    db.commit()

    flash('Review added successfully!', 'success')
    return redirect(url_for('movie_display', movie_id = request.form['movie_id']))

@app.route('/movie/<movie_id>')
def movie_display(movie_id):
    db = get_db()

    movie = db.execute(f'''
        SELECT * FROM ratings_and_movies
        WHERE id == ?''',
        (movie_id)).fetchone()
    
    reviews = db.execute('''
        SELECT * FROM reviews
        WHERE movie_id == ?
        ORDER BY created_at DESC
    ''',(movie_id)).fetchall()
    
    return render_template('movie_display.html', movie=movie, reviews=reviews)

@app.route('/search', methods=['POST'])
def search():
    db = get_db()
    search = request.form['search']
    movies = db.execute(f'''
        SELECT * FROM ratings_and_movies
        WHERE title LIKE "%{search}%"
        ORDER BY release_year DESC
        ''',).fetchall()
    return render_template('search.html', movies = movies)

@app.route('/offline')
def offline():
    response = make_response(render_template('offline.html'))
    return response

@app.route('/service-worker.js')
def sw():
    response = make_response(
        send_from_directory(os.path.join(app.root_path, 'static/js'),
        'service-worker.js')
    )
    return response

@app.route('/manifest.json')
def manifest():
    response = make_response(
        send_from_directory(os.path.join(app.root_path, 'static'), 'manifest.json')
    )
    return response

@app.route('/edit_movie/<movie_id>', methods=['POST'])
def edit_movie(movie_id):
    if 'user_id' not in session:
        return redirect(url_for('movie_display', movie_id=movie_id))
    if session['admin'] == 0:
        return redirect(url_for('movie_display', movie_id=movie_id))
    db = get_db()
    movie = db.execute(
        'SELECT * FROM movies WHERE id = ?',
        (movie_id)
    ).fetchone()

    if not movie:
        flash('Movie not found', 'error')
        return redirect(url_for('movie_display', movie_id=movie_id))
    

    title = request.form['title']
    description = request.form['description']
    release_year = request.form['year']
    director = request.form['director']

    if 'image' in request.files and request.files['image'].filename != '':
        file = request.files['image']
        if allowed_file(file.filename):
            try:
                old_image_path = os.path.join(app.root_path, 'static', movie['image_path'])
                if os.path.exists(old_image_path):
                    os.remove(old_image_path)
            except Exception as e:
                print(f"Error deleting old image: {e}")
        
            filename = secure_filename(f"{datetime.now().timestamp()}_{file.filename}")
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)

            db.execute('''
                UPDATE movies
                SET title = ?, description = ?, image_path = ?, release_year = ?, director = ?
                WHERE id = ?
            ''', (title, description, f"uploads/{filename}", release_year, director, movie_id))
            db.commit()
            return redirect(url_for('movie_display', movie_id=movie_id))
        else:
            flash('Invalid file type', 'error')
        
    else: 
        db.execute('''
            UPDATE movies
            SET title = ?, description = ?, release_year = ?, director = ?
            WHERE id = ?
        ''',(title, description, release_year, director, movie_id))

        db.commit()
        flash('Movie updated successfully!','success')
        return redirect(url_for('movie_display', movie_id=movie_id))

    

@app.route('/delete_movie/<movie_id>', methods=['POST'])
def delete_movie(movie_id):
    if 'user_id' not in session:
        return redirect(url_for('movie_display', movie_id=movie_id))
    db = get_db()

    movie = db.execute(
        'SELECT * FROM movies WHERE id = ?',
        (movie_id)
    ).fetchone()

    if not movie:
        flash('Movie not found','error')
        return redirect(url_for('movie_display', movie_id=movie_id))
    try:
        image_path = os.path.join(app.root_path, 'static',
        movie['image_path'])
        if os.path.exists(image_path):
            os.remove(image_path)
    except Exception as e:
        print(f"Error deleting image file: {e}")

    db.execute('DELETE FROM movies WHERE id = ?',
               (movie_id))
    db.commit()

    flash('Movie deleted successfully', 'success')
    return redirect(url_for('home'))

if __name__ == '__main__':
    app.run(debug=True)