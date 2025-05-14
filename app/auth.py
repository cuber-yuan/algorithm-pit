from flask import Blueprint, render_template, request, jsonify, redirect, url_for
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash
from .models import User, users
from . import login_manager

auth_bp = Blueprint('auth', __name__)

@login_manager.user_loader
def load_user(user_id):
    if user_id in users:
        return User(user_id)
    return None

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if username in users and check_password_hash(users[username], password):
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