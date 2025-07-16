from flask import Blueprint, render_template, request, jsonify, redirect, url_for
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash, generate_password_hash
from .models import User
from . import login_manager
from dotenv import load_dotenv
import os
import pymysql

load_dotenv()

auth_bp = Blueprint('auth', __name__)

def get_user_from_db(username):
    conn = pymysql.connect(
        host=os.getenv('DB_HOST'),
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASSWORD'),
        database=os.getenv('DB_NAME'),
        charset='utf8mb4'
    )
    cursor = conn.cursor()
    cursor.execute("SELECT username, password_hash FROM users WHERE username = %s", (username,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return {'username': row[0], 'password_hash': row[1]}
    return None

def create_user_in_db(username, password, email):
    password_hash = generate_password_hash(password)
    conn = pymysql.connect(
        host=os.getenv('DB_HOST'),
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASSWORD'),
        database=os.getenv('DB_NAME'),
        charset='utf8mb4'
    )
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO users (username, password_hash, email) VALUES (%s, %s, %s)", (username, password_hash, email))
        conn.commit()
        return True
    except pymysql.err.IntegrityError:
        return False
    finally:
        conn.close()

@login_manager.user_loader
def load_user(user_id):
    user_data = get_user_from_db(user_id)
    if user_data:
        return User(user_data['username'])
    return None

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user_data = get_user_from_db(username)
        if user_data and check_password_hash(user_data['password_hash'], password):
            user = User(username)
            login_user(user)
            return jsonify({"message": "Login successful"})
        else:
            return jsonify({"message": "Invalid credentials"}), 401
    return render_template('login.html')

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    next_page = request.referrer or url_for('main.home')
    return redirect(next_page)

@auth_bp.route('/protected')
@login_required
def protected():
    return jsonify({"message": f"Hello, {current_user.id}! This is a protected route."})

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        email = request.form.get('email')
        if not username or not password:
            return jsonify({"message": "Username and password required"}), 400
        if get_user_from_db(username):
            return jsonify({"message": "Username already exists"}), 409
        if create_user_in_db(username, password, email):
            return redirect(url_for('main.home'))
        else:
            return jsonify({"message": "Registration failed"}), 500
    return render_template('register.html')